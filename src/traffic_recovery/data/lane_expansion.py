"""Auditable Jan 2023 uncapped lane selection; no new labels, ML or imputation.

Inputs are the full-inventory January 1–7 outputs of the original long-window
pipeline, NOT the published selected-detector-only 2023–2026 Release. Reference
eligibility can be *proven* from a qualifying first-week subset, but full-January
fitted baselines and full-window continuity cannot be inferred from it.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

import pandas as pd

from traffic_recovery.data.events import UNIT, fit_reference
from traffic_recovery.data.http import sha256_file
from traffic_recovery.data.pilot import select_cohort


@dataclass(frozen=True)
class AuditInputs:
    """Verified full-inventory January capture/quality root and read-only evidence."""
    selection_root: Path
    configuration: Path
    published_cohort: Path
    published_comparison: Path
    metadata: Path
    published_monthly: Path
    network: Path | None = None
    processed_pilot: Path | None = None
    inventory: Path | None = None


def selection_table(profile: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Mirror select_cohort()'s four conjunctions, with individual exclusions.

    `profile` contains all seven HKT days for every historically observed unit.
    No future observations are accepted. Rows are one observed lane identity.
    """
    end = pd.Timestamp(config['selection_end'])
    if not isinstance(profile.day.dtype, pd.DatetimeTZDtype) or profile.day.isna().any():
        raise ValueError('Selection days must be aware')
    if profile.day.min() != pd.Timestamp(config['observation_start']) or profile.day.max() != end - pd.Timedelta(days=1):
        raise ValueError('Incomplete selection window or future-day leakage')
    if profile.duplicated(UNIT + ['day']).any():
        raise ValueError('Duplicate lane/day quality profile')
    if profile.groupby(UNIT, observed=True).day.nunique().ne(7).any():
        raise ValueError('Missing explicit zero-coverage days')
    table = profile.groupby(UNIT, observed=True).agg(
        valid_30s_mean=('valid_coverage', 'mean'), valid_5m_mean=('valid_5m_coverage', 'mean'),
        valid_5m_min=('valid_5m_coverage', 'min'), flow_5m_mean=('usable_5m_coverage', 'mean'),
        conflicts=('conflict_slots', 'sum'), offline_slots=('offline_slots', 'sum'),
        present_slots=('present_slots', 'sum'), valid_slots=('valid_slots', 'sum'),
        valid_5m_bins=('valid_5m_bins', 'sum'), usable_5m_bins=('usable_5m_bins', 'sum'),
        max_invalid_or_absent_gap_seconds=('max_invalid_or_absent_gap_seconds', 'max')).reset_index()
    conditions = {'valid_5m_mean': table.valid_5m_mean.ge(config['valid_5m_mean_min']),
                  'valid_5m_daily_min': table.valid_5m_min.ge(config['valid_5m_daily_min']),
                  'positive_flow_5m_mean': table.flow_5m_mean.ge(config['flow_5m_mean_min']),
                  'no_source_conflicts': table.conflicts.eq(0)}
    for name, value in conditions.items():
        table['passes_' + name] = value
    table['passes_all'] = pd.concat(conditions, axis=1).all(axis=1)
    eligible = table.loc[table.passes_all].sort_values(
        ['detector_id', 'direction', 'flow_5m_mean', 'valid_5m_mean', 'lane_id'],
        ascending=[True, True, False, False, True]).drop_duplicates(['detector_id', 'direction'])
    chosen = eligible[UNIT].assign(one_lane_chosen=True)
    table = table.merge(chosen, on=UNIT, how='left', validate='one_to_one')
    table['one_lane_chosen'] = table.one_lane_chosen.eq(True)
    table['exclusion_reasons'] = table.apply(lambda row: '|'.join(
        [name for name in conditions if not row['passes_' + name]] +
        (['eligible_other_lane_preferred'] if row.passes_all and not row.one_lane_chosen else [])), axis=1)
    return table


