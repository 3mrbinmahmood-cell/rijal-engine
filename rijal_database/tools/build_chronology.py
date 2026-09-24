#!/usr/bin/env python3
"""Conservative, explicitly provisional biography chronology; no person merges.
Dates describe source-entry candidates. Grouping requires the same extracted
name label AND death year. Undated/ambiguous/conflicting records are excluded
from time buckets, never given a guessed year.
"""
import argparse,collections,csv,html,json,re,sqlite3,sys
from pathlib import Path
from common import connect,digest,normalize
BASE=Path(__file__).resolve().parents[1]
NAME=re.compile(r'\b(?:بن|ابن|أبو|أبي|أبا|أم|بنت)\b')
STOP=re.compile(r'\b(?:ثقة|صدوق|ضعيف|مقبول|صحابي|مجهول|متروك|روى|روي|حدث|سمع|توفي|توفى|مات|ولد|قال|عن)\b')
REJECT=re.compile(r'^(?:باب|كتاب|فصل|قال|وقال|ذكر|وفي|روي|روى|ان|أن|من|في|على|هذا|هذه|له|لا|ولم|لم|وقد|كان|وكان|القول|معرفة|ذكره|ذكرهم|ثم|وممن|ذكرنا|قالوا|وهو|فقال|احاديث|حديث|اخبار|فضائل|مناقب|رواية|شيوخ|تلاميذ|اقوال|مرويات|طبقات|تراجم|رجال|اسماء|مسند|سماع|تاريخ|ومن|ومما|مما|ما|جملة|الاعتماد|الامر|كلام|ثناء|تعقيب|تعليق|قصيدة|شرح|تهذيب)\b')
DEATH=re.compile(r'(?:توفي|توفى|مات|وفاته)(?:\s+رحمه\s+الله)?(?:\s+في)?\s+(?:سنة|عام)\s+')
DIGITS=str.maketrans('٠١٢٣٤٥٦٧٨٩','0123456789')
NUMBERS={'واحد':1,'واحدة':1,'احد':1,'احدى':1,'اثنان':2,'اثنين':2,'اثنتان':2,'اثنتين':2,'اثنا':2,'اثني':2,'اثنتا':2,'اثنتي':2,
 'ثلاث':3,'ثلاثة':3,'اربع':4,'اربعة':4,'خمس':5,'خمسة':5,'ست':6,'ستة':6,'سبع':7,'سبعة':7,'ثمان':8,'ثماني':8,'ثمانية':8,'تسع':9,'تسعة':9,
 'عشر':10,'عشرة':10,'عشرين':20,'عشرون':20,'ثلاثين':30,'ثلاثون':30,'اربعين':40,'اربعون':40,'خمسين':50,'خمسون':50,'ستين':60,'ستون':60,'سبعين':70,'سبعون':70,'ثمانين':80,'ثمانون':80,'تسعين':90,'تسعون':90,
 'مائة':100,'مئة':100,'مايه':100,'مائه':100,'مئه':100,'مائتين':200,'مئتين':200,'مائتان':200,'مئتان':200,'الف':1000,'الفين':2000}
NUMBERS={normalize(k):v for k,v in NUMBERS.items()}
HUNDRED=re.compile(r'(ثلاث|اربع|خمس|ست|سبع|ثمان|تسع)(?:مائة|مئة)')

def name_label(title):
    t=re.sub(r'[\u200b-\u200f\ufeff]','',title).strip()
    t=re.sub(r'^[\s\d٠-٩()\[\].،:؛\-–]+','',t)
    t=re.sub(r'\[[ختدسقمعبخ\s،]+\]','',t)
    t=re.split(r'[\n،؛:.]|\([^)]*\d|\b(?:توفي|توفى|مات)\b',t,maxsplit=1)[0].strip()
    m=STOP.search(t)
    if m:t=t[:m.start()].strip()
    t=re.sub(r'\s+',' ',t).strip(' -*ـ[]()')
    n=normalize(t)
    if not 7<=len(n)<=180 or REJECT.match(n):return None
    m=NAME.search(t)
    if not m or m.start()>55 or len(n.split())<3:return None
    return t

