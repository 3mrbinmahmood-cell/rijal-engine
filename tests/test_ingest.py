import tempfile
import unittest
import zipfile
from pathlib import Path
from rijal_engine.__main__ import connect, ingest, audit, normalize

class IngestTests(unittest.TestCase):
    def test_reimport_and_changed_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, b = root/'a.htm', root/'b.htm'
            a.write_text('<p>أبو المليح</p>',encoding='utf-8')
            b.write_bytes(a.read_bytes())
            with connect(root/'data.sqlite') as db:
                self.assertEqual(ingest(db,root),2)
                self.assertEqual(ingest(db,root),0)
                self.assertEqual(audit(db)['blobs'],1)
                a.write_text('<p>قتادة</p>',encoding='utf-8')
                self.assertEqual(ingest(db,a),1)
                self.assertEqual(audit(db)['occurrences'],3)
                self.assertEqual(audit(db)['segments'],2)
    def test_zip(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            archive = root/'batch.zip'
            with zipfile.ZipFile(archive,'w') as z:
                z.writestr('book/page.htm','<p>شعبة</p>')
            with connect(root/'data.sqlite') as db:
                self.assertEqual(ingest(db,archive),1)
    def test_search_key(self):
        self.assertEqual(normalize('أَبُو'),'ابو')

if __name__ == '__main__':
    unittest.main()
