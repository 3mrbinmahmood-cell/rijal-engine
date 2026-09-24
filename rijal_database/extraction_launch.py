"""Verify and restore the separate extraction layer, then open its inspector."""
import gzip,hashlib,io,json,os,shutil,sys,zipfile
from pathlib import Path
BASE=Path(__file__).resolve().parent

def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()

def verify_existing(path,expected,stamp,label):
    stat=path.stat();key={'path':str(path.resolve()),'bytes':stat.st_size,'mtime_ns':stat.st_mtime_ns,'expected_sha256':expected}
    try:known=json.loads(stamp.read_text())
    except (OSError,ValueError):known=None
    if known!=key:
        print('Checking '+label+'...',flush=True)
        if sha(path)!=expected:raise RuntimeError(label+' checksum mismatch. Keep a backup and restore the matching release file.')
        stamp.write_text(json.dumps(key))

class Parts(io.RawIOBase):
    def __init__(self,paths):super().__init__();self.paths=iter(paths);self.current=None
    def readable(self):return True
    def readinto(self,b):
        while True:
            if self.current is None:
                try:self.current=open(next(self.paths),'rb')
                except StopIteration:return 0
            n=self.current.readinto(b)
            if n:return n
            self.current.close();self.current=None
    def close(self):
        if self.current:self.current.close()
        super().close()

def prepare(base=BASE):
    base=Path(base);manifest=json.loads((base/'extraction_data/PAYLOAD.json').read_text(encoding='utf-8'));original=base/'rijal.sqlite'
    if not original.is_file():raise RuntimeError('Install and start Rijal Database V1 before this update.')
    verify_existing(original,manifest['base_sha256'],base/'extraction_data/BASE_CHECK.json','V1 source database')
    target=base/'extraction.sqlite'
    if target.exists():
        verify_existing(target,manifest['database_sha256'],base/'extraction_data/EXTRACTION_CHECK.json','Extraction database')
        return target
    paths=[]
    for part in manifest['parts']:
        if Path(part['filename']).name!=part['filename'] or Path(part['archive_filename']).name!=part['archive_filename']:raise RuntimeError('Invalid package filename')
        path=base/'extraction_data'/part['filename']
        if not path.is_file():
            for parent in (base.parent,base.parent.parent):
                archive=parent/part['archive_filename']
                if archive.is_file():
                    with zipfile.ZipFile(archive) as z,z.open('rijal_database/extraction_data/'+part['filename']) as inp,path.open('wb') as out:shutil.copyfileobj(inp,out,8*1024*1024)
                    break
        if not path.is_file() or path.stat().st_size!=part['bytes'] or sha(path)!=part['sha256']:raise RuntimeError('Missing or damaged update part: '+part['filename'])
        paths.append(path)
    if shutil.disk_usage(base).free<manifest['database_bytes']+64*1024*1024:raise RuntimeError('Insufficient space to unpack the extraction layer.')
    tmp=base/'extraction.sqlite.unpacking';h=hashlib.sha256();size=0;print('Restoring and verifying the extraction layer...',flush=True)
    try:
        with Parts(paths) as parts,io.BufferedReader(parts) as buf,gzip.GzipFile(fileobj=buf) as gz,tmp.open('wb') as out:
            for block in iter(lambda:gz.read(8*1024*1024),b''):h.update(block);size+=len(block);out.write(block)
            out.flush();os.fsync(out.fileno())
        if size!=manifest['database_bytes'] or h.hexdigest()!=manifest['database_sha256']:raise RuntimeError('Extraction database checksum mismatch')
        tmp.replace(target)
    finally:
        if tmp.exists():tmp.unlink()
    return target

if __name__=='__main__':
    try:prepare()
    except (OSError,ValueError,RuntimeError,EOFError,zipfile.BadZipFile) as e:print(str(e),file=sys.stderr);sys.exit(1)
    import extraction_server
    extraction_server.main()
