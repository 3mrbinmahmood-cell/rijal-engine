"""Check ruling attribution on the recorded Tirmidhi example and mixed pages."""
import json
import sys
from zipfile import ZipFile
from annotate_grades import claims
sys.path.insert(0,'rijal_database/tools')
from import_sources import parse_source,extract_page

def test(source_zip,reader_zip):
    with ZipFile(source_zip) as z:
        n=next(n for n in z.namelist() if n.endswith('سنن الترمذي - ت شاكر/002.htm'))
        details=[extract_page(e) for e in parse_source(z.read(n))[0]]
        sample=next(d for d in details if '551 -' in d['text'])
        grade=claims(sample)
        assert grade['number']=='551' and grade['status']=='conflict'
        assert {(c['origin'],c['status']) for c in grade['claims']}=={('نص الكتاب','hasan'),('حاشية','weak')}
    with ZipFile(reader_zip) as z:
        books=json.loads(z.read('data.js').decode().removeprefix('window.SHAMELA_DATA=').rstrip(';'))
        t=next(b for b in books if b['title']=='سنن الترمذي - ت شاكر')
        page=next(p for p in t['pages'] if p.get('grade',{}).get('number')=='551')
        assert page['grade']==grade
        assert any(p.get('grade',{}).get('status')=='sahih' for p in t['pages'])
        assert z.testzip() is None
    print('PASS Tirmidhi 551: distinct main-text hasan and footnote weak; navigable explicit sahih pages')
if __name__=='__main__':test(sys.argv[1],sys.argv[2])
