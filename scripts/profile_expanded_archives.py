"""On the archive owner's machine: verify 45 ZIPs, then profile frozen 426.

NO DOWNLOAD. Bounded daily capture partitions and quality checkpoints reuse the
original long-window pipeline. Run only after an explicit complete 45-month raw
archive scan; this script will refuse missing/invalid source and an unfinished
October 1, 2026 boundary archive. Outputs remain in a NEW local ignored root.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import zipfile

import numpy as np
import pandas as pd

from scripts.download_long_window import acquire
from scripts.prepare_long_window import ingest_job, profiles, save
from scripts.scan_expanded_archives import scan
from traffic_recovery.data.coverage import profile_period
from traffic_recovery.data.events import UNIT
from traffic_recovery.data.http import sha256_file


def run(source_root: Path, output: Path, inventory: Path, january_reference: Path, *, workers: int=2) -> dict:
    """Checkpointed all-detector candidate continuity, never cohort re-selection.

    Returns measured monthly/fold quality; `source_root` needs original immutable
    raw ZIPs, HTTP metadata and integrity checkpoints. No missing month is zero-
    filled. Profile may take substantial compute/disk; use --workers 1/2 first.
    """
    if workers not in (1,2,3,4):
        raise ValueError('Use 1–4 bounded workers')
    if (output / 'continuity_manifest.json').exists():
        raise FileExistsError('Complete output exists; use new versioned root')
    if output.exists() and not (output/'archive_inventory.csv').exists():
        raise ValueError('Unrecognized pre-existing output: refuse overwrite')
    output.mkdir(parents=True, exist_ok=True)
    scan_file = output / 'archive_inventory.csv'
    if not scan_file.exists():
        scan([source_root], inventory, scan_file)
    expected = pd.read_csv(scan_file, dtype={'month':str})
    if len(expected)!=45 or expected.status.ne('verified').any():
        raise FileNotFoundError('Stop: all 45 official monthly ZIPs must be checksum-verified; see '+str(scan_file))
    boundary = source_root/'raw/20261001-boundary/archive_check.json'
    if not boundary.is_file():
        raise FileNotFoundError(f'Missing official October 1 capture-day boundary: {boundary}')
    boundary_record=json.loads(boundary.read_text(encoding='utf-8'))
    boundary_zip=source_root/boundary_record['path']
    if boundary_record['sha256']!=sha256_file(boundary_zip):
        raise ValueError('October 1 boundary ZIP hash mismatch')
    frozen=pd.read_csv('reports/lane_expansion_audit/eligible_lane_units.csv',dtype={k:str for k in UNIT})
    if len(frozen)!=426 or frozen.duplicated(UNIT).any():
        raise ValueError('Expected frozen 426 January unit keys')
    reference_manifest=json.loads((january_reference/'reference_manifest.json').read_text(encoding='utf-8'))
    ref_file=january_reference/'full_january_reference.parquet'
    if sha256_file(ref_file)!=reference_manifest['outputs_sha256']['full_january_reference.parquet']:
        raise ValueError('Frozen full-January reference integrity mismatch')
    refs=pd.read_parquet(ref_file,columns=UNIT+['baseline_kmh'])
    if refs[UNIT].to_dict('records')!=frozen[UNIT].to_dict('records'):
        raise ValueError('Frozen reference identities differ from January selection')
    ids=sorted(frozen.detector_id.unique())
    impl={p.name:sha256_file(p) for p in (Path('scripts/prepare_long_window.py'),
                                           Path('src/traffic_recovery/data/long_window.py'))}
    records=[]
    # Month-by-month immutable source verified before dispatch; ingest_job
    # verifies each capture CRC and partitions by capture day with checkpoints.
    for row in expected.itertuples(index=False):
        month=row.month
        archive=Path(row.path)
        if sha256_file(archive)!=row.sha256:
            raise ValueError('Source changed since inventory: '+month)
        with zipfile.ZipFile(archive) as bundle:
            days=sorted({Path(info.filename).name[:8] for info in bundle.infolist()
                         if info.filename.endswith('.xml')})
        jobs=[(str(archive),day,str(output/'processed/lane_snapshots'/
            (f'{day}.parquet' if day[:6]==month else f'{day}-from-{month}.parquet')),
            ids,row.sha256,impl) for day in days]
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for record in pool.map(ingest_job,jobs):records.append(record)
        save(output/'processed/ingest.json',records)
    boundary_job=(str(boundary_zip),'20261001',str(output/'processed/lane_snapshots/20261001.parquet'),
                  ids,boundary_record['sha256'],impl)
    records.append(ingest_job(boundary_job));save(output/'processed/ingest.json',records)
    cfg=json.loads(Path('configs/long_window_96_candidate.json').read_text(encoding='utf-8'))
    profile=profiles(output,output/'processed/lane_snapshots',output/'processed/derived',
        pd.Timestamp(cfg['observation_start']).tz_convert('Asia/Hong_Kong'),
        pd.Timestamp(cfg['observation_end']).tz_convert('Asia/Hong_Kong'),ids,workers)
    # All lanes/directions on frozen 426 detector IDs are retained in the
    # source profiles for identity-change diagnostics; only the frozen 426
    # chosen lane keys enter primary cohort coverage or modeling handoff.
    present=profile.loc[profile.present_slots.gt(0)].copy()
    identity=present.groupby(UNIT).agg(first_observed_day=('day','min'),
        last_observed_day=('day','max'),observed_days=('day','size'),
        first_valid_day=('first_valid','min'),last_valid_day=('last_valid','max')).reset_index()
    identity['first_seen_after_selection']=identity.first_observed_day.ge(
        pd.Timestamp(cfg['selection_end']).tz_convert('Asia/Hong_Kong'))
    identity['frozen_primary_lane']=identity.set_index(UNIT).index.isin(frozen.set_index(UNIT).index)
    quality=profile.merge(frozen[UNIT],on=UNIT,how='inner',validate='many_to_one')
    if quality.day.nunique()!=1369 or len(quality)!=len(frozen)*1369:
        raise ValueError('Incomplete candidate-day coverage grid')
    quality=quality.assign(month=quality.day.dt.strftime('%Y-%m'))
    monthly=quality.groupby(UNIT+['month']).agg(valid_slots=('valid_slots','sum'),
        usable_5m_bins=('usable_5m_bins','sum'),valid_5m_bins=('valid_5m_bins','sum'),
        offline_slots=('offline_slots','sum'),conflict_slots=('conflict_slots','sum'),
        present_slots=('present_slots','sum'),expected_slots=('expected_slots','sum'),
        missing_days=('present_slots',lambda x:x.eq(0).sum()),days=('day','size'),
        worst_invalid_day_gap_seconds=('max_invalid_or_absent_gap_seconds','max')).reset_index()
    monthly['valid_30s_coverage']=monthly.valid_slots/monthly.expected_slots
    monthly['usable_5m_coverage']=monthly.usable_5m_bins/(monthly.days*288)
    monthly['year']=monthly.month.str[:4]
    yearly=monthly.groupby(UNIT+['year']).agg(valid_slots=('valid_slots','sum'),
        usable_5m_bins=('usable_5m_bins','sum'),expected_slots=('expected_slots','sum'),
        days=('days','sum'),missing_days=('missing_days','sum'),
        offline_slots=('offline_slots','sum'),conflict_slots=('conflict_slots','sum')).reset_index()
    yearly['valid_30s_coverage']=yearly.valid_slots/yearly.expected_slots
    yearly['usable_5m_coverage']=yearly.usable_5m_bins/(yearly.days*288)
    # Month-specific p85 is a retrospective drift *diagnostic*, never used to
    # refit historical event baselines or select the initial cohort.
    diagnostic=[]
    bin_folder=output/'processed/derived'
    for month, month_group in monthly.groupby('month'):
        values:dict[tuple[str,str,str],list[float]]={}
        for path in sorted(bin_folder.glob('bins-'+month.replace('-','')+'*.parquet')):
            frame=pd.read_parquet(path,columns=UNIT+['timestamp','available_at','speed_kmh','usable'])
            frame=frame.merge(frozen[UNIT],on=UNIT,how='inner',validate='many_to_one')
            month_start=pd.Timestamp(month+'-01').tz_localize('Asia/Hong_Kong')
            month_end=month_start+pd.offsets.MonthBegin(1)
            frame=frame.loc[frame.usable & frame.speed_kmh.gt(0)
                & frame.timestamp.ge(month_start) & frame.timestamp.lt(month_end)
                & frame.available_at.lt(month_end)]
            for key, group in frame.groupby(UNIT):
                values.setdefault(tuple(key),[]).extend(group.speed_kmh.to_numpy(dtype=float))
        for key, speeds in values.items():
            diagnostic.append(dict(zip(UNIT,key))|{'month':month,
                'positive_usable_bins':len(speeds),'monthly_speed_p85_kmh':float(np.quantile(speeds,.85)),
                'scientific_status':'retrospective_drift_diagnostic_not_a_model_reference'})
    diagnostics=pd.DataFrame(diagnostic)
    if not diagnostics.empty:
        diagnostics=diagnostics.merge(refs,on=UNIT,how='left',validate='many_to_one')
        diagnostics['change_vs_frozen_jan2023_kmh']=diagnostics.monthly_speed_p85_kmh-diagnostics.baseline_kmh
    gap=profile_period(quality,pd.Timestamp(cfg['observation_start']).tz_convert('Asia/Hong_Kong'),
        pd.Timestamp(cfg['observation_end']).tz_convert('Asia/Hong_Kong'))
    quality['fold']=np.select([quality.day.lt(pd.Timestamp(cfg['validation_start'])),
                               quality.day.lt(pd.Timestamp(cfg['test_start']))],
                               ['train','validation'],default='test')
    folds=quality.groupby(UNIT+['fold']).agg(valid_slots=('valid_slots','sum'),
        expected_slots=('expected_slots','sum'),usable_5m_bins=('usable_5m_bins','sum'),
        days=('day','size'),missing_days=('present_slots',lambda x:x.eq(0).sum())).reset_index()
    folds['valid_30s_coverage']=folds.valid_slots/folds.expected_slots
    folds['usable_5m_coverage']=folds.usable_5m_bins/(folds.days*288)
    summary={'observed_months':45,'selection_frozen_from_january':True,'units':426,
        'date_range':[cfg['observation_start'],cfg['observation_end']],
        'not_selection': 'Future monthly/fold coverage and p85 are quality diagnostics; no retrospective cohort filtering',
        'raw_zip_sha256':{row.month:row.sha256 for row in expected.itertuples(index=False)},
        'boundary_zip_sha256':boundary_record['sha256'],
        'ingested_source_rows':sum(r['source_rows'] for r in records),
        'source_snapshot_exclusions':sum(len(r['quarantined_snapshots']) for r in records),
        'identity_changes':'Report keys that appear/disappear by month; physical lane identity cannot be verified from labels alone',
        'created_at_utc':datetime.now(timezone.utc).isoformat()}
    monthly.to_parquet(output/'monthly_continuity.parquet',index=False)
    yearly.to_parquet(output/'yearly_continuity.parquet',index=False)
    diagnostics.to_parquet(output/'monthly_speed_drift.parquet',index=False)
    folds.to_parquet(output/'fold_continuity.parquet',index=False)
    gap.to_parquet(output/'gap_continuity.parquet',index=False)
    identity.to_parquet(output/'detector_identity_inventory.parquet',index=False)
    summary['outputs_sha256']={p.name:sha256_file(p) for p in (output/'monthly_continuity.parquet',
        output/'yearly_continuity.parquet',output/'monthly_speed_drift.parquet',output/'fold_continuity.parquet',output/'gap_continuity.parquet',
        output/'detector_identity_inventory.parquet')}
    (output/'continuity_manifest.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    return summary


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--inventory',type=Path,required=True)
    p.add_argument('--january-reference',type=Path,required=True)
    p.add_argument('--workers',type=int,default=2)
    a=p.parse_args()
    print(json.dumps(run(a.source_root,a.output,a.inventory,a.january_reference,workers=a.workers),indent=2))


if __name__=='__main__':main()
