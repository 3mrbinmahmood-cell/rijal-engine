# Identity review queue — first pass

This is a **candidate queue**, built from the complete V1 and V1.1 databases.
It proposes entries with the same normalized name and extracted Hijri death
year. A match is not a verified identity. It does not modify either release
database or deduplicate biographies.

```bash
python -m rijal_database.review_tools.queue build rijal_database/rijal.sqlite rijal_database/extraction.sqlite review.sqlite
python -m rijal_database.review_tools.queue list review.sqlite --limit 10
python -m rijal_database.review_tools.queue show review.sqlite GROUP_ID
python -m rijal_database.review_tools.queue inspect review.sqlite rijal_database/rijal.sqlite rijal_database/extraction.sqlite GROUP_ID
python -m rijal_database.review_tools.queue decide review.sqlite ENTRY_A ENTRY_B uncertain --reason "Need fuller context" --reviewer "Omar"
```

Run these commands from the repository root. The build checks that V1.1 belongs
to the V1 release. Rebuilding the same queue preserves decisions and checks
that the source evidence still matches. Every member retains its source book,
HTML path, printed page label, death-year quotation and V1.1 classification.
The separate `review.sqlite` contains pairwise decisions and their history.
Keep and back up this file: it records work that cannot be reconstructed from
the source databases.

`inspect` displays the opening source context and up to twelve V1.1 statement
quotations for each entry, with page IDs and offsets. Statements are extraction
candidates, so the reviewer must verify their subject and attribution in context.

The first full build yielded **1,249 groups and 2,647 entry candidates**.
Of those entries, V1.1 classified 2,539 as biography candidates, 99 as short
index candidates, and 9 as cross references. No pairwise decisions or person
merges were made. This queue only covers entries with matching extracted death
years; entries without dates and differing names need later review methods.

## Broader name inventory

```bash
python -m rijal_database.review_tools.name_inventory build rijal_database/extraction.sqlite name_inventory.sqlite
python -m rijal_database.review_tools.name_inventory list name_inventory.sqlite --limit 10
python -m rijal_database.review_tools.name_inventory inspect name_inventory.sqlite rijal_database/rijal.sqlite rijal_database/extraction.sqlite "ابراهيم بن ابي موسي الاشعري"
python -m rijal_database.review_tools.name_inventory decide name_inventory.sqlite ENTRY_A ENTRY_B uncertain --reason "Compare teachers and dates" --reviewer "Omar"
```

The full V1.1 scan yielded **25,424 longer exact-name groups containing
74,081 biography candidates** from at least two books. This lower-confidence
inventory requires at least five words, 25 characters, and 2–8 occurrences
per normalized name. It can include homonyms, repeated editions, and entries
already in the chronology queue. Pairwise review decisions and their history
are stored in this separate inventory database; there is no merge operation.
Reviewers should compare source text, patronymics, teachers, students, places
and conflicting dates before promoting any pair for a decision.
