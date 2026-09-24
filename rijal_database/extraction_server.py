"""Read-only inspection of stage-three candidates alongside the unchanged V1 corpus."""
import argparse,json,mimetypes,sqlite3,sys,threading,webbrowser
from contextlib import closing
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs,urlparse
try:from .server import Database,fts_query
except ImportError:from server import Database,fts_query
BASE=Path(__file__).resolve().parent

class Extraction:
    def __init__(self,base,extracted,identity=None,dates=None,graph=None):
        self.base=Path(base);self.path=Path(extracted);self.sources=Database(base)
        self.identity_path=Path(identity) if identity else None
        self.dates_path=Path(dates) if dates else None
        self.graph_path=Path(graph) if graph else None
    def con(self):
        c=sqlite3.connect(self.path.resolve().as_uri()+'?mode=ro',uri=True);c.row_factory=sqlite3.Row;return c
    def identity_con(self):
        if not self.identity_path:raise KeyError('Identity lookup is not installed')
        c=sqlite3.connect(self.identity_path.resolve().as_uri()+'?mode=ro',uri=True)
        c.row_factory=sqlite3.Row
        return c
    def identity_entry(self,id):
        with closing(self.identity_con()) as c:
            row=c.execute('''SELECT e.*,i.display_name,i.entry_count
                FROM entry_identity e JOIN identities i ON i.id=e.identity_id
                WHERE e.entry_id=?''',(id,)).fetchone()
            if not row:raise KeyError('Entry not found in identity lookup')
            return dict(row)
    def identity_members(self,id,limit=30,offset=0):
        limit=max(1,min(100,int(limit)));offset=max(0,int(offset))
        with closing(self.identity_con()) as c:
            identity=c.execute('SELECT * FROM identities WHERE id=?',(id,)).fetchone()
            if not identity:raise KeyError('Identity not found')
            rows=[dict(r) for r in c.execute('''SELECT entry_id,name_label,classification,
                book_id,source_id,opening_page_id FROM entry_identity
                WHERE identity_id=? ORDER BY entry_id LIMIT ? OFFSET ?''',
                (id,limit+1,offset))]
            return {'identity':dict(identity),'results':rows[:limit],
                    'has_more':len(rows)>limit,'offset':offset,'limit':limit}
    def identity_dates(self,entry_id):
        identity=self.identity_entry(entry_id)
        if not self.dates_path:raise KeyError('Date evidence is not installed')
        with closing(sqlite3.connect(self.dates_path.resolve().as_uri()+'?mode=ro',
                                     uri=True)) as c:
            c.row_factory=sqlite3.Row
            summary=c.execute('SELECT * FROM identity_date_summary WHERE identity_id=?',
                              (identity['identity_id'],)).fetchone()
            claims=[dict(r) for r in c.execute('''SELECT entry_id,kind,year,
                evidence_type,exact_quote,page_id,start_offset,end_offset,reviewer,note
                FROM date_claims WHERE identity_id=? ORDER BY year,entry_id,id''',
                (identity['identity_id'],))]
        return {'identity_id':identity['identity_id'],
                'summary':dict(summary) if summary else None,'claims':claims}
    def identity_graph(self,entry_id,relation='',limit=30,offset=0):
        identity=self.identity_entry(entry_id)
        if not self.graph_path:raise KeyError('Relationship graph is not installed')
        if relation and relation not in ('teacher','student'):
            raise ValueError('Unknown graph relation')
        limit=max(1,min(100,int(limit)));offset=max(0,int(offset))
        sql='''SELECT n.relation,m.id AS mention_id,m.name,m.resolution_status,n.source_entries,
            n.supporting_pairs FROM neighbors n JOIN name_mentions m
            ON m.id=n.mention_id WHERE n.identity_id=?'''
        params=[identity['identity_id']]
        if relation:sql+=' AND n.relation=?';params.append(relation)
        sql+=' ORDER BY n.source_entries DESC,n.supporting_pairs DESC,m.name LIMIT ? OFFSET ?'
        params.extend((limit+1,offset))
        with closing(sqlite3.connect(self.graph_path.resolve().as_uri()+'?mode=ro',
                                     uri=True)) as c:
            c.row_factory=sqlite3.Row
            rows=[dict(r) for r in c.execute(sql,params)]
        return {'identity_id':identity['identity_id'],'results':rows[:limit],
                'has_more':len(rows)>limit,'limit':limit,'offset':offset,
                'status':'heuristic_unresolved_names'}
    def graph_evidence(self,entry_id,relation,mention_id,limit=30,offset=0):
        identity=self.identity_entry(entry_id)
        if not self.graph_path:raise KeyError('Relationship graph is not installed')
        if relation not in ('teacher','student'):raise ValueError('Unknown graph relation')
        limit=max(1,min(100,int(limit)));offset=max(0,int(offset))
        with closing(sqlite3.connect(self.graph_path.resolve().as_uri()+'?mode=ro',
                                     uri=True)) as c:
            c.row_factory=sqlite3.Row
            mention=c.execute('SELECT id,name,resolution_status FROM name_mentions WHERE id=?',
                              (mention_id,)).fetchone()
            if not mention:raise KeyError('Name mention not found')
            rows=[dict(r) for r in c.execute('''SELECT entry_id,paired_entry_id,
                page_id,review_priority FROM observations WHERE identity_id=?
                AND relation=? AND mention_id=? ORDER BY entry_id,paired_entry_id
                LIMIT ? OFFSET ?''',(identity['identity_id'],relation,mention_id,
                                      limit+1,offset))]
        return {'identity_id':identity['identity_id'],'mention':dict(mention),
                'relation':relation,'results':rows[:limit],
                'has_more':len(rows)>limit,'limit':limit,'offset':offset}
    def graph_mention(self,mention_id,relation='',limit=30,offset=0):
        if not self.graph_path:raise KeyError('Relationship graph is not installed')
        if relation and relation not in ('teacher','student'):
            raise ValueError('Unknown graph relation')
        limit=max(1,min(100,int(limit)));offset=max(0,int(offset))
        with closing(sqlite3.connect(self.graph_path.resolve().as_uri()+'?mode=ro',
                                     uri=True)) as c:
            c.row_factory=sqlite3.Row
            mention=c.execute('SELECT * FROM name_mentions WHERE id=?',
                              (mention_id,)).fetchone()
            if not mention:raise KeyError('Name mention not found')
            sql='''SELECT identity_id,relation,source_entries,supporting_pairs
                FROM neighbors WHERE mention_id=?'''
            params=[mention_id]
            if relation:sql+=' AND relation=?';params.append(relation)
            sql+=' ORDER BY source_entries DESC,supporting_pairs DESC,identity_id LIMIT ? OFFSET ?'
            params.extend((limit+1,offset))
            rows=[dict(r) for r in c.execute(sql,params)]
        with closing(self.identity_con()) as c:
            for row in rows[:limit]:
                found=c.execute('SELECT kind,display_name FROM identities WHERE id=?',
                                (row['identity_id'],)).fetchone()
                if found:row.update(identity_kind=found['kind'],display_name=found['display_name'])
        return {'mention':dict(mention),'results':rows[:limit],
                'has_more':len(rows)>limit,'limit':limit,'offset':offset,
                'status':'shared_name_does_not_prove_same_person'}
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
            if u.path.startswith('/api/identity/entry/'):return self.reply(db.identity_entry(u.path.rsplit('/',1)[-1]))
            if u.path.startswith('/api/identity/members/'):return self.reply(db.identity_members(u.path.rsplit('/',1)[-1],arg('limit',30),arg('offset',0)))
            if u.path.startswith('/api/identity/dates/'):return self.reply(db.identity_dates(u.path.rsplit('/',1)[-1]))
            if u.path.startswith('/api/identity/graph/'):return self.reply(db.identity_graph(u.path.rsplit('/',1)[-1],arg('relation'),arg('limit',30),arg('offset',0)))
            if u.path.startswith('/api/graph/evidence/'):return self.reply(db.graph_evidence(u.path.rsplit('/',1)[-1],arg('relation'),arg('mention'),arg('limit',30),arg('offset',0)))
            if u.path.startswith('/api/graph/mention/'):return self.reply(db.graph_mention(u.path.rsplit('/',1)[-1],arg('relation'),arg('limit',30),arg('offset',0)))
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
    p=argparse.ArgumentParser();p.add_argument('--db',default=str(BASE/'rijal.sqlite'));p.add_argument('--extraction',default=str(BASE/'extraction.sqlite'));p.add_argument('--identity',help='Optional unified_identity_view.sqlite');p.add_argument('--dates',help='Optional identity_dates.sqlite (requires --identity)');p.add_argument('--graph',help='Optional relationship_graph.sqlite (requires --identity)');p.add_argument('--port',type=int,default=8766);p.add_argument('--open',action='store_true');a=p.parse_args()
    if not Path(a.db).is_file() or not Path(a.extraction).is_file():p.error('Run START_EXTRACTION_WINDOWS.bat first.')
    if a.identity and not Path(a.identity).is_file():p.error('Identity lookup file not found.')
    if a.dates and (not a.identity or not Path(a.dates).is_file()):p.error('Date evidence requires an existing --identity file.')
    if a.graph and (not a.identity or not Path(a.graph).is_file()):p.error('Relationship graph requires an existing --identity file.')
    server=ThreadingHTTPServer(('127.0.0.1',a.port),Handler);server.db=Extraction(a.db,a.extraction,a.identity,a.dates,a.graph);url=f'http://127.0.0.1:{a.port}/';print('Biography and statement inspection:',url,flush=True)
    if a.open:threading.Timer(.4,lambda:webbrowser.open(url)).start()
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
if __name__=='__main__':main()
