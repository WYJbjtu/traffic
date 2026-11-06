"""Real artifact verification plus explicitly synthetic join-rejection fixtures."""
import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

ROOT=Path(__file__).resolve().parents[1]
FOLDER=ROOT/'experiments/tianhao/calendar_weather96_20261106'


def load(path: Path,name: str):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope='module')
def verifier(tmp_path_factory):
    archive=load(FOLDER/'verify_archive.py','handoff_archive')
    target=tmp_path_factory.mktemp('handoff')/'extracted'
    archive.verify_archive(FOLDER,target,archive_output=target.parent/'assembled.zip')
    folder=target/'calendar_weather96'
    return load(folder/'verify_handoff.py','handoff_data'),folder


def test_authentic_calendar_weather96_artifact(verifier):
    module,folder=verifier
    result=module.verify_bundle(folder)
    assert result['status']=='passed' and result['events']==30452
    assert result['temperature_missing']==18 and result['wind_missing']==116
    assert result['station_snapshots']==43387


@pytest.mark.parametrize('failure',['duplicate','wrong_time','missing_event'])
def test_join_rejects_misalignment(verifier,failure):
    module,_=verifier
    # SYNTHETIC fixture: these IDs/times are not scientific observations.
    reference=pd.DataFrame({'event_id':['synthetic-a','synthetic-b'],
        'prediction_time':pd.date_range('2024-01-01',periods=2,tz='Asia/Hong_Kong')})
    candidate=reference.copy()
    if failure=='duplicate':candidate.event_id=['synthetic-a','synthetic-a']
    elif failure=='wrong_time':candidate.prediction_time+=pd.Timedelta(minutes=5)
    else:candidate=candidate.iloc[:1]
    with pytest.raises(ValueError):module.aligned(reference,candidate)


def test_archive_corruption_is_rejected(tmp_path):
    module=load(FOLDER/'verify_archive.py','handoff_corruption')
    (tmp_path/'SHA256SUMS').write_bytes((FOLDER/'SHA256SUMS').read_bytes())
    (tmp_path/'ARCHIVE.json').write_bytes((FOLDER/'ARCHIVE.json').read_bytes())
    first=json.loads((FOLDER/'ARCHIVE.json').read_text(encoding='utf-8'))['parts'][0]['name']
    (tmp_path/first).write_bytes(b'SYNTHETIC CORRUPTED ARCHIVE PART')
    with pytest.raises(ValueError,match='SHA-256'):module.verify_archive(tmp_path)


@pytest.mark.parametrize('changed_source',[False,True])
def test_notebook_allows_output_refresh_but_rejects_code_change(verifier,changed_source):
    module,folder=verifier
    path=folder/'Calendar_Weather96_交接核验.ipynb'
    original=path.read_bytes()
    notebook=json.loads(original)
    cell=next(c for c in notebook['cells'] if c['cell_type']=='code')
    if changed_source:cell['source'].append('\nprint("SYNTHETIC TAMPER")')
    else:cell['execution_count']=999
    try:
        path.write_text(json.dumps(notebook),encoding='utf-8')
        if changed_source:
            with pytest.raises(ValueError,match='Notebook execution source'):module.verify_bundle(folder)
        else:assert module.verify_bundle(folder)['status']=='passed'
    finally:path.write_bytes(original)
