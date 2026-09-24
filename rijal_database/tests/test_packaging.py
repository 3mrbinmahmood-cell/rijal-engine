import gzip,hashlib,json,sys,tempfile,unittest,zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from launch import ensure_database

class PackagingTests(unittest.TestCase):
    def setup_files(self,root):
        data=root/'data';data.mkdir();raw=('بيانات قاعدة الرجال المحفوظة\n'*300).encode();compressed=gzip.compress(raw);parts=[]
        for i,start in enumerate(range(0,len(compressed),37),1):
            blob=compressed[start:start+37];name=f'rijal.sqlite.gz.{i:03}'
            (data/name).write_bytes(blob);parts.append({'filename':name,'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest()})
        (data/'PAYLOAD.json').write_text(json.dumps({'parts':parts,'database_bytes':len(raw),'database_sha256':hashlib.sha256(raw).hexdigest()}))
        return raw,parts
    def test_multi_part_reconstruction_and_repeat_launch(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);raw,parts=self.setup_files(root);result=ensure_database(root)
            self.assertEqual(result.read_bytes(),raw)
            self.assertEqual(ensure_database(root),result)
    def test_missing_or_changed_part_is_not_silently_used(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);raw,parts=self.setup_files(root);part=root/'data'/parts[0]['filename'];part.unlink()
            with self.assertRaises(RuntimeError):ensure_database(root)
            part.write_bytes(b'wrong bytes')
            with self.assertRaises(RuntimeError):ensure_database(root)
            self.assertFalse((root/'rijal.sqlite').exists())
    def test_extract_missing_part_from_adjacent_download_zip(self):
        with tempfile.TemporaryDirectory() as d:
            downloads=Path(d);root=downloads/'rijal_database';root.mkdir();raw,parts=self.setup_files(root)
            part=parts[-1];part['archive_filename']='Part02.zip';file=root/'data'/part['filename']
            with zipfile.ZipFile(downloads/'Part02.zip','w') as z:z.write(file,'rijal_database/data/'+file.name)
            file.unlink()
            manifest=root/'data/PAYLOAD.json';data=json.loads(manifest.read_text());data['parts']=parts;manifest.write_text(json.dumps(data))
            self.assertEqual(ensure_database(root).read_bytes(),raw)

if __name__=='__main__':unittest.main(verbosity=2)
