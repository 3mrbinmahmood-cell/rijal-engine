# Fixed book set: ṣaḥīḥ and ḍaʿīf test

Input: `sample library v 6.zip` (seven Shamela book groups, 41 HTML source files). Reader output: `Shamela_Reader_V0.6.5.zip`.

| Book | Status | New reader pages |
|---|---|---:|
| الصحيح المسند مما ليس في الصحيحين | Already present | — |
| صحيح البخاري - ت البغا | Already present | — |
| صحيح مسلم - ت عبد الباقي | Already present | — |
| سنن أبي داود - ت الأرنؤوط | Added | 4,442 |
| سنن ابن ماجه - ت الأرنؤوط | Added | 3,029 |
| سنن الترمذي - ت شاكر | Added | 6,468 |
| سنن النسائي - ط الرسالة | Added | 4,041 |

The four additions contain 17,980 page records. The existing six reader books, including the three Rijal sources, are unchanged. The reader now has ten books and 60,970 page records. The source ZIP remains unchanged.

## Paired test on a single page

In **سنن أبي داود - ت الأرنؤوط**, volume 1, **p. 9**:

- Report **9** starts with `حدَّثنا مُسدَّدُ بنُ مُسَرهَد، حدَّثنا سُفيان، عن الزهري...`; its footnote says `إسناده صحيح`.
- Report **10** starts with `حدَّثنا موسى بنُ إسماعيل، حدَّثنا وُهَيب، حدَّثنا عمرو بن يحيى، عن أبي زيد...`; its footnote says `إسناده ضعيف لجهالة أبي زيد مولى بني ثعلبة`.

The two grades occur on **the same page**. A page-wide grade would falsely label one of these reports. A nearby reference to another work's “إسناده صحيح” also must not be assigned to the current report. The book's assessment and the Rijal graph's teacher-name evidence are separate fields.

## What was verified

- ZIP integrity and all reader tests passed.
- The first six book objects are byte-equivalent at the decoded data level before and after import.
- New HTML PageText boundaries map to source page labels and are navigable in the fixed set.
- The two opposite grade expressions and their numbered report texts survive import on Abū Dāwūd p. 9.

## Still required for a live ruling comparison

This package does **not** yet parse a hadith-specific grade automatically. It displays the complete source text for manual confirmation. The horizontal chain bar checks unresolved name mentions in the separately running local Rijal database; green is evidence of a recorded teacher-name mention, not proof of hearing or a ṣaḥīḥ ruling. To evaluate these two chains end to end, run the full database service with identity and relationship graph files installed, select only the report's sanad, and compare every displayed edge against the footnote.
