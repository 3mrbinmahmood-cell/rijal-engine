# Shamela Reader V0.5.7 — start and upgrade

## Start on Windows

Extract the whole ZIP to a folder on your PC. Double click `start.bat`, or open `index.html` in Firefox or Chrome. Keep the complete extracted folder together, including `rijal-core.js` and `rijal-data.js`. It runs locally without installing Python or connecting to the internet. The initial load can take time because `data.js` is about 82 MB. The sample library contains six book groups and 42,990 page records.

## Navigation

Choose a book and use **متابعة القراءة** to return to its saved page and approximate position within that page. **من البداية** opens its first record. The left menu shows the source-derived table of contents; choose a division, filter title words, or click **عرض المزيد** for further entries. **الباب السابق** and **الباب التالي** move between listed headings. The numeric jump box uses the reader record number (1 to the book total), while each title also displays its original source page label. **علامة** saves an additional bookmark at the current spot; **العلامات** jumps to or deletes saved bookmarks.

The table of contents is a navigation aid built from source `title` styling and detectable Bukhari headings. It is not a complete verified scholarly hierarchy; the audit records skipped or unmatched labels. Within-page return uses a scroll fraction and may shift after a font or window-size change.

## Upgrade from V0.1

1. In the **same browser and same folder or same localhost origin** used for V0.1, make a backup before moving the files. If V0.1 is still in that folder, copy `legacy-export.html` from V0.2.2 into that folder and open it there. Click its download button and retain the JSON file. Keep your V0.1 folder untouched until the upgrade is verified.
2. Extract V0.2.2 into a new folder. Opening its `index.html` automatically copies old `last`, `marks`, and `note:<book>:<page>` values **only if this browser exposes the same storage origin**. It writes `shamela:v2:pre-migration` before the new state. It does not delete legacy keys. This can be repeated without duplicate bookmarks.
3. If the new folder has different storage, use **نسخة احتياطية → استيراد JSON** to import the `shamela-legacy-v1.json` saved in step 1. Confirm notes, bookmarks, and page position, then export a V0.2 backup. Importing first downloads a backup of the current V0.2 state.
4. Browser `file://` storage may differ by file path and browser. If the old installation used a server, the exporter must be visited with its old hostname and port. Do not delete the old installation or clear browser data until a new backup has been downloaded and checked.

The automatic migration is not a substitute for the legacy export when browser storage is on a different origin. Saved V0.2.2 data lives in the browser's local storage for that origin, not inside the ZIP. The sample source books are read only.

## Backups and limitations

Use **نسخة احتياطية → تصدير JSON** regularly. Import adds missing annotations and bookmarks by ID and leaves existing page notes unchanged when both copies have a note. Deletion is persisted locally, but importing an **older** backup can add that old highlight again. Reopen the same extracted folder in the same browser for normal persistence.

Highlight anchors refer to text ranges and quote context in the shipped `data.js`. Source text is rendered exactly from that array. The prototype does not include traceable original HTML file anchors or a chapter tree; future importer work must supply those. The existing search reports matching **pages**, capped at 250 displayed items, and runs on the main thread. No SQLite importer, structured narrator profiles, semantic search, online AI, tablet synchronization, or PDF handling is included in V0.2.

## Upgrade from V0.2

Export a backup in V0.2, then replace the extracted program files while keeping the same folder and browser origin. The `shamela:v2` annotation format is unchanged. Confirm a saved highlight, bookmark, and per-book position in V0.2.1 before removing the old copy.

## Staged search plan

Use **عبارة متتابعة** for consecutive words in the same order, or **كل الكلمات الكاملة** when every queried word must appear on a page in any order. Choose the current book or all six books. The displayed count is matching **page records**, not a count of word occurrences; at most 250 pages are displayed. Choose normalization explicitly: ignore vowel marks, equate alif forms, equate ى/ي, or equate ة/ه. These choices affect only the search key, never the source text. Clicking a result opens its page. Topic search and online AI assisted search remain separate later stages.

## Upgrade from V0.2.1

Export a backup, then extract V0.2.2 into the same folder used by V0.2.1. Its annotation storage format is unchanged. The larger table of contents font requires no data migration.

