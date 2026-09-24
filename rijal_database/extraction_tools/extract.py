"""Source-backed candidates, never canonical people or adjudicated claims.

Every recorded heading closes the preceding candidate. Continuations are
limited to pages of the same HTML source file. Footnotes remain separate.
"""
import argparse,bisect,collections,hashlib,json,re,sqlite3,sys,time
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/'tools'))
from common import normalize,digest,file_hash

MARKS='\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed\u0640\u200b-\u200f'
WORD_MARKS='\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed\u0640'
TERMS={
 'birth':['ولد','ولدت','مولده','مولدها','ولادته','ولادتها'],
 'death':['توفي','توفى','توفيت','توفيت','مات','ماتت','وفاته','وفاتها','المتوفى','المتوفاة'],
 'teachers':['روى عن','روت عن','حدث عن','سمع من','سمعت من','أخذ عن','تفقه على','قرأ على','شيوخه','شيوخها'],
 'students':['روى عنه','روى عنها','روت عنه','حدث عنه','حدث عنها','سمع منه','سمع منها','أخذ عنه','تلاميذه','تلاميذها'],
 'assessment':['ليس بثقة','ليس به بأس','لا بأس به','ليس بشيء','سيء الحفظ','صالح الحديث','منكر الحديث','متروك الحديث','ثقة','صدوق','ضعيف','متروك','مجهول','كذاب','وضاع','حجة','ثبت','وثقه','ضعفه'],
 'alias':['يكنى','كنيته','كنيتها','لقبه','لقبها','المعروف','يعرف','ويقال','وقيل اسمه','اسمه','اسمها'],
 'family':['والد','والدة','أبوه','أبيه','أمه','أخوه','أخيه','ابنه','ابنته','ولده','زوجها','زوجته'],
 'cross_reference':['تقدم','سيأتي','يأتي ذكره','انظر ترجمته','تقدمت ترجمته']}
LABELS={'birth':'المولد','death':'الوفاة','teachers':'الشيوخ والرواية عنهم','students':'التلاميذ والرواة عنه','assessment':'عبارات الجرح والتعديل','alias':'الأسماء والكنى والألقاب','family':'القرابة','cross_reference':'الإحالات'}

def flexible(term):
    parts=[]
    for ch in term:
        if ch==' ':parts.append(r'\s+')
        else:
            p='[اأإآٱ]' if ch in 'اأإآٱ' else '[يى]' if ch in 'يى' else re.escape(ch)
            parts.append(p+'['+MARKS+']*')
    return ''.join(parts)

PATTERN=re.compile(r'(?<![\w'+WORD_MARKS+r'])(?:[وف]['+MARKS+r']*)?(?:'+ '|'.join('(?P<'+k+'>'+ '|'.join(flexible(t) for t in sorted(set(v),key=len,reverse=True))+')' for k,v in TERMS.items())+r')(?![\w'+WORD_MARKS+r'])')
SAID=re.compile(r'(?<![\w'+WORD_MARKS+r'])(?:[وف]['+MARKS+r']*)?'+flexible('قال')+r'\s+')
SEPARATOR=re.compile(r'[\n؛.!؟]+')
REF=re.compile(r'^(?:تقدم|سياتي|انظر|ياتي|سبق)\b')

def clean_label(value):
    return re.sub(r'^[\s•*\-–()\[\]ختدسقمعب]+[)\]]\s*','',value).lstrip(' •*-–')

def classification(text,label,a,b,heading_end):
    opening=normalize(text[a:min(b,a+900)])
    after=normalize(text[heading_end:min(b,heading_end+180)])
    if any(x in normalize(text[:600]) for x in ('فهرسة مكتبة','ردمك','قائمة المحتويات','فهرس الاسماء')):
        return 'catalogue_or_index_candidate'
    if (REF.match(after) or re.search(r'\b(?:تقدم|سياتي|انظر ترجمته)\b',opening)) and b-a<300:
        return 'cross_reference_candidate'
    if b-a<160 and re.search(r'\([^)]*\d+\s*[/\\]\s*\d+',text[a:b]):return 'short_index_candidate'
    return 'biography_candidate'

