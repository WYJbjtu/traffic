"""Rerun Tianhao's frozen 30m models on the expanded96 Release, locally only."""
from pathlib import Path
import hashlib,json,sys,zipfile,shutil
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]
CFG=json.loads((ROOT/'notebooks/project.local.json').read_text(encoding='utf-8'))
REPO=ROOT/CFG['repository']
sys.path[:0]=[str(REPO/'src'),str(REPO/'experiments/tianhao')]
from prepare_local import speed_features
from prepare_external import holidays,weather
from run_experiment import GROUPS
from run_extended_models import run,sha
from run_workflow import validate_source_metadata
from traffic_recovery.models.experiment_diagnostics import exact_feature_join
from traffic_recovery.models.contract import ExperimentContract,validate_event_table
from traffic_recovery.models.dataset import build_model_dataset
from document_external_coverage import summarise_coverage

BASE=ROOT/'notebooks/outputs/release96-20261104'
EXPECTED='f5be559a6ad8df69e68fbc382fb609d13fdae40aa044c9d1fe4d7e3b2253b6b8'


def prepare() -> dict:
    """Authenticate/extract the new release and reconstruct event features."""
    out=BASE/'prepared_run'
    if out.exists():raise FileExistsError('Choose a fresh preparation directory')
    archive=BASE/'sources/data.zip'
    if archive.stat().st_size!=870121429 or sha(archive)!=EXPECTED:raise ValueError('Release checksum/size mismatch')
    data=BASE/'release';data.mkdir()
    with zipfile.ZipFile(archive) as z:
        for member in z.infolist():
            target=(data/member.filename).resolve()
            if not target.is_relative_to(data.resolve()):raise ValueError('Unsafe archive member')
        z.extractall(data)
    manifests=list(data.rglob('SHARED_DATA_MANIFEST.json'))
    if len(manifests)!=1:raise ValueError('Expected one release manifest')
    data=manifests[0].parent
    manifest=json.loads(manifests[0].read_text(encoding='utf-8'))
    for name,item in manifest['files'].items():
        expected=item['sha256'] if isinstance(item,dict) else item
        if sha(data/name)!=expected:raise ValueError('Internal checksum mismatch: '+name)
    out.mkdir();view=out/'data/processed/derived';view.mkdir(parents=True)
    for name in ['events.parquet','cohort_bins.parquet']:
        (view/name).symlink_to((data/'processed'/name).resolve())
    cache=ROOT/CFG['source_cache'];snap=ROOT/CFG['feature_snapshot']
    original=json.loads((snap/'rerun_manifest.json').read_text())
    if sha(snap/'source_checks.json')!=original['source_checks_sha256']:raise ValueError('Source evidence mismatch')
    checks=[]
    for item in json.loads((snap/'source_checks.json').read_text()):
        if item['file']=='traffic_prepared.zip':continue
        p=cache/item['file']
        if sha(p)!=item['sha256']:raise ValueError('External original bytes changed')
        validate_source_metadata(json.loads(p.with_suffix(p.suffix+'.meta.json').read_text()),item)
        checks.append(item)
    pd.DataFrame(checks).to_csv(out/'source_checks.csv',index=False)
    inputs=out/'inputs';inputs.mkdir()
    speed_features(data_dir=out/'data',output_dir=inputs)
    holidays(data_dir=out/'data',source_cache=cache,output_dir=inputs)
    weather(data_dir=out/'data',source_cache=cache,output_dir=inputs)
    events=pd.read_parquet(view/'events.parquet')
    frame=events.copy()
    for name in ['speed_history_features','calendar_event_features','weather_event_features']:
        frame=exact_feature_join(frame,pd.read_parquet(inputs/f'{name}.parquet'))
    frame['split']=frame.split_proposal.astype('string')
    groups={key:value for key,value in GROUPS.items() if key!='flow'}
    for cols in groups.values():
        for c in cols:frame[c]=pd.to_numeric(frame[c],errors='raise').astype(float)
    frame['weather_features_available_at']=frame.prediction_time
    for kind,value in [('temperature','temperature_c'),('wind','wind_speed_kmh')]:
        mask=frame[value].notna()
        if not (frame.loc[mask,kind+'_available_at'].le(frame.loc[mask,'prediction_time']) & frame.loc[mask,kind+'_observed_at'].le(frame.loc[mask,'prediction_time']) & frame.loc[mask,kind+'_age_minutes'].between(0,60)).all():raise ValueError('Weather future/stale data')
    cp=json.loads((REPO/'configs/tianhao_long_window_30m_contract.json').read_text())
    requirements={k:v for k,v in cp['availability_requirements'].items() if k!='flow_features_available_at'}
    cp.update(version='tianhao-expanded96-30m-v1',feature_groups=groups,availability_requirements=requirements,availability_columns=list(requirements))
    (out/'contract.json').write_text(json.dumps(cp,indent=2))
    contract=ExperimentContract.from_path(out/'contract.json');validate_event_table(frame,contract)
    dataset,validation=build_model_dataset(frame,contract)
    dataset.to_parquet(out/'event_features.parquet',index=False);frame.to_parquet(out/'event_feature_audit.parquet',index=False)
    summarise_coverage(frame).to_csv(out/'coverage.csv',index=False)
    result=dict(status='passed',release='data-expanded-96-2023-2026-v1',zip_sha256=EXPECTED,events=len(events),known=int(events.label_30m.notna().sum()),
        cohort_units=manifest['units'],event_units=len(events[['detector_id','direction','lane_id']].drop_duplicates()),feature_groups=groups,
        excluded='Flow/occupancy not present in expanded96 package; old24 features not reused. Rain/incidents/events/spatial lack approved replay inputs.',
        validation=validation,outputs_sha256={p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file() and not p.is_symlink()})
    (out/'manifest.json').write_text(json.dumps(result,indent=2,default=str));return result


def train(output:Path) -> dict:
    p=BASE/'prepared_run'
    manifest=json.loads((p/'manifest.json').read_text())
    for name,digest in manifest['outputs_sha256'].items():
        if sha(p/name)!=digest:raise ValueError('Prepared input changed')
    return run(dataset_path=p/'event_features.parquet',events_path=p/'data/processed/derived/events.parquet',contract_path=p/'contract.json',
        rules_path=REPO/'configs/tianhao_extended_models.json',supervised_rules_path=REPO/'configs/supervised_models.json',
        benchmark_rules_path=REPO/'configs/benchmarks.json',output=output,figures=True)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('step',choices=['prepare','train']);args=parser.parse_args()
    result=prepare() if args.step=='prepare' else train(BASE/'models')
    print({k:result[k] for k in ['status']})