## Upgrade from V0.2.2

Export a V0.2.2 backup first. Extract V0.3 into the same folder and open it in the same browser. Existing annotations use the same `shamela:v2` storage format. The theme preference uses `shamela:theme:v1`. Search controls are temporary and do not change the books.

The legacy embedded data bundle remains about 82 MB. On an HTTP origin, the search worker loads its own copy of that data and may use substantial memory. Direct `file://` opening uses a batched search on the main page, which may take longer on the full corpus. This is not yet a SQLite full-text index or Arabic root search.

## V0.4 pen notes

Press **ملاحظات بالقلم** on a book page to open its fixed study canvas. Draw with a pen or mouse, choose color and width, erase whole strokes, or undo/redo. **مسح الصفحة** is reversible with undo during the current session. Close and reopen the page to verify the saved strokes. Finger touch on the canvas is reserved for navigation; pen behavior and palm rejection require testing on your specific tablet. The canvas is attached to the page record, not to individual words, and its fixed coordinates preserve stroke positions when the window changes size. The Arabic source text is not modified.

Export a backup after important handwriting. Ink uses browser local storage; very large drawings may exceed its quota. A save failure cancels the latest stroke and shows an error.

## Upgrade from V0.3

Export a backup from V0.3. Extract V0.4 to the same folder and use the same browser. The existing `shamela:v2` record is extended with a separate `ink` field; old highlights, typed notes, bookmarks and positions remain readable. Importing a V0.3 backup will retain existing saved ink; importing a V0.4 backup merges valid strokes by ID.

This is still a local browser prototype. There is no cross-device sync or installable phone/tablet package in this release. New HTML books, SQLite/FTS5 importing, and indexed narrator profiles remain later work.

## V0.4.1 panel controls

The book stays in the center when you hide **الفهرس** or **اللوحة اليمنى**. The header buttons **فهرس الكتاب**, **ملاحظات الصفحة**, and **ملاحظات بالقلم** are always available. The first reopens the left contents panel, the second opens the right notes panel, and the third opens the current page’s pen canvas. The hide/show buttons independently control the left and right panels.

To upgrade from V0.4, export a backup and extract V0.4.1 into the same folder. Annotation storage has not changed.

## V0.4.2 notes index

Press **قائمة الملاحظات** in the header or **فهرس الملاحظات** in the right panel. Choose **القلم** to see only pages with saved pen strokes, or **النص** for typed notes. Each entry shows its book, source division, printed page label and reader record number. **افتح الصفحة** navigates to the referenced page; **افتح الرسم** opens that page’s fixed pen canvas; **افتح النص** opens its typed note. The list also finds V0.4.1 notes saved without the newer reference map.

Freehand strokes are still drawn on a separate fixed canvas attached to the page. Writing directly over live, reflowable text is not reliable across font changes and phone/tablet widths. A later fixed-layout annotation layer or text-anchored excerpt should be built and tested before describing marks as attached to individual words. The present pen canvas does not alter source wording.

To upgrade from V0.4.1, export a backup, extract V0.4.2 into the same folder, and reopen it in the same browser. Stored annotations retain version 2 compatibility.

## V0.5 rijāl source entries

Press **بحث الرجال** in the header, type a name, and optionally select one of the three source books: *تقريب التهذيب*, *تهذيب التهذيب - ط الرسالة*, or *تهذيب الكمال في أسماء الرجال*. The results list shows headings and source page labels. Select a result to see an excerpt of the original Arabic entry (at most three consecutive reader records, ending at the next detected entry). **افتح في الكتاب** opens that page in the normal reader for its full context and annotations. The result count is a count of automatically extracted entry starts, not distinct narrators. The index holds 28,039 candidate entry starts. It loads when the feature is first opened; on a slow device this can take a moment in addition to the roughly 82 MB base text.

Name search ignores vowel marks and folds alif variants, ى/ي and standalone ابن/بن. It searches indexed headings, not the full text of all biographies. The original wording remains in `data.js`; the separate index stores location, heading and source HTML filename. Similar names are never silently joined. Some headings may be missed or incorrectly split, and a long entry may continue beyond the three displayed records. Go to the book for context. Structured teachers, students, assessments and cross-source identity links require source-level review in a later stage.

