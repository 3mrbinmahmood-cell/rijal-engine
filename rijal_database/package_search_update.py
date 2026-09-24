"""Package a small search-order patch for an already installed Rijal Database V1."""
import argparse
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED


def build(output):
    output=Path(output)
    if output.exists():raise ValueError('Use a new output path')
    root=Path(__file__).resolve().parent
    with ZipFile(output,'w',ZIP_DEFLATED) as z:
        z.write(root/'server.py','rijal_database/server.py')
        z.writestr('README.txt',
            'Rijal Database V1 search ordering update\n\n'
            'Close START_WINDOWS.bat first. Make a copy of your existing '
            'rijal_database/server.py, then extract this ZIP into the parent folder '
            'that contains rijal_database. Allow server.py to be replaced. Restart '
            'START_WINDOWS.bat. No SQLite database, original source, reader note, '
            'or annotation file is changed. Searches of entries now show entries '
            'headed by the name before incidental mentions within search results. '
            'Pagination and corpus limits remain. The update does not verify '
            'identities or grade hadith.\n')
    with ZipFile(output) as z:
        if z.testzip():raise ValueError('ZIP integrity check failed')
    return output

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('output_zip')
    print(build(p.parse_args().output_zip))
