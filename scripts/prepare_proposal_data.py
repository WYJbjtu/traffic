"""Build an independent detector/direction Proposal data handoff from verified captures.

Bounded capture-day partitions; immutable inputs; never changes an old Release.
No fitting models, choosing thresholds from validation/test, or human sign-off.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
from pathlib import Path
import time
from concurrent.futures import ThreadPoolExecutor

import duckdb
import pandas as pd

from traffic_recovery.data.http import sha256_file
from traffic_recovery.data.proposal import KEY, contextual_reference, proposal_events


def save(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str)+'\n', encoding='utf-8')
    temp.replace(path)


def aggregate_day(con, paths, inventory, day):
    """All selected-direction lanes, as-of bin closure before version conflict check.

    Inventory is frozen Jan 1-7, never later coverage-screened. New or absent lane
    identities prevent a complete 30s slot. Counts are OBSERVED counts, no scaling
    to 5 minutes; occupancy is the equal-lane mean then equal-slot mean. Speed is
    count-weighted across lanes, median across complete positive-flow slots.
    """
    con.register('inventory', inventory)
    con.execute('''CREATE OR REPLACE TEMP TABLE source AS
      SELECT detector_id,direction,lane_id,timestamp,available_at,signature,conflict,
        valid,speed_kmh,volume_count,occupancy_pct
      FROM read_parquet(?) JOIN (SELECT DISTINCT detector_id,direction FROM inventory)
      USING(detector_id,direction) WHERE timestamp>? AND timestamp<=?+INTERVAL 1 DAY''', [paths,day,day])
    return con.execute("""
    WITH eligible AS (
      SELECT s.*, to_timestamp(ceil(epoch(timestamp)/300)*300) AS bin_end
      FROM source s JOIN (SELECT DISTINCT detector_id,direction FROM inventory) u
      USING(detector_id,direction)
      WHERE timestamp > ? AND timestamp <= ? + INTERVAL 1 DAY
        AND available_at <= to_timestamp(ceil(epoch(timestamp)/300)*300)+INTERVAL 10 MINUTE
    ), unique_slots AS (
      SELECT detector_id,direction,lane_id,timestamp,bin_end,
        count(DISTINCT signature)>1 OR bool_or(conflict) AS bad,
        arg_min(valid,available_at) AS valid,
        arg_min(speed_kmh,available_at) AS speed,
        arg_min(volume_count,available_at) AS volume,
        arg_min(occupancy_pct,available_at) AS occupancy,
        max(available_at) AS last_capture
      FROM eligible GROUP BY ALL
    ), lane_slots AS (
      SELECT s.*, i.lane_id IS NOT NULL AS known,
        NOT bad AND valid='Y' AND speed IS NOT NULL AND volume IS NOT NULL
          AND occupancy IS NOT NULL AS good
      FROM unique_slots s LEFT JOIN inventory i USING(detector_id,direction,lane_id)
    ), simultaneous AS (
      SELECT detector_id,direction,timestamp,bin_end,
        count(*) AS lanes_present, count(*) FILTER(WHERE NOT known) AS novel,
        bool_and(good) AS all_good, sum(volume) AS observed_volume,
        sum(speed*volume)/nullif(sum(volume),0) AS weighted_speed,
        avg(occupancy) AS occupancy, count(*) FILTER(WHERE bad) AS conflicts,
        max(last_capture) AS last_capture
      FROM lane_slots GROUP BY ALL
    ), full_slots AS (
      SELECT s.*, (novel=0 AND all_good AND lanes_present=expected_lanes) AS complete,
        expected_lanes
      FROM simultaneous s JOIN (
        SELECT detector_id,direction,count(*) AS expected_lanes FROM inventory GROUP BY ALL
      ) i USING(detector_id,direction)
    )
    SELECT detector_id,direction,bin_end AS timestamp,
      bin_end+INTERVAL 10 MINUTE AS available_at,
      max(expected_lanes) AS expected_lanes, count(*) AS present_30s_slots,
      count(*) FILTER(WHERE complete) AS complete_30s_slots,
      count(*) FILTER(WHERE complete AND observed_volume>0) AS positive_flow_slots,
      median(weighted_speed) FILTER(WHERE complete AND observed_volume>0) AS speed_kmh,
      sum(observed_volume) FILTER(WHERE complete) AS volume_observed_count,
      avg(occupancy) FILTER(WHERE complete) AS occupancy_pct,
      sum(conflicts) AS conflicting_lane_slots, sum(novel) AS novel_lane_slots,
      max(last_capture) AS last_source_available_at
    FROM full_slots GROUP BY ALL ORDER BY detector_id,direction,timestamp
    """, [day, day]).df()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture-root', type=Path, required=True)
    p.add_argument('--selection', type=Path, default=Path('reports/lane_expansion_audit/eligible_lane_units.csv'))
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--min-complete-slots', type=int, default=10, choices=range(2,11))
    p.add_argument('--workers', type=int, default=2, choices=(1,2))
    p.add_argument('--reuse-verified-bins', type=Path,
                   help='Reuse hash-verified daily aggregates from an earlier generation; preserve its provenance')
    a=p.parse_args()
    out=a.output
    if (out/'manifest.json').exists(): raise FileExistsError('Completed version exists')
    out.mkdir(parents=True,exist_ok=True)
    sources=sorted(a.capture_root.glob('*.parquet'))
    if len(sources)!=1371: raise ValueError('Expected complete verified 1371 capture partitions')
    implementation={str(x):sha256_file(x) for x in [Path(__file__),Path('src/traffic_recovery/data/proposal.py')]}
    records=[]
    for path in sources:
        meta=json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
        if sha256_file(path)!=meta['sha256']: raise ValueError('Capture SHA mismatch: '+path.name)
        records.append({'path':str(path),'sha256':meta['sha256'], 'source':meta['identity'],
                        'min':meta['min_timestamp'],'max':meta['max_timestamp']})
    save(out/'source_manifest.json',{'partitions':records,'code':implementation})
    print('VERIFIED_SOURCES',len(records),flush=True)
    chosen=pd.read_csv(a.selection,dtype=str).head(96)[KEY].drop_duplicates()
    con=duckdb.connect(); con.execute("SET TimeZone='Asia/Hong_Kong'"); con.execute('SET threads=4')
    con.register('chosen',chosen)
    early=[r['path'] for r in records if r['min'] and pd.Timestamp(r['min'])<pd.Timestamp('2023-01-08',tz='Asia/Hong_Kong')]
    inventory=con.execute("""SELECT DISTINCT detector_id,direction,lane_id FROM read_parquet(?)
      JOIN chosen USING(detector_id,direction) WHERE timestamp>='2023-01-01T00:00:00+08:00'::TIMESTAMPTZ
      AND timestamp<'2023-01-08T00:00:00+08:00'::TIMESTAMPTZ ORDER BY ALL""",[early]).df()
    inventory.to_csv(out/'frozen_lane_inventory.csv',index=False)
    if len(inventory[KEY].drop_duplicates())!=len(chosen): raise ValueError('Missing frozen direction inventory')
    fingerprint=hashlib.sha256(json.dumps({'sources':records,'code':implementation,
        'selection_sha256':sha256_file(a.selection),'min_slots':a.min_complete_slots},sort_keys=True).encode()).hexdigest()
    cached_fingerprint=None
    if a.reuse_verified_bins:
        cache_manifest=a.reuse_verified_bins/'source_manifest.json'
        cache=json.loads(cache_manifest.read_text(encoding='utf-8'))
        if cache['partitions']!=records: raise ValueError('Cached source identity differs')
        # Exact generation files must remain inspectable; never rewrite old hashes.
        for name,digest in cache['code'].items():
            snapshot=a.reuse_verified_bins/'provenance_initial'/Path(name).name
            if not snapshot.exists() or sha256_file(snapshot)!=digest:
                raise ValueError('Missing cached generation snapshot: '+name)
        def aggregation_ast(path):
            module=ast.parse(path.read_text(encoding='utf-8'))
            return ast.dump(next(n for n in module.body if isinstance(n,ast.FunctionDef)
                                 and n.name=='aggregate_day'),include_attributes=False)
        if aggregation_ast(a.reuse_verified_bins/'provenance_initial/prepare_proposal_data.py')!=aggregation_ast(Path(__file__)):
            raise ValueError('Aggregation transform changed; recompute instead of reusing')
        cached_fingerprint=hashlib.sha256(json.dumps({'sources':records,'code':cache['code'],
            'selection_sha256':sha256_file(a.selection),'min_slots':a.min_complete_slots},sort_keys=True).encode()).hexdigest()
        save(out/'reuse_provenance.json',{'source_manifest_sha256':sha256_file(cache_manifest),
            'generation_code':cache['code'],'cached_fingerprint':cached_fingerprint,
            'policy':'Only complete, byte-verified daily aggregates reused; censored event handling recomputed'})
    started=time.monotonic()
    # Observation-day processing sees all intersecting capture partitions, including midnight closure.
    def day_job(day):
        token=day.strftime('%Y%m%d'); dest=out/'bins'/f'{token}.parquet'; check=dest.with_suffix('.json')
        if check.exists():
            old=json.loads(check.read_text(encoding='utf-8'))
            if old['fingerprint']!=fingerprint or sha256_file(dest)!=old['sha256']: raise ValueError('Stale day checkpoint')
            return
        if dest.exists() or dest.with_suffix('.partial').exists(): raise ValueError('Inspect uncheckpointed partial: '+str(dest))
        if a.reuse_verified_bins:
            old_path=a.reuse_verified_bins/'bins'/dest.name
            old_check=old_path.with_suffix('.json')
            if old_check.exists():
                old=json.loads(old_check.read_text(encoding='utf-8'))
                if old['fingerprint']!=cached_fingerprint or sha256_file(old_path)!=old['sha256']:
                    raise ValueError('Corrupt or incompatible reusable day')
                dest.parent.mkdir(parents=True,exist_ok=True)
                # A byte copy isolates the new version; never edits the old cache.
                import shutil
                shutil.copyfile(old_path,dest)
                save(check,{'fingerprint':fingerprint,'sha256':old['sha256'],'rows':old['rows'],
                    'reused_checkpoint_sha256':sha256_file(old_check)})
                return
        paths=[r['path'] for r in records if r['min'] and pd.Timestamp(r['min'])<=day+pd.Timedelta(days=1)
               and pd.Timestamp(r['max'])>day]
        if not paths: raise ValueError('No source partition for day')
        worker=duckdb.connect()
        worker.execute("SET TimeZone='Asia/Hong_Kong'")
        worker.execute('SET threads=2')
        worker.execute("SET memory_limit='256MB'")
        temp=out/'scratch'/token; temp.mkdir(parents=True,exist_ok=True)
        worker.execute('SET temp_directory='+repr(str(temp).replace('\\','/')))
        try:
            frame=aggregate_day(worker,paths,inventory,day)
        finally:
            worker.close()
        for col in ('timestamp','available_at','last_source_available_at'):
            frame[col]=pd.to_datetime(frame[col],utc=True).dt.tz_convert('Asia/Hong_Kong')
        frame['usable']=frame.complete_30s_slots.ge(a.min_complete_slots)&frame.positive_flow_slots.ge(2)&frame.speed_kmh.notna()&frame.novel_lane_slots.eq(0)&frame.conflicting_lane_slots.eq(0)
        frame['complete_30s_fraction']=frame.complete_30s_slots/10
        dest.parent.mkdir(parents=True,exist_ok=True)
        frame.to_parquet(dest.with_suffix('.partial'),index=False,compression='zstd')
        dest.with_suffix('.partial').replace(dest)
        save(check,{'fingerprint':fingerprint,'sha256':sha256_file(dest),'rows':len(frame)})
        if day.day==1: print('BIN_DAY',token,'elapsed_s',round(time.monotonic()-started),flush=True)
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        list(pool.map(day_job,pd.date_range('2023-01-01','2026-10-01',tz='Asia/Hong_Kong',inclusive='left')))
    # One detector/direction at a time. Large observed data stay outside Git.
    paths=[str(x) for x in sorted((out/'bins').glob('*.parquet'))]
    con.execute('CREATE OR REPLACE VIEW all_bins AS SELECT * FROM read_parquet('+repr(paths).replace('\\','/')+')')
    ref_start=pd.Timestamp('2023-01-01',tz='Asia/Hong_Kong')
    start=pd.Timestamp('2023-03-01',tz='Asia/Hong_Kong'); end=pd.Timestamp('2026-10-01',tz='Asia/Hong_Kong')
    summaries=[]; sensitivity=[]; all_events=[]; references=[]
    for unit in chosen.to_dict('records'):
        bins=con.execute('SELECT * FROM all_bins WHERE detector_id=? AND direction=? ORDER BY timestamp',list(unit.values())).df()
        ref=contextual_reference(bins,ref_start,start); references.append(ref)
        events=proposal_events(bins,ref,start=start,end=end)
        if len(events): all_events.append(events)
        summaries.append(unit|{'bins':len(bins),'usable_bins':int(bins.usable.sum()),
            'full_10slot_bins':int(bins.complete_30s_slots.eq(10).sum()),'reference_cells':len(ref),'events':len(events),
            'novel_lane_bins':int(bins.novel_lane_slots.gt(0).sum())})
        train=bins.loc[bins.timestamp<pd.Timestamp('2024-01-01',tz=start.tz)]
        for lo in (.4,.5,.6):
            for hi in (.7,.8,.9):
                ev=proposal_events(train,ref,start=start,end=pd.Timestamp('2024-01-01',tz=start.tz),congestion=lo,recovery=hi)
                sensitivity.append(unit|{'congestion':lo,'recovery':hi,'events':len(ev),
                    **{name:int(ev.label_30m.eq(value).sum()) if len(ev) else 0 for name,value in [('positive',1),('negative',0)]},
                    'unknown':int(ev.label_30m.isna().sum()) if len(ev) else 0})
        print('EVENT_UNIT',unit,'events',len(events),flush=True)
    pd.concat(references,ignore_index=True).to_parquet(out/'reference.parquet',index=False)
    events=pd.concat(all_events,ignore_index=True) if all_events else pd.DataFrame()
    events.to_parquet(out/'events.parquet',index=False)
    pd.DataFrame(summaries).to_csv(out/'unit_quality.csv',index=False)
    pd.DataFrame(sensitivity).to_csv(out/'training_threshold_sensitivity.csv',index=False)
    stats=[]
    if len(events):
        if events.event_id.duplicated().any(): raise ValueError('Duplicate events')
        for split,g in events.groupby('split'):
            for h in (15,30,60):
                labels=g[f'label_{h}m']
                stats.append({'split':split,'horizon':h,'events':len(g),'positive':int(labels.eq(1).sum()),
                    'negative':int(labels.eq(0).sum()),'unknown':int(labels.isna().sum()),'excluded_unknown_fraction':float(labels.isna().mean())})
    pd.DataFrame(stats).to_csv(out/'label_exclusions.csv',index=False)
    outputs={x.name:sha256_file(x) for x in out.iterdir() if x.is_file() and x.name not in ['manifest.json','source_manifest.json']}
    save(out/'manifest.json',{'version':'proposal-data-v2','status':'executed_awaiting_team_review',
        'directions':len(chosen),'lane_inventory':len(inventory),'events':len(events),
        'source_manifest_sha256':sha256_file(out/'source_manifest.json'),'fingerprint':fingerprint,
        'min_complete_slots':a.min_complete_slots,'outputs':outputs,'labels':stats,
        'fit_window':[ref_start,start],'evaluation_end':end,'thresholds_selected_using_test':False,
        'limitations':['Sparse observed slots do not establish continuous physical persistence',
            'Jan-Feb 2023 reserved for reference, not evaluated','Source interval count unit requires TD specification review',
            'Frozen first-week lane inventory is not independent historical hardware verification',
            'Gap-censored train/validation episodes without observed separation are purged',
            'Human curve, identity and joint scientific approval pending; no model refit']})
    print('COMPLETE',len(events),flush=True)


if __name__=='__main__': main()