To upgrade from V0.4.2, export a backup in the old reader, extract the complete V0.5 ZIP over the same application folder, and reopen it in the same browser at the same URL or file origin. Do not overwrite your backup. Existing notes, highlights, pen drawings, bookmarks and reading positions stay in the unchanged `shamela:v2` browser storage record; the rijāl index does not migrate or alter it. Confirm a saved annotation and reading position after upgrading. If you move the folder or change browser/origin, import the saved JSON backup from **نسخة احتياطية**. Keep the old folder and backup until verified.

## V0.5.1 smarter name search and biography layout

Search also checks the beginning of each entry, so a name such as **البخاري** can find the source entry headed **محمد بن إسماعيل...**, even when the nisbah appears after the heading. Results are ranked by early identification before incidental mentions and show up to 150 of the total match count. Enter a longer name to narrow ambiguous results. A match does not assert that similarly named people are identical.

The entry view puts a large, bold source assessment and death wording above the passage when they can be conservatively extracted from the concise *تقريب التهذيب* entry. For extended books it says **لم يُستخرج من هذا المدخل** instead of risking a death date or grade that belongs to someone else mentioned in a long biography. Read the full passage for attributed opinions and dates.

When an excerpt contains explicit **روى عن:** or **روى عنه:** lines, their named phrases appear in two columns, with buttons opening the source page. The lists are textual mentions, not verified relationships, direct-hearing claims or links to unified profiles. Qualifications in the surrounding passage matter; inspect the page. A long translation may continue beyond the three-record excerpt. Narrow-screen devices stack the columns vertically for readability.

To upgrade from V0.5, export your backup, extract V0.5.1 over the application folder and reopen at the same browser origin. Its annotation format is unchanged. Verify a bookmark or note after reopening; import the backup if the folder or origin changed.

## V0.5.2 preliminary sanad screen

Open a page containing a hadith and press **افحص السند**. It examines the first recognizable chain in that page. To examine a particular chain when the page contains several, select its text first and then press the same button. It displays every extracted name in order, marks **possible weak** positions when one unambiguous *تقريب التهذيب* heading begins with that name and contains an explicit weakness expression, and opens that source entry. It counts multiple such positions separately. Ambiguous or unmatched names stay unresolved.

This is an experimental screen, **not a hadith authenticity verdict**. An incomplete or ambiguous match may hide a weakness, and a weakness expression may be conditional. The prototype cannot establish identity across editions, whether two narrators met, direct hearing, tadlīs, transmission variants, or the full scholarly context. A chain with zero flags is **not certified sound**. Read the linked Arabic source and verify each identification before relying on the result. The parser currently handles a subset of the supplied hadith formats; it may miss or mis-segment names.

To upgrade from V0.5.1, export your annotations, extract V0.5.2 into the same application folder, and reopen it at the same origin. Storage remains `shamela:v2`; the sanad screen writes no annotation records. Confirm your saved notes or bookmarks.

## V0.5.3 neighbor-evidence tracing

The sanad screen now searches the immediately preceding narrator’s explicit teachers list and the candidate narrator’s explicit students list before resolving a short name. For each adjacent pair it shows the exact source-list phrase, book and page, plus a button opening that page. A name such as **شعبة** can be distinguished using the **مسلم بن إبراهيم** entry and the reciprocal **شعبة بن الحجاج** entry; then the next **قتادة** entry is checked against Shعبة, and **أبي المليح** is checked against قتادة’s teacher list. Source names are still candidates until reviewed.

**صلة تحتاج مراجعة** means no explicit list mention was found within the examined indexed passages; it is *not* a proven broken chain. A listed teacher/student is not by itself proof of direct hearing of this particular report. Conditional assessments, tadlīs, contradictory reports and the complete isnād still require scholarly review. The screen gives no hadith authenticity verdict. The relationship parser covers unvowelled **روى عن / روى عنه / وعنه** labels in the supplied Tahdhib edition and reads at most eight reader records per biography; it can miss differently formatted evidence.

