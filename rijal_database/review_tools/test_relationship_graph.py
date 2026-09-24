import json
import sqlite3
import tempfile
from pathlib import Path
import unittest

from rijal_database.review_tools.relationship_graph import build


class RelationshipGraphTest(unittest.TestCase):
    def test_name_mention_stays_unresolved_and_sources_survive(self):
        with tempfile.TemporaryDirectory() as directory:
            queue,identity,output=[Path(directory)/f'{n}.sqlite'
                                   for n in ('queue','identity','graph')]
            with sqlite3.connect(queue) as db:
                db.executescript('''CREATE TABLE metadata(key TEXT,value TEXT);
                  CREATE TABLE pairs(left_entry_id TEXT,right_entry_id TEXT,
                    common_teachers_json TEXT,common_students_json TEXT,
                    priority TEXT);''')
                db.execute('INSERT INTO metadata VALUES (?,?)',('v1_1_sha256','sha'))
                db.execute('INSERT INTO pairs VALUES (?,?,?,?,?)',
                           ('a','b',json.dumps(['Shared Teacher']),
                            json.dumps(['Shared Student']),'both_lists_3plus'))
            with sqlite3.connect(identity) as db:
                db.executescript('''CREATE TABLE metadata(key TEXT,value TEXT);
                  CREATE TABLE entry_identity(entry_id TEXT,identity_id TEXT,
                    opening_page_id TEXT);''')
                db.execute('INSERT INTO metadata VALUES (?,?)',('v1_1_sha256','sha'))
                db.executemany('INSERT INTO entry_identity VALUES (?,?,?)',
                               [('a','person-a','page-a'),('b','person-b','page-b')])
            result=build(queue,identity,output)
            self.assertEqual(result['identity_merges'],0)
            with sqlite3.connect(output) as db:
                self.assertEqual(db.execute('SELECT count(*) FROM name_mentions').fetchone()[0],2)
                self.assertEqual(db.execute('SELECT count(*) FROM observations').fetchone()[0],4)
                self.assertEqual(set(db.execute('SELECT identity_id FROM neighbors')),
                                 {('person-a',),('person-b',)})
                self.assertEqual(set(db.execute('SELECT entry_id,page_id FROM observations')),
                                 {('a','page-a'),('b','page-b')})
                self.assertEqual(db.execute('SELECT DISTINCT resolution_status '
                    'FROM name_mentions').fetchone()[0],'unresolved_name')


if __name__=='__main__':unittest.main()
