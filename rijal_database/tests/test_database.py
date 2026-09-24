"""Meaningful source-preservation, deduplication, and reader contract checks."""
import json
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE));sys.path.insert(0,str(BASE/'tools'))
from common import normalize,digest
from import_sources import import_archive,parse_source,extract_page
from server import Database

BODY='أُسَامَة بن عُمير. روى عنه ولده وحده. '+('هذا نص طويل محفوظ بلفظه للتحقق من تكرار الفقرة مع بقاء جميع المراجع واختلاف الطبعات. '*2)
def source(title='كتاب الرجال',edition='الأولى',body=BODY,label='(ج: 1 ص: 25)'):
    return (f'''<html><head><title>{title}</title></head><body><div class="PageText"><span class="title">الكتاب:</span>{title}<p><span class="title">المؤلف:</span>مؤلف المصدر<p><span class="title">الطبعة:</span>{edition}</div>
    <div class="PageText"><div class="PageHead"><span class="PartName">الجزء الأول</span><span class="PageNumber">{label}</span></div><span class="title">1 - أسامة بن عمير</span>{body}</p>فقرة ثانية لا يجوز وصلها بالسابقة.<div class="footnote">قال المحقق: نص الحاشية. روى عنه فلان.</div></div></body></html>''').encode()

class DatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name);cls.archive=cls.root/'source.zip';cls.path=cls.root/'test.sqlite'
        with zipfile.ZipFile(cls.archive,'w') as z:
            z.writestr('exports/الكتاب أ.htm',source())
            z.writestr('exports/الكتاب ب.htm',source())
            z.writestr('exports/طبعة أخرى.htm',source(edition='الثانية'))
            z.writestr('exports/دون ترقيم.htm',source(body='أُسَامَة ابن عُمير، قول مختلف.',label=''))
        cls.import_result=import_archive(cls.path,cls.archive)
        cls.db=Database(cls.path,[cls.archive])
    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()
    def sql(self,s,args=()):
        with sqlite3.connect(self.path) as c: return c.execute(s,args).fetchall()
    def test_import_complete_and_integrity(self):
        self.assertEqual(self.import_result['failed'],0)
        self.assertEqual(self.sql('PRAGMA integrity_check'),[('ok',)])
        self.assertEqual(self.sql('PRAGMA foreign_key_check'),[])
        self.assertEqual(self.sql('SELECT COUNT(*) FROM source_files')[0][0],4)
        self.assertEqual(self.sql('SELECT COUNT(*) FROM pages')[0][0],8)
    def test_idempotent_reimport(self):
        before=self.sql('SELECT COUNT(*) FROM entries')[0][0]
        r=import_archive(self.path,self.archive)
        self.assertEqual(r['imported'],0);self.assertEqual(r['skipped'],4)
        self.assertEqual(self.sql('SELECT COUNT(*) FROM entries')[0][0],before)
    def test_exact_dedup_keeps_all_references(self):
        result=self.db.search('أسامة بن عمير',mode='phrase')
        group=next(r for r in result['results'] if r['source_count']==3)
        refs=self.db.sources(group['text_id'])['results']
        self.assertEqual(len(refs),3)
        self.assertEqual({r['edition'] for r in refs},{'الأولى','الثانية'})
        self.assertEqual(len({r['source_id'] for r in refs}),3)
    def test_original_bytes_and_footnotes(self):
        sid=self.sql('SELECT id FROM source_files WHERE zip_path=?',('exports/الكتاب أ.htm',))[0][0]
        raw,name=self.db.raw_source(sid);self.assertEqual(raw,source())
        pid=self.sql('SELECT id FROM pages WHERE source_id=? AND ordinal=1',(sid,))[0][0]
        page=self.db.page(pid)
        self.assertIn('أُسَامَة',page['text']);self.assertIn('نص الحاشية',page['text'])
        self.assertIn('\nفقرة ثانية',page['text'])
        foot=[s for s in page['spans'] if s['kind']=='footnote'];self.assertTrue(foot)
        self.assertIn('قال المحقق',page['text'][foot[0]['start_offset']:foot[0]['end_offset']])
        for m in page['mentions']:
            self.assertEqual(m['evidence'],page['text'][m['start_offset']:m['end_offset']])
        self.assertTrue(any(m['in_footnote'] for m in page['mentions']))
    def test_literal_and_normalized_search_are_distinct(self):
        self.assertTrue(self.db.search('اسامة بن عمير')['results'])
        self.assertTrue(self.db.search('أُسَامَة بن عُمير',mode='exact')['results'])
        self.assertFalse(self.db.search('اسامة بن عمير',mode='exact')['results'])
        self.assertTrue(self.db.search('أُسَامَة ابن عُمير',mode='exact')['results'])
    def test_entries_are_candidates_and_offsets_literal(self):
        rows=self.db.search('أسامة',scope='entries')['results'];self.assertTrue(rows)
        for r in rows:
            p=self.db.page(r['page_id'])
            self.assertEqual(r['title'],p['text'][r['start_offset']:r['end_offset']])
            self.assertEqual(r['status'],'automatic_candidate')
        self.assertEqual(self.sql('SELECT COUNT(*) FROM persons')[0][0],0)
        self.assertEqual(self.sql('SELECT COUNT(*) FROM assertions')[0][0],0)
    def test_changed_archive_preserves_old_version(self):
        path=self.root/'updated.zip'
        with zipfile.ZipFile(path,'w') as z:z.writestr('exports/الكتاب أ.htm',source(body='نص مصحح مختلف عن الأصل.'))
        separate=self.root/'changed.sqlite'
        import_archive(separate,self.archive);import_archive(separate,path)
        with sqlite3.connect(separate) as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM archives').fetchone()[0],2)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM source_files').fetchone()[0],5)
    def test_reference_without_page_label(self):
        sid=self.sql("SELECT id FROM source_files WHERE zip_path='exports/دون ترقيم.htm'")[0][0]
        pid=self.sql('SELECT id FROM pages WHERE source_id=? AND ordinal=1',(sid,))[0][0]
        page=self.db.page(pid);self.assertEqual(page['printed_label'],'');self.assertEqual(page['ordinal'],1)
    def test_bad_query_and_unknown_id(self):
        with self.assertRaises(ValueError):self.db.search('***')
        with self.assertRaises(KeyError):self.db.page('unknown')
        self.db.search('" OR "',mode='words') # Treated as literal tokens, not SQL/FTS operators.
    def test_passage_references_and_no_inferred_break(self):
        row=next(r for r in self.db.search('أُسَامَة')['results'] if r['source_count']==3)
        repeated=self.db.duplicate_passages(row['text_id']);self.assertTrue(repeated)
        refs=self.db.passage_sources(repeated[0]['passage_id'])['results'];self.assertGreaterEqual(len(refs),3)
        page=self.db.page(row['page_id'])
        self.assertTrue(all(m['status']=='unresolved_mention' for m in page['mentions']))
        self.assertFalse(any('broken' in m for m in page['mentions']))

if __name__=='__main__':unittest.main(verbosity=2)