def attribution(text,a,b,trigger):
    prefix=text[a:trigger];matches=list(SAID.finditer(prefix))
    if not matches:return None,None,None
    m=matches[-1];start=a+m.end();end=trigger
    while start<end and text[start] in ' \t\n:،«»"':start+=1
    while end>start and text[end-1] in ' \t\n:،«»"':end-=1
    label=text[start:end]
    if not 2<=len(label)<=100 or len(normalize(label).split())>12 or '\n' in label:return None,None,None
    # This is an attribution *label*, not a resolved scholar identity.
    if re.search(r'\b(?:انه|فيه|حديثه|اسناده|هذا|كان|روي|حدثنا|اخبرنا)\b',normalize(label)):return None,None,None
    return label,start,end

def detect(text,lo,hi,footnotes):
    """Exact offsets for clause/window candidates inside a single owner region."""
    # Separate both footnote starts and ends, including adjacent editor notes.
    cuts={lo,hi}
    for a,b in footnotes:
        if lo<a<hi:cuts.add(a)
        if lo<b<hi:cuts.add(b)
    cuts=sorted(cuts);out={}
    for left,right in zip(cuts,cuts[1:]):
        origin='footnote' if any(a<=left<b for a,b in footnotes) else 'main_text'
        stops=[left]+[m.end() for m in SEPARATOR.finditer(text,left,right)]+[right]
        for hit in PATTERN.finditer(text,left,right):
            kind=hit.lastgroup;start,end=hit.start(),hit.end()
            j=bisect.bisect_right(stops,start)-1;a=stops[j];b=stops[min(j+1,len(stops)-1)]
            # A separate short "قال فلان:" line may supply the attribution.
            if j>0:
                prev=text[stops[j-1]:a].strip()
                if len(prev)<110 and SAID.match(prev) and prev.rstrip().endswith(':'):a=stops[j-1]
            scope='clause'
            if b-a>1400:
                a=max(a,start-500);b=min(b,end+650);scope='context_window'
            while a<start and text[a].isspace():a+=1
            while b>end and text[b-1].isspace():b-=1
            # If a marker straddles a line break, retain the whole marker.
            b=max(b,end)
            att,aa,ab=attribution(text,a,b,start)
            context=normalize(text[a:b])
            subject='unresolved_in_biography_context'
            if origin=='footnote':subject='editorial_context_unresolved'
            elif kind=='assessment' and re.search(r'\b(?:اسناد|الاسناد|اسناده|حديث|الحديث|حديثه|السند|سنده|الخبر|خبر)\b',context):subject='possible_report_or_chain_assessment'
            key=(a,b,origin)
            if key not in out:out[key]={'start':a,'end':b,'quote':text[a:b],'origin':origin,'subject_status':subject,'quote_scope':scope,'attribution_text':att,'attribution_start':aa,'attribution_end':ab,'triggers':[]}
            elif subject=='possible_report_or_chain_assessment':out[key]['subject_status']=subject
            if att and not out[key]['attribution_text']:
                out[key].update(attribution_text=att,attribution_start=aa,attribution_end=ab)
            out[key]['triggers'].append({'kind':kind,'start':start,'end':end,'quote':text[start:end]})
    return list(out.values())

