"""Find conservative spelling variants without changing original Arabic names.

The signature handles kunya case forms and a small set of letter variants.
Variant buckets are candidate families, never unique-person identities.
"""
from collections import defaultdict
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import re
import sqlite3
from .relationship_candidates import relationships

SCHEMA="""
CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE variant_buckets(id TEXT PRIMARY KEY,signature TEXT NOT NULL UNIQUE,
 distinct_name_keys INTEGER NOT NULL,entries INTEGER NOT NULL);
CREATE TABLE variant_names(name_key TEXT PRIMARY KEY,bucket_id TEXT NOT NULL,
 entries INTEGER NOT NULL);
CREATE TABLE variant_entries(entry_id TEXT PRIMARY KEY,bucket_id TEXT NOT NULL,
 name_key TEXT NOT NULL);
CREATE INDEX variant_entries_bucket ON variant_entries(bucket_id);
CREATE TABLE candidate_pairs(left_entry_id TEXT NOT NULL,right_entry_id TEXT NOT NULL,
 variant_bucket_id TEXT NOT NULL,shared_long_statements INTEGER NOT NULL,
 PRIMARY KEY(left_entry_id,right_entry_id));
CREATE TABLE evidence(left_entry_id TEXT NOT NULL,right_entry_id TEXT NOT NULL,
 text_id INTEGER NOT NULL,exact_quote TEXT NOT NULL,
 PRIMARY KEY(left_entry_id,right_entry_id,text_id));
CREATE TABLE relationship_pairs(left_entry_id TEXT NOT NULL,right_entry_id TEXT NOT NULL,
 variant_bucket_id TEXT NOT NULL,common_teachers_json TEXT NOT NULL,
 common_students_json TEXT NOT NULL,priority TEXT NOT NULL,
 PRIMARY KEY(left_entry_id,right_entry_id));
"""

def signature(value):
    value=value.translate(str.maketrans({'أ':'ا','إ':'ا','آ':'ا','ؤ':'و','ئ':'ي','ة':'ه'}))
    value=re.sub(r'\b(?:ابي|ابا|ابو)\b','ابو',value)
    value=re.sub(r'\bابن\b','بن',value)
    value=re.sub(r'عبد\s+(الله|الرحمن|العزيز|الملك|الوهاب|الكريم)',r'عبد\1',value)
    return ' '.join(value.split())

