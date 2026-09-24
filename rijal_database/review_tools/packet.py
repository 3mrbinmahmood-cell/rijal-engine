"""Export complete source-backed comparison packets without identity merges."""
import argparse
from html import escape
import json
from pathlib import Path
import sqlite3

def read_only(path):
    return sqlite3.connect(f'file:{Path(path).resolve()}?mode=ro',uri=True)

def make_packet(review_path, kind, group_key, base_path, extraction_path):
    if kind not in ('dated','name'):
        raise ValueError('Review kind must be dated or name')
    with read_only(review_path) as review:
        if kind=='dated':
            ids=[r[0] for r in review.execute(
                'SELECT entry_id FROM members WHERE group_id=? ORDER BY entry_id',
                (group_key,))]
        else:
            ids=[r[0] for r in review.execute(
                'SELECT entry_id FROM name_members WHERE name_key=? ORDER BY entry_id',
                (group_key,))]
    if not ids:
        raise ValueError('Unknown or empty review group')
    packet={'kind':kind,'group':group_key,'identity_decision':'unresolved',
            'entries':[]}
    with read_only(base_path) as base, read_only(extraction_path) as extracted:
        def page(page_id):
            result=base.execute('''SELECT t.text,b.title,s.zip_path,p.printed_label,
                p.part_label,p.ordinal,s.raw_sha256
                FROM pages p JOIN page_texts t ON t.id=p.text_id
                JOIN source_files s ON s.id=p.source_id
                JOIN books b ON b.id=s.book_id WHERE p.id=?''',(page_id,)).fetchone()
            if not result:
                raise ValueError('Missing V1 page: '+page_id)
            text,book,path,label,part,ordinal,source_sha=result
            return text,{'page_id':page_id,'book':book,'source_path':path,
                         'printed_page':label,'part':part,'ordinal':ordinal,
                         'source_sha256':source_sha}
        for entry_id in ids:
            bio=extracted.execute('''SELECT name_label,classification,boundary_status,
                segment_count,statement_count FROM biographies WHERE id=?''',
                (entry_id,)).fetchone()
            if not bio:
                raise ValueError('Missing V1.1 biography: '+entry_id)
            heading=base.execute('SELECT page_id,start_offset,end_offset,title FROM entries WHERE id=?',
                                 (entry_id,)).fetchone()
            if not heading:
                raise ValueError('Missing V1 entry: '+entry_id)
            head_text,head_citation=page(heading[0])
            if head_text[heading[1]:heading[2]]!=heading[3]:
                raise ValueError('Heading offset mismatch: '+entry_id)
            record=base.execute('''SELECT death_year,evidence_page_id,evidence_start,
                evidence_end,evidence_quote FROM chronology_records WHERE entry_id=?''',
                (entry_id,)).fetchone()
            death=None
            if record and record[4]:
                year,pid,start,end,quote=record
                source,citation=page(pid)
                if start is not None and end is not None and source[start:end]!=quote:
                    raise ValueError('Date quote offset mismatch: '+entry_id)
                death={'year':year,'quote':quote,'start':start,'end':end,'citation':citation}
            item={'entry_id':entry_id,'name':bio[0],'classification':bio[1],
                  'boundary_status':bio[2],'heading':heading[3],
                  'heading_start':heading[1],'heading_end':heading[2],
                  'heading_citation':head_citation,'death_evidence':death,
                  'segments':[],'statements':[]}
            for pid,start,end,role in extracted.execute('''SELECT page_id,start_offset,
                end_offset,role FROM biography_segments WHERE biography_id=?
                ORDER BY id''',(entry_id,)):
                source,citation=page(pid)
                if start<0 or end>len(source) or end<start:
                    raise ValueError('Biography segment offset invalid: '+entry_id)
                item['segments'].append({'role':role,'text':source[start:end],
                                         'start':start,'end':end,'citation':citation})
            for sid,pid,start,end,origin,status,scope,quote,attribution in extracted.execute('''
                SELECT s.id,s.page_id,s.start_offset,s.end_offset,s.origin,
                s.subject_status,s.quote_scope,t.quote,s.attribution_text
                FROM statements s JOIN statement_texts t ON t.id=s.text_id
                WHERE s.biography_id=? ORDER BY s.page_id,s.start_offset,s.id''',
                (entry_id,)):
                source,citation=page(pid)
                if source[start:end]!=quote:
                    raise ValueError('Statement offset mismatch: '+sid)
                item['statements'].append(
                    {'id':sid,'quote':quote,'start':start,'end':end,
                     'origin':origin,'subject_status':status,'scope':scope,
                     'attribution_text':attribution,
                     'kinds':[r[0] for r in extracted.execute(
                         'SELECT DISTINCT kind FROM statement_triggers WHERE statement_id=?',
                         (sid,))],
                     'citation':citation})
            if len(item['segments'])!=bio[3] or len(item['statements'])!=bio[4]:
                raise ValueError('V1.1 candidate counts disagree: '+entry_id)
            packet['entries'].append(item)
    return packet

