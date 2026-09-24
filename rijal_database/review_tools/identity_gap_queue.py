"""Inventory unresolved repeated names across the entire extraction.

Name equality is a retrieval clue, not an identity assertion. Each candidate
retains its independent identity and source so homonyms can be distinguished.
"""
import argparse
import json
from pathlib import Path
import sqlite3


SCHEMA = '''
CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE gaps(name_bucket_id TEXT PRIMARY KEY,name_key TEXT NOT NULL,
 entry_count INTEGER NOT NULL,biography_count INTEGER NOT NULL,
 distinct_books INTEGER NOT NULL,current_identities INTEGER NOT NULL,
 reviewed_entries INTEGER NOT NULL,provisional_entries INTEGER NOT NULL,
 unresolved_entries INTEGER NOT NULL,priority TEXT NOT NULL);
CREATE INDEX gaps_priority ON gaps(priority,unresolved_entries DESC);
'''


def build(index_path,identity_path,output_path):
    if Path(output_path).exists():raise ValueError('Use a new output path')
    db=sqlite3.connect(output_path,uri=True)
    try:
        db.execute('ATTACH DATABASE ? AS idx',
                   (f'file:{Path(index_path).resolve()}?mode=ro',))
        db.execute('ATTACH DATABASE ? AS ids',
                   (f'file:{Path(identity_path).resolve()}?mode=ro',))
        sha=db.execute("SELECT value FROM idx.release_meta WHERE key='v1_1_sha256'").fetchone()
        if sha!=db.execute("SELECT value FROM ids.metadata WHERE key='v1_1_sha256'").fetchone():
            raise ValueError('Identity and name index refer to different extractions')
        expected=db.execute('SELECT count(*) FROM idx.name_entries').fetchone()[0]
        actual=db.execute('SELECT count(*) FROM ids.entry_identity').fetchone()[0]
        if expected!=actual:raise ValueError('Identity lookup has incomplete coverage')
        missing=db.execute('''SELECT 1 FROM idx.name_entries n
            LEFT JOIN ids.entry_identity e ON e.entry_id=n.entry_id
            WHERE e.entry_id IS NULL LIMIT 1''').fetchone()
        if missing:raise ValueError('Identity lookup has a missing source entry')
        db.executescript(SCHEMA)
        db.execute('INSERT INTO metadata VALUES (?,?)',('v1_1_sha256',sha[0]))
        with db:
            db.execute('''INSERT INTO gaps
                SELECT g.id,g.name_key,g.entry_count,g.biography_count,g.distinct_books,
                  count(DISTINCT e.identity_id),
                  sum(e.identity_kind IN ('reviewed_person','needs_review')),
                  sum(e.identity_kind='provisional_cluster'),
                  sum(e.identity_kind='unlinked_entry'),
                  CASE WHEN g.name_key GLOB 'اخبرنا *' OR
                    g.name_key GLOB 'حدثنا *' OR g.name_key GLOB 'قال *' OR
                    g.name_key GLOB 'سمعت *' OR g.name_key GLOB 'عن *'
                    THEN 'suspected_heading_noise'
                    WHEN g.distinct_books>=2 AND g.biography_count>=2
                    AND length(g.name_key)-length(replace(g.name_key,' ',''))>=4
                    THEN 'cross_book_long_name'
                    WHEN g.distinct_books>=2 AND g.biography_count>=2
                    THEN 'cross_book_short_name'
                    ELSE 'same_book_or_index' END
                FROM idx.name_groups g JOIN ids.entry_identity e
                  ON e.name_bucket_id=g.id
                WHERE g.entry_count>=2 AND g.biography_count>=2
                GROUP BY g.id
                HAVING count(DISTINCT e.identity_id)>=2''')
        counts=dict(db.execute('SELECT priority,count(*) FROM gaps GROUP BY priority'))
        return {'source_entries':actual,'unresolved_name_buckets':sum(counts.values()),
                'priority_counts':counts,
                'entries_in_gaps':db.execute('SELECT sum(entry_count) FROM gaps').fetchone()[0] or 0,
                'identity_merges':0}
    finally:db.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('full_index','identity_view','output'):p.add_argument(name)
    a=p.parse_args()
    print(json.dumps(build(a.full_index,a.identity_view,a.output),indent=2))


if __name__=='__main__':main()
