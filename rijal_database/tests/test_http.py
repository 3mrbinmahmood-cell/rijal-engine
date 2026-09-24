import json,sys,threading,unittest,urllib.request,urllib.error,sqlite3,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));sys.path.insert(0,str(Path(__file__).resolve().parent))
from server import Handler,ThreadingHTTPServer
from identity_api import IdentityStore
import test_database as fixture

class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.DatabaseTests.setUpClass();cls.db=fixture.DatabaseTests.db
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler);cls.server.db=cls.db
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.url='http://127.0.0.1:'+str(cls.server.server_port)
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join();fixture.DatabaseTests.tearDownClass()
    def get(self,path,origin=None):
        req=urllib.request.Request(self.url+path,headers={'Origin':origin} if origin else {})
        return urllib.request.urlopen(req,timeout=10)
    def test_api_and_null_origin_for_file_reader(self):
        with self.get('/api/v1/search?q=%D8%A3%D8%B3%D8%A7%D9%85%D8%A9&limit=1','null') as r:
            self.assertEqual(r.headers['Access-Control-Allow-Origin'],'null')
            result=json.load(r);self.assertEqual(len(result['results']),1)
        with self.get('/api/v1/page/'+result['results'][0]['page_id']) as r:
            page=json.load(r);self.assertIn('text',page);self.assertIn('raw_sha256',page['citation'])
        with self.get('/api/v1/raw/'+page['source_id']) as r:
            self.assertEqual(r.headers['Content-Type'],'application/octet-stream')
            self.assertIn('attachment',r.headers['Content-Disposition']);self.assertIn(b'<html>',r.read())
    def test_web_assets_and_api_errors(self):
        for path in ['/','/app.js','/style.css','/reader-adapter.js','/reader-button.js','/integration-demo']:
            with self.get(path) as r:self.assertEqual(r.status,200)
        with self.assertRaises(urllib.error.HTTPError) as error:self.get('/api/v1/search?q=***')
        self.assertEqual(error.exception.code,400)
        with self.assertRaises(urllib.error.HTTPError) as error:self.get('/api/v1/page/unknown')
        self.assertEqual(error.exception.code,404)
    def test_local_reader_origin_and_external_origin(self):
        with self.get('/api/v1/stats','http://localhost:8000') as r:self.assertEqual(r.headers['Access-Control-Allow-Origin'],'http://localhost:8000')
        with self.get('/api/v1/stats','https://example.invalid') as r:self.assertIsNone(r.headers.get('Access-Control-Allow-Origin'))
        request=urllib.request.Request(self.url+'/api/v1/search',method='OPTIONS',headers={'Origin':'null','Access-Control-Request-Private-Network':'true'})
        with urllib.request.urlopen(request) as r:self.assertEqual(r.status,204);self.assertEqual(r.headers['Access-Control-Allow-Private-Network'],'true')
    def test_reader_identity_endpoint_uses_source_entry_id(self):
        entry_id=self.db.con().execute('SELECT id FROM entries LIMIT 1').fetchone()[0]
        with tempfile.TemporaryDirectory() as folder:
            identity=Path(folder)/'identity.sqlite'
            with sqlite3.connect(identity) as c:
                c.executescript('''CREATE TABLE identities(id TEXT,kind TEXT,
                  display_name TEXT,entry_count INTEGER);
                  CREATE TABLE entry_identity(entry_id TEXT,identity_id TEXT,
                  identity_kind TEXT,name_bucket_id TEXT,name_key TEXT,
                  name_label TEXT,classification TEXT,book_id TEXT,
                  source_id TEXT,opening_page_id TEXT);''')
                c.execute('INSERT INTO identities VALUES (?,?,?,?)',
                          ('person','reviewed_person','Test Name',1))
                c.execute('INSERT INTO entry_identity VALUES (?,?,?,?,?,?,?,?,?,?)',
                          (entry_id,'person','reviewed_person','bucket','key','Test Name',
                           'biography_candidate','book','source','page'))
            before=self.server.db.identities
            try:
                self.server.db.identities=IdentityStore(identity)
                with self.get('/api/v1/identity/entry/'+entry_id,'null') as response:
                    row=json.load(response)
                    self.assertEqual(row['identity_id'],'person')
                    self.assertEqual(response.headers['Access-Control-Allow-Origin'],'null')
                with self.get('/api/v1/identity/members/person') as response:
                    self.assertEqual(json.load(response)['results'][0]['entry_id'],entry_id)
            finally:self.server.db.identities=before

if __name__=='__main__':unittest.main(verbosity=2)