def render_html(packet):
    h=['<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8">',
       '<title>ملف مراجعة الهوية</title>',
       '<style>body{font:20px/1.9 serif;max-width:1000px;margin:auto;padding:24px;background:#faf8f2;color:#202020} '
       'article{border:1px solid #bbb;padding:18px;margin:24px 0;background:white} '
       'pre{white-space:pre-wrap;font:inherit} small{font:14px sans-serif;color:#555} '
       'details{margin:12px 0;border-top:1px solid #ddd}</style>',
       '<h1>ملف مراجعة الهوية</h1><p>تطابق محتمل يحتاج إلى مراجعة؛ لم يُحسم اتحاد الأشخاص.</p>']
    for item in packet['entries']:
        h.append('<article><h2>'+escape(item['name'])+'</h2>')
        c=item['heading_citation']
        h.append('<small>'+escape(c['book'])+' — '+escape(str(c['printed_page'] or 'رقم الصفحة غير متاح'))
                 +' — '+escape(c['source_path'])+'</small>')
        if item['death_evidence']:
            d=item['death_evidence']
            h.append('<p><strong>نص الوفاة المستخرج:</strong> '+escape(d['quote'])+'</p>')
        h.append('<h3>نص الترجمة المستخرج</h3>')
        for segment in item['segments']:
            c=segment['citation']
            h.append('<details open><summary>'+escape(c['book'])+' — '
                     +escape(str(c['printed_page'] or c['ordinal']))+'</summary><pre>'
                     +escape(segment['text'])+'</pre></details>')
        h.append('<h3>العبارات المستخرجة ('+str(len(item['statements']))+')</h3>')
        for statement in item['statements']:
            c=statement['citation']
            h.append('<details><summary>'+escape(statement['origin'])+' — '
                     +escape(c['book'])+' — '+escape(str(c['printed_page'] or c['ordinal']))
                     +'</summary><pre>'+escape(statement['quote'])+'</pre></details>')
        h.append('</article>')
    return '\n'.join(h+['</html>'])

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('kind',choices=('dated','name'))
    p.add_argument('review_database')
    p.add_argument('group')
    p.add_argument('v1')
    p.add_argument('v1_1')
    p.add_argument('output')
    a=p.parse_args()
    packet=make_packet(a.review_database,a.kind,a.group,a.v1,a.v1_1)
    output=Path(a.output)
    output.write_text(
        render_html(packet) if output.suffix.lower()=='.html'
        else json.dumps(packet,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'entries':len(packet['entries']),
                      'segments':sum(len(e['segments']) for e in packet['entries']),
                      'statements':sum(len(e['statements']) for e in packet['entries']),
                      'output':str(output)},ensure_ascii=False))

if __name__=='__main__':
    main()
