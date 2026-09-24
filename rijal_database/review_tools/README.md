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

## Complete review packet

```bash
python -m rijal_database.review_tools.packet dated review.sqlite GROUP_ID rijal_database/rijal.sqlite rijal_database/extraction.sqlite dated_packet.html
python -m rijal_database.review_tools.packet name name_inventory.sqlite "NORMALIZED_NAME_KEY" rijal_database/rijal.sqlite rijal_database/extraction.sqlite name_packet.json
```

Use `.html` for a readable Arabic comparison or `.json` for all structured
citations and Unicode offsets. The exporter includes **all** stored biography
segments and statement occurrences for each candidate in that group, with
their original wording and source page reference. It verifies heading,
death-year quotation, and statement offsets against the V1 source text before
writing. V1.1 biography boundaries and extracted statements remain automatic
candidates; the packet is evidence for review, not an identity ruling.

## Compare two entries

```bash
python -m rijal_database.review_tools.compare dated review.sqlite GROUP_ID ENTRY_A ENTRY_B rijal_database/rijal.sqlite rijal_database/extraction.sqlite comparison.html
python -m rijal_database.review_tools.compare name name_inventory.sqlite "NORMALIZED_NAME_KEY" ENTRY_A ENTRY_B rijal_database/rijal.sqlite rijal_database/extraction.sqlite comparison.json
```

This selects exactly two entries from one review group, displays their full
packets, marks whether extracted death years agree or differ, and lists any
**literally identical statement occurrences** with both citations. It also
shows an already recorded pairwise review decision, if present. Shared
wording may have been copied between books; absent overlap does not imply
different people. No comparison signal is an automatic identity decision.

## Reviewed person ID and evidence fingerprint

```bash
python -m rijal_database.review_tools.person_registry create person_registry.sqlite name_inventory.sqlite rijal_database/rijal.sqlite rijal_database/extraction.sqlite ENTRY_A ENTRY_B --name "REVIEWED_NAME" --reviewer "REVIEWER" --reason "Source-backed rationale"
python -m rijal_database.review_tools.person_registry show person_registry.sqlite PERSON_ID
python -m rijal_database.review_tools.person_registry audit person_registry.sqlite name_inventory.sqlite
```

`create` requires a current explicit `same` decision for the selected pair.
`add` requires `same` decisions against **every** existing member of that
person record. A `different`, `uncertain`, or absent decision blocks it.
The minted UUID is a stable person ID. A SHA-256 evidence fingerprint records
the linked entry IDs, exact names, source checksums, extracted death evidence,
and literal alias, family, teacher and student cues. It changes when approved
evidence is added; it is not itself a semantic identity test or a guaranteed
unique description of a human being.

The registry is a separate SQLite file. Back it up with the review decision
file. If a decision changes later, `audit` marks the affected person
`needs_review`; it never silently splits or merges records. **No real corpus
person ID has been minted yet**, because no real pair has an approved
`same` decision.

The first full build yielded **1,249 groups and 2,647 entry candidates**.
Of those entries, V1.1 classified 2,539 as biography candidates, 99 as short
index candidates, and 9 as cross references. No pairwise decisions or person
merges were made. This queue only covers entries with matching extracted death
years; entries without dates and differing names need later review methods.

## Broader name inventory

```bash
python -m rijal_database.review_tools.name_inventory build rijal_database/extraction.sqlite name_inventory.sqlite
python -m rijal_database.review_tools.name_inventory triage name_inventory.sqlite rijal_database/rijal.sqlite rijal_database/extraction.sqlite
python -m rijal_database.review_tools.name_inventory dates name_inventory.sqlite "بشر بن المفضل بن لاحق الرقاشي"
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

The date triage found **14 groups with differing extracted death years**, **576
with at least two dated entries agreeing**, **1,946 with one dated entry**, and
**22,888 without extracted dates**. A disagreement can reflect variant
historical reports about one person; agreement can occur between homonyms.
These flags only order the review list. The inspected source quotations must
be read before recording a pairwise decision.

Conflicting extracted years remain separate in `date_evidence` with their
original quotation and source page. `date_grouping` adds the smallest shared
numeric placeholder: exact year (unit 1), 10-year range, 100-year range, then
1,000-year range. For example **186 and 187 AH → 180–189 AH**, while both
186 and 187 remain visible. If years straddle a 1,000-year boundary there is
no shared placeholder in these four levels. Undated or ambiguous textual
reports remain quoted with a null numeric year. These are decimal ranges,
not named Hijri centuries, and they do not settle identity or date accuracy.

### Additional reviewed date claims

The original V1 chronology field selects one claim per entry. A reviewer can
record further **differing years** from the same biography without changing the
source DB. A year already recorded for that biography is rejected:

```sh
python -m rijal_database.review_tools.name_inventory add-date-claim \
  name_inventory.sqlite rijal_database/rijal.sqlite rijal_database/extraction.sqlite \
  ENTRY_ID PAGE_ID 208 --quote 'EXACT SOURCE WORDING' \
  --reviewer 'Reviewer name' --note 'How the contextual year was read'
