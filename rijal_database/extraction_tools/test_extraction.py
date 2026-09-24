import hashlib,json,sqlite3,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tools'),str(Path(__file__).parent)]
from extract import build,detect
from common import file_hash

def fixture(path):
    c=sqlite3.connect(path)
    c.executescript('''
    CREATE TABLE source_files(id TEXT PRIMARY KEY,book_id TEXT,zip_path TEXT,zip_index INT);
    CREATE TABLE pages(id TEXT PRIMARY KEY,source_id TEXT,text_id INT,ordinal INT);
    CREATE INDEX source_pages ON pages(source_id,ordinal);
    CREATE TABLE page_texts(id INTEGER PRIMARY KEY,text TEXT);
    CREATE TABLE entries(id TEXT PRIMARY KEY,page_id TEXT,start_offset INT,end_offset INT,title TEXT);
    CREATE INDEX entry_page ON entries(page_id,start_offset);
    CREATE TABLE chronology_records(entry_id TEXT PRIMARY KEY,name_label TEXT);
    CREATE TABLE spans(page_id TEXT,kind TEXT,start_offset INT,end_offset INT);
    CREATE INDEX spans_page ON spans(page_id);
    CREATE VIEW citations AS SELECT p.id AS page_id,'كتاب الاختبار' AS title,'الجزء الأول' AS part_label,CAST(p.ordinal AS TEXT) AS printed_label,s.book_id,s.zip_path,p.text_id,p.ordinal FROM pages p JOIN source_files s ON s.id=p.source_id;
    ''')
    c.executemany('INSERT INTO source_files VALUES(?,?,?,?)',[('f1','b1','one.htm',0),('f2','b1','two.htm',1)])
    texts=[('p1','f1',0,'أحمد بن محمد بن زيد\nقال أبو زرعة: ثِقَةٌ.\nروى عن أبيه.\nقال المحقق: إسناده ضعيف.\n'),
      ('p2','f1',1,'تُوُفِّيَ سنة ثلاثمائة.\n'),
      ('p3','f1',2,'تتمة النص.\nباب آخر\nقال أحمد: ضعيف.\nمحمد بن عبد الله\nقال أحمد: ليس به بأس.\n'),
      ('p4','f2',0,'روى عنه ابنه.\n'),
      ('p5','f2',1,'إبراهيم بن محمد\nقال أبو زرعة: ثِقَةٌ.\n')]
    for i,(pid,sid,ord,text) in enumerate(texts,1):
        c.execute('INSERT INTO page_texts VALUES(?,?)',(i,text));c.execute('INSERT INTO pages VALUES(?,?,?,?)',(pid,sid,i,ord))
    entries=[('a','p1','أحمد بن محمد بن زيد',True),('chapter','p3','باب آخر',False),('b','p3','محمد بن عبد الله',True),('c','p5','إبراهيم بن محمد',True)]
    lookup={p:t for p,s,o,t in texts}
    for eid,pid,title,bio in entries:
        a=lookup[pid].index(title);c.execute('INSERT INTO entries VALUES(?,?,?,?,?)',(eid,pid,a,a+len(title),title))
        if bio:c.execute('INSERT INTO chronology_records VALUES(?,?)',(eid,title))
    a=lookup['p1'].index('قال المحقق');c.execute('INSERT INTO spans VALUES(?,?,?,?)',('p1','footnote',a,len(lookup['p1'])))
    c.commit();c.close()

