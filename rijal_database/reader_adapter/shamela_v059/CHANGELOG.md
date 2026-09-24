## V0.5.9 — 24 September 2026

- Paginated identity members and relationship source evidence in the reader.
- Added a shared unresolved name view across identities, with source-entry navigation and an explicit identity caution.

## V0.5.8 — 24 September 2026

- Added a name-search jump from the three-book profile to the full-corpus view. A matching name is not a verified identity.
- Date claims and unresolved teacher/student mentions now open supporting source pages.

- Added an optional full-corpus Rijal view backed by the local read-only Rijal Engine API on port 8765.
- Displays original source entries, reviewed/provisional/unlinked identity status, and available date and relationship clues without altering the bundled three-book Rijal search or isnad screen.
- Does not change annotation storage, source text, or the six bundled book groups. The external database must be started separately; network failure leaves local reading available.

## V0.5.6 — 24 September 2026

- Added local Arabic topic/context search across all six bundled book groups, ranked by nearby related terms and original page references.
- Kept phrase and whole-word search modes, page jumps, annotations, and the source text unchanged.
- Added an explainable matched-topic label and a 250-result ranked cap; the count reports all matching pages.
- This release uses a curated vocabulary and passage proximity, not model embeddings, generated answers, or the separate rijāl SQLite database.

# Changelog

## V0.5.5 — 23 September 2026

- Displayed contextual **أبيه** as a father subsection in the preceding narrator’s card, removing the duplicate unresolved narrator card.
- Consolidated repeated father references in that card and retained the source-supported candidate when duplicates differ.
- Added grouping regression checks for the screenshot’s chain and for an unanchored pronoun.

## V0.5.4 — 23 September 2026

- Resolved contextual **عن أبيه** through the previous narrator’s formal lineage and a corroborating father biography.
- Showed separate child-lineage and father-entry evidence with source-page buttons.
- Recognized the source description **صحابي** in concise Taqrib entries without treating it as an inferred hadith grade.
- Added regression tests for أبي المليح → أبيه (أسامة بن عمير) and for an unanchored father pronoun.

## V0.5.3 — 23 September 2026

- Traced short narrator names through neighboring teachers/students lists in source biographies, showing both sides of a relationship where found.
- Added source phrases, book/page references and buttons to open each evidence page from the sanad screen.
- Marked absent list mentions as links needing review, without treating absence as proven disconnection.
- Added full-corpus regression for مسلم بن إبراهيم → شعبة → قتادة → أبي المليح and a missing-link fixture.

## V0.5.2 — 23 September 2026

- Added one-click preliminary isnād screen for the first chain on a page or a selected chain, with a count of multiple possible weakness descriptions and unresolved names.
- Linked single Taqrib heading matches to their original source entry; no automated hadith grade or continuity judgment.
- Added chain parsing and two-weak-link/ambiguous-name fixture. Annotation storage is unchanged.

## V0.5.1 — 23 September 2026

- Ranked rijāl results by early identity wording and searched the opening source passage for name variants such as البخاري.
- Added two columns for names listed under explicit teacher and student narration labels, with source-page jumps and qualification warning.
- Added large bold assessment and death wording only when safely taken from concise *تقريب التهذيب* entries; left unverified extended-biography facts blank.
- Added a full-corpus regression check for the محمد بن إسماعيل البخاري search and passage extraction.

## V0.5 — 23 September 2026

- Added on-demand search of 28,039 candidate biography entry starts from three supplied rijāl books, with per-book filter and Arabic name normalization.
- Added source-backed entry view with exact Arabic text, source file provenance, printed page label, and a jump into the book reader.
- Kept each source entry separate; no identity merging or inferred teacher/student links. Annotation storage and original text remain unchanged.
- Added index builder, extraction audit and source-location fixtures.

## V0.2.2 — 23 September 2026

- Increased table of contents headings to 21 px, nested entries to 19 px, and page labels to 15 px.
- Widened the contents panel and increased spacing so long Arabic headings wrap legibly.
- Enlarged book menu labels and filter controls; mobile contents panel can use more screen height.

## V0.2.1 — 23 September 2026

- Added per-book table of contents and source division selector, title filter, chapter navigation, and page-record jump.
- Derived navigation labels from the supplied Shamela HTML. Linked its 42,990 source page records to the reader's existing page order; generated `TOC_AUDIT.json`.
- Added per-book continue reading and multiple bookmarks with an approximate within-page position. Existing V0.2 notes, highlights, bookmarks, and backups retain their storage format.
- Kept the original source archives and book text unchanged. No AI or semantic search added.

## V0.2 — 23 September 2026

- Added persistent removable highlights, color choices, linked notes, and a highlights panel.
- Added versioned backup import/export and a legacy V0.1 migration route.
- Fixed search snippet offsets after Arabic normalization.
