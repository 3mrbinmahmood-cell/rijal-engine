"""Stable reviewed person IDs with a reproducible evidence fingerprint.

The fingerprint describes the linked evidence snapshot. It is not a proof of
identity, a similarity score, or a replacement for a reviewed person ID.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS registry_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS persons(
 id TEXT PRIMARY KEY,display_name TEXT NOT NULL,status TEXT NOT NULL
 CHECK(status IN ('reviewed','needs_review')),
 evidence_sha256 TEXT NOT NULL,evidence_json TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS person_entries(
 entry_id TEXT PRIMARY KEY,person_id TEXT NOT NULL REFERENCES persons(id),
 linked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX IF NOT EXISTS person_entries_person ON person_entries(person_id);
CREATE TABLE IF NOT EXISTS events(
 id INTEGER PRIMARY KEY,person_id TEXT NOT NULL REFERENCES persons(id),
 action TEXT NOT NULL,entry_id TEXT,reviewer TEXT NOT NULL,
 reason TEXT NOT NULL,recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
"""

def connect(path):
    db=sqlite3.connect(path)
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript(SCHEMA)
    return db

def source(path):
    return sqlite3.connect(f'file:{Path(path).resolve()}?mode=ro',uri=True)

def bind_releases(registry, base_path, extraction_path):
    base=json.loads((Path(base_path).parent/'data'/'PAYLOAD.json').read_text())
    extraction=json.loads(
        (Path(extraction_path).parent/'extraction_data'/'PAYLOAD.json').read_text())
    if extraction['base_sha256']!=base['database_sha256']:
        raise ValueError('V1.1 extraction does not match the V1 release')
    expected={'v1_sha256':base['database_sha256'],
              'v1_1_sha256':extraction['database_sha256']}
    with registry:
        for key,value in expected.items():
            old=registry.execute('SELECT value FROM registry_meta WHERE key=?',
                                 (key,)).fetchone()
            if old and old[0]!=value:
                raise ValueError('Registry is bound to a different database release')
            registry.execute('INSERT OR IGNORE INTO registry_meta VALUES (?,?)',
                             (key,value))

def reviewed_pair(review, a, b):
    left,right=sorted((a,b))
    row=review.execute('SELECT decision FROM pair_decisions WHERE left_entry_id=? '
                       'AND right_entry_id=?',(left,right)).fetchone()
    return row[0] if row else None

def evidence_snapshot(entry_ids, base, extraction):
    entries=[]
    for entry_id in sorted(entry_ids):
        bio=extraction.execute('SELECT name_label,name_key,opening_page_id,classification '
                               'FROM biographies WHERE id=?',(entry_id,)).fetchone()
        if not bio:
            raise ValueError('Missing V1.1 biography: '+entry_id)
        entry=base.execute('''SELECT e.page_id,e.title,s.raw_sha256
            FROM entries e JOIN pages p ON p.id=e.page_id
            JOIN source_files s ON s.id=p.source_id WHERE e.id=?''',
            (entry_id,)).fetchone()
        if not entry:
            raise ValueError('Missing V1 source entry: '+entry_id)
        date=base.execute('SELECT death_year,evidence_quote,evidence_page_id '
                          'FROM chronology_records WHERE entry_id=?',(entry_id,)).fetchone()
        traits=extraction.execute('''SELECT DISTINCT t.kind,t.quote,s.page_id
            FROM statements s JOIN statement_triggers t ON t.statement_id=s.id
            WHERE s.biography_id=? AND t.kind IN
            ('alias','family','teachers','students')
            ORDER BY t.kind,t.quote,s.page_id''',(entry_id,)).fetchall()
        entries.append({'entry_id':entry_id,'name_exact':bio[0],
                        'name_key':bio[1],'classification':bio[3],
                        'opening_page_id':bio[2],'heading_exact':entry[1],
                        'source_sha256':entry[2],
                        'death_evidence':list(date) if date else None,
                        'literal_traits':[list(t) for t in traits]})
    payload={'version':1,'linked_entries':entries}
    canonical=json.dumps(payload,ensure_ascii=False,sort_keys=True,
                         separators=(',',':')).encode('utf-8')
    return hashlib.sha256(canonical).hexdigest(),canonical.decode('utf-8')

def require_all_same(review, entry_ids):
    ids=sorted(entry_ids)
    if len(ids)!=len(set(ids)) or len(ids)<2:
        raise ValueError('At least two distinct reviewed entries are required')
    for i,left in enumerate(ids):
        for right in ids[i+1:]:
            if reviewed_pair(review,left,right)!='same':
                raise ValueError('Every pair must have an explicit current same-person review: '
                                 +left+' / '+right)

