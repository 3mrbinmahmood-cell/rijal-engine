"""Conservative exact-name candidate inventory over all V1.1 biographies.

This inventory is lower confidence than the chronology queue. It contains no
identity assertions, decisions, or merges.
"""
import argparse
import json
from pathlib import Path
import sqlite3

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS methods(
 key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS name_groups(
 name_key TEXT PRIMARY KEY,entries INTEGER NOT NULL,books INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS name_members(
 entry_id TEXT PRIMARY KEY,
 name_key TEXT NOT NULL REFERENCES name_groups(name_key),
 name_label TEXT NOT NULL,opening_page_id TEXT NOT NULL,
 book_id TEXT NOT NULL,source_id TEXT NOT NULL,
 classification TEXT NOT NULL,statement_count INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS name_members_group ON name_members(name_key);
"""

GROUP_SQL = """
SELECT name_key,count(*) AS n,count(DISTINCT book_id) AS books
FROM biographies
WHERE classification='biography_candidate'
  AND length(name_key)>=25
  AND (length(name_key)-length(replace(name_key,' ',''))+1)>=5
GROUP BY name_key
HAVING n BETWEEN 2 AND 8 AND books>=2
ORDER BY name_key
"""

def build(extraction_path, inventory_path):
    source = sqlite3.connect(f'file:{Path(extraction_path).resolve()}?mode=ro',uri=True)
    target = sqlite3.connect(inventory_path,uri=True)
    try:
        source.execute('PRAGMA query_only=ON')
        target.executescript(SCHEMA)
        expected_sha=json.loads(
            (Path(extraction_path).parent/'extraction_data'/'PAYLOAD.json').read_text()
        )['database_sha256']
        previous=target.execute(
            "SELECT value FROM methods WHERE key='extraction_sha256'").fetchone()
        if previous and previous[0]!=expected_sha:
            raise ValueError('Existing inventory belongs to a different V1.1 release')
        groups = source.execute(GROUP_SQL).fetchall()
        target.execute('ATTACH DATABASE ? AS extraction',
                       (f'file:{Path(extraction_path).resolve()}?mode=ro',))
        with target:
            target.executemany('INSERT OR IGNORE INTO name_groups VALUES (?,?,?)',groups)
            target.execute("INSERT OR IGNORE INTO methods VALUES ('selection',?)",
                           ('Exact V1.1 normalized name; >=5 words, >=25 characters, '
                            '2-8 biography candidates across >=2 books; review only',))
            target.execute("INSERT OR IGNORE INTO methods VALUES ('extraction_sha256',?)",
                           (expected_sha,))
            target.execute("""INSERT OR IGNORE INTO name_members
                SELECT b.id,b.name_key,b.name_label,b.opening_page_id,
                       b.book_id,b.source_id,b.classification,b.statement_count
                FROM extraction.biographies b
                JOIN name_groups g ON g.name_key=b.name_key
                WHERE b.classification='biography_candidate'""")
            count=target.execute('SELECT count(*) FROM name_members').fetchone()[0]
            if count!=sum(g[1] for g in groups):
                raise ValueError('Candidate inventory count mismatch')
            if target.execute('SELECT count(*) FROM name_groups').fetchone()[0]!=len(groups):
                raise ValueError('Existing inventory differs; use a new output path')
        return {'groups':len(groups),'entries':count,'identity_merges':0}
    finally:
        source.close()
        target.close()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('extraction_database')
    parser.add_argument('inventory_database')
    args=parser.parse_args()
    print(json.dumps(build(args.extraction_database,args.inventory_database),indent=2))

if __name__=='__main__':
    main()
