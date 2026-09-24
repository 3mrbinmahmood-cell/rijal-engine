"""Find long literal overlap across the full extracted corpus's manageable name groups.

This is a ranked review queue. Same wording and same name do not by themselves
create a person identity; high-frequency short names require extra scrutiny.
"""
import argparse
from collections import defaultdict
import itertools
import json
from pathlib import Path
import sqlite3

SCHEMA="""
CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE pairs(
 left_entry_id TEXT NOT NULL,right_entry_id TEXT NOT NULL,
 name_key TEXT NOT NULL,name_words INTEGER NOT NULL,
 shared_statements INTEGER NOT NULL,years_json TEXT NOT NULL,
 priority TEXT NOT NULL,PRIMARY KEY(left_entry_id,right_entry_id));
CREATE INDEX pairs_priority ON pairs(priority,shared_statements);
CREATE TABLE evidence(
 left_entry_id TEXT NOT NULL,right_entry_id TEXT NOT NULL,
 statement_text_id INTEGER NOT NULL,exact_quote TEXT NOT NULL,
 PRIMARY KEY(left_entry_id,right_entry_id,statement_text_id));
"""

def build(full_index_path,extraction_path,base_path,output_path):
    if Path(output_path).exists():
        raise ValueError('Use a new output path to preserve earlier output')
    full=sqlite3.connect(f'file:{Path(full_index_path).resolve()}?mode=ro',uri=True)
    source=sqlite3.connect(f'file:{Path(extraction_path).resolve()}?mode=ro',uri=True)
    output=sqlite3.connect(output_path,uri=True)
    try:
        manifest=json.loads((Path(extraction_path).parent/'extraction_data'/'PAYLOAD.json').read_text())
        base_manifest=json.loads((Path(base_path).parent/'data'/'PAYLOAD.json').read_text())
        bound=full.execute("SELECT value FROM release_meta WHERE key='v1_1_sha256'").fetchone()
        if bound!=(manifest['database_sha256'],) or manifest['base_sha256']!=base_manifest['database_sha256']:
            raise ValueError('Full index and V1/V1.1 releases do not match')
        output.executescript(SCHEMA)
        source.execute('ATTACH DATABASE ? AS idx',
                       (f'file:{Path(full_index_path).resolve()}?mode=ro',))
        source.execute('ATTACH DATABASE ? AS base',
                       (f'file:{Path(base_path).resolve()}?mode=ro',))
        rows=source.execute('''SELECT g.name_key,s.text_id,e.entry_id,t.quote
            FROM idx.name_groups g JOIN idx.name_entries e ON e.name_group_id=g.id
            JOIN statements s ON s.biography_id=e.entry_id
            JOIN statement_texts t ON t.id=s.text_id
            WHERE g.entry_count BETWEEN 2 AND 8 AND g.distinct_books>=2
            AND g.biography_count>=2 AND e.classification='biography_candidate'
            AND length(t.quote)>=60
            ORDER BY g.name_key,s.text_id''')
        evidence=defaultdict(dict);current=None;members=set();wording=''
        def flush():
            if len(members)>1:
                for a,b in itertools.combinations(sorted(members),2):
                    evidence[(a,b)][current[1]]=wording
        for key,text_id,entry_id,quote in rows:
            if current is not None and current!=(key,text_id):
                flush();members=set()
            current=(key,text_id);members.add(entry_id);wording=quote
        if current is not None:flush()
        names=dict(full.execute('SELECT e.entry_id,g.name_key FROM name_entries e '
                                'JOIN name_groups g ON g.id=e.name_group_id'))
        dates=dict(source.execute('SELECT entry_id,death_year FROM base.chronology_records '
                                  'WHERE death_year IS NOT NULL'))
        pairs=[];quotes=[]
        for (a,b),shared in sorted(evidence.items()):
            name=names[a]
            if name!=names[b]:raise ValueError('Cross-name evidence pair')
            years=sorted({dates[e] for e in (a,b) if e in dates})
            words=len(name.split())
            priority=('strong_long_name' if len(shared)>=2 and words>=5 else
                      'strong_short_name_review' if len(shared)>=2 else
                      'one_literal_review')
            pairs.append((a,b,name,words,len(shared),json.dumps(years),priority))
            quotes.extend((a,b,text_id,quote) for text_id,quote in shared.items())
        with output:
            output.executemany('INSERT INTO metadata VALUES (?,?)',[
                ('v1_sha256',base_manifest['database_sha256']),
                ('v1_1_sha256',manifest['database_sha256']),
                ('selection','biography_candidate, name group 2-8 entries in >=2 books, long literal >=60 chars')])
            output.executemany('INSERT INTO pairs VALUES (?,?,?,?,?,?,?)',pairs)
            output.executemany('INSERT INTO evidence VALUES (?,?,?,?)',quotes)
        return {'pairs':len(pairs),'priority_counts':dict(output.execute(
            'SELECT priority,count(*) FROM pairs GROUP BY priority')),
            'entries_in_pairs':len({e for a,b in evidence for e in (a,b)}),
            'identity_merges':0}
    finally:
        full.close();source.close();output.close()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('full_index','extraction','v1','output'):p.add_argument(arg)
    a=p.parse_args()
    print(json.dumps(build(a.full_index,a.extraction,a.v1,a.output),indent=2))

if __name__=='__main__':main()
