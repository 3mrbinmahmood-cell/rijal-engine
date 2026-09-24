"""Index every V1.1 extraction entry by normalized name without merging people.

The index includes short names, single-book entries, and index/cross-reference
classes. Name groups are browsing buckets, never asserted unique people.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3

SCHEMA="""
CREATE TABLE release_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE name_groups(
 id TEXT PRIMARY KEY,name_key TEXT NOT NULL UNIQUE,entry_count INTEGER NOT NULL,
 biography_count INTEGER NOT NULL,distinct_books INTEGER NOT NULL,
 status TEXT NOT NULL);
CREATE TABLE name_entries(
 entry_id TEXT PRIMARY KEY,name_group_id TEXT NOT NULL REFERENCES name_groups(id),
 name_label TEXT NOT NULL,classification TEXT NOT NULL,
 book_id TEXT NOT NULL,source_id TEXT NOT NULL,opening_page_id TEXT NOT NULL);
CREATE INDEX name_entries_group ON name_entries(name_group_id);
CREATE INDEX name_entries_classification ON name_entries(classification);
"""

def build(extraction_path,output_path):
    if Path(output_path).exists():
        raise ValueError('Use a new output path to preserve earlier output')
    payload=json.loads((Path(extraction_path).parent/'extraction_data'/'PAYLOAD.json').read_text())
    target=sqlite3.connect(output_path,uri=True)
    try:
        target.executescript(SCHEMA)
        target.execute('ATTACH DATABASE ? AS source',
                       (f'file:{Path(extraction_path).resolve()}?mode=ro',))
        target.execute('INSERT INTO release_meta VALUES (?,?)',
                       ('v1_1_sha256',payload['database_sha256']))
        summaries=target.execute('''SELECT name_key,count(*),
            sum(classification='biography_candidate'),count(DISTINCT book_id)
            FROM source.biographies GROUP BY name_key''')
        group_rows=[];id_by_name={}
        for key,n,bios,books in summaries:
            group_id='name-'+hashlib.sha256(key.encode('utf-8')).hexdigest()[:32]
            id_by_name[key]=group_id
            status=('index_only' if not bios else
                    'single_entry' if n==1 else
                    'short_name_review' if len(key.split())<5 else
                    'multiple_entries')
            group_rows.append((group_id,key,n,bios,books,status))
        with target:
            target.executemany('INSERT INTO name_groups VALUES (?,?,?,?,?,?)',group_rows)
            batch=[]
            for entry,key,label,kind,book,source,page in target.execute('''SELECT id,
                name_key,name_label,classification,book_id,source_id,opening_page_id
                FROM source.biographies'''):
                batch.append((entry,id_by_name[key],label,kind,book,source,page))
                if len(batch)>=10000:
                    target.executemany('INSERT INTO name_entries VALUES (?,?,?,?,?,?,?)',batch)
                    batch.clear()
            if batch:target.executemany('INSERT INTO name_entries VALUES (?,?,?,?,?,?,?)',batch)
        counts=dict(target.execute('SELECT status,count(*) FROM name_groups GROUP BY status'))
        indexed=target.execute('SELECT count(*) FROM name_entries').fetchone()[0]
        source_count=target.execute('SELECT count(*) FROM source.biographies').fetchone()[0]
        if indexed!=source_count or sum(row[2] for row in group_rows)!=source_count:
            raise ValueError('The full extraction was not indexed')
        return {'source_entries':indexed,'name_groups':len(group_rows),
                'group_statuses':counts,'identity_merges':0}
    finally:
        target.close()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('extraction');p.add_argument('output')
    args=p.parse_args()
    print(json.dumps(build(args.extraction,args.output),indent=2))

if __name__=='__main__':main()