class DetectionTests(unittest.TestCase):
    def test_diacritics_and_direction(self):
        t='رَوَى عَنْ زيد. رَوَى عَنْهُ ابنه. قال أحمد: ثِقَةٌ.'
        r=detect(t,0,len(t),[]);types=[h['kind'] for s in r for h in s['triggers']]
        self.assertEqual(types.count('teachers'),1);self.assertEqual(types.count('students'),1)
        for s in r:
            self.assertEqual(s['quote'],t[s['start']:s['end']])
            for h in s['triggers']:self.assertEqual(h['quote'],t[h['start']:h['end']])
    def test_footnotes_do_not_supply_main_attribution(self):
        t='قال أحمد: ثقة. قال المحقق: ضعيف.';a=t.index('قال المحقق')
        r=detect(t,0,len(t),[(a,len(t))]);self.assertEqual([s['origin'] for s in r],['main_text','footnote'])
        self.assertEqual(r[0]['attribution_text'],'أحمد');self.assertEqual(r[1]['attribution_text'],'المحقق')
    def test_report_assessment_not_narrator_grade(self):
        t='قال أحمد: إسناده ضعيف.';s=detect(t,0,len(t),[])[0]
        self.assertEqual(s['subject_status'],'possible_report_or_chain_assessment')
        self.assertIsNone(s['attribution_text'])
    def test_multiple_types_share_literal_quote(self):
        t='ولد سنة مائتين وتوفي سنة ثلاثمائة.';r=detect(t,0,len(t),[])
        self.assertEqual(len(r),1);self.assertEqual({h['kind'] for h in r[0]['triggers']},{'birth','death'})
    def test_multiline_trigger_and_long_context(self):
        t='روى\nعن زيد '+('لفظ محفوظ '*200)+' ثقة.'
        for s in detect(t,0,len(t),[]):
            self.assertEqual(s['quote'],t[s['start']:s['end']])
            for h in s['triggers']:self.assertLessEqual(h['end'],s['end'])
    def test_format_marks_and_marked_conjunction(self):
        t='\u200cوَتُوُفِّيَ سنة ثلاثمائة.'
        self.assertEqual([h['kind'] for s in detect(t,0,len(t),[]) for h in s['triggers']],['death'])

class FullExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name);cls.base=cls.root/'base.sqlite';cls.out=cls.root/'extraction.sqlite'
        fixture(cls.base);cls.sha=file_hash(cls.base);cls.report=build(cls.base,cls.out,cls.root/'reports',cls.sha)
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def query(self,sql,args=()):
        with sqlite3.connect(self.out) as c:return c.execute(sql,args).fetchall()
    def test_continuation_stops_at_any_heading(self):
        self.assertEqual(self.query('SELECT page_id,role FROM biography_segments WHERE biography_id=? ORDER BY id',('a',)),[('p1','opening'),('p2','continuation'),('p3','continuation')])
        self.assertEqual(self.query("SELECT biography_id FROM statements WHERE page_id='p3' AND subject_status='unassigned_source_context'"),[(None,)])
    def test_source_file_boundary_is_never_crossed(self):
        self.assertEqual(self.query("SELECT biography_id FROM statements WHERE page_id='p4'"),[(None,)])
        self.assertEqual(self.query("SELECT boundary_status FROM biographies WHERE id='b'"),[('source_file_end_unresolved',)])
    def test_repeated_quote_keeps_both_occurrences(self):
        self.assertEqual(self.query("SELECT COUNT(*),COUNT(DISTINCT text_id) FROM statements WHERE attribution_text='أبو زرعة'"),[(2,1)])
    def test_all_checks_pass_and_base_is_unchanged(self):
        self.assertFalse(any(self.report['offset_audit'].values()));self.assertEqual(file_hash(self.base),self.sha)
        self.assertEqual(self.report['summary']['biographies'],3);self.assertEqual(self.report['summary']['identity_merges_performed'],0)
    def test_fts_exact_quote_remains_unchanged(self):
        self.assertEqual(self.query("SELECT COUNT(*) FROM statement_fts WHERE statement_fts MATCH 'ثقة'"),[(1,)])
    def test_existing_output_is_protected(self):
        with self.assertRaises(ValueError):build(self.base,self.out,self.root/'reports',self.sha)

if __name__=='__main__':unittest.main(verbosity=2)
