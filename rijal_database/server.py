#!/usr/bin/env python3
"""Read-only, loopback-only database service and Arabic source browser.
Run with Python 3.10+; the prebuilt database needs no extra Python packages.
"""
import argparse
from contextlib import closing
import json
import mimetypes
import re
import sqlite3
import sys
import threading
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse, quote
sys.path.insert(0,str(Path(__file__).resolve().parent/'tools'))
from common import VERSION, connect, digest, normalize
try:from .identity_api import IdentityStore
except ImportError:from identity_api import IdentityStore

BASE=Path(__file__).resolve().parent

def fts_query(query,mode):
    tokens=re.findall(r'[^\W_]+',normalize(query),re.UNICODE)
    if not tokens: raise ValueError('اكتب اسمًا أو كلمة للبحث.')
    if len(query)>200 or len(tokens)>20: raise ValueError('الحد الأقصى للاستعلام ٢٠ كلمة و٢٠٠ حرف.')
    if mode=='phrase': return '"'+' '.join(tokens)+'"'
    quoted=['"'+t+'"' for t in tokens]
    if mode=='prefix': quoted[-1]+='*'
    return ' AND '.join(quoted)

def excerpt(text,query,width=340):
    # Normalized offsets cannot index original text. Locate a matching original
    # token instead; fall back to a source opening when no exact token survives.
    tokens=set(re.findall(r'[^\W_]+',normalize(query)))
    at=0
    for m in re.finditer(r'\S+',text):
        if tokens.intersection(re.findall(r'[^\W_]+',normalize(m[0]))): at=m.start();break
    start=max(0,at-65);end=min(len(text),start+width)
    return {'text':text[start:end],'start_offset':start,'end_offset':end}

