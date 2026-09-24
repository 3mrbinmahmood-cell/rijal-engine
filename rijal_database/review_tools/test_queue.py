import sqlite3
import tempfile
import unittest
from pathlib import Path
from rijal_database.review_tools.queue import connect, decide
from rijal_database.review_tools.name_inventory import SCHEMA as NAME_SCHEMA, decide as decide_name

class ReviewTests(unittest.TestCase):
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

if __name__=='__main__':
    unittest.main()
