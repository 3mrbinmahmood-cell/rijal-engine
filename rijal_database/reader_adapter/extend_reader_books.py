"""Append new Shamela PageText books from an archive to a fixed reader ZIP.

Original reader books and the uploaded source archive remain unchanged.
"""
import argparse
import json
import re
import sys
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from lxml import html

TOOLS=Path(__file__).resolve().parents[1]/'tools'
sys.path.insert(0,str(TOOLS))
from import_sources import parse_source,extract_page

def clean(s):return re.sub(r'\s+',' ',s.replace('\u200c','').replace('\u200b','')).strip()
def extend(reader,source,output):
    reader,source,output=map(Path,(reader,source,output))
    if output.exists():raise ValueError('Use a fresh output path')
    with ZipFile(reader) as old,ZipFile(source) as archive:
        data=json.loads(old.read('data.js').decode('utf-8').removeprefix('window.SHAMELA_DATA=').rstrip(';'))
        toc=json.loads(old.read('toc.js').decode('utf-8').removeprefix('window.SHAMELA_TOC=').rstrip(';'))
        existing={b['title'] for b in data}
        groups={}
        for item in archive.infolist():
            if not item.filename.lower().endswith('.htm') or item.is_dir():continue
            parts=Path(item.filename).parts
            if len(parts)<3:raise ValueError('Unexpected source path: '+item.filename)
            groups.setdefault(parts[-2],[]).append(item.filename)
        added=[]
        for title,files in sorted(groups.items()):
            if title in existing:continue
            pages=[];entries=[];volumes=[];last_vol=None
            for name in sorted(files):
                elements,markers,encoding,meta,fallback=parse_source(archive.read(name))
                if fallback:raise ValueError('No PageText boundaries: '+name)
                for element in elements:
                    detail=extract_page(element);text=detail['text'];index=len(pages)
                    label=clean(detail['label'] or '') or f'{Path(name).stem}:{index+1}'
                    pages.append({'n':label,'text':text})
                    vol=clean(detail['part'] or Path(name).stem)
                    if vol!=last_vol:volumes.append({'title':vol,'page':index,'source':name});last_vol=vol
                    for start,end,_ in detail['titles']:
                        value=clean(text[start:end]);
                        if 4<len(value)<250 and not value.startswith(('المؤلف','الكتاب','الناشر','الطبعة','القسم','عدد الأجزاء')):
                            entries.append({'page':index,'title':value,'level':1 if value.startswith(('كتاب','الكتاب')) else 2})
            if not pages:raise ValueError('Empty source group: '+title)
            data.append({'title':title,'pages':pages})
            toc.append({'book':title,'volumes':volumes,'entries':entries})
            added.append({'title':title,'files':len(files),'pages':len(pages),'headings':len(entries)})
        if not added:raise ValueError('No new books in source archive')
        replacements={'data.js':('window.SHAMELA_DATA='+json.dumps(data,ensure_ascii=False,separators=(',',':'))+';').encode(),
                      'toc.js':('window.SHAMELA_TOC='+json.dumps(toc,ensure_ascii=False,separators=(',',':'))+';').encode(),
                      'BOOK_IMPORT_AUDIT.json':json.dumps({'source_archive':source.name,'existing_books_preserved':len(existing),'added':added},ensure_ascii=False,indent=2).encode()}
        replacements['index.html']=old.read('index.html').replace(b'V0.6.4',b'V0.6.5')
        with ZipFile(output,'w',ZIP_DEFLATED,compresslevel=6) as target:
            for member in old.infolist():
                if member.is_dir():target.writestr(member,b'');continue
                target.writestr(member,replacements.pop(member.filename,old.read(member.filename)))
            for name,body in replacements.items():target.writestr(name,body)
    with ZipFile(reader) as old,ZipFile(output) as new:
        if new.testzip():raise ValueError('Archive CRC failed')
        for name in old.namelist():
            if name not in ('data.js','toc.js','index.html') and old.read(name)!=new.read(name):raise ValueError('Unexpected change: '+name)
        result=json.loads(new.read('data.js').decode().removeprefix('window.SHAMELA_DATA=').rstrip(';'))
        for a,b in zip(data[:len(existing)],result):
            if a!=b:raise ValueError('Previous reader book changed')
    return added
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reader');parser.add_argument('source');parser.add_argument('output')
    args=parser.parse_args();print(json.dumps(extend(args.reader,args.source,args.output),ensure_ascii=False))
