"""Independent sampled-observation profile, never overwrite strict v2 labels.

Uses already verified complete-lane slot aggregates. Only bin eligibility changes
from 10 to >=2 complete/positive-flow slots; reference and events are recomputed.
This is measured coverage sensitivity, not proof of continuous recovery and not
a model score driven threshold choice. Both profiles remain available for review.
"""
import argparse
import hashlib
import json
from pathlib import Path

import duckdb
import pandas as pd

from traffic_recovery.data.http import sha256_file
from traffic_recovery.data.proposal import contextual_reference, proposal_events, KEY


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--strict-run',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();out=a.output
    if out.exists():raise FileExistsError('Use fresh sampled profile')
    out.mkdir(parents=True)
    paths=sorted((a.strict_run/'bins').glob('*.parquet'))
    if len(paths)!=1369:raise ValueError('Need complete 1369-day source')
    hashes={}
    for path in paths:
        check=json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
        if sha256_file(path)!=check['sha256']:raise ValueError('Bin checksum mismatch')
        hashes[path.name]=check['sha256']
    chosen=pd.read_csv(a.strict_run/'frozen_lane_inventory.csv',dtype=str)[KEY].drop_duplicates()
    start=pd.Timestamp('2023-03-01',tz='Asia/Hong_Kong');end=pd.Timestamp('2026-10-01',tz=start.tz)
    fit_start=pd.Timestamp('2023-01-01',tz=start.tz)
    con=duckdb.connect();con.execute("SET TimeZone='Asia/Hong_Kong'")
    con.execute('SET threads=2');con.execute("SET memory_limit='256MB'")
    con.execute('CREATE VIEW bins AS SELECT * FROM read_parquet('+repr([str(x) for x in paths]).replace('\\','/')+')')
    events=[];references=[];quality=[];sensitivity=[]
    for unit in chosen.to_dict('records'):
        b=con.execute('SELECT * FROM bins WHERE detector_id=? AND direction=? ORDER BY timestamp',list(unit.values())).df()
        strict_count=int(b.usable.sum())
        b['usable']=b.complete_30s_slots.ge(2)&b.positive_flow_slots.ge(2)&b.speed_kmh.notna()&b.novel_lane_slots.eq(0)&b.conflicting_lane_slots.eq(0)
        r=contextual_reference(b,fit_start,start);references.append(r)
        e=proposal_events(b,r,start=start,end=end)
        if len(e):
            e['event_id']=e.event_id.map(lambda key:hashlib.sha256(('sampled2-v2|'+key).encode()).hexdigest()[:24])
            e['definition_version']='detector-direction-sampled2-recovery-start-v2'
            events.append(e)
        quality.append(unit|{'observed_bins':len(b),'strict_usable_bins':strict_count,
            'sampled_usable_bins':int(b.usable.sum()),'reference_cells':len(r),'events':len(e)})
        train=b.loc[b.timestamp<pd.Timestamp('2024-01-01',tz=start.tz)]
        for lo in (.4,.5,.6):
            for hi in (.7,.8,.9):
                q=proposal_events(train,r,start=start,end=pd.Timestamp('2024-01-01',tz=start.tz),congestion=lo,recovery=hi)
                sensitivity.append(unit|{'congestion':lo,'recovery':hi,'events':len(q),
                    'positive':int(q.label_30m.eq(1).sum()) if len(q) else 0,
                    'negative':int(q.label_30m.eq(0).sum()) if len(q) else 0,
                    'unknown':int(q.label_30m.isna().sum()) if len(q) else 0})
        print('SAMPLED_UNIT',unit,'events',len(e),flush=True)
    con.close()
    e=pd.concat(events,ignore_index=True)
    if e.event_id.duplicated().any():raise ValueError('Duplicate sampled IDs')
    e.to_parquet(out/'events.parquet',index=False,compression='zstd')
    pd.concat(references,ignore_index=True).to_parquet(out/'reference.parquet',index=False)
    pd.DataFrame(quality).to_csv(out/'coverage_comparison.csv',index=False)
    pd.DataFrame(sensitivity).to_csv(out/'training_threshold_sensitivity.csv',index=False)
    labels=[]
    for split,g in e.groupby('split'):
        for h in (15,30,60):
            q=g[f'label_{h}m'];labels.append({'split':split,'horizon':h,'events':len(g),
                'positive':int(q.eq(1).sum()),'negative':int(q.eq(0).sum()),'unknown':int(q.isna().sum()),
                'excluded_unknown_fraction':float(q.isna().mean())})
    pd.DataFrame(labels).to_csv(out/'label_exclusions.csv',index=False)
    manifest={'version':'sampled2-coverage-sensitivity-v2','status':'executed_candidate_not_continuous_observation',
        'source_bins_sha256':hashes,'events':len(e),'directions':len(chosen),'labels':labels,
        'definition':'At least two complete and positive-flow 30s slots per 5m bin; missing remaining slots are not imputed',
        'primary_strict_profile_unchanged':True,'no_model_training':True,
        'code_sha256':{str(x):sha256_file(x) for x in [Path(__file__),Path('src/traffic_recovery/data/proposal.py')]},
        'outputs_sha256':{x.name:sha256_file(x) for x in out.iterdir() if x.is_file()}}
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print('SAMPLED_COMPLETE',len(e),flush=True)


if __name__=='__main__':main()
