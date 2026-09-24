"""Build reversible full-corpus links from multiple exact long statements.

Entries without links remain available through full_name_index. No reviewed
person ID is minted, and every source biography retains its original identity.
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
 name_key TEXT NOT NULL,shared_statements INTEGER NOT NULL,
 PRIMARY KEY(left_entry_id,right_entry_id));
CREATE TABLE clusters(id TEXT PRIMARY KEY,name_key TEXT NOT NULL,
 entry_count INTEGER NOT NULL,link_count INTEGER NOT NULL,
 years_json TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'provisional');
CREATE TABLE members(entry_id TEXT PRIMARY KEY,cluster_id TEXT NOT NULL REFERENCES clusters(id));
CREATE INDEX members_cluster ON members(cluster_id);
"""

def build(full_index_path,candidate_path,review_path,output_path):
    if Path(output_path).exists():raise ValueError('Use a new output path')
    full=sqlite3.connect(f'file:{Path(full_index_path).resolve()}?mode=ro',uri=True)
    candidates=sqlite3.connect(f'file:{Path(candidate_path).resolve()}?mode=ro',uri=True)
    review=sqlite3.connect(f'file:{Path(review_path).resolve()}?mode=ro',uri=True)
    target=sqlite3.connect(output_path,uri=True)
    try:
        target.executescript(SCHEMA)
        source_sha=full.execute("SELECT value FROM release_meta WHERE key='v1_1_sha256'").fetchone()[0]
        candidate_sha=candidates.execute("SELECT value FROM metadata WHERE key='v1_1_sha256'").fetchone()[0]
        review_sha=review.execute("SELECT value FROM methods WHERE key='extraction_sha256'").fetchone()[0]
        if source_sha!=candidate_sha or source_sha!=review_sha:
            raise ValueError('Candidate, review, and full index releases do not match')
        decisions={(a,b):d for a,b,d in review.execute(
            'SELECT left_entry_id,right_entry_id,decision FROM pair_decisions')}
        parent={};names={};years=defaultdict(set);links=[]
        def root(e):
            parent.setdefault(e,e)
            while parent[e]!=e:
                parent[e]=parent[parent[e]];e=parent[e]
            return e
        def union(a,b):
            x,y=root(a),root(b)
            if x!=y:parent[max(x,y)]=min(x,y)
        for a,b,key,n,ys in candidates.execute('''SELECT left_entry_id,
            right_entry_id,name_key,shared_statements,years_json
            FROM pairs WHERE shared_statements>=2'''):
            if decisions.get((a,b)) in ('different','uncertain'):continue
            for e in (a,b):
                if e in names and names[e]!=key:raise ValueError('Cross-name candidate')
                names[e]=key
            links.append((a,b,key,n));union(a,b)
            years[a].update(json.loads(ys));years[b].update(json.loads(ys))
        for a,b,d in review.execute('SELECT left_entry_id,right_entry_id,decision '
                                     'FROM pair_decisions WHERE decision="different"'):
            if a in parent and b in parent and root(a)==root(b):
                raise ValueError('Transitive component contradicts a different-person review')
        grouped=defaultdict(list)
        for e in parent:grouped[root(e)].append(e)
        clusters=[];members=[]
        for representative,entry_ids in grouped.items():
            entry_ids.sort();key=names[representative]
            gid='prov-'+hashlib.sha256((key+'\0'+entry_ids[0]).encode()).hexdigest()[:32]
            component=set(entry_ids)
            n=sum(a in component and b in component for a,b,_,_ in links)
            values=sorted(set().union(*(years[e] for e in entry_ids)))
            clusters.append((gid,key,len(entry_ids),n,json.dumps(values),'provisional'))
            members.extend((e,gid) for e in entry_ids)
        with target:
            target.execute('INSERT INTO metadata VALUES (?,?)',('v1_1_sha256',source_sha))
            target.executemany('INSERT INTO links VALUES (?,?,?,?)',links)
            target.executemany('INSERT INTO clusters VALUES (?,?,?,?,?,?)',clusters)
            target.executemany('INSERT INTO members VALUES (?,?)',members)
        return {'links':len(links),'provisional_clusters':len(clusters),
                'linked_entries':len(members),'reviewed_person_ids_created':0}
    finally:
        full.close();candidates.close();review.close();target.close()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for a in ('full_index','candidates','review','output'):p.add_argument(a)
    a=p.parse_args()
    print(json.dumps(build(a.full_index,a.candidates,a.review,a.output),indent=2))

if __name__=='__main__':main()