To upgrade from V0.5.2, export your annotations, extract V0.5.3 into the same folder, and open it at the same browser origin. Annotation storage remains `shamela:v2`; the source originals and rijāl index are unchanged. Confirm a saved bookmark or note after restarting.

## V0.5.4 father references in a sanad

When a resolved narrator is followed by **عن أبيه**, the analyzer reads the immediate father in that narrator’s formal **بن/ابن** lineage, then searches for a separate father biography. It displays the exact child-lineage wording and a phrase from the father’s entry with page buttons. In the supplied test chain, **أبو المليح بن أسامة بن عمير → عن أبيه** leads to **أسامة بن عمير**, whose biography identifies him as **والد أبي المليح** and says his son narrated from him. The companion description is shown as wording from *تقريب التهذيب*.

The rule applies only when the preceding narrator has already been identified and the father biography gives supporting parent wording. A standalone **عن أبيه**, an ambiguous preceding narrator, or a missing father entry stays unresolved. Being father and son does not alone establish the transmission wording for every individual report. The program does not issue a final ruling on the chain.

For an upgrade from V0.5.3, export your saved annotations, extract V0.5.4 into the same folder, then reopen it at the same origin and check a bookmark or note. No annotation format or source wording changed.

## V0.5.5 father display refinement

The chain view shows **والده: أسامة بن عمير** inside the **أبي المليح** card, immediately beneath the candidate narrator and its sources. It no longer creates a separate **أبيه** card. If the father is not established, a single inline explanation remains in that narrator card. A bare pronoun without a preceding narrator is noted above the chain, without a separate narrator card. Duplicate father references for the same displayed narrator are reduced to one, preferring the source-supported identity.

To upgrade from V0.5.3 or V0.5.4, export annotations, extract V0.5.5 to the same application folder, and open at the same origin. No annotation data migration is needed. Verify a saved note or bookmark before deleting your older extracted folder.

## V0.5.6 local topic/context search

Select **موضوع / سياق (محلي)** next to the search box, choose the whole library or current book, and enter Arabic ideas such as `ميراث المرأة`, `ضعف الراوي`, or `صلاة الجماعة`. The result quotes the original Arabic page, shows the printed page label and matched topic names, and opens that page on click. The top 250 matching pages are sorted by the number and closeness of relevant terms; the count covers all matching pages. The worker keeps the UI responsive. Direct `file://` opening uses a batched fallback.

This is a local, deterministic concept-vocabulary and passage-proximity search. It can miss concepts outside its vocabulary and can return false associations where words happen to appear near each other. It does not use embeddings, a generative model, the separate rijāl SQLite database, or an online AI service. Use the phrase/word modes for literal evidence, and read the cited original passage before drawing conclusions.

Upgrade by extracting the complete new ZIP to a new folder. Preserve the old folder and export its JSON backup first. If local browser storage uses a different origin for the new folder, import that backup under **نسخة احتياطية**. Annotation keys and backup formats are unchanged in this release.

## V0.5.7 full-corpus Rijal view

The existing **بحث الرجال** button still searches the three bundled rijāl books offline. The new **قاعدة الرجال الكاملة** button uses Rijal Engine running locally at `http://127.0.0.1:8765`. Start the separate Rijal Database package, then open this reader. For identity, dates, and graph details, start its `launch.py` with `--identity unified_identity_view.sqlite --dates identity_dates.sqlite --graph relationship_graph.sqlite`, using paths to the extracted SQLite files. Search results and source text remain available when only the base Rijal service is running. The service is read-only and bound to your computer; this reader does not upload notes or send its bundled book text to it.

If the service is not running, the full-corpus view reports a connection error and the offline reader continues working. Results represent source entries. A provisional cluster or an unresolved teacher/student name is not a verified person or transmission. This view does not change the older isnād screen's judgments.

Before upgrading, export the reader's JSON backup. Extract V0.5.7 into a new folder; if your browser treats it as a different storage origin, import the backup from the **نسخة احتياطية** tab. Annotation keys and formats are unchanged.
