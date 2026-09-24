"""Read-only inspection of stage-three candidates alongside the unchanged V1 corpus."""
import argparse,json,mimetypes,sqlite3,sys,threading,webbrowser
from contextlib import closing
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs,urlparse
from server import Database,fts_query
BASE=Path(__file__).resolve().parent

class Extraction:
    def __init__(self,base,extracted):self.base=Path(base);self.path=Path(extracted);self.sources=Database(base)
    def con(self):
        c=sqlite3.connect(self.path.resolve().as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;return c
    def stats(self):
        with closing(self.con()) as c:return {'summary':json.loads(c.execute("SELECT value FROM metadata WHERE key='summary'").fetchone()[0]),'method':c.execute("SELECT value FROM metadata WHERE key='method'").fetchone()[0],'read_only':True}
    def citation(self,c,pid):return dict(c.execute('SELECT * FROM citations WHERE page_id=?',(pid,)).fetchone())
    def biographies(self,q='',limit=30,offset=0):
        limit=max(1,min(100,int(limit)));offset=max(0,int(offset));params=[]
        sql='SELECT b.* FROM biographies b'
        if q:sql+=' JOIN biography_fts ON biography_fts.rowid=b.rowid WHERE biography_fts MATCH ?';params.append(fts_query(q,'words'))
        sql+=' ORDER BY b.rowid LIMIT ? OFFSET ?';params.extend([limit+1,offset])
        with closing(self.con()) as c,closing(self.sources.con()) as s:
            rows=[dict(r) for r in c.execute(sql,params)];more=len(rows)>limit;rows=rows[:limit]
            for r in rows:r['citation']=self.citation(s,r['opening_page_id'])
        return {'results':rows,'has_more':more,'offset':offset,'limit':limit}
    def statement_rows(self,c,s,sql,params):
        result=[]
        for row in c.execute(sql,params):
            r=dict(row);r['citation']=self.citation(s,r['page_id'])
            r['triggers']=[dict(h) for h in c.execute('SELECT * FROM statement_triggers WHERE statement_id=? ORDER BY start_offset,kind',(r['id'],))]
            result.append(r)
        return result
    def statements(self,q='',kind='',origin='',bio='',limit=30,offset=0):
        if kind and kind not in ('birth','death','teachers','students','assessment','alias','family','cross_reference'):raise ValueError('Unknown statement type')
        if origin and origin not in ('main_text','footnote'):raise ValueError('Unknown source layer')
        limit=max(1,min(100,int(limit)));offset=max(0,int(offset));params=[]
        sql='SELECT s.*,t.quote,b.name_label FROM statements s JOIN statement_texts t ON t.id=s.text_id LEFT JOIN biographies b ON b.id=s.biography_id'
        if q:sql+=' JOIN statement_fts ON statement_fts.rowid=t.id'
        where=[]
        if q:where.append('statement_fts MATCH ?');params.append(fts_query(q,'words'))
        if kind:where.append('EXISTS(SELECT 1 FROM statement_triggers h WHERE h.statement_id=s.id AND h.kind=?)');params.append(kind)
        if origin:where.append('s.origin=?');params.append(origin)
        if bio:where.append('s.biography_id=?');params.append(bio)
        if where:sql+=' WHERE '+' AND '.join(where)
        # A fixed order keeps pagination reproducible.
        sql+=' ORDER BY s.rowid LIMIT ? OFFSET ?';params.extend([limit+1,offset])
        with closing(self.con()) as c,closing(self.sources.con()) as s:rows=self.statement_rows(c,s,sql,params)
        return {'results':rows[:limit],'has_more':len(rows)>limit,'offset':offset,'limit':limit}
    def biography(self,id,offset=0,limit=12):
        offset=max(0,int(offset));limit=max(1,min(50,int(limit)))
        with closing(self.con()) as c,closing(self.sources.con()) as s:
            row=c.execute('SELECT * FROM biographies WHERE id=?',(id,)).fetchone()
            if not row:raise KeyError('Biography candidate not found')
            r=dict(row);segments=[dict(g) for g in c.execute('SELECT * FROM biography_segments WHERE biography_id=? ORDER BY id LIMIT ? OFFSET ?',(id,limit+1,offset))]
            more=len(segments)>limit;segments=segments[:limit]
            for g in segments:
                text=s.execute('SELECT t.text FROM pages p JOIN page_texts t ON t.id=p.text_id WHERE p.id=?',(g['page_id'],)).fetchone()[0]
                g['text']=text[g['start_offset']:g['end_offset']];g['citation']=self.citation(s,g['page_id'])
            r.update(segments=segments,has_more=more,offset=offset,limit=limit)
            return r

class Handler(BaseHTTPRequestHandler):
    def reply(self,value,status=200,mime='application/json; charset=utf-8'):
        raw=value if isinstance(value,bytes) else json.dumps(value,ensure_ascii=False).encode()
        self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(raw)));self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        u=urlparse(self.path);q=parse_qs(u.query);arg=lambda k,d='':q.get(k,[d])[0];db=self.server.db
        try:
            if u.path=='/api/stats':return self.reply(db.stats())
            if u.path=='/api/biographies':return self.reply(db.biographies(arg('q'),arg('limit',30),arg('offset',0)))
            if u.path=='/api/statements':return self.reply(db.statements(arg('q'),arg('kind'),arg('origin'),arg('bio'),arg('limit',30),arg('offset',0)))
            if u.path.startswith('/api/biography/'):return self.reply(db.biography(u.path.rsplit('/',1)[-1],arg('offset',0),arg('limit',12)))
            if u.path.startswith('/api/page/'):return self.reply(db.sources.page(u.path.rsplit('/',1)[-1]))
            files={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}
            if u.path in files:
                p=BASE/'extraction_web'/files[u.path];return self.reply(p.read_bytes(),mime=(mimetypes.guess_type(str(p))[0] or 'text/plain')+'; charset=utf-8')
            return self.reply({'error':'Not found'},404)
        except KeyError as e:self.reply({'error':str(e)},404)
        except (TypeError,ValueError) as e:self.reply({'error':str(e)},400)
        except (OSError,sqlite3.Error) as e:print(e,file=sys.stderr);self.reply({'error':'تعذر قراءة البيانات. راجع نافذة التشغيل.'},500)
    def log_message(self,*args):pass

def main():
    p=argparse.ArgumentParser();p.add_argument('--db',default=str(BASE/'rijal.sqlite'));p.add_argument('--extraction',default=str(BASE/'extraction.sqlite'));p.add_argument('--port',type=int,default=8766);p.add_argument('--open',action='store_true');a=p.parse_args()
    if not Path(a.db).is_file() or not Path(a.extraction).is_file():p.error('Run START_EXTRACTION_WINDOWS.bat first.')
    server=ThreadingHTTPServer(('127.0.0.1',a.port),Handler);server.db=Extraction(a.db,a.extraction);url=f'http://127.0.0.1:{a.port}/';print('Biography and statement inspection:',url,flush=True)
    if a.open:threading.Timer(.4,lambda:webbrowser.open(url)).start()
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
if __name__=='__main__':main()
