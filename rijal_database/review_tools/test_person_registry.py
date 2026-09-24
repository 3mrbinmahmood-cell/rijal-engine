import sqlite3
import unittest
from rijal_database.review_tools.person_registry import (
    SCHEMA,create,add,audit,show,bind_releases)
from pathlib import Path
import tempfile
import json

class PersonRegistryTests(unittest.TestCase):
    def test_reviewed_links_stable_id_and_changing_evidence_digest(self):
        registry=sqlite3.connect(':memory:')
        registry.execute('PRAGMA foreign_keys=ON')
        registry.executescript(SCHEMA)
        review=sqlite3.connect(':memory:')
        review.execute('CREATE TABLE pair_decisions(left_entry_id TEXT,right_entry_id TEXT,decision TEXT)')
        base=sqlite3.connect(':memory:')
        base.executescript('''
            CREATE TABLE entries(id TEXT,page_id TEXT,title TEXT);
            CREATE TABLE pages(id TEXT,source_id TEXT);
            CREATE TABLE source_files(id TEXT,raw_sha256 TEXT);
            CREATE TABLE chronology_records(entry_id TEXT,death_year INTEGER,
                evidence_quote TEXT,evidence_page_id TEXT);
        ''')
        extraction=sqlite3.connect(':memory:')
        extraction.executescript('''
            CREATE TABLE biographies(id TEXT,name_label TEXT,name_key TEXT,
                opening_page_id TEXT,classification TEXT);
            CREATE TABLE statements(id TEXT,biography_id TEXT,page_id TEXT);
            CREATE TABLE statement_triggers(statement_id TEXT,kind TEXT,quote TEXT);
        ''')
        base.execute("INSERT INTO source_files VALUES ('source','checksum')")
        for entry in ('a','b','c'):
            base.execute('INSERT INTO pages VALUES (?,?)',('page-'+entry,'source'))
            base.execute('INSERT INTO entries VALUES (?,?,?)',
                         (entry,'page-'+entry,'اسم '+entry))
            base.execute('INSERT INTO chronology_records VALUES (?,?,?,?)',
                         (entry,100,'مات سنة مائة','page-'+entry))
            extraction.execute('INSERT INTO biographies VALUES (?,?,?,?,?)',
                               (entry,'اسم '+entry,'اسم','page-'+entry,'biography_candidate'))
        with self.assertRaises(ValueError):
            create(registry,review,base,extraction,'a','b','اسم','reviewer','Evidence')
        review.execute("INSERT INTO pair_decisions VALUES ('a','b','same')")
        person_id=create(registry,review,base,extraction,'a','b','اسم','reviewer','Evidence')
        initial=registry.execute('SELECT evidence_sha256 FROM persons WHERE id=?',
                                 (person_id,)).fetchone()[0]
        with self.assertRaises(ValueError):
            add(registry,review,base,extraction,person_id,'c','reviewer','Evidence')
        review.executemany('INSERT INTO pair_decisions VALUES (?,?,?)',
                           [('a','c','same'),('b','c','same')])
        later=add(registry,review,base,extraction,person_id,'c','reviewer','Evidence')
        self.assertNotEqual(initial,later)
        self.assertEqual(show(registry,person_id)['person_id'],person_id)
        self.assertEqual(show(registry,person_id)['evidence_sha256'],later)
        self.assertEqual(registry.execute('SELECT count(*) FROM person_entries').fetchone()[0],3)
        review.execute("UPDATE pair_decisions SET decision='different' WHERE left_entry_id='a' AND right_entry_id='b'")
        result=audit(registry,review)
        self.assertEqual(result['needs_review'],1)
        self.assertEqual(registry.execute('SELECT status FROM persons').fetchone()[0],'needs_review')
        registry.close();review.close();base.close();extraction.close()

    def test_registry_rejects_mismatched_release(self):
        with tempfile.TemporaryDirectory() as tmp, sqlite3.connect(':memory:') as db:
            db.executescript(SCHEMA)
            root=Path(tmp)
            (root/'data').mkdir();(root/'extraction_data').mkdir()
            (root/'data'/'PAYLOAD.json').write_text(json.dumps({'database_sha256':'base'}))
            (root/'extraction_data'/'PAYLOAD.json').write_text(
                json.dumps({'base_sha256':'other','database_sha256':'extract'}))
            with self.assertRaises(ValueError):
                bind_releases(db,root/'rijal.sqlite',root/'extraction.sqlite')
