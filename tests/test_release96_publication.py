"""Real saved-result integrity tests; corruption uses disposable copies only."""
import importlib.util
from pathlib import Path
import shutil
import sys
import json
import subprocess
import pandas as pd
import pytest
ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'experiments/tianhao'


def load_verifier(monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    import verify_release96
    return verify_release96


def test_real_published_metrics_and_config_correspondence(monkeypatch):
    verifier=load_verifier(monkeypatch)
    result=verifier.verify_bundle()
    assert result['prediction_rows']==557160 and result['candidates']==224 and result['sources']==94


def test_autocrlf_checkout_preserves_verified_bytes(tmp_path):
    if not (ROOT/'.git').exists():pytest.skip('Requires a Git checkout')
    subprocess.run(['git','-c','core.autocrlf=true','checkout-index','--all',
                    '--prefix='+tmp_path.as_posix()+'/'],cwd=ROOT,check=True,capture_output=True)
    artifacts=SCRIPTS/'expanded96_20261104'
    manifest=json.loads((artifacts/'publication_manifest.json').read_text())
    paths=[str(artifacts.relative_to(ROOT)/name) for name in manifest['files_sha256']]
    paths+=['uv.lock',manifest['notebook_path'],*manifest['code_sha256'],
            'configs/tianhao_expanded96_30m_contract.json','configs/tianhao_extended_models.json',
            'configs/supervised_models.json','configs/benchmarks.json']
    for name in paths:
        assert (tmp_path/name).read_bytes()==(ROOT/name).read_bytes(),name


@pytest.mark.parametrize('failure',['missing_predictions','changed_metrics','changed_lock','changed_source'])
def test_corrupt_publication_fails(tmp_path,monkeypatch,failure):
    verifier=load_verifier(monkeypatch)
    artifacts=tmp_path/'artifacts';shutil.copytree(SCRIPTS/'expanded96_20261104',artifacts)
    manifest=json.loads((artifacts/'publication_manifest.json').read_text())
    for name in ['uv.lock',manifest['notebook_path'],*manifest['code_sha256']]:
        p=tmp_path/name;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,p)
    monkeypatch.setattr(verifier,'ROOT',tmp_path)
    if failure=='missing_predictions':(artifacts/'predictions.parquet').unlink()
    elif failure=='changed_metrics':
        p=artifacts/'metrics.csv';p.write_text(p.read_text()+'corrupt\n')
    elif failure=='changed_lock':(tmp_path/'uv.lock').write_text('changed')
    else:(tmp_path/next(iter(manifest['code_sha256']))).write_text('changed')
    with pytest.raises((ValueError,FileNotFoundError)):verifier.verify_bundle(artifacts)


def test_release_layout_no_symlinks_and_ambiguity_rejected(tmp_path,monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    from paths import traffic_file
    p=tmp_path/'processed/events.parquet';p.parent.mkdir();p.write_bytes(b'SYNTHETIC')
    assert traffic_file(tmp_path,'events.parquet')==p
    q=tmp_path/'processed/derived/events.parquet';q.parent.mkdir();q.write_bytes(b'SYNTHETIC')
    with pytest.raises(ValueError):traffic_file(tmp_path,'events.parquet')
