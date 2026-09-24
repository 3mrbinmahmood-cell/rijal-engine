"""Stable Arabic search normalization. Original text is never changed."""
import hashlib
import re
import sqlite3

VERSION = '1.0.0'
MARKS = re.compile('[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed\u0640\u200b-\u200f\ufeff]')
TRANSLATE = str.maketrans('أإآٱى٠١٢٣٤٥٦٧٨٩', 'ااااي0123456789')

def normalize(text):
    text = MARKS.sub('', text).translate(TRANSLATE)
    text = re.sub(r'(?<!\w)ابن(?!\w)', 'بن', text)
    return re.sub(r'\s+', ' ', text).strip().lower()

def digest(value):
    if isinstance(value, str): value = value.encode('utf-8')
    return hashlib.sha256(value).hexdigest()

def file_hash(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''): h.update(block)
    return h.hexdigest()

def connect(path, readonly=False):
    from pathlib import Path
    con = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True) if readonly else sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    con.execute('PRAGMA busy_timeout=10000')
    return con
