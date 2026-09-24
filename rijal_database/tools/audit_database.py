#!/usr/bin/env python3
"""Audit a completed import. Run with the importer and server stopped."""
import argparse
import csv
import json
import random
import sqlite3
import sys
import time
import zipfile
from pathlib import Path
from common import connect,digest,file_hash
from import_sources import parse_source,extract_page
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
from server import Database

def audit(db,archive,report_dir):
    output=Path(report_dir);output.mkdir(parents=True,exist_ok=True)
    con=connect(db);con.execute('PRAGMA journal_mode=DELETE')
    print('Checking database integrity...',flush=True)
    integrity=[r[0] for r in con.execute('PRAGMA integrity_check')]
    if integrity!=['ok']: raise RuntimeError('Integrity check failed: '+str(integrity[:3]))
    fk=[tuple(r) for r in con.execute('PRAGMA foreign_key_check')]
    if fk: raise RuntimeError('Foreign-key check failed')
    for table in ('page_fts','entry_fts'): con.execute(f"INSERT INTO {table}({table}) VALUES('integrity-check')")
    con.commit()
    tables=('books','source_files','pages','page_texts','entries','mentions','passages','passage_locations','persons','assertions')
    counts={t:con.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in tables}
    counts['candidate_biography_headings']=con.execute("SELECT COUNT(*) FROM entries WHERE kind!='source_heading'").fetchone()[0]
    counts['other_source_headings']=counts['entries']-counts['candidate_biography_headings']
    counts['raw_html_bytes']=con.execute('SELECT SUM(byte_size) FROM source_files').fetchone()[0]
    counts['unique_page_text_bytes']=con.execute('SELECT SUM(length(CAST(text AS BLOB))) FROM page_texts').fetchone()[0]
    counts['duplicate_file_groups']=con.execute('SELECT COUNT(*) FROM duplicate_files').fetchone()[0]
    counts['duplicate_page_groups']=con.execute('SELECT COUNT(*) FROM duplicate_pages').fetchone()[0]
    counts['page_storage_reuses']=counts['pages']-counts['page_texts']
    counts['exact_paragraph_storage_reuses']=counts['passage_locations']-counts['passages']
    counts['normalized_paragraph_variant_groups']=con.execute('SELECT COUNT(*) FROM (SELECT normalized_sha256 FROM passages GROUP BY normalized_sha256 HAVING COUNT(*)>1)').fetchone()[0]
    counts['unlabelled_pages']=con.execute("SELECT COUNT(*) FROM pages WHERE printed_label IS NULL OR printed_label='' ").fetchone()[0]
    counts['failed_files']=con.execute("SELECT COUNT(*) FROM source_files WHERE status!='ok'").fetchone()[0]
    counts['fallback_files']=con.execute("SELECT COUNT(*) FROM metadata WHERE key LIKE 'fallback:%'").fetchone()[0]
    violations={
        'source_page_counts':con.execute('SELECT COUNT(*) FROM source_files s WHERE s.page_count!=(SELECT COUNT(*) FROM pages p WHERE p.source_id=s.id)').fetchone()[0],
        'page_marker_counts':con.execute('SELECT COUNT(*) FROM source_files WHERE marker_count>0 AND marker_count!=page_count').fetchone()[0],
        'entry_offsets':con.execute('''SELECT COUNT(*) FROM entries e JOIN pages p ON p.id=e.page_id JOIN page_texts t ON t.id=p.text_id
            WHERE e.start_offset<0 OR e.end_offset>t.char_count OR e.title!=substr(t.text,e.start_offset+1,e.end_offset-e.start_offset)''').fetchone()[0],
        'mention_offsets':con.execute('''SELECT COUNT(*) FROM mentions m JOIN pages p ON p.id=m.page_id JOIN page_texts t ON t.id=p.text_id
            WHERE m.start_offset<0 OR m.end_offset>t.char_count OR m.end_offset<m.start_offset''').fetchone()[0],
        'span_offsets':con.execute('''SELECT COUNT(*) FROM spans s JOIN pages p ON p.id=s.page_id JOIN page_texts t ON t.id=p.text_id
            WHERE s.start_offset<0 OR s.end_offset>t.char_count OR s.end_offset<s.start_offset''').fetchone()[0],
    }
    if any(violations.values()) or counts['failed_files']:raise RuntimeError('Audit violations: '+str(violations))
    assert con.execute('SELECT COUNT(*) FROM page_fts').fetchone()[0]==counts['page_texts']
    assert con.execute('SELECT COUNT(*) FROM entry_fts').fetchone()[0]==counts['entries']
    print('Verifying original archive, every file checksum, and sampled page reconstructions...',flush=True)
    archive_hash=file_hash(archive)
    ar=con.execute('SELECT * FROM archives WHERE id=?',(archive_hash,)).fetchone();assert ar
    assert ar['status']=='complete'
    rng=random.Random(20260923);samples=[];source_verified=0
    sources=con.execute('SELECT * FROM source_files WHERE archive_id=? ORDER BY zip_index',(archive_hash,)).fetchall()
    sample_ix=set(rng.sample(range(len(sources)),min(24,len(sources))))
    for i,s in enumerate(sources):
        if any(name in s['zip_path'] for name in ('تقريب التهذيب.htm','تهذيب التهذيب - ط الرسالة/001.htm','تهذيب الكمال في أسماء الرجال/002.htm')):sample_ix.add(i)
    with zipfile.ZipFile(archive) as z:
        for i,s in enumerate(sources):
            info=z.infolist()[s['zip_index']];assert info.filename==s['zip_path']
            raw=z.read(info);assert digest(raw)==s['raw_sha256'];assert len(raw)==s['byte_size'];source_verified+=1
            if i not in sample_ix:continue
            elements,markers,enc,meta,fallback=parse_source(raw)
            indices=sorted({0,len(elements)//2,len(elements)-1})
            for ix in indices:
                page=con.execute('SELECT p.*,t.text FROM pages p JOIN page_texts t ON t.id=p.text_id WHERE source_id=? AND ordinal=?',(s['id'],ix)).fetchone()
                parsed=extract_page(elements[ix]);assert parsed['text']==page['text'];assert parsed['label']==page['printed_label']
                if markers:assert page['raw_start']==markers[ix].start()
                samples.append({'zip_path':s['zip_path'],'ordinal':ix,'page_id':page['id'],'passed':True})
    print('Benchmarking source-backed searches...',flush=True)
    api=Database(db,[archive]);timings=[]
    for q,scope,mode in [('أسامة بن عمير','pages','words'),('أبو المليح','pages','phrase'),('محمد بن إسماعيل','entries','words'),('روى عنه ولده وحده','pages','exact'),('اسامة بن عمير','pages','words')]:
        begin=time.perf_counter();result=api.search(q,scope,mode,limit=20)
        timings.append({'query':q,'scope':scope,'mode':mode,'returned':len(result['results']),'has_more':result['has_more'],'elapsed_ms':round((time.perf_counter()-begin)*1000,1)})
        assert result['results'],q
    report={'version':'1.0.0','summary':counts,'integrity_check':integrity,'foreign_key_violations':fk,'offset_violations':violations,
            'fts_integrity':'passed','source_checksums_verified':source_verified,'page_reconstruction_samples':samples,'search_benchmarks':timings,
            'archive':dict(ar),'scope':'Full-text source database with candidate headings and unresolved relationship mentions; no verified person consolidation or semantic deduplication.'}
    (output/'AUDIT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    (output/'SOURCE_MANIFEST.json').write_text(json.dumps({'archive':dict(ar),'files':[dict(s) for s in sources]},ensure_ascii=False,indent=2))
    with (output/'BOOK_INVENTORY.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(['source_group','title','author','edition','publisher','source_files','page_occurrences','candidate_headings'])
        for b in con.execute('SELECT * FROM books ORDER BY source_group'):
            n=con.execute('SELECT COUNT(*) FROM source_files WHERE book_id=?',(b['id'],)).fetchone()[0]
            p=con.execute('SELECT COUNT(*) FROM pages p JOIN source_files s ON s.id=p.source_id WHERE s.book_id=?',(b['id'],)).fetchone()[0]
            e=con.execute('SELECT COUNT(*) FROM entries e JOIN pages p ON p.id=e.page_id JOIN source_files s ON s.id=p.source_id WHERE s.book_id=?',(b['id'],)).fetchone()[0]
            writer.writerow([b['source_group'],b['title'],b['author'],b['edition'],b['publisher'],n,p,e])
    with (output/'NORMALIZATION_VARIANTS.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(['normalized_sha256','exact_variants','status'])
        for r in con.execute('SELECT normalized_sha256,COUNT(*) AS n FROM passages GROUP BY normalized_sha256 HAVING COUNT(*)>1 ORDER BY n DESC'):
            writer.writerow([r[0],r[1],'review_only_not_merged'])
    con.execute('INSERT OR REPLACE INTO metadata VALUES(?,?)',('audit_summary',json.dumps(counts)))
    con.commit();con.close()
    print(json.dumps({'summary':counts,'sampled_pages':len(samples),'search_benchmarks':timings},ensure_ascii=False,indent=2),flush=True)
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('archive');p.add_argument('--db',default=str(BASE/'rijal.sqlite'));p.add_argument('--reports',default=str(BASE/'reports'))
    args=p.parse_args();audit(args.db,args.archive,args.reports)
