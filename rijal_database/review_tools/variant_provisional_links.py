"""Create reversible links for strongly supported cross-spelling entries.

The linked source entries retain their original names and biography IDs.
No reviewed person identity is created by this heuristic pass.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sqlite3

SCHEMA="""
CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE links(left_entry_id TEXT NOT NULL,right_entry_id TEXT NOT NULL,
 variant_bucket_id TEXT NOT NULL,evidence_kind TEXT NOT NULL,
 PRIMARY KEY(left_entry_id,right_entry_id));
CREATE TABLE clusters(id TEXT PRIMARY KEY,variant_bucket_id TEXT NOT NULL,
 name_keys_json TEXT NOT NULL,entry_count INTEGER NOT NULL,
 status TEXT NOT NULL DEFAULT 'provisional');
CREATE TABLE members(entry_id TEXT PRIMARY KEY,cluster_id TEXT NOT NULL,
 original_name_key TEXT NOT NULL);
CREATE INDEX members_cluster ON members(cluster_id);
"""

def build(variants_path,full_index_path,output_path):
    if Path(output_path).exists():raise ValueError('Use a new output path')
    variants=sqlite3.connect(f'file:{Path(variants_path).resolve()}?mode=ro',uri=True)
    full=sqlite3.connect(f'file:{Path(full_index_path).resolve()}?mode=ro',uri=True)
    target=sqlite3.connect(output_path,uri=True)
    try:
        sha=variants.execute("SELECT value FROM metadata WHERE key='v1_1_sha256'").fetchone()[0]
        if full.execute("SELECT value FROM release_meta WHERE key='v1_1_sha256'").fetchone()!=(sha,):
            raise ValueError('Variant and full index releases do not match')
        target.executescript(SCHEMA)
        bio={e for e, in full.execute("SELECT entry_id FROM name_entries "
                                       "WHERE classification='biography_candidate'")}
        entries=dict(variants.execute('SELECT entry_id,name_key FROM variant_entries'))
        bucket=dict(variants.execute('SELECT entry_id,bucket_id FROM variant_entries'))
        parent={}
        def root(e):
            parent.setdefault(e,e)
            while parent[e]!=e:
                parent[e]=parent[parent[e]];e=parent[e]
            return e
        def union(a,b):
            x,y=root(a),root(b)
            if x!=y:parent[max(x,y)]=min(x,y)
        links={}
        for a,b,group,n in variants.execute('''SELECT left_entry_id,
            right_entry_id,variant_bucket_id,shared_long_statements
            FROM candidate_pairs WHERE shared_long_statements>=2'''):
            if a in bio and b in bio:links[(a,b)]=(group,'two_long_statements')
        for a,b,group in variants.execute('''SELECT left_entry_id,right_entry_id,
            variant_bucket_id FROM relationship_pairs
            WHERE priority='both_lists_3plus' '''):
            if a in bio and b in bio:
                links.setdefault((a,b),(group,'both_relationship_lists'))
        for (a,b),(group,_) in links.items():
            if bucket[a]!=group or bucket[b]!=group or entries[a]==entries[b]:
                raise ValueError('Invalid cross-spelling candidate')
            union(a,b)
        groups=defaultdict(list)
        for entry in parent:groups[root(entry)].append(entry)
        clusters=[];members=[]
        for representative,ids in groups.items():
            ids.sort();group=bucket[representative]
            cid='variant-prov-'+hashlib.sha256((group+'\0'+ids[0]).encode()).hexdigest()[:32]
            names=sorted({entries[e] for e in ids})
            clusters.append((cid,group,json.dumps(names,ensure_ascii=False),len(ids),'provisional'))
            members.extend((e,cid,entries[e]) for e in ids)
        with target:
            target.execute('INSERT INTO metadata VALUES (?,?)',('v1_1_sha256',sha))
            target.executemany('INSERT INTO links VALUES (?,?,?,?)',
                [(a,b,group,kind) for (a,b),(group,kind) in links.items()])
            target.executemany('INSERT INTO clusters VALUES (?,?,?,?,?)',clusters)
            target.executemany('INSERT INTO members VALUES (?,?,?)',members)
        return {'provisional_links':len(links),'clusters':len(clusters),
                'linked_entries':len(members),'reviewed_person_ids_created':0}
    finally:
        variants.close();full.close();target.close()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for a in ('variants','full_index','output'):p.add_argument(a)
    a=p.parse_args()
    print(json.dumps(build(a.variants,a.full_index,a.output),indent=2))

if __name__=='__main__':main()
