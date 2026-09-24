"""Rank exact-name identity candidates using shared source wording.

This is a reversible review queue. It never creates a reviewed person or
changes a source biography. Missing overlap is not evidence of different people.
"""
import argparse
from collections import defaultdict
import itertools
import json
from pathlib import Path
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS candidate_pairs(
 left_entry_id TEXT NOT NULL,right_entry_id TEXT NOT NULL,
 name_key TEXT NOT NULL,shared_long_statements INTEGER NOT NULL,
 extracted_years_json TEXT NOT NULL,date_relation TEXT NOT NULL,
 review_decision TEXT,priority TEXT NOT NULL,
 PRIMARY KEY(left_entry_id,right_entry_id));
CREATE INDEX IF NOT EXISTS candidate_priority ON candidate_pairs(priority,shared_long_statements);
CREATE TABLE IF NOT EXISTS candidate_evidence(
 left_entry_id TEXT NOT NULL,right_entry_id TEXT NOT NULL,
 statement_text_id INTEGER NOT NULL,exact_quote TEXT NOT NULL,
 PRIMARY KEY(left_entry_id,right_entry_id,statement_text_id));
"""

def build(inventory_path, extraction_path, output_path):
    if Path(output_path).exists():
        raise ValueError('Use a new output path so earlier review output is preserved')
    inventory=sqlite3.connect(f'file:{Path(inventory_path).resolve()}?mode=ro',uri=True)
    extraction=sqlite3.connect(f'file:{Path(extraction_path).resolve()}?mode=ro',uri=True)
    output=sqlite3.connect(output_path)
    try:
        source_sha=json.loads((Path(extraction_path).parent/'extraction_data'/'PAYLOAD.json').read_text())['database_sha256']
        bound=inventory.execute("SELECT value FROM methods WHERE key='extraction_sha256'").fetchone()
        if bound!=(source_sha,):
            raise ValueError('Inventory and extraction releases differ')
        output.executescript(SCHEMA)
        extraction.execute('ATTACH DATABASE ? AS review',
                           (f'file:{Path(inventory_path).resolve()}?mode=ro',))
        rows=extraction.execute('''SELECT m.name_key,s.text_id,m.entry_id,t.quote
            FROM review.name_members m JOIN statements s ON s.biography_id=m.entry_id
            JOIN statement_texts t ON t.id=s.text_id
            WHERE length(t.quote)>=60 ORDER BY m.name_key,s.text_id''')
        evidence=defaultdict(dict)
        current=None;ids=set();quote=''
        def flush():
            if len(ids)>1:
                for a,b in itertools.combinations(sorted(ids),2):
                    evidence[(a,b)][current[1]]=quote
        for key,text_id,entry_id,wording in rows:
            if current is not None and current!=(key,text_id):
                flush();ids=set()
            current=(key,text_id);quote=wording;ids.add(entry_id)
        if current is not None:flush()
        members={row[0]:row[1] for row in inventory.execute(
            'SELECT entry_id,name_key FROM name_members')}
        dates={row[0]:row[1] for row in inventory.execute(
            'SELECT entry_id,death_year FROM date_evidence WHERE death_year IS NOT NULL')}
        decisions={(row[0],row[1]):row[2] for row in inventory.execute(
            'SELECT left_entry_id,right_entry_id,decision FROM pair_decisions')}
        pairs=[];quotes=[]
        for (a,b),shared in sorted(evidence.items()):
            years=sorted({dates[e] for e in (a,b) if e in dates})
            relation=('conflicting' if len(years)>1 else
                      'matching' if len(years)==1 and a in dates and b in dates else
                      'incomplete')
            # Shared text is a ranking clue, never an automatic merge rule.
            priority='strong_literal' if len(shared)>=2 else 'one_literal'
            pairs.append((a,b,members[a],len(shared),json.dumps(years),relation,
                          decisions.get((a,b)),priority))
            quotes.extend((a,b,text_id,wording) for text_id,wording in shared.items())
        with output:
            output.executemany('INSERT INTO candidate_pairs VALUES (?,?,?,?,?,?,?,?)',pairs)
            output.executemany('INSERT INTO candidate_evidence VALUES (?,?,?,?)',quotes)
        return {'pairs':len(pairs),'strong_literal':sum(p[3]>=2 for p in pairs),
                'one_literal':sum(p[3]==1 for p in pairs),
                'entries':len({e for a,b in evidence for e in (a,b)}),
                'previously_reviewed_pairs':sum(p[6] is not None for p in pairs),
                'automatic_identity_merges':0}
    finally:
        inventory.close();extraction.close();output.close()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inventory');parser.add_argument('extraction');parser.add_argument('output')
    args=parser.parse_args()
    print(json.dumps(build(args.inventory,args.extraction,args.output),indent=2))

if __name__=='__main__':main()
