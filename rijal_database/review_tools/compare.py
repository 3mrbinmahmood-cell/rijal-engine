"""Compare two source entries in a review group; never infer an identity."""
import argparse
from html import escape
import json
from pathlib import Path
import sqlite3
from .packet import make_packet, render_html

def compare(review_path, kind, group, left, right, base_path, extraction_path):
    if left==right:
        raise ValueError('Choose two different entries')
    packet=make_packet(review_path,kind,group,base_path,extraction_path)
    chosen={item['entry_id']:item for item in packet['entries']}
    if left not in chosen or right not in chosen:
        raise ValueError('Both entries must belong to the selected group')
    a,b=chosen[left],chosen[right]
    years=[item['death_evidence']['year'] if item['death_evidence'] else None
           for item in (a,b)]
    date_relation=('unavailable' if None in years else
                   'same_extracted_year' if years[0]==years[1] else
                   'different_extracted_years')
    by_quote={}
    for statement in b['statements']:
        by_quote.setdefault(statement['quote'],[]).append(statement)
    shared=[]
    for statement in a['statements']:
        for match in by_quote.get(statement['quote'],[]):
            shared.append({'quote':statement['quote'],
                           'left_citation':statement['citation'],
                           'right_citation':match['citation'],
                           'left_kinds':statement['kinds'],
                           'right_kinds':match['kinds']})
    with sqlite3.connect(f'file:{Path(review_path).resolve()}?mode=ro',
                         uri=True) as review:
        ordered=sorted((left,right))
        decision=review.execute('''SELECT decision,reason,reviewer,decided_at
            FROM pair_decisions WHERE left_entry_id=? AND right_entry_id=?''',
            ordered).fetchone()
    packet['entries']=[a,b]
    return {'group':group,'kind':kind,'date_relation':date_relation,
            'extracted_death_years':years,
            'shared_literal_statement_occurrences':len(shared),
            'shared_literal_statements':shared,
            'recorded_review':dict(zip(('decision','reason','reviewer','decided_at'),decision))
                              if decision else None,
            'identity_inference':'none','packet':packet}

def render_comparison(result):
    summary=('<section dir="rtl"><h2>مؤشرات المقارنة</h2><p>حالة تواريخ الوفاة المستخرجة: '
             +escape(result['date_relation'])+'</p><p>عدد العبارات المتطابقة حرفيًا: '
             +str(result['shared_literal_statement_occurrences'])
             +'</p><p>هذه المؤشرات لا تثبت اتحاد الهوية ولا اختلافها.</p></section>')
    html=render_html(result['packet'])
    return html.replace('<h1>ملف مراجعة الهوية</h1>',
                        '<h1>مقارنة مدخلين</h1>'+summary,1)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('kind',choices=('dated','name'))
    p.add_argument('review_database')
    p.add_argument('group')
    p.add_argument('entry_a')
    p.add_argument('entry_b')
    p.add_argument('v1')
    p.add_argument('v1_1')
    p.add_argument('output')
    a=p.parse_args()
    result=compare(a.review_database,a.kind,a.group,a.entry_a,a.entry_b,
                   a.v1,a.v1_1)
    out=Path(a.output)
    out.write_text(render_comparison(result) if out.suffix.lower()=='.html'
                   else json.dumps(result,ensure_ascii=False,indent=2),
                   encoding='utf-8')
    print(json.dumps({'date_relation':result['date_relation'],
                      'shared_literal_statement_occurrences':
                      result['shared_literal_statement_occurrences'],
                      'recorded_review':result['recorded_review'],
                      'output':str(out)},ensure_ascii=False))

if __name__=='__main__':
    main()
