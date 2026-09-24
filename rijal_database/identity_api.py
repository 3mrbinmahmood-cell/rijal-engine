"""Read-only identity, date, and unresolved relationship lookups."""
from contextlib import closing
from pathlib import Path
import sqlite3

class IdentityStore:
    def __init__(self,identity=None,dates=None,graph=None):
        self.identity_path=Path(identity) if identity else None
        self.dates_path=Path(dates) if dates else None
        self.graph_path=Path(graph) if graph else None
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
