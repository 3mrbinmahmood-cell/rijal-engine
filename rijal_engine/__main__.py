import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path, PurePosixPath
import re
import sqlite3
import unicodedata
import zipfile

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS blobs(
 sha256 TEXT PRIMARY KEY, byte_length INTEGER NOT NULL,
 encoding TEXT NOT NULL, exact_text TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS occurrences(
 id INTEGER PRIMARY KEY, source_uri TEXT NOT NULL,
 sha256 TEXT NOT NULL REFERENCES blobs(sha256),
 imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(source_uri,sha256));
CREATE TABLE IF NOT EXISTS segments(
 id INTEGER PRIMARY KEY, sha256 TEXT NOT NULL UNIQUE REFERENCES blobs(sha256),
 page_label TEXT, exact_text TEXT NOT NULL, search_text TEXT NOT NULL);
CREATE VIRTUAL TABLE IF NOT EXISTS segment_fts USING fts5(
 search_text, content='segments', content_rowid='id', tokenize='unicode61');
CREATE TRIGGER IF NOT EXISTS segments_ai AFTER INSERT ON segments BEGIN
 INSERT INTO segment_fts(rowid,search_text) VALUES(new.id,new.search_text);
END;
CREATE TABLE IF NOT EXISTS entry_candidates(
 id INTEGER PRIMARY KEY, segment_id INTEGER NOT NULL REFERENCES segments(id),
 start_offset INTEGER NOT NULL, end_offset INTEGER NOT NULL,
 heading_exact TEXT NOT NULL, extraction_method TEXT NOT NULL,
 CHECK(start_offset>=0 AND end_offset>start_offset));
CREATE TABLE IF NOT EXISTS relationship_mentions(
 id INTEGER PRIMARY KEY,
 entry_candidate_id INTEGER NOT NULL REFERENCES entry_candidates(id),
 segment_id INTEGER NOT NULL REFERENCES segments(id),
 role TEXT NOT NULL CHECK(role IN ('teacher','student','other')),
 name_exact TEXT NOT NULL, passage_exact TEXT NOT NULL,
 start_offset INTEGER NOT NULL, extraction_status TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS identity_reviews(
 id INTEGER PRIMARY KEY,
 left_entry_id INTEGER NOT NULL REFERENCES entry_candidates(id),
 right_entry_id INTEGER NOT NULL REFERENCES entry_candidates(id),
 decision TEXT NOT NULL CHECK(decision IN ('proposed','same','different','uncertain')),
 rationale TEXT NOT NULL, reviewer TEXT, reviewed_at TEXT,
 CHECK(left_entry_id<>right_entry_id));
"""

class VisibleText(HTMLParser):
    blocks = {'p','div','br','li','tr','td','h1','h2','h3','h4'}
    ignored = {'script','style','head','template','svg'}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skip = [], 0
    def handle_starttag(self, tag, attrs):
        if tag in self.ignored:
            self.skip += 1
        if not self.skip and tag in self.blocks:
            self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag in self.ignored and self.skip:
            self.skip -= 1
        if not self.skip and tag in self.blocks:
            self.parts.append('\n')
    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)

def extract(raw):
    head = raw[:4096].decode('ascii', errors='ignore')
    match = re.search(r"charset\s*=\s*['\"]?([\w-]+)", head, re.I)
    names = ([match.group(1)] if match else []) + ['utf-8-sig','windows-1256']
    for encoding in names:
        try:
            source = raw.decode(encoding)
            break
        except (UnicodeError, LookupError):
            pass
    else:
        encoding, source = 'utf-8-replace', raw.decode('utf-8', errors='replace')
    parser = VisibleText()
    parser.feed(source)
    parser.close()
    return ''.join(parser.parts), encoding

def normalize(value):
    value = unicodedata.normalize('NFKC', value)
    value = re.sub('[\u064b-\u065f\u0670\u0640]', '', value)
    return re.sub('[أإآٱ]', 'ا', value).replace('ى','ي')

def connect(path):
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    return db

def inputs(path):
    path = Path(path)
    if path.is_dir():
        for file in sorted(path.rglob('*')):
            if file.is_file() and file.suffix.lower() in ('.htm','.html'):
                yield file.resolve().as_uri(), file.read_bytes()
    elif zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            for item in archive.infolist():
                if item.is_dir() or not item.filename.lower().endswith(('.htm','.html')):
                    continue
                member = PurePosixPath(item.filename)
                if member.is_absolute() or '..' in member.parts or '\\' in item.filename:
                    raise ValueError('Unsafe ZIP member: ' + item.filename)
                yield path.resolve().as_uri() + '!/' + item.filename, archive.read(item)
    elif path.suffix.lower() in ('.htm','.html'):
        yield path.resolve().as_uri(), path.read_bytes()
    else:
        raise ValueError('Expected HTML file, folder, or ZIP')

def ingest(db, path):
    added = 0
    for uri, raw in inputs(path):
        digest = hashlib.sha256(raw).hexdigest()
        exact, encoding = extract(raw)
        with db:
            db.execute('INSERT OR IGNORE INTO blobs VALUES (?,?,?,?)',
                       (digest,len(raw),encoding,exact))
            added += db.execute(
                'INSERT OR IGNORE INTO occurrences(source_uri,sha256) VALUES (?,?)',
                (uri,digest)).rowcount
            db.execute('INSERT OR IGNORE INTO segments(sha256,page_label,exact_text,search_text) VALUES (?,?,?,?)',
                       (digest,None,exact,normalize(exact)))
    return added

def audit(db):
    tables = ('occurrences','blobs','segments','entry_candidates',
              'relationship_mentions','identity_reviews')
    return {table: db.execute('SELECT count(*) FROM '+table).fetchone()[0]
            for table in tables}

def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest='command',required=True)
    for command in ('init','import','search','audit'):
        p = commands.add_parser(command)
        p.add_argument('database')
        if command == 'import':
            p.add_argument('source')
        if command == 'search':
            p.add_argument('query')
    args = parser.parse_args()
    with connect(args.database) as db:
        if args.command == 'import':
            print(json.dumps({'added':ingest(db,args.source),**audit(db)},ensure_ascii=False))
        elif args.command == 'search':
            words = re.findall(r'\w+',normalize(args.query))
            if not words:
                parser.error('query must contain a word')
            expression = ' AND '.join('"'+word+'"' for word in words)
            rows = db.execute("""SELECT o.source_uri,s.page_label,
              snippet(segment_fts,0,'[',']','…',12)
              FROM segment_fts JOIN segments s ON s.id=segment_fts.rowid
              JOIN occurrences o ON o.sha256=s.sha256
              WHERE segment_fts MATCH ? LIMIT 30""",(expression,)).fetchall()
            print(json.dumps(rows,ensure_ascii=False,indent=2))
        else:
            print(json.dumps(audit(db),indent=2))

if __name__ == '__main__':
    main()
