"""Build reversible identity links from strongly corroborated exact-name pairs.

Provisional IDs are not reviewed person IDs. Every biography remains in place.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3

SCHEMA = """
CREATE TABLE name_buckets(
 id TEXT PRIMARY KEY,name_key TEXT NOT NULL UNIQUE,entries INTEGER NOT NULL,
 extracted_years_json TEXT NOT NULL,date_status TEXT NOT NULL);
CREATE TABLE name_bucket_members(
 entry_id TEXT PRIMARY KEY,bucket_id TEXT NOT NULL REFERENCES name_buckets(id));
CREATE INDEX name_bucket_members_bucket ON name_bucket_members(bucket_id);
CREATE TABLE provisional_groups(
 id TEXT PRIMARY KEY,name_key TEXT NOT NULL,entries INTEGER NOT NULL,
 evidence_links INTEGER NOT NULL,years_json TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('provisional','single_entry')));
CREATE TABLE provisional_members(
 entry_id TEXT PRIMARY KEY,group_id TEXT NOT NULL REFERENCES provisional_groups(id));
CREATE INDEX provisional_members_group ON provisional_members(group_id);
CREATE TABLE provisional_links(
 left_entry_id TEXT NOT NULL,right_entry_id TEXT NOT NULL,
 shared_long_statements INTEGER NOT NULL,evidence_kind TEXT NOT NULL,
 PRIMARY KEY(left_entry_id,right_entry_id));
"""

def build(inventory_path, candidates_path, output_path, relationship_path=None):
    if Path(output_path).exists():
        raise ValueError('Use a new output path to preserve earlier output')
    inventory=sqlite3.connect(f'file:{Path(inventory_path).resolve()}?mode=ro',uri=True)
    candidates=sqlite3.connect(f'file:{Path(candidates_path).resolve()}?mode=ro',uri=True)
    relationships=(sqlite3.connect(f'file:{Path(relationship_path).resolve()}?mode=ro',uri=True)
                   if relationship_path else None)
    target=sqlite3.connect(output_path)
    try:
        target.executescript(SCHEMA)
        names=dict(inventory.execute('SELECT entry_id,name_key FROM name_members'))
        dates=dict(inventory.execute('SELECT entry_id,death_year FROM date_evidence '
                                     'WHERE death_year IS NOT NULL'))
        parent={entry:entry for entry in names}
        name_rows=list(inventory.execute('''SELECT g.name_key,g.entries,
            COALESCE(d.years_json,'[]'),COALESCE(t.status,'untriaged')
            FROM name_groups g LEFT JOIN date_grouping d USING(name_key)
            LEFT JOIN group_triage t USING(name_key)'''))
        buckets={name:'name-'+hashlib.sha256(name.encode()).hexdigest()[:32]
                 for name,_,_,_ in name_rows}
        def root(entry):
            while parent[entry]!=entry:
                parent[entry]=parent[parent[entry]]
                entry=parent[entry]
            return entry
        def union(a,b):
            x,y=root(a),root(b)
            if x!=y:parent[max(x,y)]=min(x,y)
        links=[];literal_support={}
        for a,b,name,support,decision in candidates.execute('''SELECT left_entry_id,
            right_entry_id,name_key,shared_long_statements,review_decision
            FROM candidate_pairs'''):
            if names.get(a)!=name or names.get(b)!=name:
                raise ValueError('Candidate name group does not match inventory')
            literal_support[(a,b)]=(support,decision)
            if support<2:
                continue
            if decision in ('different','uncertain'):
                continue
            links.append((a,b,support,'two_long_statements'));union(a,b)
        if relationships:
            linked={(a,b) for a,b,_,_ in links}
            for a,b,name in relationships.execute('''SELECT left_entry_id,right_entry_id,
                name_key FROM pairs WHERE priority='both_lists_3plus' '''):
                if (a,b) in linked or name.startswith(('سيرة ','كتاب ','باب ')):
                    continue
                support,decision=literal_support.get((a,b),(0,None))
                if support<1 or decision in ('different','uncertain'):
                    continue
                if names.get(a)!=name or names.get(b)!=name:
                    raise ValueError('Relationship candidate name group mismatch')
                links.append((a,b,support,'literal_and_both_relationships'))
                union(a,b)
        # A prior different-person decision must also veto transitive links.
        for a,b in inventory.execute("SELECT left_entry_id,right_entry_id FROM pair_decisions "
                                     "WHERE decision='different'"):
            if a in parent and b in parent and root(a)==root(b):
                raise ValueError('Provisional component conflicts with a reviewed different-person pair')
        components={}
        for entry,name in names.items():
            components.setdefault(root(entry),[]).append(entry)
        groups=[];members=[]
        for representative,entry_ids in components.items():
            entry_ids.sort()
            name=names[representative]
            gid='prov-'+hashlib.sha256((name+'\0'+entry_ids[0]).encode()).hexdigest()[:32]
            years=sorted({dates[e] for e in entry_ids if e in dates})
            component=set(entry_ids)
            link_count=sum(a in component and b in component for a,b,_,_ in links)
            status='provisional' if len(entry_ids)>1 else 'single_entry'
            groups.append((gid,name,len(entry_ids),link_count,json.dumps(years),status))
            members.extend((entry,gid) for entry in entry_ids)
        with target:
            target.executemany('INSERT INTO name_buckets VALUES (?,?,?,?,?)',
                [(buckets[name],name,count,years,status)
                 for name,count,years,status in name_rows])
            target.executemany('INSERT INTO name_bucket_members VALUES (?,?)',
                               [(entry,buckets[name]) for entry,name in names.items()])
            target.executemany('INSERT INTO provisional_groups VALUES (?,?,?,?,?,?)',groups)
            target.executemany('INSERT INTO provisional_members VALUES (?,?)',members)
            target.executemany('INSERT INTO provisional_links VALUES (?,?,?,?)',links)
        return {'source_entries':len(names),'name_buckets':len(name_rows),
                'name_buckets_are_not_people':True,'provisional_groups':len(groups),
                'multi_entry_groups':sum(g[2]>1 for g in groups),
                'entries_in_multi_entry_groups':sum(g[2] for g in groups if g[2]>1),
                'supported_links':len(links),
                'combined_relationship_links':sum(link[3]=='literal_and_both_relationships'
                                                   for link in links),
                'reviewed_person_ids_created':0}
    finally:
        inventory.close();candidates.close();target.close()
        if relationships:relationships.close()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('inventory');p.add_argument('candidates');p.add_argument('output')
    p.add_argument('--relationships',help='Optional ranked relationship candidate database')
    a=p.parse_args()
    print(json.dumps(build(a.inventory,a.candidates,a.output,a.relationships),indent=2))

if __name__=='__main__':main()
