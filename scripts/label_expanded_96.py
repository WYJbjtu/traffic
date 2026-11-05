"""Conditional authentic 96-unit event pilot; NO model fitting or interpolation.

Requires complete, checksum-verified 426-unit four-year continuity output
produced by profile_expanded_archives.py. Never run on January-only data or
the published selected-24 Release. New versioned output root only.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pandas as pd

from scripts.label_long_window import availability_safe_splits
from traffic_recovery.data.events import UNIT, EventRules, build_events, fit_reference
from traffic_recovery.data.http import sha256_file
from traffic_recovery.data.pilot import label_summary


def run(profile_root: Path, january: Path, config_path: Path, output: Path) -> dict:
    """Label frozen id-order 96 with existing January fit, quality and split rules.

    No future screening, zero filling, cohort replacement or threshold tuning.
    One unit is read at a time from the full-history 5m Parquet partitions.
    Resume only if per-unit checkpoint identity and hashes validate; partial
    units without checkpoint require manual review before retry.
    """
    manifest_path=profile_root/'continuity_manifest.json'
    if not manifest_path.is_file():
        raise FileNotFoundError(f'Missing complete verified 2023–2026 source: {manifest_path}')
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('observed_months')!=45 or manifest.get('units')!=426:
        raise ValueError('Continuity artifact is not complete frozen 426 cohort')
    for name, sha in manifest['outputs_sha256'].items():
        if sha256_file(profile_root/name)!=sha:
            raise ValueError('Continuity manifest hash mismatch: '+name)
    config=json.loads(config_path.read_text(encoding='utf-8'))
    original=json.loads(Path('configs/long_window.json').read_text(encoding='utf-8'))
    for key,value in original.items():
        if key not in {'max_units','status','version'} and config.get(key)!=value:
            raise ValueError('Scientific rule differs from published study: '+key)
    if config['max_units']!=96:
        raise ValueError('Expected frozen 96-unit configuration')
    full_ref_manifest=json.loads((january/'reference_manifest.json').read_text(encoding='utf-8'))
    frozen_ref=january/'full_january_reference.parquet'
    if sha256_file(frozen_ref)!=full_ref_manifest['outputs_sha256']['full_january_reference.parquet']:
        raise ValueError('January reference hash mismatch')
    ref=pd.read_parquet(frozen_ref)
    frozen=pd.read_csv('reports/lane_expansion_audit/eligible_lane_units.csv',dtype={x:str for x in UNIT}).head(96)
    if len(frozen)!=96 or ref.head(96)[UNIT].to_dict('records')!=frozen[UNIT].to_dict('records'):
        raise ValueError('96-unit selection changed')
    if not ref.head(96).full_january_reference_eligible.all():
        raise ValueError('January reference requirement not met')
    paths=sorted((profile_root/'processed/derived').glob('bins-*.parquet'))
    if len(paths)<1369:
        raise ValueError('Incomplete full-window daily bins')
    config_sha=sha256_file(config_path)
    input_fingerprint={'continuity_manifest_sha256':sha256_file(manifest_path),
                       'january_reference_sha256':sha256_file(frozen_ref),
                       'config_sha256':config_sha,
                       'label_code_sha256':sha256_file(Path('src/traffic_recovery/data/events.py')),
                       'split_code_sha256':sha256_file(Path('scripts/label_long_window.py'))}
    fit_start=pd.Timestamp(config['observation_start']).tz_convert('Asia/Hong_Kong')
    fit_end=pd.Timestamp(config['reference_end']).tz_convert('Asia/Hong_Kong')
    end=pd.Timestamp(config['observation_end']).tz_convert('Asia/Hong_Kong')
    val=pd.Timestamp(config['validation_start']).tz_convert('Asia/Hong_Kong')
    test=pd.Timestamp(config['test_start']).tz_convert('Asia/Hong_Kong')
    rules=EventRules(config['congestion_ratio'],config['recovery_ratio'],config['onset_bins'],config['recovery_bins'])
    if (output/'pilot_manifest.json').exists():
        raise FileExistsError('Completed expanded pilot exists: choose new version')
    output.mkdir(parents=True, exist_ok=True)
    results=[]
    for _, identity in frozen.iterrows():
        unit={k:identity[k] for k in UNIT}
        key=hashlib.sha256(json.dumps(unit,sort_keys=True).encode()).hexdigest()[:16]
        folder=output/'units'/key
        checkpoint=folder/'checkpoint.json'
        if checkpoint.exists():
            prior=json.loads(checkpoint.read_text(encoding='utf-8'))
            if (prior.get('inputs')!=input_fingerprint or prior.get('unit')!=unit
                    or any(sha256_file(folder/name)!=digest for name,digest in prior['outputs_sha256'].items())):
                raise ValueError('Stale/corrupt unit checkpoint: '+str(folder))
            results.append(prior['result'])
            continue
        if folder.exists():
            raise ValueError('Partial uncheckpointed output; inspect before rerun: '+str(folder))
        filters=[(k,'==',unit[k]) for k in UNIT]
        bins=pd.read_parquet(paths,filters=filters).sort_values('timestamp')
        if bins.empty or bins.timestamp.duplicated().any():
            raise ValueError('Absent or duplicate historical bins for '+str(unit))
        actual=fit_reference(bins,fit_start=fit_start,fit_end=fit_end,min_bins=config['min_reference_bins'])
        earlier=ref.loc[(ref.detector_id==unit['detector_id']) & (ref.direction==unit['direction']) &
                        (ref.lane_id==unit['lane_id'])].iloc[0]
        if (len(actual)!=1 or actual.iloc[0].reference_bins!=earlier.reference_bins or
                actual.iloc[0].baseline_kmh!=earlier.baseline_kmh):
            raise ValueError('Full-window January source conflicts with frozen reference: '+str(unit))
        events=build_events(bins,float(earlier.baseline_kmh),start=fit_end,end=end,rules=rules)
        if len(events):
            events['reference_fit_end']=fit_end
            events['split_proposal'],events['outcome_maturity_at']=availability_safe_splits(events,val,test,end)
            if events.event_id.duplicated().any():
                raise ValueError('Duplicate event IDs')
        folder.mkdir(parents=True)
        bins.to_parquet(folder/'bins.parquet',index=False,compression='zstd')
        outputs={'bins.parquet':sha256_file(folder/'bins.parquet')}
        if len(events):
            events.to_parquet(folder/'events.parquet',index=False,compression='zstd')
            outputs['events.parquet']=sha256_file(folder/'events.parquet')
        result={'unit':unit,'events':len(events),'labels':label_summary(events),
            'split_counts':events.split_proposal.value_counts().to_dict() if len(events) else {},
            'source_reference_bins':int(earlier.reference_bins),
            'source_baseline_kmh':float(earlier.baseline_kmh)}
        checkpoint.write_text(json.dumps({'inputs':input_fingerprint,'unit':unit,
            'outputs_sha256':outputs,'result':result},indent=2)+'\n',encoding='utf-8')
        results.append(result)
    # Outcome rows remain distinct from 24-unit published events; no labels
    # changed, and any unknown is kept as nullable in each real event table.
    summary={'status':'authentic_expanded_96_data_only_pilot','units':96,'config_version':config['version'],
        'inputs':input_fingerprint,'events':sum(r['events'] for r in results),
        'per_unit':results,
        'by_split':{split:sum(r['split_counts'].get(split,0) for r in results)
                    for split in ('train','validation','test','purged')},
        'horizons':{str(h):{name:sum(r['labels']['horizons'][str(h)][name]
            for r in results) for name in ('positive','negative','unknown')} for h in (15,30,60)},
        'no_model_training':True,'created_at_utc':datetime.now(timezone.utc).isoformat()}
    (output/'pilot_manifest.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    return summary


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profile-root',type=Path,required=True)
    p.add_argument('--january-reference',type=Path,required=True)
    p.add_argument('--config',type=Path,default=Path('configs/long_window_96_candidate.json'))
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    result=run(a.profile_root,a.january_reference,a.config,a.output)
    print(json.dumps({k:v for k,v in result.items() if k!='per_unit'},indent=2))


if __name__=='__main__':main()
