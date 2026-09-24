#!/usr/bin/env python3
"""Idempotent Shamela ZIP importer; requires lxml only for rebuilding imports.
Original archive bytes are retained externally, never rewritten or extracted over.
Each source file is one atomic transaction. Failed files stay visible for retry.
"""
import argparse
import datetime
import json
import re
import sqlite3
import sys
import time
import zipfile
from pathlib import Path
from lxml import html
from common import VERSION, connect, digest, file_hash, normalize

BASE = Path(__file__).resolve().parents[1]
MARKER = re.compile(rb'<div\b[^>]*\bclass\s*=\s*[\'"][^\'"]*\bPageText\b[^\'"]*[\'"][^>]*>', re.I)
NUMBER = re.compile(r'^[\s\u200b-\u200f]*(?:[\d٠-٩]{1,6})\s*[-–ـ]')
NAME = re.compile(r'(?:\b(?:بن|ابن|أبو|أبي|أبا|أم|بنت)\b)')
NON_PERSON = re.compile(r'^(?:باب|فصل|كتاب|حرف|مقدمة|المقدمة|الفهرس|فهارس|الجزء|الباب|المحتويات|تمهيد|تنبيه|المبحث|المطلب)\b')
RELATION = re.compile(r'(?<![\w])(?:و)?(روى عنه|روى عن|سمع من|والد|ابنه|ابنته)(?![\w])')

def hasclass(el, value): return value in (el.get('class') or '').split()
def element_text(el): return ''.join(el.itertext())

def extract_page(el):
    chunks=[]; count=0; spans=[]; titles=[]; number_starts=[]
    def emit(value):
        nonlocal count
        if value: chunks.append(value); count += len(value)
    def newline():
        if chunks and not chunks[-1].endswith('\n'): emit('\n')
    def walk(node, footnote=False):
        tag=node.tag if isinstance(node.tag,str) else ''
        if not tag or tag in ('script','style') or hasclass(node,'PageHead'): return
        block=tag in ('div','p','br','li','tr','h1','h2','h3','h4','hr')
        title=hasclass(node,'title') or node.get('data-type')=='title'
        foot=hasclass(node,'footnote')
        numbered=hasclass(node,'punct') and NUMBER.match(element_text(node))
        if block or title or numbered: newline()
        start=count
        if numbered and not footnote: number_starts.append(start)
        emit(node.text)
        for child in node:
            walk(child,footnote or foot)
            emit(child.tail)
        end=count
        if title and end>start:
            spans.append(('heading',start,end,node.get('id')))
            if not footnote: titles.append((start,end,node.get('id')))
        if foot and end>start: spans.append(('footnote',start,end,node.get('id')))
        elif node.get('id') and not title: spans.append(('anchor',start,end,node.get('id')))
        if block or title: newline()
        elif tag in ('td','th'): emit('\t')
    walk(el)
    text=''.join(chunks)
    header=el.xpath('.//*[contains(concat(" ",normalize-space(@class)," ")," PageHead ")]')
    part=el.xpath('.//*[contains(concat(" ",normalize-space(@class)," ")," PartName ")]')
    label=el.xpath('.//*[contains(concat(" ",normalize-space(@class)," ")," PageNumber ")]')
    return {'text':text,'spans':spans,'titles':titles,'number_starts':number_starts,
            'header':element_text(header[0]) if header else None,
            'part':element_text(part[0]) if part else None,
            'label':element_text(label[0]) if label else None,'anchor':el.get('id')}

def decode(raw):
    for encoding in ('utf-8-sig','cp1256'):
        try: return raw.decode(encoding),encoding
        except UnicodeDecodeError: pass
    raise ValueError('Cannot decode source losslessly as UTF-8 or CP1256')

def parse_source(raw):
    decoded,encoding=decode(raw)
    # Shamela exports contain unmatched </p>. Preserve these visual boundaries
    # as literal newlines before lxml repairs HTML. Never alter source bytes.
    decoded=re.sub(r'</p\s*>','\n</p>',decoded,flags=re.I)
    root=html.fromstring(decoded,parser=html.HTMLParser(encoding='utf-8',recover=True))
    els=root.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," PageText ")]')
    markers=list(MARKER.finditer(raw))
    fallback=not els
    if fallback: els=[root.find('body') if root.find('body') is not None else root]
    if markers and len(markers)!=len(els): raise ValueError(f'Page marker mismatch: raw={len(markers)}, parsed={len(els)}')
    meta={}
    first=extract_page(els[0])['text']
    # Metadata title labels can be on their own line after structural extraction.
    for line in re.sub(r':\s*\n',': ',first).splitlines():
        m=re.match(r'\s*([^:：]{2,45})\s*[:：]\s*(.+)',line)
        if m: meta[m[1].strip()]=m[2].strip()
    title=root.find('.//title')
    meta['_html_title']=element_text(title) if title is not None else ''
    return els,markers,encoding,meta,fallback

