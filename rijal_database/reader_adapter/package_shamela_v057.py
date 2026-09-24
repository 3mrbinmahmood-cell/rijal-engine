"""Rebuild Shamela Reader V0.5.7 from the unchanged V0.5.6 ZIP.

Only program files in shamela_v057 are overlaid. The large source data and
all other archive members are copied unchanged from the input ZIP.
"""
import argparse
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

OVERLAY=Path(__file__).with_name('shamela_v057')


def build(source,output):
    source=Path(source);output=Path(output)
    if output.exists():raise ValueError('Use a new output path')
    if source.resolve()==output.resolve():raise ValueError('Do not replace the source')
    replacement={p.relative_to(OVERLAY).as_posix():p for p in OVERLAY.rglob('*')
                 if p.is_file()}
    if not {'index.html','full-corpus.js','rijal-db-client.js'}<=replacement.keys():
        raise ValueError('Reader overlay is incomplete')
    with ZipFile(source) as original:
        names={info.filename for info in original.infolist()}
        if not {'index.html','reader.js','data.js','rijal-data.js'}<=names:
            raise ValueError('Expected Shamela Reader package is missing')
        if 'قاعدة الرجال الكاملة' in original.read('index.html').decode('utf-8'):
            raise ValueError('Input reader already has the full-corpus view')
        with ZipFile(output,'w',ZIP_DEFLATED,compresslevel=6) as target:
            for info in original.infolist():
                if info.is_dir():target.writestr(info,b'');continue
                path=replacement.pop(info.filename,None)
                target.writestr(info,path.read_bytes() if path else original.read(info.filename))
            for name,path in sorted(replacement.items()):target.write(path,name)
    with ZipFile(source) as original,ZipFile(output) as result:
        for name in ('data.js','toc.js','rijal-data.js','reader.js'):
            if original.read(name)!=result.read(name):
                raise ValueError('Bundled source data or reader logic changed: '+name)
        if result.testzip():raise ValueError('Output ZIP failed CRC verification')
    return output


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('v056_zip');p.add_argument('output_zip')
    a=p.parse_args()
    print(build(a.v056_zip,a.output_zip))


if __name__=='__main__':main()