def parse_year(text):
    """Return (year,status,length). Only complete stated years, not short centuries."""
    # Called on a short original fragment. Normalization is for parsing only.
    s=normalize(text.translate(DIGITS))
    if re.match(r'(?:نحو|قرابة|حوالي|بعد|قبل|بضع|نيف|اواخر|اوائل|حدود)\b',s):return None,'approximate_or_range',0
    m=re.match(r'[\s(\[]*(\d{1,4})\s*[)\]]?\s*(هـ|ه\b|هجري\w*|م\b|ميلادي\w*)?',s)
    if m:
        year=int(m[1]);cal=m[2] or ''
        tail=s[m.end():m.end()+30]
        if cal.startswith(('م','ميل')):return None,'gregorian_only',m.end()
        if re.match(r'\s*(?:او|وقيل|ونيف|وبضع|تقريبا|[-–/])',tail):return None,'conflicting_or_range',m.end()
        if not 1<=year<=1450:return None,'out_of_supported_hijri_range',m.end()
        if year<100 and not cal:return None,'short_year_needs_century',m.end()
        return year,'explicit_hijri' if cal else 'hijri_assumed_from_death_context',m.end()
    words=[]
    for m in re.finditer(r'\S+',s):
        token=m[0].strip('،.؛:()[]')
        if token=='و':continue
        if token.startswith('و') and (token[1:] in NUMBERS or HUNDRED.fullmatch(token[1:])):token=token[1:]
        hundred=HUNDRED.fullmatch(token)
        if token not in NUMBERS and not hundred:break
        val=NUMBERS[token] if token in NUMBERS else NUMBERS[hundred[1]]*100
        words.append((token,val,m.end()))
        if len(words)>10:break
    if not words:return None,'unparsed_date',0
    values=[];i=0
    while i<len(words):
        token,val,end=words[i]
        if val<10 and i+1<len(words) and words[i+1][1]==100:
            values.append(val*100);i+=2
        else:values.append(val);i+=1
    year=sum(values);end=words[-1][2]
    if not any(v>=100 for v in values):return None,'short_year_needs_century',end
    if re.match(r'\s*(?:او|وقيل|ونيف|وبضع|تقريبا|[-–/])',s[end:]):return None,'conflicting_or_range',end
    if not 100<=year<=1450:return None,'out_of_supported_hijri_range',end
    return year,'hijri_assumed_from_death_context',end

def date_evidence(text,start,end,heading_end,footnotes):
    segment=text[start:end];found=[];unresolved=[]
    # Headings with explicit death abbreviation or explicit lifespan, strongest automatic cue.
    head=text[start:heading_end]
    patterns=[re.compile(r'(?:\(|\[|\s)ت\s*[:.،-]?\s*(\d{1,4})\s*(هـ|ه\b|م\b)?'),
              re.compile(r'[\[(]\s*\d{1,4}\s*[-–]\s*(\d{1,4})\s*(هـ|ه\b)')]
    for pat in patterns:
        for m in pat.finditer(head.translate(DIGITS)):
            fragment=m[1]+(m[2] or '')
            year,status,_=parse_year(fragment)
            item={'year':year,'date_status':status,'evidence_kind':'heading_death_date','start':start+m.start(),'end':start+m.end(),'quote':text[start+m.start():start+m.end()]}
            (found if year is not None else unresolved).append(item)
    if found:return found,unresolved
    # Search only this candidate's same-page span, outside editor footnotes.
    # These are contextual proposals and remain labelled unverified.
    for m in DEATH.finditer(segment):
        a=start+m.start();b=min(end,start+m.end()+110)
        if any(x<=a<y for x,y in footnotes):continue
        original=text[start+m.end():b]
        year,status,_=parse_year(original)
        quote_end=min(b, next((v for v in [text.find('\n',start+m.end(),b),text.find('.',start+m.end(),b)] if v>=0),b))
        item={'year':year,'date_status':status,'evidence_kind':'same_entry_death_context','start':a,'end':quote_end,'quote':text[a:quote_end]}
        (found if year is not None else unresolved).append(item)
    return found,unresolved

