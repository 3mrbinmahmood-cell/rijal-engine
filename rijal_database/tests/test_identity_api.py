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


if __name__=='__main__':unittest.main()
