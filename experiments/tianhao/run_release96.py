"""Portable, explicit-input reproduction of the frozen expanded96 experiment."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import pandas as pd
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src'))
from prepare_local import speed_features
from prepare_external import holidays,weather
from paths import traffic_file
from run_extended_models import run,sha
from traffic_recovery.models.experiment_diagnostics import exact_feature_join
from traffic_recovery.models.contract import ExperimentContract,validate_event_table
from traffic_recovery.models.dataset import build_model_dataset
from document_external_coverage import summarise_coverage

ARTIFACTS=Path(__file__).with_name('expanded96_20261104')
CONTRACT=ROOT/'configs/tianhao_expanded96_30m_contract.json'
PREPARATION_CODE=['experiments/tianhao/run_release96.py','experiments/tianhao/prepare_local.py',
 'experiments/tianhao/prepare_external.py','experiments/tianhao/paths.py',
 'src/traffic_recovery/models/contract.py','src/traffic_recovery/models/dataset.py',
 'src/traffic_recovery/models/experiment_diagnostics.py','src/traffic_recovery/external/calendar.py',
 'src/traffic_recovery/external/_validation.py']


def verify_release(data: Path) -> None:
    """Check every expanded96 file against the repository-pinned Release inventory."""
    path=data/'SHARED_DATA_MANIFEST.json'
    if sha(path)!=sha(ARTIFACTS/'release_files.json'):raise ValueError('Wrong Release manifest')
    for name,item in json.loads(path.read_text(encoding='utf-8'))['files'].items():
        p=(data/name).resolve()
        if not p.is_relative_to(data.resolve()) or p.stat().st_size!=item['bytes'] or sha(p)!=item['sha256']:
            raise ValueError('Release file changed: '+name)


def verify_sources(cache: Path) -> list[dict]:
    """Require exactly the verified weather inventory and preserve fresh retrieval metadata.

    Fresh retrieval times may differ from the historical run; they are recorded as
    new evidence, never substituted for the frozen source inventory timestamps.
    """
    expected=pd.read_csv(ARTIFACTS/'sources.csv').to_dict('records')
    weather_names={r['file'] for r in expected if r['file'].startswith(('temperature_','wind_'))}
    actual={p.name for pattern in ['temperature_????????.zip','wind_????????.zip'] for p in cache.glob(pattern)}
    if actual!=weather_names:raise ValueError('Weather cache inventory differs from authenticated list')
    records=[]
    for item in expected:
        path=cache/item['file'];meta=json.loads(path.with_suffix(path.suffix+'.meta.json').read_text(encoding='utf-8'))
        stamp=pd.Timestamp(meta.get('retrieved_at'))
        if sha(path)!=item['sha256'] or meta.get('sha256')!=item['sha256'] or meta.get('requested_url')!=item['url'] or pd.isna(stamp) or stamp.tzinfo is None or meta.get('status')!=200:
            raise ValueError('Invalid external evidence: '+item['file'])
        records.append(dict(file=item['file'],url=item['url'],sha256=item['sha256'],retrieved_at=stamp.isoformat(),metadata_sha256=sha(path.with_suffix(path.suffix+'.meta.json'))))
    return records


def prepare(data: Path, cache: Path, output: Path) -> dict:
    """Rebuild original96 features without symlinks, personal config or old24 inputs."""
    if output.exists():raise FileExistsError('Use a fresh preparation output')
    verify_release(data);records=verify_sources(cache)
    output.mkdir(parents=True);inputs=output/'inputs';inputs.mkdir()
    speed_features(data_dir=data,output_dir=inputs)
    holidays(data_dir=data,source_cache=cache,output_dir=inputs)
    weather(data_dir=data,source_cache=cache,output_dir=inputs)
    frame=pd.read_parquet(traffic_file(data,'events.parquet'))
    for name in ['speed_history_features','calendar_event_features','weather_event_features']:
        frame=exact_feature_join(frame,pd.read_parquet(inputs/(name+'.parquet')))
    cp=json.loads(CONTRACT.read_text(encoding='utf-8'));contract=ExperimentContract.from_path(CONTRACT)
    frame['split']=frame.split_proposal.astype('string')
    for columns in contract.feature_groups.values():
        for column in columns:frame[column]=pd.to_numeric(frame[column],errors='raise').astype(float)
    frame['weather_features_available_at']=frame.prediction_time
    for kind,value in [('temperature','temperature_c'),('wind','wind_speed_kmh')]:
        mask=frame[value].notna()
        if not (frame.loc[mask,kind+'_available_at'].le(frame.loc[mask,'prediction_time'])&frame.loc[mask,kind+'_observed_at'].le(frame.loc[mask,'prediction_time'])&frame.loc[mask,kind+'_age_minutes'].between(0,60)).all():raise ValueError('Weather availability/age violation')
    validate_event_table(frame,contract)
    dataset,_=build_model_dataset(frame,contract)
    dataset.to_parquet(output/'event_features.parquet',index=False)
    frame.to_parquet(output/'event_feature_audit.parquet',index=False)
    pd.DataFrame(records).to_csv(output/'sources.csv',index=False)
    summarise_coverage(frame).to_csv(output/'coverage.csv',index=False)
    (output/'contract.json').write_text(json.dumps(cp,indent=2),encoding='utf-8')
    manifest=dict(status='passed',created_at=datetime.now(timezone.utc).isoformat(),events=len(frame),known=int(frame.label_30m.notna().sum()),
        release_manifest_sha256=sha(data/'SHARED_DATA_MANIFEST.json'),lock_sha256=sha(ROOT/'uv.lock'),
        code_sha256={name:sha(ROOT/name) for name in PREPARATION_CODE},
        outputs_sha256={p.relative_to(output).as_posix():sha(p) for p in output.rglob('*') if p.is_file()})
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest


def train(prepared: Path, data: Path, output: Path) -> dict:
    """Authenticate prepared bytes, release and preparation source before fitting."""
    verify_release(data)
    manifest=json.loads((prepared/'manifest.json').read_text(encoding='utf-8'))
    if manifest['lock_sha256']!=sha(ROOT/'uv.lock'):raise ValueError('Preparation lock changed')
    for name,digest in manifest['code_sha256'].items():
        if sha(ROOT/name)!=digest:raise ValueError('Preparation source changed: '+name)
    for name,digest in manifest['outputs_sha256'].items():
        if sha(prepared/name)!=digest:raise ValueError('Prepared input changed: '+name)
    return run(dataset_path=prepared/'event_features.parquet',events_path=traffic_file(data,'events.parquet'),contract_path=prepared/'contract.json',
        rules_path=ROOT/'configs/tianhao_extended_models.json',supervised_rules_path=ROOT/'configs/supervised_models.json',
        benchmark_rules_path=ROOT/'configs/benchmarks.json',output=output,figures=True)


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('step',choices=['prepare','train'])
    parser.add_argument('--release-dir',required=True,type=Path)
    parser.add_argument('--source-cache',type=Path)
    parser.add_argument('--prepared-dir',type=Path)
    parser.add_argument('--output-dir',required=True,type=Path)
    args=parser.parse_args()
    if args.step=='prepare':
        if not args.source_cache:parser.error('prepare requires --source-cache')
        result=prepare(args.release_dir,args.source_cache,args.output_dir)
    else:
        if not args.prepared_dir:parser.error('train requires --prepared-dir')
        result=train(args.prepared_dir,args.release_dir,args.output_dir)
    print(json.dumps({k:v for k,v in result.items() if k not in ['outputs_sha256','code_sha256']},indent=2))


if __name__=='__main__':main()
