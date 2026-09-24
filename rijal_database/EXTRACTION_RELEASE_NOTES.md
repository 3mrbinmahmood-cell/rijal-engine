# Rijal Database V1.1 — biography and statement extraction

This is stage three of your sequence: preserve/inventory → full-text search → biography and statement extraction → identity/duplicate review → reader integration.

## Install

Keep your installed V1 database. Extract the update beside its existing `rijal_database` folder, merging the folders, then open `START_EXTRACTION_WINDOWS.bat`. Python 3.10+ is required. On Linux/macOS use `sh start_extraction.sh`. The inspector opens at http://127.0.0.1:8766/.

If the update has several ZIP parts, download all parts and keep them together. Extract Part 01; the launcher can read the remaining adjacent ZIPs. Alternatively extract them all into the same parent folder.

The update checks the V1 database checksum and creates a separate `extraction.sqlite`. It does not replace V1 source text, change its death-year tables, or modify the reader's notes. Existing V1 files and the original raw source archive remain necessary.

## Extracted

| Measure | Count |
|---|---:|
| V1 pages scanned | 677,154 |
| Retained candidate biography entries | 664,308 |
| Source-page segments assigned to candidates | 1,025,806 |
| Candidates with later-page continuations | 238,921 |
| Statement occurrences | 1,937,255 |
| Distinct literal statement texts | 1,751,146 |
| Extracted attribution labels | 320,115 |

Each occurrence retains its original Arabic quotation, source page, Unicode offsets, main-text/footnote layer, and candidate biography context. Identical quotations share stored text while keeping every occurrence.

## Limits and next stage

Biography boundaries are automatic: every recorded heading closes the preceding candidate, even an internal non-person heading. Continuations stop at HTML-file boundaries. Index entries and short cross-references remain visible with flags. These are candidate regions, not a claim of complete, verified biographies.

Statement extraction uses a documented vocabulary of Arabic cues. It is not exhaustive semantic extraction. Birth/death passages are not automatically dated or attributed to a verified person. Teacher/student and family passages remain literal statements, with no resolved relationship edges. A reliability expression may assess a hadith, chain, quoted narrator or another person; extracted attribution labels are also unverified.

Identity merges performed: **0**. Verified distinct-person count: **not yet established**. Identity and duplicate review is the next stage; reader integration follows that review.

## Validation

- All stored quotations, triggers and attribution offsets matched their exact V1 source text.
- Biography segments stayed within source files and did not cross recorded headings.
- Main text and footnotes were checked separately; every assigned statement stayed inside its candidate region.
- SQLite integrity, foreign keys and full-text indexes passed.
- The V1 database matched its original release checksum before and after extraction.
- 18 automated tests cover Arabic diacritics, teacher/student direction, footnotes, attribution, report/chain judgments, continuation boundaries, exact-text reuse, API pagination and errors, installer compatibility and damaged-file rejection. JavaScript syntax also passed.
- Full-corpus source retrieval and search checks passed. No real-browser visual verification was performed.
- The complete compressed extraction database was decompressed and checked against its original checksum; every ZIP was tested.

Detailed reports, inspectable sample evidence, rebuild code, and Arabic instructions are included. The inspector is read-only. The full count of distinct people remains pending identity review.
