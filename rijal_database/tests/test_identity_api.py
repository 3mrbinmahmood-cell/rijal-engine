import sqlite3
import tempfile
from pathlib import Path
import unittest

from rijal_database.extraction_server import Extraction


class IdentityApiTest(unittest.TestCase):
    def test_reviewed_and_provisional_remain_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'identity.sqlite'
            with sqlite3.connect(path) as db:
                db.executescript('''CREATE TABLE identities(id TEXT,kind TEXT,
                  display_name TEXT,entry_count INTEGER);
                  CREATE TABLE entry_identity(entry_id TEXT,identity_id TEXT,
                  identity_kind TEXT,name_bucket_id TEXT,name_key TEXT,
                  name_label TEXT,classification TEXT,book_id TEXT,
                  source_id TEXT,opening_page_id TEXT);''')
                db.executemany('INSERT INTO identities VALUES (?,?,?,?)',
                    [('person','reviewed_person','Name',1),
                     ('cluster','provisional_cluster','Name',2)])
                db.executemany('INSERT INTO entry_identity VALUES (?,?,?,?,?,?,?,?,?,?)',
                    [(entry,identity,kind,'bucket','name','Name',
                      'biography_candidate','book','source','page') for entry,identity,kind in
                     [('a','person','reviewed_person'),('b','cluster','provisional_cluster'),
                      ('c','cluster','provisional_cluster')]])
            api=Extraction.__new__(Extraction)
            api.identity_path=path
            api.dates_path=None
            self.assertEqual(api.identity_entry('a')['identity_kind'],'reviewed_person')
            self.assertEqual(api.identity_entry('b')['identity_kind'],'provisional_cluster')
            members=api.identity_members('cluster',limit=1)
            self.assertEqual(len(members['results']),1)
            self.assertTrue(members['has_more'])
            self.assertEqual(api.identity_members('cluster',limit=1,offset=1)['results'][0]['entry_id'],'c')
            with self.assertRaises(KeyError):api.identity_entry('missing')
            dates=Path(directory)/'dates.sqlite'
            with sqlite3.connect(dates) as db:
                db.executescript('''CREATE TABLE identity_date_summary(identity_id TEXT,
                  years_json TEXT,bucket_unit INTEGER,bucket_start INTEGER,
                  bucket_end INTEGER);
                  CREATE TABLE date_claims(id INTEGER PRIMARY KEY,identity_id TEXT,
                  entry_id TEXT,kind TEXT,year INTEGER,evidence_type TEXT,
                  exact_quote TEXT,page_id TEXT,start_offset INTEGER,
                  end_offset INTEGER,reviewer TEXT,note TEXT);''')
                db.execute('INSERT INTO identity_date_summary VALUES (?,?,?,?,?)',
                           ('person','[186, 187]',10,180,189))
                db.executemany('''INSERT INTO date_claims(identity_id,entry_id,
                  kind,year,evidence_type,exact_quote,page_id) VALUES (?,?,?,?,?,?,?)''',
                  [('person','a','death',186,'automatic','quote one','page'),
                   ('person','a','death',187,'reviewed_claim','quote two','page')])
            api.dates_path=dates
            result=api.identity_dates('a')
            self.assertEqual([r['year'] for r in result['claims']],[186,187])
            self.assertIsNone(api.identity_dates('b')['summary'])
            graph=Path(directory)/'graph.sqlite'
            with sqlite3.connect(graph) as db:
                db.executescript('''CREATE TABLE name_mentions(id TEXT,name TEXT,
                  resolution_status TEXT);
                  CREATE TABLE neighbors(identity_id TEXT,relation TEXT,
                  mention_id TEXT,source_entries INTEGER,supporting_pairs INTEGER);
                  CREATE TABLE observations(identity_id TEXT,entry_id TEXT,
                  paired_entry_id TEXT,relation TEXT,mention_id TEXT,
                  page_id TEXT,review_priority TEXT);''')
                db.execute('INSERT INTO name_mentions VALUES (?,?,?)',
                           ('mention','Teacher Name','unresolved_name'))
                db.execute('INSERT INTO neighbors VALUES (?,?,?,?,?)',
                           ('person','teacher','mention',2,3))
                db.execute('INSERT INTO neighbors VALUES (?,?,?,?,?)',
                           ('cluster','teacher','mention',1,1))
                db.execute('INSERT INTO observations VALUES (?,?,?,?,?,?,?)',
                           ('person','a','b','teacher','mention','page','both_lists_3plus'))
            api.graph_path=graph
            self.assertEqual(api.identity_graph('a','teacher')['results'][0]['name'],
                             'Teacher Name')
            self.assertEqual(api.identity_graph('b','teacher')['results'][0]['name'],
                             'Teacher Name')
            self.assertEqual(api.graph_evidence('a','teacher','mention')['results'][0]
                             ['page_id'],'page')
            self.assertEqual(api.graph_evidence('b','teacher','mention')['results'],[])
            related=api.graph_mention('mention','teacher')['results']
            self.assertEqual([r['identity_id'] for r in related],['person','cluster'])
            self.assertEqual(related[1]['identity_kind'],'provisional_cluster')
            self.assertEqual(api.graph_mention('mention')['status'],
                             'shared_name_does_not_prove_same_person')
            with self.assertRaises(ValueError):api.identity_graph('a','unknown')
            with self.assertRaises(KeyError):api.graph_mention('missing')


if __name__=='__main__':unittest.main()
