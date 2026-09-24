import sqlite3
import tempfile
import unittest
from pathlib import Path
from rijal_database.review_tools.queue import connect, decide
from rijal_database.review_tools.name_inventory import (
    SCHEMA as NAME_SCHEMA, decide as decide_name, triage, common_bucket,
    add_date_claim)
import json

class ReviewTests(unittest.TestCase):
    def test_nearest_common_numeric_date_bucket(self):
        self.assertEqual(common_bucket([70,70]),(1,70,70))
        self.assertEqual(common_bucket([186,187]),(10,180,189))
        self.assertEqual(common_bucket([165,195]),(100,100,199))
        self.assertEqual(common_bucket([188,207]),(1000,0,999))
        self.assertEqual(common_bucket([999,1000]),(None,None,None))
        self.assertEqual(common_bucket([]),(None,None,None))
    def test_pairwise_decision_history_and_group_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            with connect(Path(tmp)/'review.sqlite') as db:
                db.execute("INSERT INTO groups(id,name_label,name_key,death_year,source_entries) VALUES ('g','سعيد','سعيد',100,2)")
                db.execute("INSERT INTO groups(id,name_label,name_key,death_year,source_entries) VALUES ('h','سعيد','سعيد',101,2)")
                for entry,group in [('a','g'),('b','g'),('c','h')]:
                    db.execute("""INSERT INTO members(
                        entry_id,group_id,name_label,death_year,evidence_page_id,evidence_quote,
                        entry_page_id,entry_start,book_title,zip_path,printed_label) VALUES
                        (?,?, 'سعيد',100,'page','توفي سنة مائة','page',0,'كتاب','file.htm','(ص: 1)')""",
                        (entry,group))
                with self.assertRaises(ValueError):
                    decide(db,'a','c','same','matching name','reviewer')
                with self.assertRaises(ValueError):
                    decide(db,'a','b','same','','reviewer')
                decide(db,'b','a','uncertain','Need source context','reviewer')
                decide(db,'a','b','different','Conflicting patronymic','reviewer')
                self.assertEqual(db.execute('SELECT decision FROM pair_decisions').fetchone()[0],'different')
                self.assertEqual(db.execute('SELECT count(*) FROM decision_history').fetchone()[0],2)
                self.assertEqual(db.execute('SELECT count(*) FROM groups').fetchone()[0],2)

    def test_name_inventory_requires_same_group_and_keeps_history(self):
        with sqlite3.connect(':memory:') as db:
            db.executescript(NAME_SCHEMA)
            db.executemany('INSERT INTO name_groups VALUES (?,?,?)',[('name',2,2),('other',2,2)])
            for entry,key in [('a','name'),('b','name'),('c','other')]:
                db.execute('INSERT INTO name_members VALUES (?,?,?,?,?,?,?,?)',
                           (entry,key,key,'page','book','source','biography_candidate',0))
            with self.assertRaises(ValueError):
                decide_name(db,'a','c','same','looks similar','reviewer')
            decide_name(db,'b','a','uncertain','Compare patronymics','reviewer')
            decide_name(db,'a','b','different','Different teachers','reviewer')
            self.assertEqual(db.execute('SELECT decision FROM pair_decisions').fetchone()[0],'different')
            self.assertEqual(db.execute('SELECT count(*) FROM decision_history').fetchone()[0],2)

    def test_date_triage_does_not_make_identity_decisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'data').mkdir()
            (root/'extraction_data').mkdir()
            (root/'data'/'PAYLOAD.json').write_text(json.dumps({'database_sha256':'base'}))
            (root/'extraction_data'/'PAYLOAD.json').write_text(
                json.dumps({'base_sha256':'base','database_sha256':'extract'}))
            base=root/'v1.sqlite'
            with sqlite3.connect(base) as source:
                source.execute('CREATE TABLE chronology_records(entry_id TEXT PRIMARY KEY,death_year INTEGER,evidence_quote TEXT,evidence_page_id TEXT)')
                source.executemany('INSERT INTO chronology_records VALUES (?,?,?,?)',
                                   [(entry,year,str(year),'page') for entry,year in
                                    [('a',100),('b',101),('c',100),('d',100)]])
            with sqlite3.connect(root/'review.sqlite',uri=True) as db:
                db.executescript(NAME_SCHEMA)
                db.execute("INSERT INTO methods VALUES ('extraction_sha256','extract')")
                db.executemany('INSERT INTO name_groups VALUES (?,?,?)',
                               [('conflict',2,2),('agree',2,2),('unknown',2,2)])
                for entry,key in [('a','conflict'),('b','conflict'),('c','agree'),
                                  ('d','agree'),('e','unknown'),('f','unknown')]:
                    db.execute('INSERT INTO name_members VALUES (?,?,?,?,?,?,?,?)',
                               (entry,key,key,'page','book','source','biography_candidate',0))
                result=triage(db,base,root/'extraction.sqlite')
                self.assertEqual(result,{'conflicting_dates':1,'matching_dates':1,'no_dates':1})
                self.assertEqual(db.execute(
                    "SELECT years_json,bucket_unit,bucket_start,bucket_end "
                    "FROM date_grouping WHERE name_key='conflict'").fetchone(),
                    ('[100, 101]',10,100,109))
                self.assertEqual(db.execute(
                    "SELECT count(*) FROM date_evidence WHERE name_key='conflict'").fetchone()[0],2)
                self.assertEqual(db.execute('SELECT count(*) FROM pair_decisions').fetchone()[0],0)

    def test_additional_claim_requires_exact_biography_span_and_updates_bucket(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'data').mkdir();(root/'extraction_data').mkdir()
            (root/'data'/'PAYLOAD.json').write_text(json.dumps({'database_sha256':'base'}))
            (root/'extraction_data'/'PAYLOAD.json').write_text(json.dumps(
                {'base_sha256':'base','database_sha256':'extract'}))
            base=root/'v1.sqlite'; extraction=root/'v1_1.sqlite'
            page='ذكر 206 ثم مات سنة سبع ومائتين وذكر 208 في الخبر التالي'
            with sqlite3.connect(base) as db:
                db.executescript('CREATE TABLE pages(id TEXT,text_id INTEGER);'
                                 'CREATE TABLE page_texts(id INTEGER,text TEXT);')
                db.execute('INSERT INTO pages VALUES (?,?)',('page',1))
                db.execute('INSERT INTO page_texts VALUES (?,?)',(1,page))
            with sqlite3.connect(extraction) as db:
                db.execute('CREATE TABLE biography_segments('
                           'biography_id TEXT,page_id TEXT,start_offset INTEGER,end_offset INTEGER)')
                db.execute('INSERT INTO biography_segments VALUES (?,?,?,?)',
                           ('a','page',0,len(page)))
            with sqlite3.connect(root/'review.sqlite') as db:
                db.executescript(NAME_SCHEMA)
                db.executemany('INSERT INTO methods VALUES (?,?)',
                               [('base_sha256','base'),('extraction_sha256','extract')])
                db.execute("INSERT INTO name_groups VALUES ('person',2,2)")
                db.execute("INSERT INTO name_members VALUES ('a','person','person','page','book','source','biography_candidate',0)")
                db.execute("INSERT INTO date_evidence VALUES ('a','person',207,'سنة سبع ومائتين','page')")
                with self.assertRaises(ValueError):
                    add_date_claim(db,base,extraction,'a','page',206,'ليس في النص','reviewer','context')
                add_date_claim(db,base,extraction,'a','page',206,'ذكر 206','reviewer','context')
                add_date_claim(db,base,extraction,'a','page',208,'ذكر 208','reviewer','context')
                self.assertEqual(db.execute('SELECT years_json,bucket_unit,bucket_start,bucket_end '
                                            'FROM date_grouping').fetchone(),
                                 ('[206, 207, 208]',10,200,209))
                self.assertEqual(db.execute('SELECT count(*) FROM additional_date_claims').fetchone()[0],2)

if __name__=='__main__':
    unittest.main()
