# Reader V0.6.6 review build

Rebuild the four new Sunan books from V0.6.4 using `extend_reader_books.py` and `sample library v 6.zip`, then overlay `full-corpus.js` and `tests/test_full_corpus.js` from this folder.

The importer skips per-file metadata when building volume navigation, so each volume appears once and its headings load immediately. The sanad display filters incidental mentions out of candidate biographies. Short ambiguous names remain unresolved. Source mention matches are not final identity or direct-hearing determinations. A red edge means no mention among the checked records; it is not a proven break. The reader does not yet extract a hadith-specific editor grade or automatic weak-link diagnosis.
