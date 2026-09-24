"""Conservative exact-name candidate inventory over all V1.1 biographies.

This inventory is lower confidence than the chronology queue. Review decisions
are recorded separately; no identity merges are made.
"""
import argparse
import json
from pathlib import Path
import sqlite3
from .queue import inspect_entries

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
CREATE TABLE IF NOT EXISTS pair_decisions(
 left_entry_id TEXT NOT NULL REFERENCES name_members(entry_id),
 right_entry_id TEXT NOT NULL REFERENCES name_members(entry_id),
 decision TEXT NOT NULL CHECK(decision IN ('same','different','uncertain')),
 reason TEXT NOT NULL CHECK(length(trim(reason))>0),
 reviewer TEXT NOT NULL CHECK(length(trim(reviewer))>0),
 decided_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY(left_entry_id,right_entry_id),
 CHECK(left_entry_id<right_entry_id));
CREATE TABLE IF NOT EXISTS decision_history(
 id INTEGER PRIMARY KEY,left_entry_id TEXT NOT NULL,right_entry_id TEXT NOT NULL,
 decision TEXT NOT NULL,reason TEXT NOT NULL,reviewer TEXT NOT NULL,
 recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS group_triage(
 name_key TEXT PRIMARY KEY REFERENCES name_groups(name_key),
 dated_entries INTEGER NOT NULL,distinct_years INTEGER NOT NULL,
 status TEXT NOT NULL CHECK(status IN
 ('conflicting_dates','matching_dates','one_date','no_dates')));
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
        return {'groups':len(groups),'entries':count,
                'decisions':target.execute('SELECT count(*) FROM pair_decisions').fetchone()[0],
                'identity_merges':0}
    finally:
        source.close()
        target.close()

def decide(db, a, b, decision, reason, reviewer):
    if a==b or decision not in ('same','different','uncertain') or not reason.strip() or not reviewer.strip():
        raise ValueError('Two different entries, valid decision, reason and reviewer are required')
    left,right=sorted((a,b))
    rows=db.execute('SELECT entry_id,name_key FROM name_members WHERE entry_id IN (?,?)',
                    (left,right)).fetchall()
    if len(rows)!=2 or rows[0][1]!=rows[1][1]:
        raise ValueError('Both entries must occur in the same name group')
    with db:
        db.execute('INSERT INTO decision_history(left_entry_id,right_entry_id,decision,reason,reviewer) VALUES (?,?,?,?,?)',
                   (left,right,decision,reason,reviewer))
        db.execute("""INSERT INTO pair_decisions(left_entry_id,right_entry_id,decision,reason,reviewer)
            VALUES (?,?,?,?,?) ON CONFLICT(left_entry_id,right_entry_id) DO UPDATE SET
            decision=excluded.decision,reason=excluded.reason,reviewer=excluded.reviewer,
            decided_at=CURRENT_TIMESTAMP""",(left,right,decision,reason,reviewer))

def inspect(db, base_path, extraction_path, name_key):
    ids=db.execute('SELECT entry_id,name_label FROM name_members WHERE name_key=? ORDER BY entry_id',
                   (name_key,)).fetchall()
    if not ids:
        raise ValueError('Unknown name group')
    members=[]
    with sqlite3.connect(f'file:{Path(base_path).resolve()}?mode=ro',uri=True) as base:
        for entry_id,name in ids:
            citation=base.execute("""SELECT r.evidence_quote,b.title,s.zip_path,p.printed_label
                FROM entries e JOIN pages p ON p.id=e.page_id
                JOIN source_files s ON s.id=p.source_id JOIN books b ON b.id=s.book_id
                LEFT JOIN chronology_records r ON r.entry_id=e.id
                WHERE e.id=?""",(entry_id,)).fetchone()
            if not citation:
                raise ValueError('Missing V1 source entry')
            members.append((entry_id,name,*citation))
    return inspect_entries(members,base_path,extraction_path)

def triage(db, base_path, extraction_path):
    base_manifest=json.loads((Path(base_path).parent/'data'/'PAYLOAD.json').read_text())
    extraction_manifest=json.loads(
        (Path(extraction_path).parent/'extraction_data'/'PAYLOAD.json').read_text())
    if base_manifest['database_sha256']!=extraction_manifest['base_sha256']:
        raise ValueError('V1 and V1.1 releases do not match')
    previous=db.execute("SELECT value FROM methods WHERE key='extraction_sha256'").fetchone()
    if not previous or previous[0]!=extraction_manifest['database_sha256']:
        raise ValueError('Inventory was built from a different V1.1 release')
    db.execute('ATTACH DATABASE ? AS v1',
               (f'file:{Path(base_path).resolve()}?mode=ro',))
    try:
        with db:
            db.execute("""INSERT INTO group_triage(name_key,dated_entries,distinct_years,status)
                SELECT m.name_key,count(r.death_year),count(DISTINCT r.death_year),
                CASE WHEN count(DISTINCT r.death_year)>1 THEN 'conflicting_dates'
                     WHEN count(r.death_year)>=2 THEN 'matching_dates'
                     WHEN count(r.death_year)=1 THEN 'one_date'
                     ELSE 'no_dates' END
                FROM name_members m
                LEFT JOIN v1.chronology_records r ON r.entry_id=m.entry_id
                GROUP BY m.name_key
                ON CONFLICT(name_key) DO UPDATE SET
                dated_entries=excluded.dated_entries,
                distinct_years=excluded.distinct_years,
                status=excluded.status""")
            db.execute("INSERT OR IGNORE INTO methods VALUES ('base_sha256',?)",
                       (base_manifest['database_sha256'],))
            if db.execute('SELECT count(*) FROM group_triage').fetchone()[0] != db.execute(
                    'SELECT count(*) FROM name_groups').fetchone()[0]:
                raise ValueError('Triage did not cover every name group')
        return dict(db.execute(
            'SELECT status,count(*) FROM group_triage GROUP BY status').fetchall())
    finally:
        db.execute('DETACH DATABASE v1')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    p=commands.add_parser('build');p.add_argument('extraction_database');p.add_argument('inventory_database')
    p=commands.add_parser('list');p.add_argument('inventory_database');p.add_argument('--limit',type=int,default=10)
    p=commands.add_parser('inspect');p.add_argument('inventory_database');p.add_argument('v1')
    p.add_argument('v1_1');p.add_argument('name_key')
    p=commands.add_parser('triage');p.add_argument('inventory_database');p.add_argument('v1')
    p.add_argument('v1_1')
    p=commands.add_parser('decide');p.add_argument('inventory_database')
    p.add_argument('entry_a');p.add_argument('entry_b')
    p.add_argument('decision',choices=('same','different','uncertain'))
    p.add_argument('--reason',required=True);p.add_argument('--reviewer',required=True)
    args=parser.parse_args()
    if args.command=='build':
        result=build(args.extraction_database,args.inventory_database)
    else:
        with sqlite3.connect(args.inventory_database,uri=True) as db:
            db.execute('PRAGMA foreign_keys=ON')
            db.executescript(SCHEMA)
            if args.command=='list':
                result=db.execute("""SELECT g.name_key,g.entries,g.books,
                                    COALESCE(t.status,'untriaged')
                                    FROM name_groups g LEFT JOIN group_triage t USING(name_key)
                                    ORDER BY CASE t.status
                                      WHEN 'conflicting_dates' THEN 0
                                      WHEN 'matching_dates' THEN 1
                                      WHEN 'one_date' THEN 2 ELSE 3 END,
                                    g.entries DESC,g.name_key LIMIT ?""",
                                  (max(1,min(args.limit,100)),)).fetchall()
            elif args.command=='inspect':
                result=inspect(db,args.v1,args.v1_1,args.name_key)
            elif args.command=='triage':
                result=triage(db,args.v1,args.v1_1)
            else:
                decide(db,args.entry_a,args.entry_b,args.decision,args.reason,args.reviewer)
                result={'recorded':True}
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
