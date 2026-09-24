"""Compare teacher/student clues for unresolved repeated full names.

The parser is heuristic. Overlap ranks review; absence of overlap is not
evidence that two entries are different people. No identity links are made.
"""
import argparse
import itertools
import json
from pathlib import Path
import sqlite3

from .relationship_candidates import relationships

SCHEMA='''
CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE pairs(left_entry_id TEXT NOT NULL,right_entry_id TEXT NOT NULL,
 name_bucket_id TEXT NOT NULL,left_identity_id TEXT NOT NULL,
 right_identity_id TEXT NOT NULL,left_book_id TEXT NOT NULL,
 right_book_id TEXT NOT NULL,common_teachers_json TEXT NOT NULL,
 common_students_json TEXT NOT NULL,priority TEXT NOT NULL,
 PRIMARY KEY(left_entry_id,right_entry_id));
CREATE INDEX pairs_priority ON pairs(priority,name_bucket_id);
'''


def ranked_pairs(entries,bucket):
    result=[]
    for (a,ai,ab,af),(b,bi,bb,bf) in itertools.combinations(entries,2):
        if ai==bi:continue
        teachers=sorted(af['teachers'] & bf['teachers'])
        students=sorted(af['students'] & bf['students'])
        if not teachers and not students:continue
        priority=('both_lists_3plus' if teachers and students and
                  len(teachers)+len(students)>=3 else
                  'one_list_3plus' if max(len(teachers),len(students))>=3
                  else 'weak_overlap')
        if a>b:a,b=b,a;ai,bi=bi,ai;ab,bb=bb,ab
        result.append((a,b,bucket,ai,bi,ab,bb,
                       json.dumps(teachers,ensure_ascii=False),
                       json.dumps(students,ensure_ascii=False),priority))
    return result


def build(gaps_path,identity_path,extraction_path,base_path,output_path,max_group=20):
    if Path(output_path).exists():raise ValueError('Use a new output path')
    extract=json.loads((Path(extraction_path).parent/'extraction_data'/'PAYLOAD.json').read_text())
    base=json.loads((Path(base_path).parent/'data'/'PAYLOAD.json').read_text())
    source=sqlite3.connect(f'file:{Path(extraction_path).resolve()}?mode=ro',uri=True)
    out=sqlite3.connect(output_path)
    try:
        if extract['base_sha256']!=base['database_sha256']:raise ValueError('V1 source mismatch')
        for path,table,key in ((gaps_path,'metadata','v1_1_sha256'),
                               (identity_path,'metadata','v1_1_sha256')):
            with sqlite3.connect(f'file:{Path(path).resolve()}?mode=ro',uri=True) as db:
                bound=db.execute(f'SELECT value FROM {table} WHERE key=?',
                                 (key,)).fetchone()
                if bound!=(extract['database_sha256'],):
                    raise ValueError('Review inputs have different extraction releases')
        source.execute('ATTACH DATABASE ? AS gaps',
                       (f'file:{Path(gaps_path).resolve()}?mode=ro',))
        source.execute('ATTACH DATABASE ? AS ids',
                       (f'file:{Path(identity_path).resolve()}?mode=ro',))
        source.execute('ATTACH DATABASE ? AS base',
                       (f'file:{Path(base_path).resolve()}?mode=ro',))
        out.executescript(SCHEMA)
        out.execute('INSERT INTO metadata VALUES (?,?)',
                    ('v1_1_sha256',extract['database_sha256']))
        records=source.execute('''SELECT g.name_bucket_id,e.entry_id,e.identity_id,
            e.book_id,substr(t.text,seg.start_offset+1,
            min(seg.end_offset-seg.start_offset,5000))
            FROM gaps.gaps g JOIN ids.entry_identity e
              ON e.name_bucket_id=g.name_bucket_id
            JOIN biography_segments seg ON seg.biography_id=e.entry_id
              AND seg.role='opening'
            JOIN base.pages p ON p.id=seg.page_id
            JOIN base.page_texts t ON t.id=p.text_id
            WHERE g.priority='cross_book_long_name' AND g.entry_count<=?
              AND e.classification='biography_candidate'
            ORDER BY g.name_bucket_id,e.entry_id''',(max_group,))
        current=None;entries=[];groups=0;examined=0;counts={}
        def flush():
            nonlocal groups
            if len(entries)<2:return
            groups+=1
            rows=ranked_pairs(entries,current)
            out.executemany('INSERT OR IGNORE INTO pairs VALUES (?,?,?,?,?,?,?,?,?,?)',rows)
            for row in rows:counts[row[-1]]=counts.get(row[-1],0)+1
        with out:
            for bucket,entry,identity,book,text in records:
                if current is not None and bucket!=current:
                    flush();entries=[]
                current=bucket;examined+=1
                entries.append((entry,identity,book,relationships(text)))
            if current is not None:flush()
        return {'examined_biography_entries':examined,'examined_name_groups':groups,
                'overlap_pairs':out.execute('SELECT count(*) FROM pairs').fetchone()[0],
                'priority_counts':counts,'identity_merges':0}
    finally:source.close();out.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('gaps','identity','extraction','v1','output'):p.add_argument(name)
    p.add_argument('--max-group',type=int,default=20)
    a=p.parse_args()
    print(json.dumps(build(a.gaps,a.identity,a.extraction,a.v1,a.output,
                           a.max_group),indent=2))


if __name__=='__main__':main()
