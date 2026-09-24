"""Build an evidence-backed, non-destructive identity review queue from V1.

Only V1 chronology groups with more than one source entry are proposed.
Matching name and death year is insufficient to establish identity.
"""
import argparse
import json
import sqlite3
from pathlib import Path

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS groups(
 id TEXT PRIMARY KEY,name_label TEXT NOT NULL,name_key TEXT NOT NULL,
 death_year INTEGER NOT NULL,source_entries INTEGER NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending');
CREATE TABLE IF NOT EXISTS members(
 entry_id TEXT PRIMARY KEY,group_id TEXT NOT NULL REFERENCES groups(id),
 name_label TEXT NOT NULL,death_year INTEGER NOT NULL,
 evidence_page_id TEXT NOT NULL,evidence_quote TEXT NOT NULL,
 entry_page_id TEXT NOT NULL,entry_start INTEGER NOT NULL,
 book_title TEXT NOT NULL,zip_path TEXT NOT NULL,printed_label TEXT,
 extraction_classification TEXT,statement_count INTEGER);
CREATE INDEX IF NOT EXISTS members_group ON members(group_id);
CREATE TABLE IF NOT EXISTS pair_decisions(
 left_entry_id TEXT NOT NULL REFERENCES members(entry_id),
 right_entry_id TEXT NOT NULL REFERENCES members(entry_id),
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
"""

def connect(path):
    db = sqlite3.connect(path)
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript(SCHEMA)
    return db

def build(base_path, extraction_path, queue_path):
    with sqlite3.connect(f'file:{Path(base_path).resolve()}?mode=ro',uri=True) as base, connect(queue_path) as queue:
        base.execute('PRAGMA query_only=ON')
        groups = base.execute(
            'SELECT id,name_label,name_key,death_year,source_entries '
            'FROM chronology_groups WHERE source_entries>1 ORDER BY id').fetchall()
        rows = base.execute("""
            SELECT r.entry_id,r.group_id,r.name_label,r.death_year,
                   r.evidence_page_id,r.evidence_quote,e.page_id,e.start_offset,
                   b.title,s.zip_path,p.printed_label
            FROM chronology_records r
            JOIN chronology_groups g ON g.id=r.group_id AND g.source_entries>1
            JOIN entries e ON e.id=r.entry_id
            JOIN pages p ON p.id=e.page_id
            JOIN source_files s ON s.id=p.source_id
            JOIN books b ON b.id=s.book_id
            ORDER BY r.group_id,r.entry_id""").fetchall()
        if any(not row[5] for row in rows):
            raise ValueError('A proposed member lacks a death-year evidence quote')
        expected = {g[0]:g[4] for g in groups}
        actual = {}
        for row in rows:
            actual[row[1]] = actual.get(row[1],0)+1
        if actual != expected:
            raise ValueError('Chronology group/member counts disagree')
        with sqlite3.connect(f'file:{Path(extraction_path).resolve()}?mode=ro',uri=True) as extraction:
            expected_sha = json.loads((Path(base_path).parent/'data'/'PAYLOAD.json').read_text())['database_sha256']
            actual_sha = extraction.execute(
                "SELECT value FROM metadata WHERE key='base_database_sha256'").fetchone()
            if not actual_sha or actual_sha[0] != expected_sha:
                raise ValueError('V1.1 extraction layer does not match this V1 release')
            ids = {row[0] for row in rows}
            details = {id_:(classification,count) for id_,classification,count in extraction.execute(
                'SELECT id,classification,statement_count FROM biographies') if id_ in ids}
            rows = [row+details.get(row[0],(None,None)) for row in rows]
        with queue:
            for group in groups:
                queue.execute(
                    'INSERT OR IGNORE INTO groups(id,name_label,name_key,death_year,source_entries) '
                    'VALUES (?,?,?,?,?)',group)
            queue.executemany(
                'INSERT OR IGNORE INTO members(entry_id,group_id,name_label,death_year,'
                'evidence_page_id,evidence_quote,entry_page_id,entry_start,book_title,zip_path,printed_label,'
                'extraction_classification,statement_count) '
                'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',rows)
            old = queue.execute('SELECT count(*) FROM members').fetchone()[0]
            if old != len(rows) or queue.execute('SELECT count(*) FROM groups').fetchone()[0] != len(groups):
                raise ValueError('Existing queue differs from this V1 corpus; use a separate queue file')
            stored_groups = queue.execute('SELECT id,name_label,name_key,death_year,source_entries FROM groups ORDER BY id').fetchall()
            stored_rows = queue.execute(
                'SELECT entry_id,group_id,name_label,death_year,evidence_page_id,evidence_quote,'
                'entry_page_id,entry_start,book_title,zip_path,printed_label,'
                'extraction_classification,statement_count '
                'FROM members ORDER BY group_id,entry_id').fetchall()
            if stored_groups != groups or stored_rows != rows:
                raise ValueError('Existing queue evidence differs from this V1 corpus')
            queue.execute('INSERT OR IGNORE INTO metadata VALUES (?,?)',('method','same normalized name and extracted death year; review only'))
            return {'groups':len(groups),'members':len(rows),
                    'decisions':queue.execute('SELECT count(*) FROM pair_decisions').fetchone()[0]}

def decide(db, a, b, decision, reason, reviewer):
    if a == b or decision not in ('same','different','uncertain') or not reason.strip() or not reviewer.strip():
        raise ValueError('Two different entries, valid decision, reason and reviewer are required')
    left,right = sorted((a,b))
    found = db.execute('SELECT entry_id,group_id FROM members WHERE entry_id IN (?,?)',(left,right)).fetchall()
    if len(found)!=2 or found[0][1]!=found[1][1]:
        raise ValueError('Both entries must occur in the same proposed group')
    with db:
        db.execute('INSERT INTO decision_history(left_entry_id,right_entry_id,decision,reason,reviewer) VALUES (?,?,?,?,?)',
                   (left,right,decision,reason,reviewer))
        db.execute("""INSERT INTO pair_decisions(left_entry_id,right_entry_id,decision,reason,reviewer)
            VALUES (?,?,?,?,?) ON CONFLICT(left_entry_id,right_entry_id) DO UPDATE SET
            decision=excluded.decision,reason=excluded.reason,reviewer=excluded.reviewer,
            decided_at=CURRENT_TIMESTAMP""",(left,right,decision,reason,reviewer))

def inspect(queue, base_path, extraction_path, group_id, context_chars=400):
    members = queue.execute(
        'SELECT entry_id,name_label,evidence_quote,book_title,zip_path,printed_label '
        'FROM members WHERE group_id=? ORDER BY entry_id',(group_id,)).fetchall()
    if not members:
        raise ValueError('Unknown review group')
    output = []
    with sqlite3.connect(f'file:{Path(base_path).resolve()}?mode=ro',uri=True) as base, \
         sqlite3.connect(f'file:{Path(extraction_path).resolve()}?mode=ro',uri=True) as extraction:
        for entry_id,name,death_quote,book,path,label in members:
            page = base.execute('''SELECT e.title,e.start_offset,e.end_offset,t.text
                FROM entries e JOIN pages p ON p.id=e.page_id
                JOIN page_texts t ON t.id=p.text_id WHERE e.id=?''',(entry_id,)).fetchone()
            if not page:
                raise ValueError('Missing V1 source entry')
            title,start,end,source = page
            if source[start:end] != title:
                raise ValueError('Source heading offset mismatch')
            statements = extraction.execute('''SELECT s.page_id,s.start_offset,s.end_offset,
                s.origin,s.subject_status,t.quote
                FROM statements s JOIN statement_texts t ON t.id=s.text_id
                WHERE s.biography_id=? ORDER BY s.page_id,s.start_offset LIMIT 12''',
                (entry_id,)).fetchall()
            output.append({
                'entry_id':entry_id,'name':name,'book':book,'source_path':path,
                'printed_page':label,'death_evidence':death_quote,
                'heading_exact':title,
                'opening_context':source[max(0,start-context_chars):min(len(source),end+context_chars)],
                'statements':[dict(zip(('page_id','start_offset','end_offset',
                                        'origin','subject_status','quote'),s)) for s in statements]
            })
    return output

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command',required=True)
    p = sub.add_parser('build');p.add_argument('v1');p.add_argument('v1_1');p.add_argument('queue')
    p = sub.add_parser('list');p.add_argument('queue');p.add_argument('--limit',type=int,default=10)
    p = sub.add_parser('show');p.add_argument('queue');p.add_argument('group_id')
    p = sub.add_parser('inspect');p.add_argument('queue');p.add_argument('v1')
    p.add_argument('v1_1');p.add_argument('group_id')
    p = sub.add_parser('decide');p.add_argument('queue');p.add_argument('entry_a');p.add_argument('entry_b')
    p.add_argument('decision',choices=('same','different','uncertain'))
    p.add_argument('--reason',required=True);p.add_argument('--reviewer',required=True)
    args = parser.parse_args()
    if args.command=='build':
        result=build(args.v1,args.v1_1,args.queue)
    else:
        with connect(args.queue) as db:
            if args.command=='list':
                result=db.execute('SELECT id,name_label,death_year,source_entries FROM groups '
                                  'ORDER BY source_entries DESC,id LIMIT ?',(max(1,min(args.limit,100)),)).fetchall()
            elif args.command=='show':
                result=db.execute('SELECT entry_id,name_label,evidence_quote,book_title,zip_path,printed_label,'
                                  'extraction_classification,statement_count '
                                  'FROM members WHERE group_id=? ORDER BY entry_id',(args.group_id,)).fetchall()
            elif args.command=='inspect':
                result=inspect(db,args.v1,args.v1_1,args.group_id)
            else:
                decide(db,args.entry_a,args.entry_b,args.decision,args.reason,args.reviewer)
                result={'recorded':True}
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
