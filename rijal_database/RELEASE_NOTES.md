# Rijal Database V1 — release notes

Complete source-corpus import: **1,622 HTML files**, **578 source groups**, **677,154 page occurrences**.

The database stores **668,042 distinct extracted page texts**, retaining every occurrence. Exact paragraph reuse is indexed separately. Candidate headings and relationship mentions are not verified people or final scholarly claims.

## Download and start

Download all **6 ZIP file(s)** and keep them together. Extract Part 01 and open `rijal_database/START_WINDOWS.bat`. The launcher reads the remaining ZIPs beside the extracted folder (or one folder above it), verifies the parts, and restores the database. Alternatively, extract every ZIP into the same destination so their `rijal_database` folders combine. Python 3.10+ is required.

Database after unpacking: **4.93 GiB**. Compressed data: **1964.9 MiB**. Keep enough free space for both while unpacking.

The old reader is not replaced. An optional toolbar/dialog adapter is included, with instructions in `README.md` and a stable asynchronous API in `API.md`. The old reader's original note storage remains unchanged.

Keep your existing `Rijaal database data raw.zip` unchanged. It is already your preserved source archive and is not duplicated in these downloads. For direct original-HTML downloads, place it in the database's `sources` folder. The database text, citations and search work without this step.

## Verified

- Database integrity, foreign keys, FTS index integrity, complete source counts, and all stored entry offsets.
- SHA-256 checksums of all 1,622 source files against the original archive.
- 84 page reconstructions across selected source files, including the three old-reader rijal sources.
- 19 Python tests: source preservation, duplicate/changed imports, exact and flexible Arabic search, missing printed page labels, footnotes, source citations, HTTP API, local/file reader origin support, multipart reconstruction, date parsing, and 30-/100-year boundaries.
- JavaScript adapter contract and DOM mount checks, plus the old reader's note migration and father-pronoun regression tests.
- Complete compressed-database round trip matched the final database SHA-256.

## Current limits

This is a source database with exact textual deduplication. Semantic overlap and identical normalized paragraphs are review candidates, not automatically merged statements. Canonical person identities, reconciled claims and scholarly grading are not fabricated or marked as complete.

Real-browser visual automation could not run in this environment because a browser executable was unavailable. API, JavaScript syntax, adapter DOM/contract checks, and old-reader regressions were tested; a visual Chromium/Firefox run is still a useful follow-up during the next reader integration.

The chronology tables are available in the local browser and in `reports/CHRONOLOGY.html`. Their counts are provisional name-label and matching-death-year groups, not a verified distinct-person total. Records without usable dates remain outside the timeline.

See `reports/AUDIT.json`, `reports/SOURCE_MANIFEST.json`, and `reports/BOOK_INVENTORY.csv` for detailed evidence.