def create(registry, review, base, extraction, a, b, name, reviewer, reason):
    if not name.strip() or not reviewer.strip() or not reason.strip():
        raise ValueError('Name, reviewer and reason are required')
    require_all_same(review,[a,b])
    digest,payload=evidence_snapshot([a,b],base,extraction)
    person_id=str(uuid.uuid4())
    with registry:
        registry.execute('INSERT INTO persons(id,display_name,status,evidence_sha256,evidence_json) '
                         'VALUES (?,? ,\'reviewed\',?,?)',(person_id,name,digest,payload))
        registry.executemany('INSERT INTO person_entries(entry_id,person_id) VALUES (?,?)',
                             [(a,person_id),(b,person_id)])
        registry.execute('INSERT INTO events(person_id,action,reviewer,reason) VALUES (?,?,?,?)',
                         (person_id,'create',reviewer,reason))
    return person_id

def add(registry, review, base, extraction, person_id, entry_id, reviewer, reason):
    if not reviewer.strip() or not reason.strip():
        raise ValueError('Reviewer and reason are required')
    ids=[r[0] for r in registry.execute('SELECT entry_id FROM person_entries WHERE person_id=?',
                                        (person_id,))]
    if not ids:
        raise ValueError('Unknown person ID')
    require_all_same(review,ids+[entry_id])
    digest,payload=evidence_snapshot(ids+[entry_id],base,extraction)
    with registry:
        registry.execute('INSERT INTO person_entries(entry_id,person_id) VALUES (?,?)',
                         (entry_id,person_id))
        registry.execute('UPDATE persons SET evidence_sha256=?,evidence_json=?,'
                         'updated_at=CURRENT_TIMESTAMP WHERE id=?',
                         (digest,payload,person_id))
        registry.execute('INSERT INTO events(person_id,action,entry_id,reviewer,reason) '
                         'VALUES (?,?,?,?,?)',(person_id,'add',entry_id,reviewer,reason))
    return digest

def audit(registry, review):
    flagged=[]
    for person_id, in registry.execute('SELECT id FROM persons'):
        ids=[r[0] for r in registry.execute(
            'SELECT entry_id FROM person_entries WHERE person_id=?',(person_id,))]
        try:
            require_all_same(review,ids)
        except ValueError as exc:
            flagged.append({'person_id':person_id,'issue':str(exc)})
    with registry:
        for item in flagged:
            registry.execute("UPDATE persons SET status='needs_review' WHERE id=?",
                             (item['person_id'],))
    return {'persons':registry.execute('SELECT count(*) FROM persons').fetchone()[0],
            'needs_review':len(flagged),'issues':flagged}

def show(registry, person_id):
    row=registry.execute('SELECT id,display_name,status,evidence_sha256,evidence_json,'
                         'created_at,updated_at FROM persons WHERE id=?',
                         (person_id,)).fetchone()
    if not row:
        raise ValueError('Unknown person ID')
    return {'person_id':row[0],'display_name':row[1],'status':row[2],
            'evidence_sha256':row[3],'evidence':json.loads(row[4]),
            'created_at':row[5],'updated_at':row[6],
            'events':[dict(zip(('action','entry_id','reviewer','reason','recorded_at'),r))
                      for r in registry.execute(
                          'SELECT action,entry_id,reviewer,reason,recorded_at '
                          'FROM events WHERE person_id=? ORDER BY id',(person_id,))]}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    for action in ('create','add','audit','show'):
        q=sub.add_parser(action)
        q.add_argument('registry')
        if action!='show':
            q.add_argument('review')
        if action in ('create','add'):
            q.add_argument('v1');q.add_argument('v1_1')
            q.add_argument('--reviewer',required=True);q.add_argument('--reason',required=True)
        if action=='create':
            q.add_argument('entry_a');q.add_argument('entry_b')
            q.add_argument('--name',required=True)
        if action=='add':
            q.add_argument('person_id');q.add_argument('entry_id')
        if action=='show':
            q.add_argument('person_id')
    args=p.parse_args()
    with connect(args.registry) as registry:
        if args.command=='show':
            result=show(registry,args.person_id)
        elif args.command=='audit':
            with source(args.review) as review:
                result=audit(registry,review)
        else:
            bind_releases(registry,args.v1,args.v1_1)
            with source(args.review) as review, \
                 source(args.v1) as base,source(args.v1_1) as extraction:
                if args.command=='create':
                    result={'person_id':create(registry,review,base,extraction,
                        args.entry_a,args.entry_b,args.name,args.reviewer,args.reason)}
                else:
                    result={'evidence_sha256':add(registry,review,base,extraction,
                        args.person_id,args.entry_id,args.reviewer,args.reason)}
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
