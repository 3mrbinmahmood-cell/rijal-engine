"""Map every extraction entry to a reviewed, provisional, or singleton identity.

Provisional evidence never expands a reviewed person. Source records remain
immutable, and name buckets are retained separately from person identity.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import sqlite3

SCHEMA="""
PRAGMA foreign_keys=ON;
CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE identities(id TEXT PRIMARY KEY,kind TEXT NOT NULL,
 display_name TEXT NOT NULL,entry_count INTEGER NOT NULL);
CREATE TABLE entry_identity(entry_id TEXT PRIMARY KEY,
 identity_id TEXT NOT NULL REFERENCES identities(id),
 identity_kind TEXT NOT NULL,name_bucket_id TEXT NOT NULL,
 name_key TEXT NOT NULL,name_label TEXT NOT NULL,
 classification TEXT NOT NULL,book_id TEXT NOT NULL,
 source_id TEXT NOT NULL,opening_page_id TEXT NOT NULL);
CREATE INDEX entry_identity_identity ON entry_identity(identity_id);
CREATE INDEX entry_identity_bucket ON entry_identity(name_bucket_id);
CREATE TABLE evidence_links(left_entry_id TEXT NOT NULL,right_entry_id TEXT NOT NULL,
 evidence_kind TEXT NOT NULL,disposition TEXT NOT NULL,
 PRIMARY KEY(left_entry_id,right_entry_id,evidence_kind));
