"""Authenticate and optionally extract the self-contained Calendar/Weather handoff."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import zipfile

ARCHIVE='Tianhao_Calendar_Weather_96_20261106.zip'


def verify_archive(folder: Path, destination: Path|None=None, archive_output: Path|None=None) -> str:
    """Verify the pinned SHA and ZIP CRC before extraction; refuse existing output.

    The archive contains only data/code/evidence, never fitted model binaries.
    Authenticity of SHA256SUMS is supplied by the reviewed Git commit.
    """
    manifest=json.loads((folder/'ARCHIVE.json').read_text(encoding='utf-8'))
    if manifest['archive_name']!=ARCHIVE:raise ValueError('Unexpected archive name')
    checks={name:digest for digest,name in (line.split(maxsplit=1) for line in
            (folder/'SHA256SUMS').read_text(encoding='utf-8').splitlines())}
    if destination is not None and destination.exists():raise FileExistsError(destination)
    if archive_output is not None and archive_output.exists():raise FileExistsError(archive_output)
    with tempfile.TemporaryDirectory(prefix='tianhao-context-') as temp:
        archive=Path(temp)/ARCHIVE
        with archive.open('wb') as output:
            for part in manifest['parts']:
                if Path(part['name']).name!=part['name']:raise ValueError('Unsafe part path')
                path=folder/part['name']
                with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
                if digest!=part['sha256'] or checks.get(part['name'])!=digest or path.stat().st_size!=part['bytes']:
                    raise ValueError('Part SHA-256/size mismatch: '+part['name'])
                with path.open('rb') as stream:shutil.copyfileobj(stream,output)
        with archive.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
        if digest!=manifest['archive_sha256'] or archive.stat().st_size!=manifest['archive_bytes']:
            raise ValueError('Archive SHA-256/size mismatch')
        with zipfile.ZipFile(archive) as zipped:
            if zipped.testzip() is not None:raise ValueError('ZIP CRC failure')
            names=zipped.namelist()
            if len(names)!=len(set(names)):raise ValueError('Duplicate ZIP paths')
            for name in names:
                path=Path(name)
                if path.is_absolute() or '..' in path.parts or path.parts[0]!='calendar_weather96':
                    raise ValueError('Unsafe ZIP path')
            if destination is not None:
                destination.mkdir(parents=True)
                zipped.extractall(destination)
        if archive_output is not None:shutil.copyfile(archive,archive_output)
        return digest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument('--extract',type=Path,help='New directory; never overwrite existing files')
    parser.add_argument('--assemble',type=Path,help='Optional output ZIP path; never overwrite')
    args=parser.parse_args()
    print('Parts, complete ZIP SHA-256 and CRC passed:',verify_archive(args.directory,args.extract,args.assemble))
