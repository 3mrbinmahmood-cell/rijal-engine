"""Annotate unambiguous single-report Shamela pages with attributed grade phrases.

No grade is inferred from a book title or from another report on the page.
"""
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from import_sources import parse_source,extract_page

PATTERNS=[('weak',re.compile(r'(?:اسناده\s+ضعيف|ضعيف\s+الاسناد|هذا\s+حديث\s+ضعيف)')),
          ('sahih',re.compile(r'(?:اسناده\s+صحيح|صحيح\s+الاسناد|هذا\s+حديث\s+صحيح|صحيح\s+لغيره)')),
          ('hasan',re.compile(r'(?:هذا\s+حديث\s+حسن|اسناده\s+حسن|حديث\s+حسن)'))]

def normalized_map(value):
    text=[];positions=[]
    for i,c in enumerate(value):
        if c in '\u200b\u200c' or unicodedata.category(c)=='Mn':continue
        if c in 'أإآٱ':c='ا'
        if c.isspace():c=' '
        if c==' ' and (not text or text[-1]==' '):continue
        text.append(c);positions.append(i)
    return ''.join(text),positions

def claims(detail):
    text=detail['text'];numbers=[]
    for start in detail['number_starts']:
        m=re.match(r'[\u200b\u200c\s]*(\d{1,5})\s*[-–]',text[start:start+25])
        if m:numbers.append(m.group(1))
    if len(numbers)!=1:return None
    foot=[(start,end) for kind,start,end,_ in detail['spans'] if kind=='footnote']
    out=[];seen=set()
    for status,pattern in PATTERNS:
        norm,map_=normalized_map(text)
        for m in pattern.finditer(norm):
            begin,end=map_[m.start()],map_[m.end()-1]+1
            footmatch=next(((a,b) for a,b in foot if a<=begin<b),None)
            if footmatch and begin-footmatch[0]>160:continue  # Later comparisons often grade a different report.
            origin='حاشية' if footmatch else 'نص الكتاب'
            key=(status,origin)
            if key in seen:continue
            seen.add(key)
            out.append({'status':status,'origin':origin,'quote':text[begin:end].strip()})
    if not out:return None
    statuses={x['status'] for x in out}
    overall='conflict' if 'weak' in statuses and len(statuses)>1 else 'weak' if 'weak' in statuses else 'sahih' if 'sahih' in statuses else 'hasan'
    return {'number':numbers[0],'status':overall,'claims':out}

def annotate(reader,source,output):
    reader,source,output=map(Path,(reader,source,output))
    if output.exists():raise ValueError('Output already exists')
    with ZipFile(reader) as old,ZipFile(source) as archive:
        books=json.loads(old.read('data.js').decode().removeprefix('window.SHAMELA_DATA=').rstrip(';'))
        groups={}
        for n in archive.namelist():
            if n.endswith('.htm'):groups.setdefault(Path(n).parts[-2],[]).append(n)
        audit={}
        for book in books:
            files=groups.get(book['title'])
            if not files or book['title'] in ('صحيح البخاري - ت البغا','صحيح مسلم - ت عبد الباقي','الصحيح المسند مما ليس في الصحيحين'):continue
            index=0;counts={'weak':0,'sahih':0,'hasan':0,'conflict':0}
            for n in sorted(files):
                elements,*_=parse_source(archive.read(n))
                for el in elements:
                    d=extract_page(el)
                    if d['text']!=book['pages'][index]['text']:raise ValueError('Source page differs: '+book['title']+' '+str(index))
                    grade=claims(d)
                    if grade:book['pages'][index]['grade']=grade;counts[grade['status']]+=1
                    index+=1
            if index!=len(book['pages']):raise ValueError('Page count mismatch: '+book['title'])
            audit[book['title']]=counts
        data=('window.SHAMELA_DATA='+json.dumps(books,ensure_ascii=False,separators=(',',':'))+';').encode()
        with ZipFile(output,'w',ZIP_DEFLATED,compresslevel=6) as new:
            for member in old.infolist():
                if member.is_dir():new.writestr(member,b'');continue
                new.writestr(member,data if member.filename=='data.js' else old.read(member.filename))
            new.writestr('GRADE_ANNOTATION_AUDIT.json',json.dumps(audit,ensure_ascii=False,indent=2).encode())
    return audit
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('reader');p.add_argument('source');p.add_argument('output');a=p.parse_args();print(json.dumps(annotate(a.reader,a.source,a.output),ensure_ascii=False))