"""

def open_ro(path):
    return sqlite3.connect(f'file:{Path(path).resolve()}?mode=ro',uri=True)

def build(full_path,registry_path,full_links_path,variant_links_path,
          review_path,output_path):
    if Path(output_path).exists():raise ValueError('Use a new output path')
    full=open_ro(full_path);registry=open_ro(registry_path)
    literal=open_ro(full_links_path);variants=open_ro(variant_links_path)
    review=open_ro(review_path);target=sqlite3.connect(output_path)
    try:
        sha=full.execute("SELECT value FROM release_meta WHERE key='v1_1_sha256'").fetchone()[0]
        for db,table,key in ((registry,'registry_meta','v1_1_sha256'),
                             (literal,'metadata','v1_1_sha256'),
                             (variants,'metadata','v1_1_sha256'),
                             (review,'methods','extraction_sha256')):
            if db.execute(f'SELECT value FROM {table} WHERE key=?',(key,)).fetchone()!=(sha,):
                raise ValueError('Identity inputs refer to different extraction releases')
        target.executescript(SCHEMA)
        reviewed=dict(registry.execute('SELECT entry_id,person_id FROM person_entries'))
        people={pid:(name,status) for pid,name,status in registry.execute(
            'SELECT id,display_name,status FROM persons')}
        parent={}
        def root(e):
            parent.setdefault(e,e)
            while parent[e]!=e:
                parent[e]=parent[parent[e]];e=parent[e]
            return e
        def union(a,b):
            x,y=root(a),root(b)
            if x!=y:parent[max(x,y)]=min(x,y)
        veto={(a,b) for a,b,d in review.execute('SELECT left_entry_id,right_entry_id,decision '
                                                 'FROM pair_decisions WHERE decision IN '
                                                 '("different","uncertain")')}
        links=[]
        for a,b,n in literal.execute('SELECT left_entry_id,right_entry_id,shared_statements '
                                     'FROM links'):
            links.append((a,b,'long_statements_'+str(n)))
        for a,b,kind in variants.execute('SELECT left_entry_id,right_entry_id,evidence_kind '
                                          'FROM links'):
            links.append((a,b,'variant_'+kind))
        dispositions=[]
        for a,b,kind in links:
            pair=tuple(sorted((a,b)))
            if pair in veto:
                disposition='review_veto'
            elif a in reviewed or b in reviewed:
                disposition=('already_reviewed' if reviewed.get(a)==reviewed.get(b)
                             and a in reviewed and b in reviewed else 'review_bridge')
            else:
                union(a,b);disposition='provisional_link'
            dispositions.append((a,b,kind,disposition))
        for a,b in veto:
            if a in parent and b in parent and root(a)==root(b):
                raise ValueError('Provisional transitive component crosses a review veto')
        components=defaultdict(list)
        for entry in parent:components[root(entry)].append(entry)
        cluster_id={};cluster_sizes={}
        for entries in components.values():
            entries.sort()
            cid='prov-'+hashlib.sha256(('\0'.join(entries)).encode()).hexdigest()[:32]
            cluster_sizes[cid]=len(entries)
            cluster_id.update((entry,cid) for entry in entries)
        target.execute('INSERT INTO metadata VALUES (?,?)',('v1_1_sha256',sha))
        target.executemany('INSERT INTO evidence_links VALUES (?,?,?,?)',dispositions)
        identity_rows=[(pid,'reviewed_person' if status=='reviewed' else 'needs_review',
                        name,registry.execute('SELECT count(*) FROM person_entries WHERE person_id=?',
                                               (pid,)).fetchone()[0])
                       for pid,(name,status) in people.items()]
        target.executemany('INSERT INTO identities VALUES (?,?,?,?)',identity_rows)
        provisional_labels={}
        entries=[];single=[]
        for entry,bucket,label,kind,book,source,page in full.execute('''SELECT e.entry_id,
            e.name_group_id,e.name_label,e.classification,e.book_id,e.source_id,
            e.opening_page_id FROM name_entries e'''):
            if entry in reviewed:
                identity=reviewed[entry]
                identity_kind=('reviewed_person' if people[identity][1]=='reviewed'
                               else 'needs_review')
            elif entry in cluster_id:
                identity=cluster_id[entry];identity_kind='provisional_cluster'
                provisional_labels.setdefault(identity,label)
            else:
                identity='single-'+entry;identity_kind='unlinked_entry'
                single.append((identity,identity_kind,label,1))
            entries.append((entry,identity,identity_kind,bucket,None,label,kind,
                            book,source,page))
        names=dict(full.execute('SELECT id,name_key FROM name_groups'))
        with target:
            target.executemany('INSERT INTO identities VALUES (?,?,?,?)',
                [(cid,'provisional_cluster',provisional_labels[cid],n)
                 for cid,n in cluster_sizes.items()])
            for i in range(0,len(single),10000):
                target.executemany('INSERT INTO identities VALUES (?,?,?,?)',single[i:i+10000])
            for i in range(0,len(entries),10000):
                target.executemany('INSERT INTO entry_identity VALUES (?,?,?,?,?,?,?,?,?,?)',
                    [(entry,identity,kind,bucket,names[bucket],label,classification,
                      book,source,page)
                     for entry,identity,kind,bucket,_,label,classification,book,source,page
                     in entries[i:i+10000]])
        count=target.execute('SELECT count(*) FROM entry_identity').fetchone()[0]
        expected=full.execute('SELECT count(*) FROM name_entries').fetchone()[0]
        if count!=expected:raise ValueError('Full source coverage failed')
        return {'source_entries':count,'reviewed_people':len(people),
                'reviewed_entries':len(reviewed),'provisional_clusters':len(cluster_sizes),
                'provisionally_linked_entries':len(cluster_id),
                'unlinked_entries':len(single),
                'review_bridges':sum(d[3]=='review_bridge' for d in dispositions),
                'vetoed_links':sum(d[3]=='review_veto' for d in dispositions)}
    finally:
        full.close();registry.close();literal.close();variants.close();review.close();target.close()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for a in ('full_index','registry','full_links','variant_links','review','output'):
        p.add_argument(a)
    a=p.parse_args()
    print(json.dumps(build(a.full_index,a.registry,a.full_links,a.variant_links,
                           a.review,a.output),indent=2))

if __name__=='__main__':main()
