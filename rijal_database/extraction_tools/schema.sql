PRAGMA user_version=1;
CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
CREATE TABLE biographies(
 id TEXT PRIMARY KEY,name_label TEXT NOT NULL,name_key TEXT NOT NULL,
 opening_page_id TEXT NOT NULL,source_id TEXT NOT NULL,book_id TEXT NOT NULL,
 heading_start INTEGER NOT NULL,heading_end INTEGER NOT NULL,
 classification TEXT NOT NULL,boundary_status TEXT NOT NULL,
 segment_count INTEGER NOT NULL DEFAULT 0,char_count INTEGER NOT NULL DEFAULT 0,
 statement_count INTEGER NOT NULL DEFAULT 0);
CREATE INDEX bio_source ON biographies(source_id);
CREATE INDEX bio_book ON biographies(book_id);
CREATE VIRTUAL TABLE biography_fts USING fts5(name_key,content='',tokenize='unicode61');
CREATE TABLE biography_segments(
 id INTEGER PRIMARY KEY,biography_id TEXT NOT NULL REFERENCES biographies(id),
 page_id TEXT NOT NULL,start_offset INTEGER NOT NULL,end_offset INTEGER NOT NULL,
 role TEXT NOT NULL,CHECK(start_offset>=0 AND end_offset>=start_offset),
 UNIQUE(biography_id,page_id,start_offset));
CREATE INDEX segment_bio ON biography_segments(biography_id,id);
CREATE INDEX segment_page ON biography_segments(page_id,start_offset);
CREATE TABLE statement_texts(id INTEGER PRIMARY KEY,sha256 TEXT UNIQUE NOT NULL,quote TEXT NOT NULL);
CREATE VIRTUAL TABLE statement_fts USING fts5(search_text,content='',tokenize='unicode61');
CREATE TABLE statements(
 id TEXT PRIMARY KEY,text_id INTEGER NOT NULL REFERENCES statement_texts(id),
 biography_id TEXT REFERENCES biographies(id),page_id TEXT NOT NULL,source_id TEXT NOT NULL,book_id TEXT NOT NULL,
 start_offset INTEGER NOT NULL,end_offset INTEGER NOT NULL,
 origin TEXT NOT NULL,subject_status TEXT NOT NULL,quote_scope TEXT NOT NULL,
 attribution_text TEXT,attribution_start INTEGER,attribution_end INTEGER,
 CHECK(start_offset>=0 AND end_offset>start_offset));
CREATE INDEX statement_text ON statements(text_id);
CREATE INDEX statement_bio ON statements(biography_id);
CREATE INDEX statement_page ON statements(page_id,start_offset);
CREATE INDEX statement_book ON statements(book_id);
CREATE INDEX statement_origin ON statements(origin);
CREATE TABLE statement_triggers(
 statement_id TEXT NOT NULL REFERENCES statements(id),kind TEXT NOT NULL,
 start_offset INTEGER NOT NULL,end_offset INTEGER NOT NULL,quote TEXT NOT NULL,
 PRIMARY KEY(statement_id,kind,start_offset)) WITHOUT ROWID;
CREATE INDEX trigger_kind ON statement_triggers(kind,statement_id);
