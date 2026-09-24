import sqlite3
import tempfile
import unittest
from pathlib import Path

from rijal_database.review_tools.full_provisional_links import build


class FullProvisionalTests(unittest.TestCase):
    def test_different_review_vetoes_strong_literal_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);full=root/'full.sqlite';candidate=root/'candidates.sqlite'
            review=root/'review.sqlite';out=root/'out.sqlite'
            with sqlite3.connect(full) as db:
                db.execute('CREATE TABLE release_meta(key TEXT,value TEXT)')
                db.execute("INSERT INTO release_meta VALUES ('v1_1_sha256','release')")
            with sqlite3.connect(candidate) as db:
                db.execute('CREATE TABLE metadata(key TEXT,value TEXT)')
                db.execute("INSERT INTO metadata VALUES ('v1_1_sha256','release')")
                db.execute('CREATE TABLE pairs(left_entry_id TEXT,right_entry_id TEXT,name_key TEXT,shared_statements INTEGER,years_json TEXT)')
                db.execute("INSERT INTO pairs VALUES ('a','b','same name',2,'[100, 101]')")
            with sqlite3.connect(review) as db:
                db.execute('CREATE TABLE methods(key TEXT,value TEXT)')
                db.execute("INSERT INTO methods VALUES ('extraction_sha256','release')")
                db.execute('CREATE TABLE pair_decisions(left_entry_id TEXT,right_entry_id TEXT,decision TEXT)')
                db.execute("INSERT INTO pair_decisions VALUES ('a','b','different')")
            self.assertEqual(build(full,candidate,review,out)['links'],0)
            with sqlite3.connect(out) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM members').fetchone()[0],0)


if __name__=='__main__':unittest.main()
