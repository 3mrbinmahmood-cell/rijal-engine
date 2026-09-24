# Reader integration contract — Rijal Database 1.0

Base URL: `http://127.0.0.1:8765/api/v1/`. GET only; JSON is UTF-8. The database and browser are local. No writes, person merges, annotation migrations, or isnad grading are performed by this API. Query responses are paginated; do not download the full database into browser memory.

Load `reader_adapter/rijal-db-client.js` to obtain `window.RijalDatabaseClient`. For a toolbar and in-reader dialog, also load `rijal-db-button.js`. Configure a different service URL with `window.RIJAL_DATABASE_URL` before loading the button script. An unmodified copy of the old reader should continue to load and store its notes at its original URL.

```js
const db = new RijalDatabaseClient('http://127.0.0.1:8765');
const result = await db.search('أسامة بن عمير', {
  scope: 'pages', mode: 'words', limit: 30, offset: 0
});
const page = await db.page(result.results[0].page_id);
// Use textContent to display page.text. Never execute source HTML.
const references = await db.sources(page.text_id);
```

| Endpoint | Parameters / behavior |
|---|---|
| `chronology` | Provisional name-and-death-year group counts, 30-/100-year Hijri bins, missing-date statuses and endpoint evidence. Never a verified census of distinct narrators. |
| `stats` | Corpus totals, schema application version, read-only status. Counts of entries are candidate records, not people. |
| `books` | Optional `q`; source book groups, available author/edition/publisher/category metadata. The same work in different editions can have separate groups. |
| `search` | Required `q`; optional `scope=pages\|entries`, `mode=words\|phrase\|exact\|prefix`, `book=<book_id>`, `limit=1..100`, `offset>=0`. Returns `results`, `has_more`; does not claim an exhaustive total count. |
| `page/<page_id>` | Complete canonical extracted text of the page, citation, metadata, heading/footnote spans, entries, relationship mentions with verbatim evidence, previous/next page IDs. |
| `entry/<entry_id>` | Candidate source entry, opening passage through the next candidate on the same page, and continuation link. `scope=current_page_only`. Never a verified canonical narrator. |
| `sources` | Required `text_id`; all occurrences of identical page text; `limit=1..500`, `offset`. |
| `duplicates` | Required `text_id`; exact repeated paragraphs on the page with occurrence counts and offsets. |
| `passage-sources` | Required `id=<passage_id>`; all references to that exact paragraph, `limit`, `offset`. |
| `raw/<source_id>` | Downloads exact source HTML after SHA-256 verification. Optional `page=<page_id>` returns the original byte range covering that page. Requires unchanged original ZIP in `sources/` or `--archive` startup argument. The last page byte range may include trailing source markup. |
| `identity/entry/<entry_id>` | Optional reviewed/provisional/unlinked identity for a V1 source entry ID. Requires `--identity`. |
| `identity/members/<identity_id>` | Paginated source entries under that identity. Requires `--identity`. |
| `identity/dates/<entry_id>` | Available death-year claims and their original quotes. Requires `--identity` and `--dates`. |
| `identity/graph/<entry_id>` | Paginated unresolved teacher/student name mentions. Requires `--identity` and `--graph`. |
| `graph/evidence/<entry_id>` | `relation=teacher\|student&mention=<mention_id>`; entry and page evidence for one mention. |
| `graph/mention/<mention_id>` | Identities mentioning the same unresolved name; spelling does not establish a shared person. |

The API permits read requests from local HTTP origins and `file://` (`Origin: null`) for the downloadable reader. It binds to loopback, not the LAN. HTTP error bodies have an `error` string and appropriate 400/404/500 status.

Start the main service with `--identity unified_identity_view.sqlite --dates
identity_dates.sqlite --graph relationship_graph.sqlite` to enable the
optional identity endpoints. The reader adapter exposes `identity(entryId)`,
`identityMembers(identityId)`, `identityDates(entryId)`,
`identityGraph(entryId)`, `graphEvidence(entryId,relation,mentionId)`, and
`graphMention(mentionId)`. V1.1 reuses V1 source entry IDs, so `entry(id)` and
`identity(id)` refer to the same source candidate.

## Stable references and offset semantics

`archive_id` is SHA-256 of the complete original ZIP. `source_id` includes that archive identity, the ZIP entry index and exact path. `page_id` includes source ID and page ordinal. The same archive reimport keeps IDs; a changed archive is a separate preserved version. `text_id` is an internal SQLite row ID and should not be used for persistent annotations. Use `page_id` plus offsets and a quoted-text check.

Every offset is a zero-based Unicode code point index into the returned `page.text`, with an exclusive end. JavaScript must use `Array.from(text).slice(start,end).join('')`, or explicitly convert to UTF-16 units before using DOM ranges. Metadata headers are separate from page body text. Original HTML bytes are preserved in the source ZIP; extraction adds structural newlines and decodes HTML entities.

`citation` includes `page_id`, `book_id`, `title`, `author`, `edition`, `publisher`, `part_label`, `printed_label`, `ordinal`, `zip_path`, `zip_index`, `raw_sha256`, `archive_id`, and archive filename. Empty printed labels remain empty. Never invent a printed page number from the ordinal.

Page search groups only identical extracted page text. Each result includes a representative `page_id`, source count, verbatim excerpt and its code point offsets. Entry search returns distinct candidate source entries. Flexible query normalization affects search keys only and does not prove name equivalence. Exact search uses a normalized index to find candidates followed by a literal substring check against original extracted text.

## Identity and claims

`entries.status=automatic_candidate` and `mentions.status=unresolved_mention` are intentional. A relationship mention can quote another speaker, appear in a footnote, or concern another person. `entry_id` on a mention is an unverified same-page contextual suggestion. The `persons`, `aliases`, `assertions`, `identity_links`, and `review_log` tables are reserved for evidence-based review. They do not contain automatically invented identities or judgments.

The old reader's three-book experiment remains independent. This adapter does not replace its synchronous `ShamelaRijal.search` with a network call or feed unreviewed corpus candidates into its existing isnad decisions. New reader development should explicitly adopt the asynchronous API and display source-backed uncertainty.

## Optional extraction inspector (port 8766)

The separate `extraction_server.py` can also load `--identity`, `--dates`, and
`--graph` SQLite files. These endpoints are read-only equivalents on port
8766:

| Endpoint | Meaning |
|---|---|
| `/api/identity/entry/<entry_id>` | Current reviewed/provisional/unlinked identity and original source fields. |
| `/api/identity/members/<identity_id>` | Paginated source entries in that identity. |
| `/api/identity/dates/<entry_id>` | Every available death-year claim with source quote and decimal grouping. |
| `/api/identity/graph/<entry_id>?relation=teacher\|student` | Paginated unresolved name mentions for the entry's current identity. Includes `mention_id`. |
| `/api/graph/evidence/<entry_id>?relation=teacher\|student&mention=<mention_id>` | Paginated biography entry IDs and opening page IDs supporting that graph edge. |
| `/api/graph/mention/<mention_id>?relation=teacher\|student` | Paginated identities mentioning the same name. Shared spelling does not prove a shared person. |

All graph names are heuristic and unresolved. Source page IDs support manual
verification; they are not exact quotation offsets for relationship phrases.
