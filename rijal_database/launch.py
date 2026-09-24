#!/usr/bin/env python3
"""One-time verified unpacking of database payload parts, then local startup."""
import gzip
import hashlib
import io
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

BASE=Path(__file__).resolve().parent

def hash_file(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()

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

def ensure_database(base=BASE):
    base=Path(base);target=base/'rijal.sqlite';manifest=base/'data/PAYLOAD.json'
    if target.is_file():return target
    if not manifest.is_file():raise RuntimeError('Database not found. Extract all database ZIP packages into the same folder first.')
    data=json.loads(manifest.read_text(encoding='utf-8'));paths=[]
    for item in data['parts']:
        if Path(item['filename']).name!=item['filename']:raise RuntimeError('Invalid database part filename.')
        path=base/'data'/item['filename']
        if not path.is_file() and item.get('archive_filename'):
            for folder in (base.parent,base.parent.parent):
                archive=folder/item['archive_filename']
                if archive.is_file():
                    print('Reading downloaded part: '+archive.name,flush=True)
                    with zipfile.ZipFile(archive) as z,z.open('rijal_database/data/'+item['filename']) as source,open(path,'wb') as target_part:
                        shutil.copyfileobj(source,target_part,8*1024*1024)
                    break
        if not path.is_file():raise RuntimeError('Missing database part: '+item['filename']+'. Extract all ZIP packages into the same parent folder.')
        paths.append(path)
    if shutil.disk_usage(base).free<data['database_bytes']+64*1024*1024:
        raise RuntimeError('Insufficient free disk space for the database. Required: '+str(round(data['database_bytes']/1024**3,2))+' GiB plus 64 MiB.')
    print('First launch: checking the compressed database parts...',flush=True)
    for item,path in zip(data['parts'],paths):
        if path.stat().st_size!=item['bytes'] or hash_file(path)!=item['sha256']:
            raise RuntimeError('Database part checksum mismatch: '+item['filename']+'. Download and extract that part again.')
    tmp=base/'rijal.sqlite.unpacking';h=hashlib.sha256();size=0;next_progress=256*1024*1024
    try:
        with Parts(paths) as source,io.BufferedReader(source,1024*1024) as buffered,gzip.GzipFile(fileobj=buffered) as gz,open(tmp,'wb') as out:
            for block in iter(lambda:gz.read(8*1024*1024),b''):
                out.write(block);h.update(block);size+=len(block)
                if size>=next_progress:print('Unpacking database: '+str(round(size*100/data['database_bytes']))+'%',flush=True);next_progress+=256*1024*1024
            out.flush();os.fsync(out.fileno())
        if size!=data['database_bytes'] or h.hexdigest()!=data['database_sha256']:
            raise RuntimeError('Database checksum mismatch after unpacking.')
        os.replace(tmp,target)
    finally:
        if tmp.exists():tmp.unlink()
    print('Database verified and ready. Future launches skip unpacking.',flush=True)
    return target

def main():
    if '--db' not in sys.argv:
        try:ensure_database()
        except (RuntimeError,OSError,EOFError) as e:print(str(e),file=sys.stderr);sys.exit(1)
    import server
    server.main()

if __name__=='__main__':main()
