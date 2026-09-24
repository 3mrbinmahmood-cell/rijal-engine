import json
import sqlite3
import tempfile
from pathlib import Path
import unittest

from rijal_database.review_tools.relationship_provisional_links import build


class RelationshipLinksTest(unittest.TestCase):
    def test_requires_three_on_both_sides_and_unlinked_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            q,i,r,o=[Path(directory)/f'{name}.sqlite' for name in 'qiro']
            with sqlite3.connect(q) as db:
                db.executescript('''CREATE TABLE metadata(key TEXT,value TEXT);
                  CREATE TABLE pairs(left_entry_id TEXT,right_entry_id TEXT,
                    left_identity_id TEXT,right_identity_id TEXT,left_book_id TEXT,
                    right_book_id TEXT,common_teachers_json TEXT,
                    common_students_json TEXT,priority TEXT);''')
                db.execute('INSERT INTO metadata VALUES (?,?)',('v1_1_sha256','sha'))
                db.executemany('INSERT INTO pairs VALUES (?,?,?,?,?,?,?,?,?)',[
                    ('a','b','single-a','single-b','one','two',
                     json.dumps(['t1','t2','t3']),json.dumps(['s1','s2','s3']),
                     'both_lists_3plus'),
                    ('c','d','single-c','single-d','one','two',
                     json.dumps(['t1','t2']),json.dumps(['s1','s2','s3']),
                     'both_lists_3plus'),
                    ('e','f','person','single-f','one','two',
                     json.dumps(['t1','t2','t3']),json.dumps(['s1','s2','s3']),
                     'both_lists_3plus')])
            with sqlite3.connect(i) as db:
                db.execute('CREATE TABLE metadata(key TEXT,value TEXT)')
                db.execute('INSERT INTO metadata VALUES (?,?)',('v1_1_sha256','sha'))
            with sqlite3.connect(r) as db:
                db.executescript('''CREATE TABLE methods(key TEXT,value TEXT);
                    CREATE TABLE pair_decisions(left_entry_id TEXT,right_entry_id TEXT,
                    decision TEXT);''')
                db.execute('INSERT INTO methods VALUES (?,?)',('extraction_sha256','sha'))
            result=build(q,i,r,o)
            self.assertEqual(result['links'],1)
            self.assertEqual(result['excluded_existing_identity'],1)
            with sqlite3.connect(o) as db:
                self.assertEqual(db.execute('SELECT left_entry_id,right_entry_id '
                    'FROM links').fetchall(),[('a','b')])


if __name__=='__main__':unittest.main()
