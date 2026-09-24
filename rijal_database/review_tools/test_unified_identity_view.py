"""Check that provisional evidence cannot silently enlarge a reviewed person."""
import sqlite3
import tempfile
from pathlib import Path
import unittest

from rijal_database.review_tools.unified_identity_view import build


class UnifiedIdentityViewTest(unittest.TestCase):
    def test_full_coverage_and_review_bridge(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory) / f'{name}.sqlite' for name in
                     ('full', 'registry', 'literal', 'variant', 'review', 'output')]
            full, registry, literal, variant, review, output = paths
            with sqlite3.connect(full) as db:
                db.executescript('''CREATE TABLE release_meta(key TEXT,value TEXT);
                    CREATE TABLE name_groups(id TEXT,name_key TEXT);
                    CREATE TABLE name_entries(entry_id TEXT,name_group_id TEXT,
                      name_label TEXT,classification TEXT,book_id TEXT,
                      source_id TEXT,opening_page_id TEXT);''')
                db.execute('INSERT INTO release_meta VALUES (?,?)',('v1_1_sha256','sha'))
                db.execute('INSERT INTO name_groups VALUES (?,?)',('bucket','name'))
                db.executemany('INSERT INTO name_entries VALUES (?,?,?,?,?,?,?)',
                    [(entry,'bucket','Name','biography_candidate','book','source','page')
                     for entry in 'abcde'])
            with sqlite3.connect(registry) as db:
                db.executescript('''CREATE TABLE registry_meta(key TEXT,value TEXT);
                    CREATE TABLE persons(id TEXT,display_name TEXT,status TEXT);
                    CREATE TABLE person_entries(entry_id TEXT,person_id TEXT);''')
                db.execute('INSERT INTO registry_meta VALUES (?,?)',('v1_1_sha256','sha'))
                db.execute('INSERT INTO persons VALUES (?,?,?)',('person','Name','reviewed'))
                db.executemany('INSERT INTO person_entries VALUES (?,?)',
                               [('a','person'),('b','person')])
            with sqlite3.connect(literal) as db:
                db.executescript('''CREATE TABLE metadata(key TEXT,value TEXT);
                    CREATE TABLE links(left_entry_id TEXT,right_entry_id TEXT,
                      shared_statements INTEGER);''')
                db.execute('INSERT INTO metadata VALUES (?,?)',('v1_1_sha256','sha'))
                db.executemany('INSERT INTO links VALUES (?,?,?)',
                               [('b','c',2),('c','d',2)])
            with sqlite3.connect(variant) as db:
                db.executescript('''CREATE TABLE metadata(key TEXT,value TEXT);
                    CREATE TABLE links(left_entry_id TEXT,right_entry_id TEXT,
                      evidence_kind TEXT);''')
                db.execute('INSERT INTO metadata VALUES (?,?)',('v1_1_sha256','sha'))
            with sqlite3.connect(review) as db:
                db.executescript('''CREATE TABLE methods(key TEXT,value TEXT);
                    CREATE TABLE pair_decisions(left_entry_id TEXT,right_entry_id TEXT,
                      decision TEXT);''')
                db.execute('INSERT INTO methods VALUES (?,?)',('extraction_sha256','sha'))
            result=build(*paths)
            self.assertEqual(result['source_entries'],5)
            self.assertEqual(result['review_bridges'],1)
            with sqlite3.connect(output) as db:
                rows=dict(db.execute('SELECT entry_id,identity_id FROM entry_identity'))
                self.assertEqual(rows['a'],rows['b'])
                self.assertNotEqual(rows['b'],rows['c'])
                self.assertEqual(rows['c'],rows['d'])
                self.assertNotEqual(rows['d'],rows['e'])
                self.assertEqual(db.execute('SELECT disposition FROM evidence_links '
                    'WHERE left_entry_id=? AND right_entry_id=?',('b','c')).fetchone()[0],
                    'review_bridge')


if __name__ == '__main__':
    unittest.main()