def candidates(page,metadata_page=False):
    if metadata_page: return []
    text=page['text']; found={}; foot=[(s,e) for k,s,e,a in page['spans'] if k=='footnote']
    def isfoot(start): return any(s<=start<e for s,e in foot)
    def add(start,end,kind):
        value=text[start:end]
        plain=normalize(value)
        if len(plain)<5 or len(plain)>350 or isfoot(start): return
        cleaned=re.sub(r'^[\d\W_]+','',plain)
        if NON_PERSON.match(cleaned): return
        # This is a source-heading candidate, never a verified person.
        found[start]=(start,end,value,kind)
    for start,end,anchor in page['titles']:
        value=text[start:end]
        if NUMBER.match(value) or NAME.search(value): add(start,end,'biography_heading_candidate')
        elif len(normalize(value))<=180: add(start,end,'source_heading')
    for start in page['number_starts']:
        end=text.find('\n',start+1)
        if end<0: end=len(text)
        # A punctuation marker is often alone, followed by a styled heading.
        line=text[start:end]
        if len(normalize(line))<8:
            next_end=text.find('\n',end+1)
            end=next_end if next_end>=0 else len(text)
        if any(start<=s<min(end,start+25) for s in found): continue
        if NAME.search(text[start:min(end,start+75)]):
            add(start,min(end,start+300),'numbered_entry_candidate')
    return sorted(found.values())

def store_payload(con,text):
    h=digest(text)
    row=con.execute('SELECT id FROM page_texts WHERE sha256=?',(h,)).fetchone()
    if row: return row[0],False
    tid=con.execute('INSERT INTO page_texts(sha256,text,char_count) VALUES(?,?,?)',(h,text,len(text))).lastrowid
    con.execute('INSERT INTO page_fts(rowid,search_text) VALUES(?,?)',(tid,normalize(text)))
    # Exact paragraph reuse: keep offsets into preserved page text, not copies.
    for m in re.finditer(r'[^\n]+',text):
        if len(m[0].strip())<80: continue
        ph=digest(m[0]); row=con.execute('SELECT id FROM passages WHERE sha256=?',(ph,)).fetchone()
        if row: pid=row[0]
        else:
            pid=con.execute('INSERT INTO passages(sha256,normalized_sha256,text_id,start_offset,end_offset) VALUES(?,?,?,?,?)',
                (ph,digest(normalize(m[0])),tid,m.start(),m.end())).lastrowid
        con.execute('INSERT OR IGNORE INTO passage_locations VALUES(?,?,?,?)',(pid,tid,m.start(),m.end()))
    return tid,True