def bins(years,width):
    if not years:return []
    first=((min(years)-1)//width)*width+1;last=((max(years)-1)//width)*width+1
    return [{'start':start,'end':start+width-1,'groups':sum(v['groups'] for y,v in years.items() if start<=y<start+width),
             'source_entries':sum(v['source_entries'] for y,v in years.items() if start<=y<start+width)} for start in range(first,last+1,width)]

def build(db,out):
    out=Path(out);out.mkdir(exist_ok=True,parents=True);con=connect(db)
    con.executescript('''CREATE TABLE IF NOT EXISTS chronology_records(
      entry_id TEXT PRIMARY KEY REFERENCES entries(id),name_label TEXT NOT NULL,name_key TEXT NOT NULL,
      death_year INTEGER,date_status TEXT NOT NULL,evidence_page_id TEXT NOT NULL REFERENCES pages(id),
      evidence_start INTEGER,evidence_end INTEGER,evidence_quote TEXT,evidence_kind TEXT,group_id TEXT);
      CREATE TABLE IF NOT EXISTS chronology_groups(id TEXT PRIMARY KEY,name_label TEXT NOT NULL,name_key TEXT NOT NULL,
      death_year INTEGER NOT NULL,source_entries INTEGER NOT NULL,status TEXT NOT NULL);
      CREATE INDEX IF NOT EXISTS chronology_year ON chronology_groups(death_year);
      CREATE INDEX IF NOT EXISTS chronology_record_name ON chronology_records(name_key,death_year);
      CREATE INDEX IF NOT EXISTS chronology_record_group ON chronology_records(group_id);
      DELETE FROM chronology_records;DELETE FROM chronology_groups;''')
    print('Extracting biography chronology candidates...',flush=True)
    pending=[];source_rows=0;unclassified=0
    # Read pages in source order so each large text is read once.
    page_rows=con.execute('SELECT p.id,t.text FROM pages p JOIN page_texts t ON t.id=p.text_id WHERE EXISTS(SELECT 1 FROM entries e WHERE e.page_id=p.id)')
    for page in page_rows:
        entries=con.execute('SELECT * FROM entries WHERE page_id=? ORDER BY start_offset',(page['id'],)).fetchall()
        foot=[tuple(r) for r in con.execute("SELECT start_offset,end_offset FROM spans WHERE page_id=? AND kind='footnote'",(page['id'],))]
        for i,e in enumerate(entries):
            label=name_label(e['title'])
            if not label:unclassified+=1;continue
            source_rows+=1;end=entries[i+1]['start_offset'] if i+1<len(entries) else len(page['text'])
            found,unresolved=date_evidence(page['text'],e['start_offset'],end,e['end_offset'],foot)
            years={f['year'] for f in found}
            if len(years)==1 and not any(u['date_status'] in ('conflicting_or_range','approximate_or_range') for u in unresolved):
                evidence=found[0];year=evidence['year'];status=evidence['date_status']
            else:
                evidence=(found or unresolved or [{}])[0];year=None
                status='conflicting_dates_in_entry' if len(years)>1 else (unresolved[0]['date_status'] if unresolved else 'no_usable_death_date')
            pending.append((e['id'],label,normalize(label),year,status,page['id'],evidence.get('start'),evidence.get('end'),evidence.get('quote'),evidence.get('evidence_kind'),None))
            if len(pending)>=10000:
                con.executemany('INSERT INTO chronology_records VALUES(?,?,?,?,?,?,?,?,?,?,?)',pending);pending.clear()
        if source_rows and source_rows%25000<len(entries):print('Biographical candidate rows:',source_rows,flush=True)
    con.executemany('INSERT INTO chronology_records VALUES(?,?,?,?,?,?,?,?,?,?,?)',pending);con.commit()
    # A repeated label with different death years is ambiguous; do not put it
    # into several bins as though it were certainly several different people.
    conflicts={r[0] for r in con.execute('SELECT name_key FROM chronology_records WHERE death_year IS NOT NULL GROUP BY name_key HAVING COUNT(DISTINCT death_year)>1')}
    con.executemany("UPDATE chronology_records SET date_status='ambiguous_name_or_conflicting_year',death_year=NULL WHERE name_key=?",[(n,) for n in conflicts])
    for r in con.execute('SELECT name_key,death_year,MIN(name_label) AS name_label,COUNT(*) AS n FROM chronology_records WHERE death_year IS NOT NULL GROUP BY name_key,death_year').fetchall():
        gid=digest(r['name_key']+'\0'+str(r['death_year']))
        con.execute('INSERT INTO chronology_groups VALUES(?,?,?,?,?,?)',(gid,r['name_label'],r['name_key'],r['death_year'],r['n'],'provisional_name_and_year_group'))
        con.execute('UPDATE chronology_records SET group_id=? WHERE name_key=? AND death_year=?',(gid,r['name_key'],r['death_year']))
    con.commit()
    years={r['death_year']:{'groups':r['n'],'source_entries':r['entries']} for r in con.execute('SELECT death_year,COUNT(*) AS n,SUM(source_entries) AS entries FROM chronology_groups GROUP BY death_year ORDER BY death_year')}
    statuses={r[0]:r[1] for r in con.execute('SELECT date_status,COUNT(*) FROM chronology_records GROUP BY date_status')}
    groups=con.execute('SELECT COUNT(*) FROM chronology_groups').fetchone()[0]
    summary={'verified_distinct_people':None,'biographical_source_entry_candidates':source_rows,
        'distinct_name_labels_not_people':con.execute('SELECT COUNT(DISTINCT name_key) FROM chronology_records').fetchone()[0],
        'dated_name_and_year_groups_provisional':groups,'dated_source_entries':sum(v['source_entries'] for v in years.values()),
        'undated_or_unresolved_source_entries':con.execute('SELECT COUNT(*) FROM chronology_records WHERE death_year IS NULL').fetchone()[0],
        'other_headings_excluded':unclassified,'ambiguous_name_labels':len(conflicts),
        'earliest_extracted_death_year_ah':min(years) if years else None,'latest_extracted_death_year_ah':max(years) if years else None}
    examples=[]
    if years:
        for year in (min(years),max(years)):
            for r in con.execute('''SELECT g.id,g.name_label,g.death_year,r.evidence_quote,r.evidence_kind,r.evidence_start,r.evidence_end,
                c.title,c.printed_label,c.part_label,c.zip_path,c.page_id,c.book_id FROM chronology_groups g
                JOIN chronology_records r ON r.group_id=g.id JOIN citations c ON c.page_id=r.evidence_page_id
                WHERE g.death_year=? GROUP BY g.id ORDER BY g.name_label LIMIT 8''',(year,)):
                examples.append(dict(r))
    result={'summary':summary,'year_counts':[{'year':y,**v} for y,v in years.items()],'bands_30':bins(years,30),'bands_100':bins(years,100),'date_status_counts':statuses,'endpoint_examples':examples,
        'method':'Death years in Hijri chronology. Unlabelled complete years in Arabic death statements are provisionally treated as Hijri, flagged separately. Short years, approximate dates, conflicts, Gregorian-only dates and missing dates are excluded. Grouping uses extracted name labels plus matching death year; groups are not verified distinct people. Scope is all candidate biographies in the supplied collection, not only hadith narrators. No semantic identity reconciliation has been completed.'}
    (out/'CHRONOLOGY.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    with (out/'CHRONOLOGY_EVIDENCE.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(['entry_id','name_label','death_year_ah','date_status','group_id','evidence','book','part','printed_page','source_file','page_id'])
        for r in con.execute('''SELECT r.entry_id,r.name_label,r.death_year,r.date_status,r.group_id,r.evidence_quote,c.title,c.part_label,c.printed_label,c.zip_path,c.page_id
          FROM chronology_records r JOIN citations c ON c.page_id=r.evidence_page_id ORDER BY r.name_key,r.death_year'''):writer.writerow(tuple(r))
    def table(rows,width):
        return '<h2>فترات '+str(width)+' سنة هجرية</h2><table><thead><tr><th>من</th><th>إلى</th><th>مجموعات الاسم وسنة الوفاة (أولية)</th><th>مداخل المصادر المؤرخة</th></tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+str(r[k])+'</td>' for k in ('start','end','groups','source_entries'))+'</tr>' for r in rows)+'</tbody></table>'
    doc='''<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>إحصاءات الرجال والتوزيع الزمني</title><style>body{font:17px/1.8 Tahoma,Arial;margin:30px auto;max-width:1150px;padding:20px;color:#19332e;background:#fffdf7}table{border-collapse:collapse;width:100%;margin-bottom:30px}th{background:#163e53;color:white}td,th{padding:8px 14px;border-bottom:1px solid #cfd6d5;text-align:right}.notice{padding:18px;background:#fff0cd}h1{font-size:28px}.cols{display:grid;grid-template-columns:1fr 1fr;gap:25px}@media(max-width:800px){.cols{display:block}}</style><h1>إحصاءات التراجم والتوزيع الزمني</h1><p class="notice">العدد المحقق للأشخاص المختلفين لم يثبت بعد. الأعداد الزمنية أدناه لمجموعات أولية تتفق في الاسم المستخرج وسنة الوفاة؛ قد يبقى فيها تكرار أو اشتباه هوية. تشمل المجموعة تراجم عامة، وليست جميعها لرواة الحديث. السنوات بحسب الوفاة الهجرية، مع افتراض التقويم الهجري للسنوات الكاملة غير المصرح بتقويمها في سياق الوفاة.</p>'''
    labels={'biographical_source_entry_candidates':'مداخل تراجم مرشحة في المصادر','distinct_name_labels_not_people':'صيغ أسماء مختلفة (ليست عدد الأشخاص)','dated_name_and_year_groups_provisional':'مجموعات مؤرخة أولية','dated_source_entries':'مداخل مصدر مؤرخة داخلة في الجداول','undated_or_unresolved_source_entries':'مداخل بلا تاريخ صالح أو غير محسومة','earliest_extracted_death_year_ah':'أقدم سنة وفاة مستخرجة','latest_extracted_death_year_ah':'أحدث سنة وفاة مستخرجة'}
    doc+='<table>'+''.join('<tr><th>'+label+'</th><td>'+str(summary[k])+'</td></tr>' for k,label in labels.items())+'</table>'
    doc+='<div class="cols"><div>'+table(result['bands_30'],30)+'</div><div>'+table(result['bands_100'],100)+'</div></div><h2>شواهد الحدين الزمنيّين</h2>'
    for r in examples:doc+='<p><b>'+html.escape(r['name_label'])+' — '+str(r['death_year'])+' هـ</b><br>'+html.escape(r['evidence_quote'] or '')+'<br>'+html.escape(r['title']+' · '+(r['part_label'] or '')+' · '+(r['printed_label'] or 'بلا ترقيم'))+'</p>'
    (out/'CHRONOLOGY.html').write_text(doc+'</html>')
    assert sum(r['groups'] for r in result['bands_30'])==groups
    assert sum(r['groups'] for r in result['bands_100'])==groups
    assert summary['dated_source_entries']+summary['undated_or_unresolved_source_entries']==source_rows
    bad=con.execute('SELECT COUNT(*) FROM chronology_records r JOIN pages p ON p.id=r.evidence_page_id JOIN page_texts t ON t.id=p.text_id WHERE r.evidence_quote IS NOT NULL AND r.evidence_quote!=substr(t.text,r.evidence_start+1,r.evidence_end-r.evidence_start)').fetchone()[0]
    assert bad==0, 'Chronology evidence offset mismatch'
    con.execute('INSERT OR REPLACE INTO metadata VALUES(?,?)',('chronology_summary',json.dumps(summary)))
    con.commit();con.close();print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--db',default=str(BASE/'rijal.sqlite'));p.add_argument('--out',default=str(BASE/'reports'));a=p.parse_args();build(a.db,a.out)
