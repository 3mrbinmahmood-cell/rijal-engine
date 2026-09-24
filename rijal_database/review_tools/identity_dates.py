"""Attach every available death-year claim to the current identity view.

Conflicting years remain separate source claims. The decimal range is only a
display grouping, never a replacement for the individual dates.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import sqlite3

from .name_inventory import common_bucket

SCHEMA='''
CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE date_claims(id INTEGER PRIMARY KEY,identity_id TEXT NOT NULL,
 entry_id TEXT NOT NULL,kind TEXT NOT NULL,year INTEGER NOT NULL,
 evidence_type TEXT NOT NULL,exact_quote TEXT NOT NULL,page_id TEXT NOT NULL,
 start_offset INTEGER,end_offset INTEGER,reviewer TEXT,note TEXT);
CREATE INDEX claims_identity ON date_claims(identity_id,year);
CREATE INDEX claims_entry ON date_claims(entry_id);
CREATE TABLE identity_date_summary(identity_id TEXT PRIMARY KEY,
 years_json TEXT NOT NULL,claim_count INTEGER NOT NULL,
 entry_count INTEGER NOT NULL,bucket_unit INTEGER,bucket_start INTEGER,
 bucket_end INTEGER);
'''


def build(identity_path,inventory_path,output_path):
    if Path(output_path).exists():raise ValueError('Use a new output path')
    identity=sqlite3.connect(f'file:{Path(identity_path).resolve()}?mode=ro',uri=True)
    inventory=sqlite3.connect(f'file:{Path(inventory_path).resolve()}?mode=ro',uri=True)
    out=sqlite3.connect(output_path)
    try:
        sha=identity.execute("SELECT value FROM metadata WHERE key='v1_1_sha256'").fetchone()
        if sha!=inventory.execute(
            "SELECT value FROM methods WHERE key='extraction_sha256'").fetchone():
            raise ValueError('Identity and date evidence refer to different extractions')
        entries={row[0] for row in inventory.execute(
            'SELECT entry_id FROM date_evidence WHERE death_year IS NOT NULL')}
        entries.update(row[0] for row in inventory.execute(
            'SELECT entry_id FROM additional_date_claims'))
        identities={}
        for batch in (list(entries)[i:i+500] for i in range(0,len(entries),500)):
            marks=','.join('?' for _ in batch)
            identities.update(identity.execute(
                f'SELECT entry_id,identity_id FROM entry_identity WHERE entry_id IN ({marks})',
                batch))
        if len(identities)!=len(entries):raise ValueError('Date entry missing from identity view')
        claims=[]
        for entry,year,quote,page in inventory.execute('''SELECT entry_id,death_year,
            evidence_quote,evidence_page_id FROM date_evidence
            WHERE death_year IS NOT NULL'''):
            claims.append((identities[entry],entry,'death',year,'automatic',
                           quote or '',page,None,None,None,None))
        for entry,year,page,start,end,quote,reviewer,note in inventory.execute(
            '''SELECT entry_id,year,page_id,start_offset,end_offset,exact_quote,
               reviewer,note FROM additional_date_claims'''):
            claims.append((identities[entry],entry,'death',year,'reviewed_claim',
                           quote,page,start,end,reviewer,note))
        grouped=defaultdict(list)
        for row in claims:grouped[row[0]].append(row)
        summaries=[]
        for identity_id,rows in grouped.items():
            years=sorted({r[3] for r in rows})
            summaries.append((identity_id,json.dumps(years),len(rows),
                              len({r[1] for r in rows}),*common_bucket(years)))
        out.executescript(SCHEMA)
        with out:
            out.execute('INSERT INTO metadata VALUES (?,?)',('v1_1_sha256',sha[0]))
            out.executemany('''INSERT INTO date_claims(identity_id,entry_id,kind,year,
                evidence_type,exact_quote,page_id,start_offset,end_offset,reviewer,note)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)''',claims)
            out.executemany('INSERT INTO identity_date_summary VALUES (?,?,?,?,?,?,?)',
                            summaries)
        return {'claims':len(claims),'dated_entries':len(entries),
                'dated_identities':len(summaries),
                'identities_with_multiple_years':sum(len(json.loads(r[1]))>1
                                                    for r in summaries)}
    finally:identity.close();inventory.close();out.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('identity','inventory','output'):p.add_argument(arg)
    a=p.parse_args()
    print(json.dumps(build(a.identity,a.inventory,a.output),indent=2))


if __name__=='__main__':main()
