import json
import sqlite3
import tempfile
from pathlib import Path
import unittest

from rijal_database.review_tools.identity_dates import build


class IdentityDatesTest(unittest.TestCase):
    def test_conflicting_claims_preserve_quotes_and_nearest_range(self):
        with tempfile.TemporaryDirectory() as directory:
            identity,inventory,output=[Path(directory)/f'{n}.sqlite'
                                       for n in ('identity','inventory','dates')]
            with sqlite3.connect(identity) as db:
                db.executescript('''CREATE TABLE metadata(key TEXT,value TEXT);
                  CREATE TABLE entry_identity(entry_id TEXT,identity_id TEXT);''')
                db.execute('INSERT INTO metadata VALUES (?,?)',('v1_1_sha256','sha'))
                db.executemany('INSERT INTO entry_identity VALUES (?,?)',
                               [('a','person'),('b','person')])
            with sqlite3.connect(inventory) as db:
                db.executescript('''CREATE TABLE methods(key TEXT,value TEXT);
                  CREATE TABLE date_evidence(entry_id TEXT,death_year INTEGER,
                    evidence_quote TEXT,evidence_page_id TEXT);
                  CREATE TABLE additional_date_claims(entry_id TEXT,year INTEGER,
                    page_id TEXT,start_offset INTEGER,end_offset INTEGER,
                    exact_quote TEXT,reviewer TEXT,note TEXT);''')
                db.execute('INSERT INTO methods VALUES (?,?)',('extraction_sha256','sha'))
                db.executemany('INSERT INTO date_evidence VALUES (?,?,?,?)',
                               [('a',186,'quote 186','page1'),
                                ('b',187,'quote 187','page2')])
                db.execute('INSERT INTO additional_date_claims VALUES (?,?,?,?,?,?,?,?)',
                           ('b',189,'page2',12,20,'quote 189','reviewer','note'))
            result=build(identity,inventory,output)
            self.assertEqual(result['identities_with_multiple_years'],1)
            with sqlite3.connect(output) as db:
                years,unit,start,end=db.execute('''SELECT years_json,bucket_unit,
                    bucket_start,bucket_end FROM identity_date_summary''').fetchone()
                self.assertEqual(json.loads(years),[186,187,189])
                self.assertEqual((unit,start,end),(10,180,189))
                self.assertEqual([r[0] for r in db.execute(
                    'SELECT exact_quote FROM date_claims ORDER BY year')],
                    ['quote 186','quote 187','quote 189'])


if __name__=='__main__':unittest.main()