def import_archive(db,archive,max_files=None,group_filter=None):
    archive=Path(archive).resolve(); db=Path(db); db.parent.mkdir(parents=True,exist_ok=True)
    con=connect(db)
    con.execute('PRAGMA journal_mode=DELETE'); con.execute('PRAGMA synchronous=FULL')
    con.execute('PRAGMA cache_size=-131072'); con.execute('PRAGMA temp_store=MEMORY')
    con.executescript((BASE/'schema.sql').read_text())
    con.execute('INSERT OR REPLACE INTO metadata VALUES(?,?)',('schema_version','1'))
    con.execute('INSERT OR REPLACE INTO metadata VALUES(?,?)',('importer_version',VERSION))
    con.execute('INSERT OR REPLACE INTO metadata VALUES(?,?)',('normalization_version','arabic_search_v1'))
    aid=file_hash(archive); start=time.monotonic(); processed=0; skipped=0; failures=0
    with zipfile.ZipFile(archive) as z:
        selected=[(i,info) for i,info in enumerate(z.infolist()) if not info.is_dir() and info.filename.lower().endswith(('.htm','.html'))]
        con.execute('INSERT OR IGNORE INTO archives VALUES(?,?,?,?,?,?)',(aid,archive.name,archive.stat().st_size,len(selected),datetime.datetime.now(datetime.timezone.utc).isoformat(),'importing'))
        con.commit()
        # Strip a common wrapper folder only when all entries have that wrapper.
        roots={info.filename.split('/')[0] for _,info in selected}
        wrapped=len(roots)==1 and all('/' in info.filename for _,info in selected)
        for ix,info in selected:
            parts=info.filename.split('/')[1:] if wrapped else info.filename.split('/')
            group=parts[0] if len(parts)>1 else Path(parts[0]).stem
            if group_filter and group not in group_filter: continue
            if max_files is not None and processed>=max_files: break
            sid=digest(aid+'\0'+str(ix)+'\0'+info.filename)
            prior=con.execute('SELECT status FROM source_files WHERE id=?',(sid,)).fetchone()
            if prior and prior['status']=='ok': skipped+=1; continue
            raw=z.read(info); rawhash=digest(raw); bid=digest(aid+'\0'+group)
            try:
                els,markers,encoding,meta,fallback=parse_source(raw)
                title=meta.get('الكتاب') or group
                with con:
                    con.execute('INSERT OR IGNORE INTO books VALUES(?,?,?,?,?,?,?,?,?)',
                        (bid,aid,group,title,meta.get('المؤلف'),meta.get('الطبعة'),meta.get('الناشر') or meta.get('دار النشر'),meta.get('القسم'),json.dumps(meta,ensure_ascii=False)))
                    con.execute('INSERT OR REPLACE INTO source_files VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                        (sid,aid,ix,info.filename,bid,rawhash,len(raw),encoding,json.dumps(meta,ensure_ascii=False),len(els),len(markers),'ok',None))
                    for ordinal,el in enumerate(els):
                        page=extract_page(el);text=page['text'];tid,new=store_payload(con,text)
                        pid=digest(sid+'\0'+str(ordinal))
                        rawstart=markers[ordinal].start() if markers else 0
                        rawend=markers[ordinal+1].start() if markers and ordinal+1<len(markers) else len(raw)
                        con.execute('INSERT INTO pages VALUES(?,?,?,?,?,?,?,?,?,?)',
                            (pid,sid,tid,ordinal,page['label'],page['part'],page['header'],page['anchor'],rawstart,rawend))
                        con.executemany('INSERT INTO spans(page_id,kind,start_offset,end_offset,anchor) VALUES(?,?,?,?,?)',[(pid,*s) for s in page['spans']])
                        entries=candidates(page,ordinal==0 and bool(meta.get('الكتاب')))
                        entryrefs=[]
                        for s,e,title,kind in entries:
                            eid=digest(pid+'\0'+str(s))
                            rowid=con.execute('INSERT INTO entries(id,page_id,start_offset,end_offset,title,search_title,kind) VALUES(?,?,?,?,?,?,?)',
                                (eid,pid,s,e,title,normalize(title),kind)).lastrowid
                            con.execute('INSERT INTO entry_fts(rowid,search_title) VALUES(?,?)',(rowid,normalize(title)))
                            entryrefs.append((s,eid))
                        foot=[(s,e) for k,s,e,a in page['spans'] if k=='footnote']
                        mentions=[]
                        for m in RELATION.finditer(text):
                            s=m.start();end=min(len(text),s+600)
                            bounds=[text.find(c,m.end(),end) for c in ('\n','.')]
                            bounds=[b for b in bounds if b>=0]
                            if bounds: end=min(bounds)
                            in_foot=any(a<=s<b for a,b in foot)
                            prior=[eid for pos,eid in entryrefs if pos<=s]
                            trigger=m[1];kind='student_mention' if trigger=='روى عنه' else 'teacher_mention' if trigger in ('روى عن','سمع من') else 'family_mention'
                            mentions.append((pid,prior[-1] if prior and not in_foot else None,kind,trigger,s,end,int(in_foot)))
                        con.executemany('INSERT INTO mentions(page_id,entry_id,kind,trigger,start_offset,end_offset,in_footnote) VALUES(?,?,?,?,?,?,?)',mentions)
                    if fallback:
                        con.execute('INSERT OR REPLACE INTO metadata VALUES(?,?)',('fallback:'+sid,'No PageText markers; complete document imported as one page.'))
                processed+=1
            except Exception as exc:
                con.rollback();failures+=1
                with con:
                    con.execute('INSERT OR IGNORE INTO books VALUES(?,?,?,?,?,?,?,?,?)',(bid,aid,group,group,None,None,None,None,'{}'))
                    con.execute('INSERT OR REPLACE INTO source_files VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                        (sid,aid,ix,info.filename,bid,rawhash,len(raw),'unknown','{}',0,0,'failed',str(exc)))
                print(json.dumps({'error':info.filename,'detail':str(exc)},ensure_ascii=False),flush=True)
            if processed%40==0 or failures:
                print(json.dumps({'imported':processed,'skipped':skipped,'failed':failures,'total':len(selected),'elapsed_s':round(time.monotonic()-start),'file':info.filename},ensure_ascii=False),flush=True)
        n=con.execute("SELECT COUNT(*) FROM source_files WHERE archive_id=? AND status='ok'",(aid,)).fetchone()[0]
        with con: con.execute('UPDATE archives SET status=? WHERE id=?',('complete' if n==len(selected) else 'partial',aid))
    con.close()
    return {'archive_sha256':aid,'imported':processed,'skipped':skipped,'failed':failures,'elapsed_s':round(time.monotonic()-start,2)}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('archive');p.add_argument('--db',default=str(BASE/'rijal.sqlite'))
    p.add_argument('--max-files',type=int);p.add_argument('--group',action='append')
    a=p.parse_args();result=import_archive(a.db,a.archive,a.max_files,a.group);print(json.dumps(result,ensure_ascii=False,indent=2))
    sys.exit(1 if result['failed'] else 0)