class Database:
    def __init__(self,path,archives=(),identity=None,dates=None,graph=None):
        self.path=Path(path);self.archives=[Path(p) for p in archives]
        self.identities=IdentityStore(identity,dates,graph)
    def con(self): return connect(self.path,readonly=True)
    def stats(self):
        with closing(self.con()) as c:
            row=c.execute("SELECT value FROM metadata WHERE key='audit_summary'").fetchone()
            result=json.loads(row[0]) if row else {t:c.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ('books','source_files','pages','page_texts','entries','mentions')}
            result['version']=VERSION;result['read_only']=True
            return result
    def books(self,q=''):
        with closing(self.con()) as c:
            rows=c.execute('SELECT b.*, (SELECT COUNT(*) FROM source_files s WHERE s.book_id=b.id) AS files FROM books b ORDER BY b.source_group').fetchall()
            return [dict(r) for r in rows if not q or normalize(q) in normalize(r['title']+' '+r['source_group'])]
    def search(self,q,scope='pages',mode='words',book=None,limit=30,offset=0):
        if scope not in ('pages','entries') or mode not in ('words','phrase','exact','prefix'): raise ValueError('Invalid search mode')
        limit=max(1,min(100,int(limit)));offset=max(0,int(offset))
        fts=fts_query(q,mode);params=[fts]
        with closing(self.con()) as c:
            if scope=='entries':
                sql='SELECT e.*, bm25(entry_fts) AS rank FROM entry_fts JOIN entries e ON e.rowid=entry_fts.rowid WHERE entry_fts MATCH ?'
                if mode=='exact': sql+=' AND instr(e.title,?)>0';params.append(q)
                if book: sql+=' AND EXISTS(SELECT 1 FROM pages p JOIN source_files s ON s.id=p.source_id WHERE p.id=e.page_id AND s.book_id=?)';params.append(book)
                sql+=' ORDER BY rank,e.rowid LIMIT ? OFFSET ?';params.extend([limit+1,offset])
                rows=c.execute(sql,params).fetchall();results=[]
                for row in rows[:limit]:
                    r=dict(row);r['citation']=dict(c.execute('SELECT * FROM citations WHERE page_id=?',(r['page_id'],)).fetchone());results.append(r)
            else:
                sql='SELECT t.id,t.text,bm25(page_fts) AS rank FROM page_fts JOIN page_texts t ON t.id=page_fts.rowid WHERE page_fts MATCH ?'
                if mode=='exact': sql+=' AND instr(t.text,?)>0';params.append(q)
                if book: sql+=' AND EXISTS(SELECT 1 FROM pages p JOIN source_files s ON s.id=p.source_id WHERE p.text_id=t.id AND s.book_id=?)';params.append(book)
                sql+=' ORDER BY rank,t.id LIMIT ? OFFSET ?';params.extend([limit+1,offset])
                rows=c.execute(sql,params).fetchall();results=[]
                for row in rows[:limit]:
                    where='text_id=?';p=[row['id']]
                    if book: where+=' AND book_id=?';p.append(book)
                    citation=dict(c.execute('SELECT * FROM citations WHERE '+where+' ORDER BY page_id LIMIT 1',p).fetchone())
                    count=c.execute('SELECT COUNT(*) FROM citations WHERE '+where,p).fetchone()[0]
                    results.append({'text_id':row['id'],'page_id':citation['page_id'],'citation':citation,'source_count':count,'excerpt':excerpt(row['text'],q)})
        return {'query':q,'scope':scope,'mode':mode,'limit':limit,'offset':offset,'has_more':len(rows)>limit,'results':results,'grouping':'exact_page_text' if scope=='pages' else 'source_entry'}
    def sources(self,text_id,limit=100,offset=0):
        limit=max(1,min(500,int(limit)));offset=max(0,int(offset))
        with closing(self.con()) as c:
            rows=c.execute('SELECT * FROM citations WHERE text_id=? ORDER BY title,zip_path,ordinal LIMIT ? OFFSET ?',(int(text_id),limit+1,offset)).fetchall()
            return {'results':[dict(r) for r in rows[:limit]],'has_more':len(rows)>limit,'offset':offset,'limit':limit}
    def page(self,pid):
        with closing(self.con()) as c:
            row=c.execute('SELECT p.*,t.text FROM pages p JOIN page_texts t ON t.id=p.text_id WHERE p.id=?',(pid,)).fetchone()
            if not row: raise KeyError('Page not found')
            result=dict(row);result['citation']=dict(c.execute('SELECT * FROM citations WHERE page_id=?',(pid,)).fetchone())
            result['spans']=[dict(r) for r in c.execute('SELECT kind,start_offset,end_offset,anchor FROM spans WHERE page_id=?',(pid,))]
            result['entries']=[dict(r) for r in c.execute('SELECT * FROM entries WHERE page_id=? ORDER BY start_offset',(pid,))]
            result['mentions']=[dict(r) for r in c.execute('SELECT * FROM mentions WHERE page_id=? ORDER BY start_offset',(pid,))]
            for r in result['mentions']: r['evidence']=result['text'][r['start_offset']:r['end_offset']]
            for label,op,direction in (('previous','<','DESC'),('next','>','ASC')):
                p=c.execute(f'SELECT id FROM pages WHERE source_id=? AND ordinal{op}? ORDER BY ordinal {direction} LIMIT 1',(row['source_id'],row['ordinal'])).fetchone()
                if not p:
                    # Cross file boundaries only within the same source group.
                    p=c.execute(f'''SELECT p.id FROM pages p JOIN source_files s ON s.id=p.source_id
                        WHERE s.book_id=? AND s.zip_index {op} ? ORDER BY s.zip_index {direction},p.ordinal {direction} LIMIT 1''',
                        (result['citation']['book_id'],result['citation']['zip_index'])).fetchone()
                result[label]=p[0] if p else None
            result['source_count']=c.execute('SELECT COUNT(*) FROM pages WHERE text_id=?',(row['text_id'],)).fetchone()[0]
            result['raw_source_available']=self.find_archive(result['citation']['archive_filename']) is not None
            return result
    def entry(self,eid):
        with closing(self.con()) as c:
            row=c.execute('SELECT * FROM entries WHERE id=?',(eid,)).fetchone()
            if not row: raise KeyError('Entry not found')
            r=dict(row);page=self.page(r['page_id'])
            following=[e['start_offset'] for e in page['entries'] if e['start_offset']>r['start_offset']]
            end=min(following) if following else len(page['text'])
            return {'entry':r,'citation':page['citation'],'text':page['text'][r['start_offset']:end],
                    'start_offset':r['start_offset'],'end_offset':end,'scope':'current_page_only',
                    'page_id':r['page_id'],'next_page':page['next'],'status':'automatic_candidate'}
    def duplicate_passages(self,text_id):
        with closing(self.con()) as c:
            rows=c.execute('''SELECT l.*,p.sha256,
                (SELECT COUNT(*) FROM passage_locations x JOIN pages pg ON pg.text_id=x.text_id WHERE x.passage_id=l.passage_id) AS source_occurrences
                FROM passage_locations l JOIN passages p ON p.id=l.passage_id WHERE l.text_id=?''',(int(text_id),)).fetchall()
            return [dict(r) for r in rows if r['source_occurrences']>1]
    def passage_sources(self,pid,limit=100,offset=0):
        limit=max(1,min(500,int(limit)));offset=max(0,int(offset))
        with closing(self.con()) as c:
            rows=c.execute('''SELECT c.*,l.start_offset,l.end_offset FROM passage_locations l
                JOIN citations c ON c.text_id=l.text_id WHERE l.passage_id=? ORDER BY c.title,c.page_id,l.start_offset LIMIT ? OFFSET ?''',
                (int(pid),limit+1,offset)).fetchall()
            return {'results':[dict(r) for r in rows[:limit]],'has_more':len(rows)>limit,'offset':offset,'limit':limit}
    def find_archive(self,name):
        candidates=self.archives+[BASE/'sources'/name,BASE/name,BASE.parent/name]
        exact=next((p for p in candidates if p.is_file() and p.name==name),None)
        return exact or (self.archives[0] if len(self.archives)==1 and self.archives[0].is_file() else None)
    def raw_source(self,sid,page_id=None):
        with closing(self.con()) as c:
            row=c.execute('SELECT s.*,a.filename FROM source_files s JOIN archives a ON a.id=s.archive_id WHERE s.id=?',(sid,)).fetchone()
            if not row: raise KeyError('Source not found')
            archive=self.find_archive(row['filename'])
            if not archive: raise KeyError('Place the unchanged original ZIP in the sources folder to open original HTML.')
            with zipfile.ZipFile(archive) as z:
                info=z.infolist()[row['zip_index']]
                if info.filename!=row['zip_path']: raise ValueError('Original archive entry does not match recorded provenance')
                raw=z.read(info)
            if digest(raw)!=row['raw_sha256']: raise ValueError('Original source checksum mismatch')
            if page_id:
                page=c.execute('SELECT raw_start,raw_end FROM pages WHERE id=? AND source_id=?',(page_id,sid)).fetchone()
                if not page: raise KeyError('Page not found')
                raw=raw[page[0]:page[1]]
            return raw,row['zip_path']