def build(full_index_path,extraction_path,base_path,output_path):
    if Path(output_path).exists():raise ValueError('Use a new output path')
    full=sqlite3.connect(f'file:{Path(full_index_path).resolve()}?mode=ro',uri=True)
    source=sqlite3.connect(f'file:{Path(extraction_path).resolve()}?mode=ro',uri=True)
    output=sqlite3.connect(output_path,uri=True)
    try:
        manifest=json.loads((Path(extraction_path).parent/'extraction_data'/'PAYLOAD.json').read_text())
        base_manifest=json.loads((Path(base_path).parent/'data'/'PAYLOAD.json').read_text())
        bound=full.execute("SELECT value FROM release_meta WHERE key='v1_1_sha256'").fetchone()
        if bound!=(manifest['database_sha256'],) or manifest['base_sha256']!=base_manifest['database_sha256']:
            raise ValueError('Release mismatch')
        output.executescript(SCHEMA)
        families=defaultdict(list)
        for key,n in full.execute('SELECT name_key,entry_count FROM name_groups'):
            families[signature(key)].append((key,n))
        chosen={sig:items for sig,items in families.items() if len(items)>1}
        bucket_ids={sig:'variant-'+hashlib.sha256(sig.encode()).hexdigest()[:32]
                    for sig in chosen}
        names={key:bucket_ids[sig] for sig,items in chosen.items() for key,_ in items}
        with output:
            output.execute('INSERT INTO metadata VALUES (?,?)',
                           ('v1_1_sha256',manifest['database_sha256']))
            output.executemany('INSERT INTO variant_buckets VALUES (?,?,?,?)',
                [(bucket_ids[sig],sig,len(items),sum(n for _,n in items))
                 for sig,items in chosen.items()])
            output.executemany('INSERT INTO variant_names VALUES (?,?,?)',
                [(key,bucket_ids[sig],n) for sig,items in chosen.items()
                 for key,n in items])
            rows=[]
            for entry,key in full.execute('''SELECT e.entry_id,g.name_key FROM name_entries e
                JOIN name_groups g ON g.id=e.name_group_id'''):
                if key in names:rows.append((entry,names[key],key))
            output.executemany('INSERT INTO variant_entries VALUES (?,?,?)',rows)
        source.execute('ATTACH DATABASE ? AS variants',
                       (f'file:{Path(output_path).resolve()}?mode=ro',))
        records=source.execute('''SELECT v.bucket_id,s.text_id,v.entry_id,v.name_key,t.quote
            FROM variants.variant_entries v JOIN statements s ON s.biography_id=v.entry_id
            JOIN statement_texts t ON t.id=s.text_id WHERE length(t.quote)>=60
            ORDER BY v.bucket_id,s.text_id''')
        evidence=defaultdict(dict);current=None;members={};wording=''
        def flush():
            if len(members)>1:
                for a,b in itertools.combinations(sorted(members),2):
                    if members[a]!=members[b]:evidence[(a,b)][current[1]]=wording
        for bucket,text_id,entry,key,quote in records:
            if current is not None and current!=(bucket,text_id):
                flush();members={}
            current=(bucket,text_id);members[entry]=key;wording=quote
        if current is not None:flush()
        entry_buckets={entry:bucket for entry,bucket,_ in rows}
        with output:
            output.executemany('INSERT INTO candidate_pairs VALUES (?,?,?,?)',
                [(a,b,entry_buckets[a],len(items)) for (a,b),items in evidence.items()])
            output.executemany('INSERT INTO evidence VALUES (?,?,?,?)',
                [(a,b,tid,quote) for (a,b),items in evidence.items()
                 for tid,quote in items.items()])
        source.execute('ATTACH DATABASE ? AS base',
                       (f'file:{Path(base_path).resolve()}?mode=ro',))
        relation_groups=defaultdict(list)
        for bucket,entry,key,text in source.execute('''SELECT v.bucket_id,v.entry_id,
            v.name_key,substr(t.text,seg.start_offset+1,
            min(seg.end_offset-seg.start_offset,5000))
            FROM variants.variant_entries v JOIN biography_segments seg
            ON seg.biography_id=v.entry_id AND seg.role='opening'
            JOIN base.pages p ON p.id=seg.page_id
            JOIN base.page_texts t ON t.id=p.text_id'''):
            relation_groups[bucket].append((entry,key,relationships(text)))
        relation_pairs=[]
        for bucket,entries in relation_groups.items():
            for (a,ka,fa),(b,kb,fb) in itertools.combinations(entries,2):
                if ka==kb:continue
                teachers=sorted(fa['teachers']&fb['teachers'])
                students=sorted(fa['students']&fb['students'])
                if not teachers and not students:continue
                priority=('both_lists_3plus' if teachers and students and
                          len(teachers)+len(students)>=3 else 'review_overlap')
                a,b=sorted((a,b))
                relation_pairs.append((a,b,bucket,json.dumps(teachers,ensure_ascii=False),
                                       json.dumps(students,ensure_ascii=False),priority))
        with output:
            output.executemany('INSERT OR IGNORE INTO relationship_pairs VALUES (?,?,?,?,?,?)',
                               relation_pairs)
        return {'variant_buckets':len(chosen),'name_keys':len(names),
                'entries':len(rows),'pairs_with_shared_wording':len(evidence),
                'pairs_with_two_or_more_quotes':sum(len(v)>=2 for v in evidence.values()),
                'relationship_overlap_pairs':len(relation_pairs),
                'strong_relationship_pairs':sum(p[5]=='both_lists_3plus'
                                                for p in relation_pairs),
                'identity_merges':0}
    finally:
        full.close();source.close();output.close()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('full_index','extraction','v1','output'):p.add_argument(arg)
    a=p.parse_args()
    print(json.dumps(build(a.full_index,a.extraction,a.v1,a.output),indent=2))

if __name__=='__main__':main()