def processed_proximity(network: Path, processed: Path, detectors: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """100m EPSG:2326 geographic *review leads*, NOT approved road matching.

    Only source-valid processed records with exact current route ID and real
    archived snapshot are considered. Historical route geometry/version and
    detector-coordinate validity remain unverified; no nearest-road fallback.
    """
    import pyarrow.dataset as ds
    from shapely import wkb
    from shapely.geometry import Point
    from shapely.strtree import STRtree
    samples = sorted(processed.glob('observations_*.parquet'))
    if not samples:
        raise FileNotFoundError('No authentic processed snapshots')
    frames = [pd.read_parquet(path, columns=['segment_id', 'speed_kmh', 'valid', 'id_match',
        'irn_version', 'observed_at']).assign(snapshot_id=path.stem.removeprefix('observations_'))
        for path in samples]
    all_speed = pd.concat(frames, ignore_index=True)
    good = all_speed.loc[all_speed.valid.eq('Y') & all_speed.speed_kmh.notna() & all_speed.id_match].copy()
    ids = sorted(set(good.segment_id.astype(str)))
    geometry = ds.dataset(network / 'geometry', format='parquet', partitioning='hive').to_table(
        columns=['route_id', 'geometry_wkb_2326'], filter=ds.field('route_id').isin(ids)).to_pandas()
    if geometry.route_id.duplicated().any():
        raise ValueError('Duplicate current-network ROUTE_ID')
    lines = geometry.geometry_wkb_2326.map(wkb.loads).tolist()
    tree = STRtree(lines)
    rows = []
    by_route = good.groupby('segment_id').snapshot_id.agg(lambda s:'|'.join(sorted(set(s)))).to_dict()
    for row in detectors.itertuples(index=False):
        if pd.isna(row.Easting) or pd.isna(row.Northing):
            continue
        location = Point(float(row.Easting), float(row.Northing))
        for index in tree.query(location, predicate='dwithin', distance=100):
            rid = geometry.iloc[int(index)].route_id
            rows.append({'detector_id':row.detector_id, 'direction':row.direction,
                'lane_id':row.lane_id, 'route_id_current_geometry':rid,
                'distance_m':location.distance(lines[int(index)]),
                'processed_snapshot_ids':by_route[rid],
                'review_status':'proximity_only_unverified_not_navigable'})
    result = pd.DataFrame(rows, columns=['detector_id','direction','lane_id','route_id_current_geometry',
        'distance_m','processed_snapshot_ids','review_status'])
    return result, {'radius_m':100, 'candidate_detector_ids':int(result.detector_id.nunique()),
        'candidate_segment_ids':int(result.route_id_current_geometry.nunique()),
        'candidate_pairs':len(result), 'raw_processed_same_time_agreement':None,
        'historical_version_approved':False,
        'warning':'Distance-only review leads; no historical road version/turn/direction validation or raw/processed independence claim'}


def audit(inputs: AuditInputs, output: Path) -> dict:
    """Write lightweight evidence only after immutable-source and 24-unit checks.

    Fails closed if outputs already exist. Complete original source ZIP and
    eight checkpoint hashes are verified; no new source is fetched. Output
    event counts for expanded scenarios stay null, not a guessed extrapolation.
    """
    if output.exists():
        raise FileExistsError(f'Choose a new report version; refusing overwrite: {output}')
    config = json.loads(inputs.configuration.read_text(encoding='utf-8'))
    root = inputs.selection_root
    archive = root / 'raw/202301/raw_202301.zip'
    check = json.loads((archive.parent / 'archive_check.json').read_text(encoding='utf-8'))
    if check['sha256'] != sha256_file(archive) or check['month'] != '202301':
        raise ValueError('Official January archive checksum/identity mismatch')
    archive_meta = json.loads(archive.with_name(archive.name + '.meta.json').read_text(encoding='utf-8'))
    if archive_meta.get('sha256') != check['sha256'] or archive_meta.get('status') != 206:
        raise ValueError('Archived ZIP HTTP metadata disagrees with checked source')
    sources: dict = {'official_raw_url': 'https://resource.data.one.gov.hk/td/traffic-detectors/rawSpeedVol-all.xml',
                     'archive_requested_url': archive_meta['requested_url'],
                     'archive_final_url': archive_meta['final_url'],
                     'archive_206_etag': archive_meta['headers']['ETag'],
                     'archive_acquired_at_utc': archive_meta['completed_at'],
                     'archive_range_request_log': str(archive.parent / 'range_requests.jsonl'),
                     'january_archive_sha256': check['sha256'], 'january_archive_bytes': check['bytes'],
                     'january_archive_snapshots': check['snapshots'],
                     'source_config_sha256': sha256_file(inputs.configuration)}
    if inputs.inventory is not None:
        listing_meta = json.loads(inputs.inventory.with_name(inputs.inventory.name + '.meta.json').read_text(encoding='utf-8'))
        if listing_meta.get('sha256') != sha256_file(inputs.inventory) or listing_meta.get('status') != 200:
            raise ValueError('Official archive inventory evidence mismatch')
        sources.update(archive_inventory_url=listing_meta['requested_url'],
            archive_inventory_sha256=listing_meta['sha256'],
            archive_inventory_retrieved_at_utc=listing_meta['retrieved_at'])
    for day in range(1, 9):
        token = f'202301{day:02d}'
        path = root / f'selection/lane_snapshots/{token}.parquet'
        stamp = json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
        if (stamp['identity']['source_sha256'] != check['sha256'] or stamp['identity']['detector_ids'] is not None
                or sha256_file(path) != stamp['sha256'] or stamp['quarantined_snapshots']):
            raise ValueError(f'Unverified full-inventory capture: {path}')
        sources[token + '_capture_sha256'] = stamp['sha256']
    profile_path = root / 'selection/derived/coverage_lane_day.parquet'
    profile = pd.read_parquet(profile_path)
    sources['selection_profile_sha256'] = sha256_file(profile_path)
    summary = selection_table(profile, config)
    capped, comparisons = select_cohort(profile, pd.Timestamp(config['selection_end']), config)
    actual = pd.read_csv(inputs.published_cohort, dtype={name: str for name in UNIT})
    if capped[UNIT].to_dict('records') != actual[UNIT].to_dict('records'):
        raise ValueError('Published 24-unit cohort mismatch; stop before expansion')
    expected_comparison = pd.read_csv(inputs.published_comparison)
    pd.testing.assert_frame_equal(comparisons, expected_comparison, check_dtype=False)
    if len(capped) != config['max_units'] or config['max_units'] != 24:
        raise ValueError('Original cap changed; stop before expansion')
    without_cap = config | {'max_units': len(summary) + 1}
    all_chosen, _ = select_cohort(profile, pd.Timestamp(config['selection_end']), without_cap)
    if all_chosen[UNIT].to_dict('records') != summary.loc[summary.one_lane_chosen].sort_values(
            ['detector_id', 'direction'])[UNIT].to_dict('records'):
        raise ValueError('Uncapped selector diverges from original policy')
    all_chosen = all_chosen.merge(summary[UNIT + ['present_slots']], on=UNIT, how='left', validate='one_to_one')
    # Existing first-week 5m bins contain positive-flow, capture-closure-safe
    # observations; subset of January 1–31, so >=300 proves eligibility.
    bin_files = []
    for day in range(1, 8):
        token = f'202301{day:02d}'
        quality = json.loads((root / f'selection/derived/quality-{token}.json').read_text(encoding='utf-8'))
        for name, digest in quality['outputs'].items():
            target = root / 'selection/derived' / name
            if sha256_file(target) != digest:
                raise ValueError('Quality output checkpoint mismatch: ' + name)
        bin_files.append(root / f'selection/derived/bins-{token}.parquet')
    import pyarrow.parquet as pq
    bins = pq.read_table([str(p) for p in bin_files], columns=UNIT +
                         ['timestamp', 'available_at', 'usable', 'speed_kmh']).to_pandas()
    reference = fit_reference(bins, fit_start=pd.Timestamp(config['observation_start']),
                              fit_end=pd.Timestamp(config['reference_end']), min_bins=config['min_reference_bins'])
    # Reference values are FIRST-WEEK diagnostics, not January fitted baselines.
    proof = reference[UNIT + ['reference_bins']].rename(columns={'reference_bins': 'first_week_reference_bins'})
    all_chosen = all_chosen.merge(proof, on=UNIT, how='left', validate='one_to_one')
    all_chosen['reference_eligible_proven'] = all_chosen.first_week_reference_bins.ge(config['min_reference_bins']).fillna(False)
    summary = summary.merge(proof, on=UNIT, how='left', validate='one_to_one')
    summary['reference_eligible_proven'] = summary.first_week_reference_bins.ge(config['min_reference_bins']).fillna(False)
    chosen_set = set(map(tuple, all_chosen[UNIT].to_numpy()))
    if len(chosen_set) != len(all_chosen) or not set(map(tuple, capped[UNIT].to_numpy())) <= chosen_set:
        raise ValueError('Non-unique lane or original lane omitted')
    meta = pd.read_csv(inputs.metadata, dtype=str, encoding='utf-8-sig').rename(columns={'AID_ID_Number': 'detector_id'})
    if meta.detector_id.duplicated().any():
        raise ValueError('Duplicate official metadata detector IDs')
    sources['detector_metadata_url'] = 'https://static.data.gov.hk/td/traffic-data-strategic-major-roads/info/traffic_speed_volume_occ_info.csv'
    sources['detector_metadata_sha256'] = sha256_file(inputs.metadata)
    inventory = meta[['detector_id', 'District', 'Road_EN', 'Easting', 'Northing']].copy()
    inventory = inventory.merge(summary.groupby('detector_id').agg(observed_lane_units=('lane_id', 'size'),
        eligible_lane_units=('passes_all', 'sum'), one_lane_groups=('one_lane_chosen', 'sum')).reset_index(),
        on='detector_id', how='outer', validate='one_to_one', indicator=True)
    inventory['historical_inventory_status'] = inventory.pop('_merge').map(
        {'both': 'observed_and_in_current_metadata', 'left_only': 'metadata_only',
         'right_only': 'observed_missing_current_metadata'})
    inventory['observed_lane_units'] = inventory.observed_lane_units.fillna(0).astype(int)
    inventory['eligible_lane_units'] = inventory.eligible_lane_units.fillna(0).astype(int)
    inventory['one_lane_groups'] = inventory.one_lane_groups.fillna(0).astype(int)
    chosen_meta = all_chosen.merge(meta[['detector_id', 'District', 'Road_EN', 'Easting', 'Northing']],
                                   on='detector_id', how='left', validate='many_to_one')
    scenarios, geo = [], []
    for name, limit in [('Original 24', 24), ('Expanded 48', 48), ('Expanded 96', 96), ('All eligible', None)]:
        subset = chosen_meta.head(limit) if limit is not None else chosen_meta
        proven = int(subset.reference_eligible_proven.sum())
        scenarios.append({'scenario': name, 'detectors': int(subset.detector_id.nunique()),
            'detector_direction_groups': int(len(subset[['detector_id', 'direction']].drop_duplicates())),
            'lane_units': len(subset), 'january_valid_30s_mean': float(subset.valid_30s_mean.mean()),
            'january_valid_5m_mean': float(subset.valid_5m_mean.mean()),
            'january_min_daily_valid_5m_min': float(subset.valid_5m_min.min()),
            'january_positive_flow_5m_mean': float(subset.flow_5m_mean.mean()),
            'january_usable_5m_mean': float(subset.flow_5m_mean.mean()),
            'january_missing_5m_mean': float(1 - subset.valid_5m_mean.mean()),
            'first_week_reference_eligible_proven': proven,
            'january_full_reference_speed_fitted': name == 'Original 24',
            'first_week_present_lane_slots': int(subset.present_slots.sum()),
            'four_year_raw_ingestion_rows': None, 'recovery_events_published_existing_or_measured': 7597 if name == 'Original 24' else None,
            'status': 'existing provisional cohort' if name == 'Original 24' else 'January eligible; four-year continuity unknown'})
        for district, group in subset.groupby('District', dropna=False):
            geo.append({'scenario': name, 'district_current_metadata': district if pd.notna(district) else None,
                'detectors': int(group.detector_id.nunique()), 'lane_units': len(group),
                'coordinate_status': 'HK1980 Grid from CURRENT TD metadata; historical validity unverified'})
    # The published monthly report was constructed only for 24 selected detectors.
    monthly = pd.read_csv(inputs.published_monthly, dtype={'detector_id': str})
    if not set(monthly.detector_id) <= set(capped.detector_id):
        raise ValueError('Monthly coverage contains units outside original 24 detectors')
    monthly['coverage_scope'] = 'published_selected_24_detectors_only; no expanded continuity claim'
    remaining = int(len(all_chosen) - len(capped))
    reasons = summary.loc[~summary.one_lane_chosen, UNIT + ['exclusion_reasons']].copy()
    summary_counts = {'selection_window': [config['observation_start'], config['selection_end']],
        'historical_detector_ids': int(summary.detector_id.nunique()),
        'historical_detector_direction_groups': int(len(summary[['detector_id', 'direction']].drop_duplicates())),
        'observed_lane_units': len(summary),
        'individual_conditions': {name: int(summary['passes_' + name].sum()) for name in
            ['valid_5m_mean', 'valid_5m_daily_min', 'positive_flow_5m_mean', 'no_source_conflicts']},
        'passes_all_combined': int(summary.passes_all.sum()),
        'eligible_detector_direction_groups': len(all_chosen), 'one_per_group_before_cap': len(all_chosen),
        'original_24_exactly_reproduced': True, 'excluded_only_by_24_cap': remaining,
        'eligible_on_existing_24_detectors_beyond_chosen_lane': int(summary.loc[
            summary.detector_id.isin(capped.detector_id) & summary.passes_all & ~summary.one_lane_chosen].shape[0]),
        'all_chosen_reference_minimum_proven_from_first_week': int(all_chosen.reference_eligible_proven.sum()),
        'all_chosen_reference_unproven': int((~all_chosen.reference_eligible_proven).sum()),
        'full_january_baselines_for_expanded_units': None, 'four_year_continuity_for_expanded_units': None,
        'new_recovery_event_count': None, 'geography_basis': 'current official detector metadata, not historical approval',
        'processed_segment_speed_is_lane_units': False,
        'raw_archive_scope': 'one verified January 2023 ZIP only; not 45 months',
        'generated_at_utc': datetime.now(timezone.utc).isoformat()}
    if inputs.network is not None and (inputs.network / 'manifest.json').is_file():
        road = json.loads((inputs.network / 'manifest.json').read_text(encoding='utf-8'))
        summary_counts['candidate_road_segments'] = road['parsed_valid_segments']
        summary_counts['road_version_compatible_with_jan2023'] = False
        sources['current_road_source_sha256'] = road['sources']['CENTERLINE.gml']['sha256']
    if inputs.processed_pilot is not None and (inputs.processed_pilot / 'pilot.json').is_file():
        processed = json.loads((inputs.processed_pilot / 'pilot.json').read_text(encoding='utf-8'))
        summary_counts['processed_snapshot_id_only_valid_overlap'] = {item['requested_day_hkt']:
            item['coverage']['valid_numeric_exact_matches'] for item in processed['results']
            if item['status'] == 'sample_parsed_unapproved'}
        summary_counts['approved_processed_spatial_features'] = 0
        sources['processed_pilot_sha256'] = sha256_file(inputs.processed_pilot / 'pilot.json')
    # These pairs are only geographic review leads, not neighbor traffic inputs.
    if (inputs.network is not None and inputs.processed_pilot is not None
            and (inputs.network / 'manifest.json').is_file()
            and (inputs.processed_pilot / 'pilot.json').is_file()):
        pairs, candidate_counts = processed_proximity(inputs.network, inputs.processed_pilot, chosen_meta)
        summary_counts['processed_proximity_only'] = candidate_counts
    else:
        pairs = None
    output.mkdir(parents=True)
    if pairs is not None:
        pairs.to_csv(output / 'processed_proximity_review_leads.csv', index=False)
    inventory.to_csv(output / 'official_inventory.csv', index=False)
    summary[UNIT + ['passes_valid_5m_mean', 'passes_valid_5m_daily_min',
        'passes_positive_flow_5m_mean', 'passes_no_source_conflicts', 'passes_all', 'one_lane_chosen',
        'first_week_reference_bins']].to_csv(output / 'selection_funnel.csv', index=False)
    chosen_meta.drop(columns=['first_week_reference_bins'], errors='ignore').to_csv(output / 'eligible_lane_units.csv', index=False)
    reasons.to_csv(output / 'exclusion_reasons.csv', index=False)
    pd.DataFrame(scenarios).to_csv(output / 'expansion_scenarios.csv', index=False)
    monthly.to_csv(output / 'monthly_coverage.csv', index=False)
    pd.DataFrame(geo).to_csv(output / 'geographic_coverage.csv', index=False)
    all_chosen[UNIT + ['first_week_reference_bins', 'reference_eligible_proven']].assign(
        four_year_event_eligible=pd.NA).to_csv(output / 'event_eligibility.csv', index=False)
    sources['published_cohort_sha256'] = sha256_file(inputs.published_cohort)
    sources['published_comparison_sha256'] = sha256_file(inputs.published_comparison)
    sources['published_monthly_sha256'] = sha256_file(inputs.published_monthly)
    sources['source_type'] = 'official_raw_detector_lanes; processed segments separate; no fabricated observations'
    (output / 'source_manifest.json').write_text(json.dumps(sources, indent=2) + '\n', encoding='utf-8')
    summary_counts['scenarios'] = scenarios
    (output / 'summary.json').write_text(json.dumps(summary_counts, indent=2) + '\n', encoding='utf-8')
    rows = ['# 香港官方車道樣本擴充審計', '',
        '**僅 2023-01-01 至 07 的全站原始觀測通過核證；不是四年資料完整性保證。**', '',
        f"1. 原先為何僅 24 條？`max_units=24` 人工上限；已逐筆重現原 24 條及比較表。", 
        f"2. 完整條件（五分鐘平均 ≥95%、每日最小 ≥90%、正流量可用平均 ≥80%、無來源衝突）共 {summary_counts['passes_all_combined']} 條原始車道符合；每個偵測器／方向只取一條後 {len(all_chosen)} 條。",
        f"3. 除原 24 條之外，有 {remaining} 條不受上限約束的**一方向一車道的歷史篩選候選**。全部 {int(all_chosen.reference_eligible_proven.sum())} 條在第一週已有 ≥300 個正速度參考箱（最少 {int(all_chosen.first_week_reference_bins.min())}），故一月參考**門檻**已被真實資料證實；完整一月參考值尚未擬合。四年穩定性尚未驗證。",
        '4. 48、96 及無上限方案均在原規則下可組成；未量測新事件數，不可聲稱四年可靠增加量。',
        '5. 現行官方站點地區分佈見 geographic_coverage.csv；後期月份資料只覆蓋原 24 站，不能外推給新增站點。',
        '6. 擴充增加未來空間配對的候選地理站點，但道路版本、方向／轉向、歷史發布可用性及獨立性都未核實；空間 ML 仍 NO-GO。',
        '7. 要證實四年事件數／穩定性須取回團隊保存的其餘 44 個月官方 raw ZIP 與核驗清單，再獨立分區重算，不需重新下載整套 47 GB；只限已選24站的公開 prepared Release 無法回答新增站點問題。', '',
        '| Scenario | Detectors | Lane Units | Coverage (January 1–7 usable 5m mean) | Reference Eligible | Recovery Events | Status |',
        '|---|---:|---:|---:|---:|---:|---|']
    for scenario in scenarios:
        rows.append(f"| {scenario['scenario']} | {scenario['detectors']} | {scenario['lane_units']} | {scenario['january_usable_5m_mean']:.2%} | {scenario['first_week_reference_eligible_proven']} (門檻已證) | " +
            ('7,597 已發表' if scenario['scenario'] == 'Original 24' else '未量測') +
            f" | {scenario['status']} |")
    rows.extend(['', '2023-05-15、2026-09-15 處理後道路速度是另外的路段資料，並非新增車道；與現時道路 ID 重合也不能確認歷史版本。無速度補值、插值或模型訓練。',
        '篩選只用一月第一週；2025/2026 覆蓋絕不可回饋決定初始車道名單。',
        '其他來源、精確 SHA-256 及未觀測欄位見 source_manifest.json、summary.json。'])
    (output / 'report_zh.md').write_text('\n'.join(rows) + '\n', encoding='utf-8')
    return summary_counts


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--selection-root', type=Path, default=Path('data/local/lane-expansion/source'))
    p.add_argument('--output', type=Path, default=Path('reports/lane_expansion_audit'))
    p.add_argument('--inventory', type=Path, default=Path('data/local/smoke-audit/coverage_raw.json'))
    a = p.parse_args()
    result = audit(AuditInputs(a.selection_root, Path('configs/long_window.json'),
        Path('reports/long_window/cohort.csv'), Path('reports/long_window/selection_filter_comparison.csv'),
        Path('data/sample/verified/detectors.csv'), Path('reports/long_window/coverage_detector_month.csv'),
        Path('data/local/network-full/v1'), Path('data/local/processed-pilot/v1'), a.inventory), a.output)
    print(json.dumps({k:v for k,v in result.items() if k != 'scenarios'}, indent=2))


if __name__ == '__main__':
    main()