python -m rijal_database.review_tools.name_inventory dates \
  name_inventory.sqlite 'NORMALIZED NAME KEY'
```

The quote must occur exactly once within that entry's biography segment on
the specified source page. The inventory checks the V1/V1.1 release bindings,
stores the original page offsets and attribution note, and includes additional
reviewed years in the smallest shared decimal bucket. It does not automatically
interpret every date phrase. Editorial footnotes outside a biography segment
need separate review evidence; they cannot be silently added as a biography
claim. Very broad buckets such as 0–999 AH are mechanical groupings, not useful
historical estimates.

### Bulk identity candidate queue

Run `python -m rijal_database.review_tools.bulk_candidates
name_inventory.sqlite rijal_database/extraction.sqlite candidates.sqlite` to
rank exact-name pairs sharing long (at least 60 characters) verbatim statement
text. Two or more shared statements receive `strong_literal` priority. The
output retains each quotation, extracted date relation, and any existing pair
decision. It assigns no reviewed person ID and makes no merge. The exact-name
inventory covers 74,081 biography entries; missing shared text is not a
different-person decision. Teachers, students, and regions can be incomplete
or vary between books, so nonoverlapping lists alone cannot split identities.

Run `python -m rijal_database.review_tools.provisional_identity
name_inventory.sqlite candidates.sqlite provisional.sqlite` to materialize two
reversible views. `name_buckets` groups all 74,081 entries by the existing
normalized name key for browsing; **a bucket is not a person**. The separate
`provisional_groups` view joins pairs with at least two shared long verbatim
statements, excluding explicit `different` or `uncertain` reviews and failing
if a transitive component contradicts a reviewed `different` decision. Each
source entry remains present, and no reviewed person ID is minted. Preserve
the reviewed registry for final identity and treat this view as an accelerated
starting point for finding duplicates.

Run `python -m rijal_database.review_tools.relationship_candidates
name_inventory.sqlite rijal_database/extraction.sqlite rijal_database/rijal.sqlite
relationships.sqlite` to rank name pairs by overlapping teacher and student
names in their opening biographies. The output stores each parsed name and
source page. `both_lists_3plus` requires at least one overlap in each direction
and at least three names total. This is a **heuristic review queue**: it can
capture incidental mentions or miss names with variant spelling. It makes no
identity links; absent overlap is not evidence of separate people.

Pass `--relationships relationships.sqlite` to `provisional_identity` to also
link pairs that share one long verbatim statement **and** qualify for
`both_lists_3plus`. The links remain provisional. An existing `different` or
`uncertain` review blocks them, and a transitive conflict with a reviewed
`different` decision aborts the build.

### Full extraction name coverage

Run `python -m rijal_database.review_tools.full_name_index
rijal_database/extraction.sqlite full_name_index.sqlite` to index **all** V1.1
extraction entries, including short names, entries appearing in only one book,
cross-references, and short indexes. It creates stable `name-...` bucket IDs,
retains each entry's source and classification, and records the V1.1 release
checksum. In the current release this covers 664,308 entries in 412,280 name
buckets. A bucket is a search/review convenience, **not** a unique person;
index and cross-reference candidates especially should not become people
automatically. The earlier 74,081-entry inventory remains the conservative
multi-book review subset.

Run `python -m rijal_database.review_tools.full_literal_candidates
full_name_index.sqlite rijal_database/extraction.sqlite rijal_database/rijal.sqlite
full_candidates.sqlite` for all biography candidates in repeated name groups of
2–8 entries spanning at least two books. The queue preserves each shared long
quotation and distinguishes short-name candidates. Run
`python -m rijal_database.review_tools.full_provisional_links
full_name_index.sqlite full_candidates.sqlite name_inventory.sqlite
full_links.sqlite` to build reversible links for pairs with at least two
matching long statements. Reviewed `different` and `uncertain` decisions veto
links, and a transitive different-person conflict aborts the build. Only linked
entries occur in `full_links.sqlite`; all other entries remain available in
the full index. These are provisional links, never reviewed person IDs.

Pass `--all-groups` to `full_literal_candidates` to include larger name groups
and same-book repeats. A shared quotation is skipped if it occurs in more than
20 entries of one name group (`--max-quote-entries` adjusts this cap). The
candidate still requires an exact normalized name and a long quotation;
shorter and common names remain flagged for further context checks.
