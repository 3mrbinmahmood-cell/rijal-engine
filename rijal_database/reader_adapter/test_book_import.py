"""Regression checks for the supplied mixed-grading Shamela archive."""
import json
import sys
from zipfile import ZipFile

def books(path):
    with ZipFile(path) as z:
        return json.loads(z.read('data.js').decode().removeprefix('window.SHAMELA_DATA=').rstrip(';'))

def test(old_path,new_path):
    before=books(old_path);after=books(new_path)
    assert before==after[:len(before)]
    assert len(after)==10
    dawud=next(b for b in after if b['title']=='سنن أبي داود - ت الأرنؤوط')
    page=next(p for p in dawud['pages'] if p['n']=='(ص: 9)')
    assert '9 -' in page['text'] and '10 -' in page['text']
    assert 'إسناده صحيح' in page['text'] and 'إسناده ضعيف' in page['text']
    # Both judgments share a page; page-wide grading would be wrong.
    assert page['text'].index('إسناده صحيح')<page['text'].index('إسناده ضعيف')
    assert 'أبي زيد' in page['text']
    with ZipFile(new_path) as z:
        toc=json.loads(z.read('toc.js').decode().removeprefix('window.SHAMELA_TOC=').rstrip(';'))
        assert len(toc)==len(after)
        for book in toc[6:]:
            assert book['volumes'][0]['page']==1
            assert not book['volumes'][0]['title'].isnumeric()
            assert book['entries'] and all(e['page']>0 for e in book['entries'])
        assert z.testzip() is None
    print('PASS: 10 books, six original books intact, mixed grades preserved on Abu Dawud p.9')
if __name__=='__main__':test(sys.argv[1],sys.argv[2])
