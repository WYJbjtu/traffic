"""Fit original full-January reference for frozen uncapped January 1–7 cohort.

Only one checked January ZIP is needed. Reuses original 8 full-inventory daily
capture checkpoints; ingests Jan 9–31 for the 426 historically chosen detector
IDs into NEW ignored storage. No future-day/site selection or model training.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path

import pandas as pd

from scripts.prepare_long_window import ingest_job, profile_job, VERSION
from traffic_recovery.data.events import UNIT, fit_reference
from traffic_recovery.data.http import sha256_file
from traffic_recovery.data.pilot import select_cohort


def hkt_boundary(value: str) -> pd.Timestamp:
    """Produce Arrow-comparable nanosecond HKT boundaries from +08 config."""
    return pd.Timestamp(value).tz_convert('Asia/Hong_Kong').as_unit('ns')


def run(root: Path, output: Path, *, workers: int = 2) -> dict:
    """Return measured Jan fit and source-backed monthly quality in isolated root.

    `output` must not exist; original daily source partitions remain untouched.
    Year/month of archive files and all checkpoint hashes are validated. Work
    is resumable via ingest_job/profile_job checkpoints in the same output root;
    an existing final manifest is refused rather than silently overwritten.
    """
    if workers < 1 or workers > 4:
        raise ValueError('Workers must be 1..4 for bounded memory')
    if (output / 'reference_manifest.json').exists():
        raise FileExistsError('Completed full-January reference; use a new output version')
    source = root / 'raw/202301/raw_202301.zip'
    record = json.loads((source.parent / 'archive_check.json').read_text(encoding='utf-8'))
    if record['sha256'] != sha256_file(source) or record['month'] != '202301':
        raise ValueError('Official January ZIP hash/version mismatch')
    config_path = Path('configs/long_window.json')
    cfg = json.loads(config_path.read_text(encoding='utf-8'))
    selection_end, fit_start, fit_end = (hkt_boundary(cfg[key])
                                         for key in ('selection_end', 'observation_start', 'reference_end'))
    profile_path = root / 'selection/derived/coverage_lane_day.parquet'
    first_week = pd.read_parquet(profile_path)
    if first_week.day.min() != fit_start or first_week.day.max() != selection_end - pd.Timedelta(days=1):
        raise ValueError('Selection profile must cover exactly January 1–7')
    candidates, _ = select_cohort(first_week, selection_end, cfg | {'max_units': 100000})
    expected = pd.read_csv('reports/lane_expansion_audit/eligible_lane_units.csv', dtype={name: str for name in UNIT})
    if candidates[UNIT].to_dict('records') != expected[UNIT].to_dict('records'):
        raise ValueError('Frozen 426 identities differ from verified selection; do not choose on future observations')
    ids = sorted(candidates.detector_id.unique())
    source_impl = {p.name: sha256_file(p) for p in
                   (Path('scripts/prepare_long_window.py'), Path('src/traffic_recovery/data/long_window.py'))}
    paths = []
    for day in range(1, 9):
        path = root / f'selection/lane_snapshots/202301{day:02d}.parquet'
        checkpoint = json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
        if (checkpoint['identity']['source_sha256'] != record['sha256']
                or checkpoint['identity']['detector_ids'] is not None
                or checkpoint['sha256'] != sha256_file(path)):
            raise ValueError(f'Unverified original full-inventory partition: {path}')
        paths.append(path)
    jobs = [(str(source), f'202301{day:02d}', str(output / f'lane_snapshots/202301{day:02d}.parquet'),
             ids, record['sha256'], source_impl) for day in range(9, 32)]
    output.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(max_workers=min(workers, 2)) as pool:
        for result in pool.map(ingest_job, jobs):
            if result['quarantined_snapshots']:
                raise ValueError(f'Quarantined January snapshot; review before using reference: {result["identity"]["day"]}')
    paths += [output / f'lane_snapshots/202301{day:02d}.parquet' for day in range(9, 32)]
    if len(paths) != 31:
        raise AssertionError('Missing January capture partitions')
    # Source capture day D and D+1 may contribute to observation day D;
    # January 31's bin-end +10m cutoff is Feb 1, which is outside fit_end.
    # It is excluded by original fit_reference; February captures cannot enter.
    quality_dir = output / 'derived'
    quality_jobs = [(fit_start + pd.Timedelta(days=d),
        [str(paths[d]), str(paths[d + 1])] if d < 30 else [str(paths[d])],
        str(quality_dir), ids) for d in range(31)]
    with ProcessPoolExecutor(max_workers=min(workers, 2)) as pool:
        quality_paths = list(pool.map(profile_job, quality_jobs))
    quality = pd.concat([pd.read_parquet(path) for path in quality_paths], ignore_index=True)
    # Include an explicit zero profile for absent lane-days. No future cohorts.
    days = pd.DataFrame({'day':pd.date_range(fit_start, fit_end, freq='D', inclusive='left')})
    quality = candidates[UNIT].merge(days, how='cross').merge(quality, on=UNIT + ['day'], how='left', validate='one_to_one')
    for key in ['present_slots','valid_slots','offline_slots','conflict_slots','valid_5m_bins','usable_5m_bins']:
        quality[key] = quality[key].fillna(0).astype(int)
    quality['expected_slots'] = 2880
    quality['valid_30s_coverage'] = quality.valid_slots / 2880
    quality['valid_5m_coverage'] = quality.valid_5m_bins / 288
    quality['usable_5m_coverage'] = quality.usable_5m_bins / 288
    quality['missing_day'] = quality.present_slots.eq(0)
    bin_paths = [quality_dir / f'bins-202301{d:02d}.parquet' for d in range(1, 32)]
    reference_parts = []
    first_week_parts = []
    for start in range(0, len(candidates), 24):
        units = candidates.iloc[start:start + 24]
        filters = [[(k, '==', r[k]) for k in UNIT] for _, r in units.iterrows()]
        bins = pd.read_parquet(bin_paths, filters=filters,
            columns=UNIT + ['timestamp','available_at','usable','speed_kmh'])
        ref = fit_reference(bins, fit_start=fit_start, fit_end=fit_end, min_bins=cfg['min_reference_bins'])
        if not ref.empty: reference_parts.append(ref)
        # Earlier first-week *reference proof* used day-7 bins including its
        # 00:00 end and +10m closure (after selection_end), but fit_end=Feb 1.
        # This checks that frozen proof exactly, NOT a cohort selection feature.
        week = fit_reference(bins.loc[bins.timestamp.le(selection_end)],
                             fit_start=fit_start, fit_end=fit_end, min_bins=cfg['min_reference_bins'])
        if not week.empty: first_week_parts.append(week[UNIT + ['reference_bins']])
    reference = pd.concat(reference_parts, ignore_index=True) if reference_parts else pd.DataFrame(columns=UNIT)
    first_week_ref = pd.concat(first_week_parts, ignore_index=True) if first_week_parts else pd.DataFrame(columns=UNIT)
    old_week = pd.read_csv('reports/lane_expansion_audit/event_eligibility.csv', dtype={name:str for name in UNIT})
    check = first_week_ref.merge(old_week[UNIT + ['first_week_reference_bins']], on=UNIT, how='outer', indicator=True)
    if len(check) != len(candidates) or check['_merge'].ne('both').any() or not check.reference_bins.eq(check.first_week_reference_bins).all():
        raise ValueError('First-week reference counts differ from frozen verified selection')
    reference = candidates[UNIT].merge(reference, on=UNIT, how='left', validate='one_to_one')
    reference['full_january_reference_eligible'] = reference.reference_bins.ge(cfg['min_reference_bins']).fillna(False)
    published = pd.read_csv('reports/long_window/cohort.csv', dtype={key:str for key in UNIT})
    matched = reference.head(24).merge(published[UNIT + ['baseline_kmh','reference_bins']], on=UNIT,
        suffixes=('_audit','_published'), validate='one_to_one')
    if (len(matched)!=24 or not matched.baseline_kmh_audit.eq(matched.baseline_kmh_published).all()
            or not matched.reference_bins_audit.eq(matched.reference_bins_published).all()):
        raise ValueError('Original published 24 full-January fitted references differ; stop')
    if not reference.full_january_reference_eligible.all():
        # Do not weaken thresholds or silently drop failures.
        print('WARNING: some first-week eligible units failed full January reference; inspect source', flush=True)
    lane_quality = quality.groupby(UNIT).agg(january_present_slots=('present_slots','sum'),
        january_valid_slots=('valid_slots','sum'), january_offline_slots=('offline_slots','sum'),
        january_conflict_slots=('conflict_slots','sum'), missing_days=('missing_day','sum'),
        january_usable_5m_bins=('usable_5m_bins','sum'),
        january_valid_5m_bins=('valid_5m_bins','sum')).reset_index()
    reference = reference.merge(lane_quality, on=UNIT, validate='one_to_one')
    reference['january_valid_30s_coverage'] = reference.january_valid_slots / (31 * 2880)
    reference['january_usable_5m_coverage'] = reference.january_usable_5m_bins / (31 * 288)
    # No official four-year data have been inspected; do not claim reliability.
    result = {'selection_frozen_from': str(profile_path), 'selection_profile_sha256': sha256_file(profile_path),
        'source_archive_sha256':record['sha256'], 'source_archive_bytes':record['bytes'],
        'source_archive_url': json.loads(source.with_name(source.name+'.meta.json').read_text(encoding='utf-8'))['requested_url'],
        'selection_end_hkt': cfg['selection_end'], 'reference_fit_end_hkt':cfg['reference_end'],
        'reference_method':'Existing fit_reference: positive finite usable 5m km/h; timestamp AND available_at < Feb 1; 85th percentile; >=300 bins',
        'jan31_boundary':'No February 1 capture ingested; any capture after reference-fit end would be excluded. Jan31 23:50/55/Feb1 bin-end closures excluded by fit boundary.',
        'selected_units':len(candidates), 'full_january_reference_eligible':int(reference.full_january_reference_eligible.sum()),
        'reference_failed':int((~reference.full_january_reference_eligible).sum()),
        'original_published_24_reference_exact_match':True,
        'baseline_kmh_min':float(reference.baseline_kmh.min()) if reference.baseline_kmh.notna().any() else None,
        'baseline_kmh_median':float(reference.baseline_kmh.median()) if reference.baseline_kmh.notna().any() else None,
        'baseline_kmh_max':float(reference.baseline_kmh.max()) if reference.baseline_kmh.notna().any() else None,
        'reference_bins_min':int(reference.reference_bins.min()) if reference.reference_bins.notna().any() else None,
        'reference_bins_median':float(reference.reference_bins.median()) if reference.reference_bins.notna().any() else None,
        'january_missing_unit_days':int(quality.missing_day.sum()),
        'full_window_continuity_2023_2026':None, 'expanded_recovery_events':None,
        'created_at_utc':datetime.now(timezone.utc).isoformat()}
    reference.to_parquet(output / 'full_january_reference.parquet', index=False)
    quality.to_parquet(output / 'january_lane_day.parquet', index=False)
    result['outputs_sha256'] = {p.name:sha256_file(p) for p in [output/'full_january_reference.parquet',output/'january_lane_day.parquet']}
    (output / 'reference_manifest.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    return result


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path('data/local/lane-expansion/source'))
    p.add_argument('--output',type=Path,default=Path('data/local/lane-expansion/january426/v1'))
    p.add_argument('--workers',type=int,default=2)
    a=p.parse_args()
    print(json.dumps(run(a.root,a.output,workers=a.workers),indent=2))


if __name__=='__main__':main()
