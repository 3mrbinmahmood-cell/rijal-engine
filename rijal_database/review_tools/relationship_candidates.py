"""Rank exact-name pairs by overlapping teacher and student names.

Heuristic extraction can include incidental names. This queue does not merge
people, and nonoverlap never means that two biographies describe different people.
"""
import argparse
from collections import defaultdict
import itertools
import json
from pathlib import Path
import re
import sqlite3

VOWELS=re.compile('[\u064b-\u065f\u0670ـ]')
MARK=re.compile(r'(?:روى|روي)\s+عنه\s*[:：]?|وعنه\s*[:：]?|'
                r'(?:روى|روي)\s+عن(?!ه)\s*[:：]?')
STOP=re.compile(r'[.؛\n]|(?:\s+قال\s)|(?:\s+حدثنا\s)')
BAD=('غيره','جماعة','اخرون','عدة','قال','حديث','كتاب','توفي','مات',
     'ثقة','يعني','نسخة','بلغني','باس','روى','روي','سمع','حدث','يروي')
SCHEMA="""
CREATE TABLE features(entry_id TEXT NOT NULL,kind TEXT NOT NULL,
 name TEXT NOT NULL,page_id TEXT NOT NULL,
 PRIMARY KEY(entry_id,kind,name,page_id));
CREATE TABLE pairs(left_entry_id TEXT NOT NULL,right_entry_id TEXT NOT NULL,
 name_key TEXT NOT NULL,common_teachers_json TEXT NOT NULL,
 common_students_json TEXT NOT NULL,priority TEXT NOT NULL,
 PRIMARY KEY(left_entry_id,right_entry_id));
CREATE INDEX pairs_priority ON pairs(priority);
"""

def normalize(s):
    s=VOWELS.sub('',s).translate(str.maketrans({'أ':'ا','إ':'ا','آ':'ا','ى':'ي'}))
    return ' '.join(re.sub(r'[^\u0621-\u064a ]',' ',s).split())

def relationships(text):
    # Keep punctuation for list boundaries; the normalization above is for names.
    text=VOWELS.sub('',text).translate(str.maketrans({'أ':'ا','إ':'ا','آ':'ا','ى':'ي'}))
    found={'teachers':set(),'students':set()}
    for match in MARK.finditer(text):
        kind='students' if 'عنه' in match.group() else 'teachers'
        tail=text[match.end():match.end()+360]
        stop=STOP.search(tail)
        if stop:tail=tail[:stop.start()]
        following=MARK.search(tail)
        if following:tail=tail[:following.start()]
        for raw in re.split(r'،|,|\s+و(?=[ا-ي]{3})',tail):
            name=normalize(raw)
            if name.startswith('و'):name=name[1:]
            if (2<=len(name.split())<=6 and len(name)>=8 and
                not any(word in name for word in BAD)):
                found[kind].add(name)
    return found

def build(inventory_path,extraction_path,base_path,output_path):
    if Path(output_path).exists():
        raise ValueError('Use a new output path to preserve earlier output')
    inventory=sqlite3.connect(f'file:{Path(inventory_path).resolve()}?mode=ro',uri=True)
    extraction=sqlite3.connect(f'file:{Path(extraction_path).resolve()}?mode=ro',uri=True)
    output=sqlite3.connect(output_path)
    try:
        manifest=json.loads((Path(extraction_path).parent/'extraction_data'/'PAYLOAD.json').read_text())
        base=json.loads((Path(base_path).parent/'data'/'PAYLOAD.json').read_text())
        bound=inventory.execute("SELECT value FROM methods WHERE key='extraction_sha256'").fetchone()
        if bound!=(manifest['database_sha256'],) or manifest['base_sha256']!=base['database_sha256']:
            raise ValueError('Source releases and review inventory do not match')
        output.executescript(SCHEMA)
        extraction.execute('ATTACH DATABASE ? AS review',
                           (f'file:{Path(inventory_path).resolve()}?mode=ro',))
        extraction.execute('ATTACH DATABASE ? AS base',
                           (f'file:{Path(base_path).resolve()}?mode=ro',))
        groups=defaultdict(list);feature_rows=[]
        for entry,key,page,text in extraction.execute('''SELECT m.entry_id,m.name_key,
            seg.page_id,substr(t.text,seg.start_offset+1,
            min(seg.end_offset-seg.start_offset,5000))
            FROM review.name_members m JOIN biography_segments seg
            ON seg.biography_id=m.entry_id AND seg.role='opening'
            JOIN base.pages p ON p.id=seg.page_id
            JOIN base.page_texts t ON t.id=p.text_id'''):
            features=relationships(text)
            groups[key].append((entry,features))
            feature_rows.extend((entry,kind,name,page) for kind,names in features.items()
                                for name in names)
        pair_rows=[]
        for key,entries in groups.items():
            for (a,left),(b,right) in itertools.combinations(entries,2):
                teachers=sorted(left['teachers']&right['teachers'])
                students=sorted(left['students']&right['students'])
                if not teachers and not students:continue
                priority=('both_lists_3plus' if teachers and students and
                          len(teachers)+len(students)>=3 else
                          'one_list_3plus' if max(len(teachers),len(students))>=3 else
                          'weak_overlap')
                a,b=sorted((a,b))
                pair_rows.append((a,b,key,json.dumps(teachers,ensure_ascii=False),
                                  json.dumps(students,ensure_ascii=False),priority))
        with output:
            output.executemany('INSERT OR IGNORE INTO features VALUES (?,?,?,?)',feature_rows)
            output.executemany('INSERT INTO pairs VALUES (?,?,?,?,?,?)',pair_rows)
        return {'source_entries':sum(map(len,groups.values())),'pairs':len(pair_rows),
                'both_lists_3plus':sum(p[5]=='both_lists_3plus' for p in pair_rows),
                'one_list_3plus':sum(p[5]=='one_list_3plus' for p in pair_rows),
                'heuristic_identity_merges':0}
    finally:
        inventory.close();extraction.close();output.close()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('inventory');p.add_argument('extraction');p.add_argument('v1');p.add_argument('output')
    a=p.parse_args()
    print(json.dumps(build(a.inventory,a.extraction,a.v1,a.output),indent=2))

if __name__=='__main__':main()
