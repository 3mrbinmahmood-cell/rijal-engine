# Sprint 1 status

Run with Python 3.10+:

```bash
python -m rijal_engine import data.sqlite /path/to/html-folder
python -m rijal_engine import data.sqlite /path/to/batch.zip
python -m rijal_engine search data.sqlite "أبو المليح"
python -m rijal_engine audit data.sqlite
python -m unittest discover -s tests
```

This is an auditable staging database, not a validated narrator compilation. The original bytes stay in user-provided files; SHA-256 and source URI preserve provenance. Byte-identical inputs share one indexed text but retain separate occurrences. Changed files remain in the history. Every HTML file is currently one segment with unknown page label; page and biography parsing require sample-specific validation. Candidate entries, relationship mentions, and identity reviews are explicit empty tables. No identities or isnāds are inferred. Search is lexical FTS5, not semantic search.

Do not commit source books or generated SQLite files. Reader v0.5.5 integration will follow after the import and source-offset audit.
