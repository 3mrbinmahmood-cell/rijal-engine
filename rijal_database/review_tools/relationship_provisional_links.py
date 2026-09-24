"""Reversible links for exact-name cross-book pairs with 3+3 relationship clues."""
import argparse
import json
from pathlib import Path
import sqlite3

SCHEMA='''
CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE links(left_entry_id TEXT NOT NULL,right_entry_id TEXT NOT NULL,
 evidence_kind TEXT NOT NULL,common_teachers_json TEXT NOT NULL,
 common_students_json TEXT NOT NULL,
 PRIMARY KEY(left_entry_id,right_entry_id));
'''


def build(queue_path,identity_path,review_path,output_path):
    if Path(output_path).exists():raise ValueError('Use a new output path')
    queue=sqlite3.connect(f'file:{Path(queue_path).resolve()}?mode=ro',uri=True)
    identities=sqlite3.connect(f'file:{Path(identity_path).resolve()}?mode=ro',uri=True)
    review=sqlite3.connect(f'file:{Path(review_path).resolve()}?mode=ro',uri=True)
    out=sqlite3.connect(output_path)
    try:
        sha=queue.execute("SELECT value FROM metadata WHERE key='v1_1_sha256'").fetchone()
        if sha!=identities.execute("SELECT value FROM metadata WHERE key='v1_1_sha256'").fetchone() or \
           sha!=review.execute("SELECT value FROM methods WHERE key='extraction_sha256'").fetchone():
            raise ValueError('Identity sources refer to different extractions')
        veto={tuple(sorted((a,b))) for a,b,d in review.execute(
            'SELECT left_entry_id,right_entry_id,decision FROM pair_decisions '
            'WHERE decision IN ("different","uncertain")')}
        rows=[];skipped_reviewed=0;skipped_veto=0
        for a,b,ai,bi,ab,bb,ts,ss in queue.execute('''SELECT left_entry_id,
            right_entry_id,left_identity_id,right_identity_id,left_book_id,
            right_book_id,common_teachers_json,common_students_json
            FROM pairs WHERE priority='both_lists_3plus' '''):
            if ab==bb or len(json.loads(ts))<3 or len(json.loads(ss))<3:continue
            if tuple(sorted((a,b))) in veto:skipped_veto+=1;continue
            if ai.startswith('single-') and bi.startswith('single-'):
                rows.append((a,b,'teachers_3plus_students_3plus',ts,ss))
            else:skipped_reviewed+=1
        out.executescript(SCHEMA)
        with out:
            out.execute('INSERT INTO metadata VALUES (?,?)',('v1_1_sha256',sha[0]))
            out.executemany('INSERT INTO links VALUES (?,?,?,?,?)',rows)
        return {'links':len(rows),'excluded_existing_identity':skipped_reviewed,
                'excluded_review_veto':skipped_veto,'reviewed_people_created':0}
    finally:queue.close();identities.close();review.close();out.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('relationship_queue','identity','review','output'):p.add_argument(name)
    a=p.parse_args()
    print(json.dumps(build(a.relationship_queue,a.identity,a.review,a.output),indent=2))


if __name__=='__main__':main()
