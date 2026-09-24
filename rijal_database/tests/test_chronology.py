import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from build_chronology import parse_year,name_label,bins,date_evidence

class ChronologyTests(unittest.TestCase):
    def test_date_types(self):
        for text,year in [('249 هـ',249),('١٣ هـ',13),('تسع وعشرين ومائتين',229),('ثلاث مائة وخمس عشرة',315),('تسعمائة وخمس',905),('الف واربع مائة وخمس',1405)]:
            self.assertEqual(parse_year(text)[0],year,text)
        for text in ['نحو مائتين','بعد سنة مائتين','سبعين','سنة مائتين','200 م','2000 م','230 أو 231','مائتين ونيف']:
            self.assertIsNone(parse_year(text)[0],text)
    def test_biography_names_and_dates(self):
        self.assertEqual(name_label('123 - أسامة بن عمير، والد أبي المليح'),'أسامة بن عمير')
        self.assertIsNone(name_label('1 - قال ابن حجر في مقدمته'))
        text='محمد بن علي (ت 230 هـ)\nروى عن فلان.'
        found,_=date_evidence(text,0,len(text),text.index('\n'),[])
        self.assertEqual(found[0]['year'],230)
        self.assertEqual(text[found[0]['start']:found[0]['end']],found[0]['quote'])
        text='محمد بن علي\nنص الترجمة.\nتوفي سنة 230 هـ.'
        found,_=date_evidence(text,0,len(text),11,[(text.index('توفي'),len(text))]);self.assertEqual(found,[])
    def test_period_boundaries(self):
        years={1:{'groups':1,'source_entries':2},30:{'groups':1,'source_entries':1},31:{'groups':2,'source_entries':3},100:{'groups':3,'source_entries':5},101:{'groups':1,'source_entries':2}}
        b=bins(years,30);self.assertEqual(b[0]['groups'],2);self.assertEqual(b[1]['groups'],2)
        b=bins(years,100);self.assertEqual(b[0]['groups'],7);self.assertEqual(b[1]['groups'],1)
        self.assertEqual(sum(x['groups'] for x in b),8)

if __name__=='__main__':unittest.main(verbosity=2)
