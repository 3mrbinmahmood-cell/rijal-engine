"""Build a provenance graph from shared teacher and student name clues.

Name mentions are unresolved text labels, never asserted person identities.
Every observation retains the biography entry and source page that led to it.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3

SCHEMA='''
CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE name_mentions(id TEXT PRIMARY KEY,name TEXT NOT NULL UNIQUE,
 resolution_status TEXT NOT NULL DEFAULT 'unresolved_name');
CREATE TABLE observations(identity_id TEXT NOT NULL,entry_id TEXT NOT NULL,
 paired_entry_id TEXT NOT NULL,relation TEXT NOT NULL,
 mention_id TEXT NOT NULL REFERENCES name_mentions(id),
 page_id TEXT NOT NULL,review_priority TEXT NOT NULL,
 PRIMARY KEY(entry_id,paired_entry_id,relation,mention_id));
CREATE INDEX observations_identity ON observations(identity_id,relation);
CREATE INDEX observations_mention ON observations(mention_id,relation);
CREATE TABLE neighbors(identity_id TEXT NOT NULL,relation TEXT NOT NULL,
 mention_id TEXT NOT NULL REFERENCES name_mentions(id),
 source_entries INTEGER NOT NULL,supporting_pairs INTEGER NOT NULL,
 PRIMARY KEY(identity_id,relation,mention_id));
CREATE INDEX neighbors_mention ON neighbors(mention_id,relation);
'''


def build(queue_path,identity_path,output_path):
    if Path(output_path).exists():raise ValueError('Use a new output path')
    queue=sqlite3.connect(f'file:{Path(queue_path).resolve()}?mode=ro',uri=True)
    identity=sqlite3.connect(f'file:{Path(identity_path).resolve()}?mode=ro',uri=True)
    out=sqlite3.connect(output_path)
    try:
        sha=queue.execute("SELECT value FROM metadata WHERE key='v1_1_sha256'").fetchone()
        if sha!=identity.execute(
            "SELECT value FROM metadata WHERE key='v1_1_sha256'").fetchone():
            raise ValueError('Relationship and identity releases differ')
        pairs=list(queue.execute('''SELECT left_entry_id,right_entry_id,
            common_teachers_json,common_students_json,priority FROM pairs'''))
        ids={entry for a,b,*_ in pairs for entry in (a,b)}
        entries={}
        ordered=sorted(ids)
        for start in range(0,len(ordered),500):
            batch=ordered[start:start+500]
            marks=','.join('?' for _ in batch)
            entries.update((entry,(identity_id,page)) for entry,identity_id,page in
                identity.execute(f'''SELECT entry_id,identity_id,opening_page_id
                    FROM entry_identity WHERE entry_id IN ({marks})''',batch))
        if len(entries)!=len(ids):raise ValueError('Relationship entry missing from identity view')
        mentions={};observations=[]
        for a,b,teachers,students,priority in pairs:
            for relation,encoded in (('teacher',teachers),('student',students)):
                for name in json.loads(encoded):
                    mention='mention-'+hashlib.sha256(name.encode()).hexdigest()[:32]
                    mentions[mention]=name
                    for entry,partner in ((a,b),(b,a)):
                        identity_id,page=entries[entry]
                        observations.append((identity_id,entry,partner,relation,
                                             mention,page,priority))
        out.executescript(SCHEMA)
        with out:
            out.execute('INSERT INTO metadata VALUES (?,?)',('v1_1_sha256',sha[0]))
            out.executemany('INSERT INTO name_mentions(id,name) VALUES (?,?)',
                            mentions.items())
            out.executemany('INSERT OR IGNORE INTO observations VALUES (?,?,?,?,?,?,?)',
                            observations)
            out.execute('''INSERT INTO neighbors
                SELECT identity_id,relation,mention_id,count(DISTINCT entry_id),count(*)
                FROM observations GROUP BY identity_id,relation,mention_id''')
        return {'source_pairs':len(pairs),'source_entries':len(entries),
                'unresolved_name_mentions':len(mentions),
                'observations':out.execute('SELECT count(*) FROM observations').fetchone()[0],
                'identity_name_edges':out.execute('SELECT count(*) FROM neighbors').fetchone()[0],
                'identity_merges':0}
    finally:queue.close();identity.close();out.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('relationship_queue','identity','output'):p.add_argument(arg)
    a=p.parse_args()
    print(json.dumps(build(a.relationship_queue,a.identity,a.output),indent=2))


if __name__=='__main__':main()
