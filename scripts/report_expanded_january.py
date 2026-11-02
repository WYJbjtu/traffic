"""Produce measured Jan quality and frozen 96/stratified candidate diagnostics.

No four-year continuity or event counts are inferred. Geographic alternatives
use CURRENT metadata solely for exploratory planning, never future test labels.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
from shapely.geometry import Point
from shapely.strtree import STRtree

from traffic_recovery.data.events import UNIT, fit_reference
from traffic_recovery.data.http import sha256_file


def district_round_robin(eligible: pd.DataFrame, limit: int) -> pd.DataFrame:
    """Deterministic current-district rotation, for planning ONLY (not 2023 fit)."""
    district={name:list(group.sort_values(['detector_id','direction']).index)
              for name,group in eligible.groupby('District',sort=True)}
    indices=[]
    while len(indices)<limit:
        before=len(indices)
        for name in sorted(district):
            if district[name] and len(indices)<limit:
                indices.append(district[name].pop(0))
        if len(indices)==before:
            raise ValueError('Not enough eligible candidates for geographic alternative')
    return eligible.loc[indices].copy()


def report(january: Path, output: Path, *, candidate_config: Path, metadata: Path) -> dict:
    """Write lightweight CSV/JSON from checked January result; refuse overwrite."""
    if (output / 'january_reference.csv').exists():
        raise FileExistsError('Use a new report version; original measurements are immutable')
    result = json.loads((january / 'reference_manifest.json').read_text(encoding='utf-8'))
    for name, digest in result['outputs_sha256'].items():
        if sha256_file(january / name) != digest:
            raise ValueError('January reference output checksum mismatch: '+name)
    cfg = json.loads(candidate_config.read_text(encoding='utf-8'))
    original = json.loads(Path('configs/long_window.json').read_text(encoding='utf-8'))
    for key in original:
        if key not in {'max_units','status','version'} and cfg.get(key) != original[key]:
            raise ValueError('96-unit config changed original scientific rule: '+key)
    if cfg['max_units'] != 96:
        raise ValueError('Expected predetermined 96-unit cap')
    reference = pd.read_parquet(january / 'full_january_reference.parquet')
    days = pd.read_parquet(january / 'january_lane_day.parquet')
    chosen = pd.read_csv('reports/lane_expansion_audit/eligible_lane_units.csv', dtype={k:str for k in UNIT})
    if reference[UNIT].to_dict('records') != chosen[UNIT].to_dict('records') or len(reference)!=426:
        raise ValueError('Full-January output is not the frozen 426 cohort')
    if not reference.full_january_reference_eligible.all():
        raise ValueError('Unqualified January reference must not be silently retained')
    original24 = pd.read_csv('reports/long_window/cohort.csv', dtype={k:str for k in UNIT})
    same = reference.head(24).merge(original24[UNIT+['reference_bins','baseline_kmh']],on=UNIT,suffixes=('_audit','_published'),validate='one_to_one')
    if len(same)!=24 or not same.reference_bins_audit.eq(same.reference_bins_published).all() or not same.baseline_kmh_audit.eq(same.baseline_kmh_published).all():
        raise ValueError('Published original 24 January baseline mismatch')
    meta = pd.read_csv(metadata, encoding='utf-8-sig', dtype=str).rename(columns={'AID_ID_Number':'detector_id'})
    if meta.detector_id.duplicated().any():
        raise ValueError('Duplicate current metadata detector ID')
    merged = reference.merge(meta[['detector_id','District','Road_EN','Easting','Northing']],on='detector_id',how='left',validate='one_to_one')
    if merged.head(96)[['Easting','Northing','District']].isna().any().any():
        raise ValueError('96 candidate metadata locations missing')
    # Geographic alternative: sorted by district, one earliest detector per
    # district per round. Does not use 2023–2026 continuity or outcomes.
    alternative = district_round_robin(merged,96)
    ordered = [('Original 24',merged.head(24)),('ID-order 48',merged.head(48)),
               ('ID-order 96',merged.head(96)),('All January 426',merged),
               ('District-round-robin 96 (current metadata only)',alternative)]
    scen=[];geo=[]
    for name, subset in ordered:
        subset_days = days.merge(subset[UNIT],on=UNIT,how='inner',validate='many_to_one')
        scen.append({'scenario':name,'lane_units':len(subset),'detectors':subset.detector_id.nunique(),
            'districts_current_metadata':subset.District.nunique(),
            'full_jan_reference_pass':int(subset.full_january_reference_eligible.sum()),
            'january_reference_bins_min':int(subset.reference_bins.min()),
            'january_valid_30s_mean':float(subset.january_valid_30s_coverage.mean()),
            'january_usable_5m_mean':float(subset.january_usable_5m_coverage.mean()),
            'missing_lane_days_january':int(subset.missing_days.sum()),
            'offline_lane_slots_january':int(subset.january_offline_slots.sum()),
            'conflict_lane_slots_january':int(subset.january_conflict_slots.sum()),
            'new_event_count':None, 'train_validation_test_continuity':None})
        for district_name,group in subset.groupby('District'):
            geo.append({'scenario':name,'district_current_metadata':district_name,
                'detector_ids':group.detector_id.nunique(),'lane_units':len(group)})
    # First-week vs full-January baseline drift is purely retrospective quality
    # evidence within January, not a feature refit for validation or test.
    week_paths=[Path('data/local/lane-expansion/source/selection/derived')/f'bins-202301{d:02d}.parquet' for d in range(1,8)]
    first = pd.read_parquet(week_paths, filters=[[(k,'==',r[k]) for k in UNIT] for _,r in reference.iterrows()],
                            columns=UNIT+['timestamp','available_at','usable','speed_kmh'])
    week=fit_reference(first,fit_start=pd.Timestamp(original['observation_start']).tz_convert('Asia/Hong_Kong'),
                             fit_end=pd.Timestamp(original['reference_end']).tz_convert('Asia/Hong_Kong'),
                             min_bins=original['min_reference_bins'])
    drift=reference[UNIT+['baseline_kmh','reference_bins']].merge(week[UNIT+['baseline_kmh','reference_bins']],
        on=UNIT,suffixes=('_full_january','_first_week'),validate='one_to_one')
    drift['january_reference_change_kmh']=drift.baseline_kmh_full_january-drift.baseline_kmh_first_week
    # Geographic proximity is only a review lead. No graph turn / version
    # approval or independent neighbor observation is inferred.
    points=[Point(float(r.Easting),float(r.Northing)) for r in merged.itertuples(index=False)]
    tree=STRtree(points)
    pairs=[]
    for i,point in enumerate(points):
        for j in tree.query(point,predicate='dwithin',distance=250):
            j=int(j)
            if j <= i: continue
            pairs.append({'detector_a':merged.iloc[i].detector_id,'detector_b':merged.iloc[j].detector_id,
                'distance_m_hk1980':point.distance(points[j]),
                'current_metadata_road_a':merged.iloc[i].Road_EN,
                'current_metadata_road_b':merged.iloc[j].Road_EN,
                'id_order_96_a':i<96,'id_order_96_b':j<96,
                'connection_status':'geographic_proximity_only_unverified'})
    spatial=pd.DataFrame(pairs,columns=['detector_a','detector_b','distance_m_hk1980',
        'current_metadata_road_a','current_metadata_road_b','id_order_96_a','id_order_96_b','connection_status'])
    pair96=spatial.loc[spatial.id_order_96_a & spatial.id_order_96_b]
    inventory_path=output/'archive_inventory.csv'
    missing_months=(int(pd.read_csv(inventory_path).status.eq('missing').sum())
                    if inventory_path.is_file() else None)
    summary={'january_only':True,'full_january_reference_count':len(reference),
        'original_24_reference_exact_match':True,
        'january_reference_bin_min':int(reference.reference_bins.min()),
        'january_baseline_kmh_median':float(reference.baseline_kmh.median()),
        'january_missing_candidate_unit_days':int(reference.missing_days.sum()),
        'source_gap_days_at_least_317_of_426':sorted(str(x) for x,v in
            days.groupby('day').missing_day.sum().items() if v>=317),
        'within_january_baseline_change_median_kmh':float(drift.january_reference_change_kmh.median()),
        'within_january_baseline_change_abs_90pct_kmh':float(drift.january_reference_change_kmh.abs().quantile(.9)),
        'district_round_robin_metadata_history_verified':False,
        'proximity_candidate_pairs_250m_all_426':len(spatial),
        'proximity_candidate_pairs_250m_id_order_96':len(pair96),
        'verified_neighbor_pairs':0,
        'continuity_months_for_expanded_units':1,
        'remaining_months_missing_raw_archive':missing_months,
        'new_96_event_count':None,
        'source_january_reference_sha256':sha256_file(january/'reference_manifest.json'),
        'candidate_config_sha256':sha256_file(candidate_config),
        'current_metadata_sha256':sha256_file(metadata),
        'source_notes':'Jan reference is January 1–31; district metadata is current and not proven effective in Jan 2023; 250m pairs are distance-only review leads'}
    output.mkdir(parents=True, exist_ok=True)
    reference.to_csv(output/'january_reference.csv',index=False)
    # Full lane/day detail stays in ignored local january_lane_day.parquet;
    # do not commit a multi-megabyte duplicate CSV to the lightweight report.
    drift.to_csv(output/'january_reference_drift.csv',index=False)
    pd.DataFrame(scen).to_csv(output/'january_scenarios.csv',index=False)
    pd.DataFrame(geo).to_csv(output/'geographic_scenarios.csv',index=False)
    merged.head(96).to_csv(output/'frozen_id_order_96.csv',index=False)
    alternative.to_csv(output/'exploratory_district_round_robin_96.csv',index=False)
    spatial.to_csv(output/'detector_proximity_review_leads.csv',index=False)
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    return summary


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--january',type=Path,default=Path('data/local/lane-expansion/january426/v1'))
    p.add_argument('--output',type=Path,default=Path('reports/lane_expansion_continuity'))
    p.add_argument('--config',type=Path,default=Path('configs/long_window_96_candidate.json'))
    p.add_argument('--metadata',type=Path,default=Path('data/sample/verified/detectors.csv'))
    a=p.parse_args()
    print(json.dumps(report(a.january,a.output,candidate_config=a.config,metadata=a.metadata),indent=2))


if __name__=='__main__':main()
