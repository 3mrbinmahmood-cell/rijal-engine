PRAGMA user_version=1;
CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS archives(
 id TEXT PRIMARY KEY, filename TEXT NOT NULL, byte_size INTEGER NOT NULL,
 expected_files INTEGER NOT NULL, imported_at TEXT NOT NULL, status TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS books(
 id TEXT PRIMARY KEY, archive_id TEXT NOT NULL REFERENCES archives(id), source_group TEXT NOT NULL,
 title TEXT NOT NULL, author TEXT, edition TEXT, publisher TEXT, category TEXT,
 metadata_json TEXT NOT NULL, UNIQUE(archive_id,source_group));
CREATE TABLE IF NOT EXISTS source_files(
 id TEXT PRIMARY KEY, archive_id TEXT NOT NULL REFERENCES archives(id), zip_index INTEGER NOT NULL,
 zip_path TEXT NOT NULL, book_id TEXT NOT NULL REFERENCES books(id), raw_sha256 TEXT NOT NULL,
 byte_size INTEGER NOT NULL, encoding TEXT NOT NULL, metadata_json TEXT NOT NULL,
 page_count INTEGER NOT NULL, marker_count INTEGER NOT NULL, status TEXT NOT NULL, error TEXT,
 UNIQUE(archive_id,zip_index));
CREATE INDEX IF NOT EXISTS source_book ON source_files(book_id);
CREATE INDEX IF NOT EXISTS source_hash ON source_files(raw_sha256);
CREATE TABLE IF NOT EXISTS page_texts(
 id INTEGER PRIMARY KEY, sha256 TEXT NOT NULL UNIQUE, text TEXT NOT NULL, char_count INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS pages(
 id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES source_files(id),
 text_id INTEGER NOT NULL REFERENCES page_texts(id), ordinal INTEGER NOT NULL,
 printed_label TEXT, part_label TEXT, header_text TEXT, anchor TEXT,
 raw_start INTEGER, raw_end INTEGER, UNIQUE(source_id,ordinal));
CREATE INDEX IF NOT EXISTS page_text_ref ON pages(text_id);
CREATE INDEX IF NOT EXISTS page_source_order ON pages(source_id,ordinal);
CREATE VIRTUAL TABLE IF NOT EXISTS page_fts USING fts5(search_text, content='', tokenize='unicode61');
CREATE TABLE IF NOT EXISTS spans(
 id INTEGER PRIMARY KEY, page_id TEXT NOT NULL REFERENCES pages(id), kind TEXT NOT NULL,
 start_offset INTEGER NOT NULL, end_offset INTEGER NOT NULL, anchor TEXT,
 CHECK(start_offset>=0 AND end_offset>=start_offset));
CREATE INDEX IF NOT EXISTS span_page ON spans(page_id);
CREATE TABLE IF NOT EXISTS entries(
 id TEXT PRIMARY KEY, page_id TEXT NOT NULL REFERENCES pages(id),
 start_offset INTEGER NOT NULL, end_offset INTEGER NOT NULL, title TEXT NOT NULL,
 search_title TEXT NOT NULL, kind TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'automatic_candidate',
 UNIQUE(page_id,start_offset), CHECK(start_offset>=0 AND end_offset>start_offset));
CREATE INDEX IF NOT EXISTS entry_page ON entries(page_id,start_offset);
CREATE INDEX IF NOT EXISTS entry_title ON entries(search_title);
CREATE VIRTUAL TABLE IF NOT EXISTS entry_fts USING fts5(search_title, content='', tokenize='unicode61');
CREATE TABLE IF NOT EXISTS mentions(
 id INTEGER PRIMARY KEY, page_id TEXT NOT NULL REFERENCES pages(id),
 entry_id TEXT REFERENCES entries(id), kind TEXT NOT NULL, trigger TEXT NOT NULL,
 start_offset INTEGER NOT NULL, end_offset INTEGER NOT NULL,
 in_footnote INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'unresolved_mention');
CREATE INDEX IF NOT EXISTS mention_page ON mentions(page_id,start_offset);
CREATE TABLE IF NOT EXISTS passages(
 id INTEGER PRIMARY KEY, sha256 TEXT NOT NULL UNIQUE, normalized_sha256 TEXT NOT NULL,
 text_id INTEGER NOT NULL REFERENCES page_texts(id), start_offset INTEGER NOT NULL,
 end_offset INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS passage_normalized ON passages(normalized_sha256);
CREATE TABLE IF NOT EXISTS passage_locations(
 passage_id INTEGER NOT NULL REFERENCES passages(id), text_id INTEGER NOT NULL REFERENCES page_texts(id),
 start_offset INTEGER NOT NULL, end_offset INTEGER NOT NULL,
 PRIMARY KEY(passage_id,text_id,start_offset)) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS passage_location_text ON passage_locations(text_id,start_offset);
CREATE TABLE IF NOT EXISTS persons(
 id TEXT PRIMARY KEY, preferred_name TEXT NOT NULL, status TEXT NOT NULL, review_note TEXT);
CREATE TABLE IF NOT EXISTS aliases(
 id INTEGER PRIMARY KEY, person_id TEXT NOT NULL REFERENCES persons(id), alias TEXT NOT NULL,
 evidence_page_id TEXT NOT NULL REFERENCES pages(id), start_offset INTEGER NOT NULL, end_offset INTEGER NOT NULL,
 status TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS assertions(
 id TEXT PRIMARY KEY, person_id TEXT REFERENCES persons(id), predicate TEXT NOT NULL,
 literal_value TEXT NOT NULL, attributed_scholar TEXT,
 evidence_page_id TEXT NOT NULL REFERENCES pages(id), start_offset INTEGER NOT NULL, end_offset INTEGER NOT NULL,
 status TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS identity_links(
 id INTEGER PRIMARY KEY, entry_id TEXT NOT NULL REFERENCES entries(id), person_id TEXT NOT NULL REFERENCES persons(id),
 status TEXT NOT NULL, evidence_json TEXT NOT NULL, review_note TEXT);
CREATE TABLE IF NOT EXISTS review_log(
 id INTEGER PRIMARY KEY, created_at TEXT NOT NULL, target_type TEXT NOT NULL, target_id TEXT NOT NULL,
 old_value_json TEXT, new_value_json TEXT, reason TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS chronology_records(
 entry_id TEXT PRIMARY KEY REFERENCES entries(id),name_label TEXT NOT NULL,name_key TEXT NOT NULL,
 death_year INTEGER,date_status TEXT NOT NULL,evidence_page_id TEXT NOT NULL REFERENCES pages(id),
 evidence_start INTEGER,evidence_end INTEGER,evidence_quote TEXT,evidence_kind TEXT,group_id TEXT);
CREATE TABLE IF NOT EXISTS chronology_groups(
 id TEXT PRIMARY KEY,name_label TEXT NOT NULL,name_key TEXT NOT NULL,death_year INTEGER NOT NULL,
 source_entries INTEGER NOT NULL,status TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS chronology_year ON chronology_groups(death_year);
CREATE INDEX IF NOT EXISTS chronology_record_name ON chronology_records(name_key,death_year);
CREATE INDEX IF NOT EXISTS chronology_record_group ON chronology_records(group_id);
CREATE VIEW IF NOT EXISTS citations AS
 SELECT p.id AS page_id,p.text_id,p.ordinal,p.printed_label,p.part_label,p.anchor,
 s.id AS source_id,s.zip_path,s.zip_index,s.raw_sha256,s.archive_id,
 b.id AS book_id,b.title,b.author,b.edition,b.publisher,b.category,a.filename AS archive_filename
 FROM pages p JOIN source_files s ON s.id=p.source_id JOIN books b ON b.id=s.book_id
 JOIN archives a ON a.id=s.archive_id;
CREATE VIEW IF NOT EXISTS duplicate_files AS
 SELECT raw_sha256,COUNT(*) AS occurrences FROM source_files GROUP BY raw_sha256 HAVING COUNT(*)>1;
CREATE VIEW IF NOT EXISTS duplicate_pages AS
 SELECT text_id,COUNT(*) AS occurrences FROM pages GROUP BY text_id HAVING COUNT(*)>1;
