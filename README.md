# Rijāl Engine

This repository tracks the source code for the existing **Rijal Database V1** and **V1.1 extraction update**. The complete database is the baseline for later identity and duplicate review. The 53-file sample importer from the first GitHub pass was superseded by these complete releases.

## Complete corpus

- V1: 1,622 HTML source files, 578 source groups, 677,154 page occurrences, and 668,042 distinct extracted page texts.
- V1.1: 664,308 candidate biography entries and 1,937,255 statement occurrences. These are candidates and textual occurrences, not verified distinct people.
- Identity merges performed: **0**. Semantic deduplication and identity resolution are the next stage.

The source and reports are under [`rijal_database/`](rijal_database/). The full SQLite payloads are distributed separately in the **six V1 ZIP parts** and **five V1.1 ZIP parts** saved with the releases. Keep every part in each set together, extract Part 01 of V1, then merge Part 01 of V1.1 into the same `rijal_database` directory. The launchers verify and reconstruct the remaining payload parts. The V1.1 launcher checks the V1 database checksum.

On Windows, run `START_WINDOWS.bat`, then `START_EXTRACTION_WINDOWS.bat`. On Linux/macOS, run `sh start.sh`, then `sh start_extraction.sh` from `rijal_database/`. Python 3.10+ and SQLite FTS5 are required. See the [V1 instructions](rijal_database/README.md), [V1.1 instructions](rijal_database/EXTRACTION_README.md), and [local API](rijal_database/API.md).

Keep the original `Rijaal database data raw.zip` unchanged outside Git. Generated SQLite files, compressed payloads, source books, and oversized evidence exports are excluded from this code repository. The release manifests and audit reports provide byte-level verification.

## Next sprint

Review identity candidates against the full V1/V1.1 corpus with source quotations and page offsets. Record proposed links and decisions without changing source text, silently merging people, or treating an absent teacher/student mention as a proven chain break. Integrate reviewed records with Shamela Reader v0.5.5 after the review layer is validated.
