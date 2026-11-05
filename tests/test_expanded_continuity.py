"""Synthetic source fixtures for offline acquisition gate and static cohort policy."""
from hashlib import sha256
import json
from pathlib import Path

import pandas as pd
import pytest


def _modules(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1]))
    from scripts.label_expanded_96 import run as label
    from scripts.profile_expanded_archives import run as profile
    from scripts.report_expanded_january import district_round_robin
    from scripts.scan_expanded_archives import scan
    return scan,profile,label,district_round_robin


def test_missing_44_archives_are_not_zero_filled_or_labeled(tmp_path,monkeypatch):
    scan,profile,label,_=_modules(monkeypatch)
    inv=tmp_path/'archive_inventory.json'
    months=[f'{year}{month:02d}' for year in range(2023,2027) for month in range(1,13)
            if (year,month)<=(2026,9)]
    archive=tmp_path/'source/raw/202301/raw_202301.zip'
    archive.parent.mkdir(parents=True)
    archive.write_bytes(b'synthetic-fixture-not-an-official-archive')
    digest=sha256(archive.read_bytes()).hexdigest()
    (archive.parent/'archive_check.json').write_text(json.dumps({'bytes':archive.stat().st_size,
        'sha256':digest,'snapshots':1}),encoding='utf-8')
    (archive.parent/'raw_202301.zip.meta.json').write_text(json.dumps({'bytes':archive.stat().st_size,
        'sha256':digest}),encoding='utf-8')
    inv.write_text(json.dumps({'data-files':[{'timestamp':m+'01','period':'M',
        'size':archive.stat().st_size if m=='202301' else 100,'resource_file_count':1}
        for m in months]}),encoding='utf-8')
    (tmp_path/'archive_inventory.json.meta.json').write_text(json.dumps({'sha256':sha256(inv.read_bytes()).hexdigest(),
        'status':200,'requested_url':'synthetic://inventory'}),encoding='utf-8')
    result=scan([tmp_path/'source'],inv,tmp_path/'scan.csv')
    assert result['verified_months']==1 and result['missing_months']==44
    with pytest.raises(FileNotFoundError,match='45 official monthly ZIPs'):
        profile(tmp_path/'source',tmp_path/'output',inv,tmp_path/'missing-january')
    assert not (tmp_path/'output/processed').exists()
    with pytest.raises(FileNotFoundError,match='complete verified'):
        label(tmp_path/'output',tmp_path/'missing-january',tmp_path/'candidate.json',tmp_path/'pilot')
    assert not (tmp_path/'pilot').exists()


def test_static_district_rotation_never_uses_future_quality(tmp_path,monkeypatch):
    _,_,_,rotate=_modules(monkeypatch)
    frame=pd.DataFrame({'detector_id':['A1','A2','B1','B2','B3'],
                        'direction':['North']*5,'District':['A','A','B','B','B'],
                        'test_coverage':[0,1,1,0,1]})
    result=rotate(frame,4)
    assert result.detector_id.tolist()==['A1','B1','A2','B2']
    frame['test_coverage']=[1,0,0,1,0]
    assert rotate(frame,4).detector_id.tolist()==result.detector_id.tolist()
    with pytest.raises(ValueError,match='Not enough eligible'):
        rotate(frame,6)
