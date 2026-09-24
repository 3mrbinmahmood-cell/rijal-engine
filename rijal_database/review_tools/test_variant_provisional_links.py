import sqlite3
import tempfile
import unittest
from pathlib import Path

from rijal_database.review_tools.variant_provisional_links import build


class VariantLinkTests(unittest.TestCase):
    def test_preserves_both_original_name_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);variants=root/'v.sqlite';full=root/'f.sqlite';out=root/'o.sqlite'
            with sqlite3.connect(full) as db:
                db.execute('CREATE TABLE release_meta(key TEXT,value TEXT)')
                db.execute("INSERT INTO release_meta VALUES ('v1_1_sha256','sha')")
                db.execute('CREATE TABLE name_entries(entry_id TEXT,classification TEXT)')
                db.executemany('INSERT INTO name_entries VALUES (?,?)',
                               [('a','biography_candidate'),('b','biography_candidate')])
            with sqlite3.connect(variants) as db:
                db.executescript('''CREATE TABLE metadata(key TEXT,value TEXT);
                    CREATE TABLE variant_entries(entry_id TEXT,bucket_id TEXT,name_key TEXT);
                    CREATE TABLE candidate_pairs(left_entry_id TEXT,right_entry_id TEXT,
                    variant_bucket_id TEXT,shared_long_statements INTEGER);
                    CREATE TABLE relationship_pairs(left_entry_id TEXT,right_entry_id TEXT,
                    variant_bucket_id TEXT,priority TEXT);''')
                db.execute("INSERT INTO metadata VALUES ('v1_1_sha256','sha')")
                db.executemany('INSERT INTO variant_entries VALUES (?,?,?)',
                               [('a','bucket','ابو زيد'),('b','bucket','ابي زيد')])
                db.execute("INSERT INTO candidate_pairs VALUES ('a','b','bucket',2)")
            self.assertEqual(build(variants,full,out)['provisional_links'],1)
            with sqlite3.connect(out) as db:
                self.assertEqual({r[0] for r in db.execute('SELECT original_name_key FROM members')},
                                 {'ابو زيد','ابي زيد'})


if __name__=='__main__':unittest.main()
