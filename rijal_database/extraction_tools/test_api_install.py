import gzip,hashlib,json,sqlite3,sys,tempfile,threading,unittest,urllib.error,urllib.request,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tools'),str(Path(__file__).parent)]
# In the assembled update, server.py is provided by the installed V1 package.
if not (ROOT/'server.py').exists():sys.path.append(str(ROOT.parents[2]/'rijal_build/package/rijal_database'))
from extraction_server import Extraction,Handler,ThreadingHTTPServer
from extraction_launch import prepare
from test_extraction import fixture
from extract import build
from common import file_hash

class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name);cls.base=cls.root/'base.sqlite';cls.out=cls.root/'extraction.sqlite'
        fixture(cls.base);build(cls.base,cls.out,cls.root/'reports',file_hash(cls.base));cls.api=Extraction(cls.base,cls.out)
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);cls.server.db=cls.api;cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start();cls.url='http://127.0.0.1:'+str(cls.server.server_address[1])
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.tmp.cleanup()
    def test_biography_search_and_paginated_continuation(self):
        r=self.api.biographies('أحمد بن محمد');self.assertEqual(len(r['results']),1)
        r=self.api.biography('a',limit=1);self.assertTrue(r['has_more']);self.assertEqual(r['segments'][0]['page_id'],'p1')
        r=self.api.biography('a',offset=1,limit=1);self.assertEqual(r['segments'][0]['page_id'],'p2')
    def test_literal_statements_with_type_origin_and_owner_filters(self):
        r=self.api.statements('ثقة',kind='assessment');self.assertEqual(len(r['results']),2)
        self.assertTrue(all('ثِقَةٌ' in s['quote'] for s in r['results']))
        self.assertEqual(len(self.api.statements(origin='footnote')['results']),1)
        self.assertTrue(all(s['biography_id']=='a' for s in self.api.statements(bio='a')['results']))
    def test_http_stats_errors_and_static_ui(self):
        with urllib.request.urlopen(self.url+'/api/stats') as r:self.assertTrue(json.load(r)['read_only'])
        with urllib.request.urlopen(self.url+'/') as r:self.assertIn('التراجم'.encode(),r.read())
        for path,status in [('/api/statements?kind=invalid',400),('/api/biography/missing',404),('/api/page/missing',404),('/missing',404)]:
            with self.assertRaises(urllib.error.HTTPError) as caught:urllib.request.urlopen(self.url+path)
            self.assertEqual(caught.exception.code,status)

class InstallTests(unittest.TestCase):
    def package(self,root):
        data=root/'extraction_data';data.mkdir();base=b'unchanged source database';(root/'rijal.sqlite').write_bytes(base)
        raw=('قاعدة المقتطفات\n'*100).encode();blob=gzip.compress(raw);parts=[]
        for i,a in enumerate(range(0,len(blob),25)):
            value=blob[a:a+25];name=f'extraction.gz.{i:03d}';(data/name).write_bytes(value)
            parts.append({'filename':name,'bytes':len(value),'sha256':hashlib.sha256(value).hexdigest(),'archive_filename':f'part{i}.zip'})
        manifest={'base_sha256':hashlib.sha256(base).hexdigest(),'database_sha256':hashlib.sha256(raw).hexdigest(),'database_bytes':len(raw),'parts':parts}
        (data/'PAYLOAD.json').write_text(json.dumps(manifest));return raw,manifest
    def test_restore_and_adjacent_zip(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'rijal_database';root.mkdir();raw,m=self.package(root);part=m['parts'][-1];p=root/'extraction_data'/part['filename']
            with zipfile.ZipFile(root.parent/part['archive_filename'],'w') as z:z.write(p,'rijal_database/extraction_data/'+p.name)
            p.unlink();self.assertEqual(prepare(root).read_bytes(),raw);self.assertEqual(prepare(root).read_bytes(),raw)
    def test_wrong_base_and_damaged_part_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);raw,m=self.package(root);base=(root/'rijal.sqlite').read_bytes();(root/'rijal.sqlite').write_bytes(b'wrong')
            with self.assertRaises(RuntimeError):prepare(root)
            (root/'rijal.sqlite').write_bytes(base);(root/'extraction_data'/m['parts'][0]['filename']).write_bytes(b'wrong')
            with self.assertRaises(RuntimeError):prepare(root)
            self.assertFalse((root/'extraction.sqlite').exists())
    def test_changed_existing_extraction_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);raw,m=self.package(root);prepare(root);(root/'extraction.sqlite').write_bytes(b'changed')
            with self.assertRaises(RuntimeError):prepare(root)

if __name__=='__main__':unittest.main(verbosity=2)