class Handler(BaseHTTPRequestHandler):
    server_version='RijalDB/'+VERSION
    def headers_out(self,status=200,mime='application/json; charset=utf-8',length=None,download=None):
        self.send_response(status);self.send_header('Content-Type',mime)
        self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store')
        origin=self.headers.get('Origin','')
        if origin=='null' or (urlparse(origin).scheme in ('http','https') and urlparse(origin).hostname in ('127.0.0.1','localhost','::1')):
            self.send_header('Access-Control-Allow-Origin',origin);self.send_header('Vary','Origin')
            self.send_header('Access-Control-Allow-Private-Network','true')
        if length is not None: self.send_header('Content-Length',str(length))
        if download: self.send_header('Content-Disposition',"attachment; filename*=UTF-8''"+quote(download))
        self.end_headers()
    def json(self,obj,status=200):
        raw=json.dumps(obj,ensure_ascii=False).encode('utf-8');self.headers_out(status,'application/json; charset=utf-8',len(raw));self.wfile.write(raw)
    def do_OPTIONS(self):
        self.send_response(204);origin=self.headers.get('Origin','')
        if origin=='null' or urlparse(origin).hostname in ('127.0.0.1','localhost','::1'):
            self.send_header('Access-Control-Allow-Origin',origin)
            self.send_header('Access-Control-Allow-Methods','GET, OPTIONS')
            self.send_header('Access-Control-Allow-Private-Network','true')
        self.end_headers()
    def do_GET(self):
        u=urlparse(self.path);path=u.path;qs=parse_qs(u.query)
        def arg(k,d=None): return qs.get(k,[d])[0]
        db=self.server.db
        try:
            if path=='/api/v1/stats': return self.json(db.stats())
            if path=='/api/v1/chronology':
                report=BASE/'reports/CHRONOLOGY.json'
                if not report.is_file(): raise KeyError('Chronology report has not been built')
                return self.json(json.loads(report.read_text(encoding='utf-8')))
            if path=='/api/v1/books': return self.json(db.books(arg('q','')))
            if path=='/api/v1/search': return self.json(db.search(arg('q',''),arg('scope','pages'),arg('mode','words'),arg('book'),arg('limit',30),arg('offset',0)))
            if path=='/api/v1/sources': return self.json(db.sources(arg('text_id'),arg('limit',100),arg('offset',0)))
            if path=='/api/v1/duplicates': return self.json(db.duplicate_passages(arg('text_id')))
            if path=='/api/v1/passage-sources': return self.json(db.passage_sources(arg('id'),arg('limit',100),arg('offset',0)))
            if path.startswith('/api/v1/page/'): return self.json(db.page(path.rsplit('/',1)[-1]))
            if path.startswith('/api/v1/entry/'): return self.json(db.entry(path.rsplit('/',1)[-1]))
            if path.startswith('/api/v1/identity/entry/'): return self.json(db.identities.identity_entry(path.rsplit('/',1)[-1]))
            if path.startswith('/api/v1/identity/members/'): return self.json(db.identities.identity_members(path.rsplit('/',1)[-1],arg('limit',30),arg('offset',0)))
            if path.startswith('/api/v1/identity/dates/'): return self.json(db.identities.identity_dates(path.rsplit('/',1)[-1]))
            if path.startswith('/api/v1/identity/graph/'): return self.json(db.identities.identity_graph(path.rsplit('/',1)[-1],arg('relation',''),arg('limit',30),arg('offset',0)))
            if path.startswith('/api/v1/graph/evidence/'): return self.json(db.identities.graph_evidence(path.rsplit('/',1)[-1],arg('relation',''),arg('mention',''),arg('limit',30),arg('offset',0)))
            if path.startswith('/api/v1/graph/mention/'): return self.json(db.identities.graph_mention(path.rsplit('/',1)[-1],arg('relation',''),arg('limit',30),arg('offset',0)))
            if path.startswith('/api/v1/raw/'):
                raw,name=db.raw_source(path.rsplit('/',1)[-1],arg('page'))
                self.headers_out(200,'application/octet-stream',len(raw),Path(name).name);self.wfile.write(raw);return
            files={'/':BASE/'web/index.html','/app.js':BASE/'web/app.js','/style.css':BASE/'web/style.css',
                   '/reader-adapter.js':BASE/'reader_adapter/rijal-db-client.js','/reader-button.js':BASE/'reader_adapter/rijal-db-button.js',
                   '/integration-demo':BASE/'reader_adapter/demo.html','/chronology':BASE/'reports/CHRONOLOGY.html'}
            if path in files:
                raw=files[path].read_bytes();mime=mimetypes.guess_type(str(files[path]))[0] or 'text/plain'
                self.headers_out(200,mime+'; charset=utf-8',len(raw));self.wfile.write(raw);return
            self.json({'error':'Not found'},404)
        except KeyError as e: self.json({'error':str(e)},404)
        except (ValueError,TypeError) as e: self.json({'error':str(e)},400)
        except (sqlite3.Error,OSError,zipfile.BadZipFile) as e:
            print('Request failed:',e,file=sys.stderr);self.json({'error':'Database request failed; see the local server console.'},500)
    def log_message(self,fmt,*args):
        if args and str(args[1] if len(args)>1 else '') not in ('200','204'): super().log_message(fmt,*args)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--db',default=str(BASE/'rijal.sqlite'));p.add_argument('--port',type=int,default=8765)
    p.add_argument('--identity',help='Optional unified_identity_view.sqlite')
    p.add_argument('--dates',help='Optional identity_dates.sqlite (requires --identity)')
    p.add_argument('--graph',help='Optional relationship_graph.sqlite (requires --identity)')
    p.add_argument('--archive',action='append',default=[]);p.add_argument('--open',action='store_true');a=p.parse_args()
    if not Path(a.db).is_file(): p.error('Database file not found. Extract the complete database package first.')
    if a.identity and not Path(a.identity).is_file():p.error('Identity lookup file not found.')
    if a.dates and (not a.identity or not Path(a.dates).is_file()):p.error('Date evidence requires an existing --identity file.')
    if a.graph and (not a.identity or not Path(a.graph).is_file()):p.error('Relationship graph requires an existing --identity file.')
    try: server=ThreadingHTTPServer(('127.0.0.1',a.port),Handler)
    except OSError as e: p.error(f'Cannot start on port {a.port}: {e}. Use --port with another number.')
    server.db=Database(a.db,a.archive,a.identity,a.dates,a.graph);url=f'http://127.0.0.1:{a.port}/'
    print('Rijal database:',url,'\nKeep this window open. Ctrl+C stops the server.',flush=True)
    if a.open: threading.Timer(.4,lambda:webbrowser.open(url)).start()
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__=='__main__': main()