def build(source,dest,report_dir,expected_sha):
    started=time.perf_counter();source=Path(source);dest=Path(dest);report_dir=Path(report_dir);report_dir.mkdir(parents=True,exist_ok=True)
    if dest.exists():raise ValueError('Use a new output path; existing extraction data is never overwritten.')
    print('Checking V1 release checksum...',flush=True)
    assert file_hash(source)==expected_sha,'Wrong base database'
    src=sqlite3.connect(source.resolve().as_uri()+'?mode=ro&immutable=1',uri=True);src.row_factory=sqlite3.Row
    src.execute('PRAGMA cache_size=-65536')
    out=sqlite3.connect(dest);out.execute('PRAGMA journal_mode=DELETE');out.execute('PRAGMA synchronous=FULL');out.execute('PRAGMA cache_size=-131072');out.execute('PRAGMA foreign_keys=ON');out.executescript((Path(__file__).parent/'schema.sql').read_text())
    out.execute('INSERT INTO metadata VALUES(?,?)',('base_database_sha256',expected_sha))
    out.execute('INSERT INTO metadata VALUES(?,?)',('version','1.1-extraction'))
    counts=collections.Counter();active=None;source_id=None;bio_sizes=collections.defaultdict(lambda:[0,0]);last_bio=None
    print('Extracting biography spans and statement candidates...',flush=True)
    for page in src.execute('SELECT p.*,t.text,s.book_id FROM pages p JOIN page_texts t ON t.id=p.text_id JOIN source_files s ON s.id=p.source_id ORDER BY p.source_id,p.ordinal'):
        if source_id!=page['source_id']:
            if active:out.execute("UPDATE biographies SET boundary_status='source_file_end_unresolved' WHERE id=?",(active,))
            source_id=page['source_id'];active=None
        text=page['text'];entries=src.execute('''SELECT e.*,r.name_label FROM entries e LEFT JOIN chronology_records r ON r.entry_id=e.id WHERE e.page_id=? ORDER BY e.start_offset''',(page['id'],)).fetchall()
        feet=[tuple(r) for r in src.execute("SELECT start_offset,end_offset FROM spans WHERE page_id=? AND kind='footnote' ORDER BY start_offset",(page['id'],))]
        # Before the first heading, carry only the preceding file-local owner.
        regions=[];first=entries[0]['start_offset'] if entries else len(text)
        if first:regions.append((0,first,active,'continuation' if active else 'unassigned'))
        for i,e in enumerate(entries):
            if active:out.execute("UPDATE biographies SET boundary_status='next_recorded_heading' WHERE id=?",(active,))
            active=None;a=e['start_offset'];b=entries[i+1]['start_offset'] if i+1<len(entries) else len(text)
            if e['name_label']:
                active=e['id'];label=clean_label(e['name_label']);kind=classification(text,label,a,b,e['end_offset'])
                cur=out.execute('INSERT INTO biographies(id,name_label,name_key,opening_page_id,source_id,book_id,heading_start,heading_end,classification,boundary_status) VALUES(?,?,?,?,?,?,?,?,?,?)',
                    (active,label,normalize(label),page['id'],source_id,page['book_id'],a,e['end_offset'],kind,'pending_boundary'))
                out.execute('INSERT INTO biography_fts(rowid,name_key) VALUES(?,?)',(cur.lastrowid,normalize(label)))
                counts['biographies']+=1
            regions.append((a,b,active,'opening' if active else 'unassigned'))
        for a,b,bio,role in regions:
            if b<=a:continue
            if bio:
                out.execute('INSERT INTO biography_segments(biography_id,page_id,start_offset,end_offset,role) VALUES(?,?,?,?,?)',(bio,page['id'],a,b,role))
                bio_sizes[bio][0]+=1;bio_sizes[bio][1]+=b-a;counts['segments']+=1
                if role=='continuation':counts['continuation_segments']+=1
            for item in detect(text,a,b,feet):
                sha=digest(item['quote']);existing=out.execute('SELECT id FROM statement_texts WHERE sha256=?',(sha,)).fetchone()
                if existing:tid=existing[0]
                else:
                    tid=out.execute('INSERT INTO statement_texts(sha256,quote) VALUES(?,?)',(sha,item['quote'])).lastrowid
                    out.execute('INSERT INTO statement_fts(rowid,search_text) VALUES(?,?)',(tid,normalize(item['quote'])))
                sid=digest(page['id']+':'+str(item['start'])+':'+str(item['end'])+':'+item['origin'])
                status=item['subject_status'] if bio else ('editorial_context_unresolved' if item['origin']=='footnote' else 'unassigned_source_context')
                out.execute('INSERT INTO statements VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(sid,tid,bio,page['id'],source_id,page['book_id'],item['start'],item['end'],item['origin'],status,item['quote_scope'],item['attribution_text'],item['attribution_start'],item['attribution_end']))
                out.executemany('INSERT OR IGNORE INTO statement_triggers VALUES(?,?,?,?,?)',[(sid,h['kind'],h['start'],h['end'],h['quote']) for h in item['triggers']])
                counts['statements']+=1
        counts['pages_scanned']+=1
        if counts['pages_scanned']%25000==0:
            out.commit();print(json.dumps(dict(counts)),flush=True)
    if active:out.execute("UPDATE biographies SET boundary_status='source_file_end_unresolved' WHERE id=?",(active,))
    out.executemany('UPDATE biographies SET segment_count=?,char_count=? WHERE id=?',[(v[0],v[1],k) for k,v in bio_sizes.items()])
    out.execute('UPDATE biographies SET statement_count=(SELECT COUNT(*) FROM statements s WHERE s.biography_id=biographies.id)')
    out.commit();out.execute('ANALYZE');out.commit()
    print('Auditing every quotation, trigger and source offset...',flush=True)
    out.execute('ATTACH DATABASE ? AS corpus',(str(source.resolve()),))
    checks={
      'quote_mismatches':out.execute('''SELECT COUNT(*) FROM statements s JOIN statement_texts q ON q.id=s.text_id JOIN corpus.pages p ON p.id=s.page_id JOIN corpus.page_texts t ON t.id=p.text_id WHERE q.quote!=substr(t.text,s.start_offset+1,s.end_offset-s.start_offset)''').fetchone()[0],
      'trigger_mismatches':out.execute('''SELECT COUNT(*) FROM statement_triggers h JOIN statements s ON s.id=h.statement_id JOIN corpus.pages p ON p.id=s.page_id JOIN corpus.page_texts t ON t.id=p.text_id WHERE h.quote!=substr(t.text,h.start_offset+1,h.end_offset-h.start_offset) OR h.start_offset<s.start_offset OR h.end_offset>s.end_offset''').fetchone()[0],
      'attribution_mismatches':out.execute('''SELECT COUNT(*) FROM statements s JOIN corpus.pages p ON p.id=s.page_id JOIN corpus.page_texts t ON t.id=p.text_id WHERE s.attribution_text IS NOT NULL AND s.attribution_text!=substr(t.text,s.attribution_start+1,s.attribution_end-s.attribution_start)''').fetchone()[0],
      'bad_segments':out.execute('''SELECT COUNT(*) FROM biography_segments g JOIN biographies b ON b.id=g.biography_id JOIN corpus.pages p ON p.id=g.page_id JOIN corpus.page_texts t ON t.id=p.text_id WHERE g.start_offset<0 OR g.end_offset>length(t.text) OR p.source_id!=b.source_id''').fetchone()[0],
      'wrong_biography_owner':out.execute('''SELECT COUNT(*) FROM statements s WHERE s.biography_id IS NOT NULL AND NOT EXISTS(SELECT 1 FROM biography_segments g WHERE g.biography_id=s.biography_id AND g.page_id=s.page_id AND g.start_offset<=s.start_offset AND g.end_offset>=s.end_offset)''').fetchone()[0],
      'headings_crossed':out.execute('''SELECT COUNT(*) FROM biography_segments g WHERE EXISTS(SELECT 1 FROM corpus.entries e WHERE e.page_id=g.page_id AND e.start_offset>g.start_offset AND e.start_offset<g.end_offset)''').fetchone()[0],
      'footnote_layer_errors':out.execute('''SELECT COUNT(*) FROM statements s WHERE (s.origin='footnote' AND NOT EXISTS(SELECT 1 FROM corpus.spans f WHERE f.page_id=s.page_id AND f.kind='footnote' AND f.start_offset<=s.start_offset AND f.end_offset>=s.end_offset)) OR (s.origin='main_text' AND EXISTS(SELECT 1 FROM corpus.spans f WHERE f.page_id=s.page_id AND f.kind='footnote' AND f.start_offset<s.end_offset AND f.end_offset>s.start_offset))''').fetchone()[0],
      'pending_boundaries':out.execute("SELECT COUNT(*) FROM biographies WHERE boundary_status='pending_boundary'").fetchone()[0],
      'missing_candidates':src.execute('SELECT COUNT(*) FROM chronology_records').fetchone()[0]-counts['biographies']}
    assert not any(checks.values()),checks
    assert counts['pages_scanned']==src.execute('SELECT COUNT(*) FROM pages').fetchone()[0]
    assert not out.execute('PRAGMA foreign_key_check').fetchall()
    integrity=[r[0] for r in out.execute('PRAGMA integrity_check')];assert integrity==['ok'],integrity[:3]
    for name in ('biography_fts','statement_fts'):out.execute(f"INSERT INTO {name}({name}) VALUES('integrity-check')")
    assert out.execute('select count(*) from biography_fts').fetchone()[0]==counts['biographies']
    assert out.execute('select count(*) from statement_fts').fetchone()[0]==out.execute('select count(*) from statement_texts').fetchone()[0]
    summary=dict(counts);summary.update(
      distinct_statement_texts=out.execute('SELECT COUNT(*) FROM statement_texts').fetchone()[0],
      biography_classifications=dict(out.execute('SELECT classification,COUNT(*) FROM biographies GROUP BY classification')),
      statement_origins=dict(out.execute('SELECT origin,COUNT(*) FROM statements GROUP BY origin')),
      statement_types=dict(out.execute('SELECT kind,COUNT(DISTINCT statement_id) FROM statement_triggers GROUP BY kind')),
      subject_statuses=dict(out.execute('SELECT subject_status,COUNT(*) FROM statements GROUP BY subject_status')),
      boundary_statuses=dict(out.execute('SELECT boundary_status,COUNT(*) FROM biographies GROUP BY boundary_status')),
      biographies_with_continuations=out.execute("SELECT COUNT(DISTINCT biography_id) FROM biography_segments WHERE role='continuation'").fetchone()[0],
      biographies_with_statements=out.execute('SELECT COUNT(*) FROM biographies WHERE statement_count>0').fetchone()[0],
      statements_with_attribution_labels=out.execute('SELECT COUNT(*) FROM statements WHERE attribution_text IS NOT NULL').fetchone()[0],
      verified_people=None,identity_merges_performed=0,original_source_text_changed=False)
    report={'version':'1.1-extraction','base_sha256':expected_sha,'summary':summary,'offset_audit':checks,'integrity_check':integrity,'fts_integrity':'passed','elapsed_seconds':round(time.perf_counter()-started,1),
      'method':'All V1 candidate names retained. Every recorded heading closes the preceding candidate, including non-biographical headings. Continuation stays within one HTML source file. Literal trigger-based excerpts include separate footnotes and unassigned contexts. Labels and attribution strings are unverified; no person merges, adjudicated grades, resolved teacher/student edges, or chronology changes.'}
    out.execute('INSERT INTO metadata VALUES(?,?)',('summary',json.dumps(summary,ensure_ascii=False)));out.execute('INSERT INTO metadata VALUES(?,?)',('method',report['method']));out.commit()
    (report_dir/'EXTRACTION_AUDIT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    src.close();out.close();assert file_hash(source)==expected_sha,'Base database changed during extraction'
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('output');p.add_argument('--reports',required=True);p.add_argument('--base-sha',required=True);a=p.parse_args();build(a.source,a.output,a.reports,a.base_sha)
