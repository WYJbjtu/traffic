"""Independently check event outcomes against exact source-bin timestamps."""
import argparse
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from traffic_recovery.data.http import sha256_file


def verify(bins_root: Path, profile: Path, *, sampled: bool = False) -> dict:
    events=pd.read_parquet(profile/'events.parquet')
    refs=pd.read_parquet(profile/'reference.parquet')
    if events.event_id.duplicated().any():raise ValueError('Duplicate event IDs')
    if (events.reference_fit_end>events.prediction_time).any():raise ValueError('Future reference')
    if (events.feature_max_available_at>events.prediction_time).any():raise ValueError('Future feature')
    if not (events.prediction_time-events.onset_confirmed_at).eq(pd.Timedelta(minutes=10)).all():
        raise ValueError('Incorrect prediction closure')
    for split,bound in [('train','2025-01-01'),('validation','2026-01-01'),('test','2026-10-01')]:
        g=events.loc[events.split.eq(split)]
        if not g.outcome_maturity_at.lt(pd.Timestamp(bound,tz='Asia/Hong_Kong')).all():
            raise ValueError('Outcome window crosses '+split+' boundary')
    for split,bound in [('validation','2025-01-01'),('test','2026-01-01')]:
        if not events.loc[events.split.eq(split),'onset_time'].ge(pd.Timestamp(bound,tz='Asia/Hong_Kong')).all():
            raise ValueError('Input crosses '+split+' boundary')
    expected=[]
    positive_count=negative_count=0
    for _,e in events.iterrows():
        for horizon in (15,30,60):
            label=e[f'label_{horizon}m']
            if pd.isna(label):continue
            if label==1:
                if not e.prediction_time<e.recovery_start<=e.prediction_time+pd.Timedelta(minutes=horizon):
                    raise ValueError('Incorrect positive start')
                if e.recovery_confirmed_at-e.recovery_start!=pd.Timedelta(minutes=10):
                    raise ValueError('Incorrect positive persistence')
                stamps=pd.date_range(e.recovery_start,periods=3,freq='5min')
                positive_count+=1
            else:
                stamps=pd.date_range(e.prediction_time+pd.Timedelta(minutes=5),
                    e.prediction_time+pd.Timedelta(minutes=horizon+10),freq='5min')
                negative_count+=1
            for stamp in stamps:
                expected.append({'event_id':e.event_id,'horizon':horizon,'label':int(label),
                    'detector_id':e.detector_id,'direction':e.direction,'timestamp':stamp,
                    'prediction_time':e.prediction_time,'recovery_ratio':e.recovery_ratio})
    expected=pd.DataFrame(expected)
    with duckdb.connect() as con:
        con.execute("SET TimeZone='Asia/Hong_Kong'");con.execute("SET memory_limit='256MB'");con.execute('SET threads=2')
        con.register('expected',expected);con.register('refs',refs)
        paths=[str(x) for x in sorted(bins_root.glob('*.parquet'))]
        con.execute('CREATE VIEW bins AS SELECT * FROM read_parquet('+repr(paths).replace('\\','/')+')')
        usable=('b.complete_30s_slots>=2 AND b.positive_flow_slots>=2 AND b.speed_kmh IS NOT NULL AND b.novel_lane_slots=0 AND b.conflicting_lane_slots=0'
                if sampled else 'b.usable')
        checked=con.execute('''SELECT e.*,b.timestamp IS NOT NULL AS present,
            ('''+usable+''') AS usable,b.speed_kmh/r.baseline_kmh AS ratio
            FROM expected e LEFT JOIN bins b USING(detector_id,direction,timestamp)
            LEFT JOIN refs r ON e.detector_id=r.detector_id AND e.direction=r.direction
              AND extract(isodow FROM e.timestamp)-1=r.weekday AND extract(hour FROM e.timestamp)=r.hour
            ORDER BY event_id,horizon,timestamp''').df()
    if len(checked)!=len(expected):raise ValueError('Unexpected source/reference join cardinality')
    if not checked.present.all() or not checked.usable.fillna(False).all() or not np.isfinite(checked.ratio).all():
        raise ValueError('Known label contains missing/invalid observations')
    for (_,h),g in checked.groupby(['event_id','horizon'],sort=False):
        high=g.ratio.ge(g.recovery_ratio).to_numpy()
        if g.label.iloc[0]==1:
            if len(g)!=3 or not high.all():raise ValueError('Unwitnessed positive')
        else:
            # All possible three-endpoint runs starting after prediction and no
            # later than the horizon fit inside this verified follow-up grid.
            if (high[:-2]&high[1:-1]&high[2:]).any():raise ValueError('Negative contains qualifying recovery')
    result={'status':'passed','profile':'sampled2' if sampled else 'strict10',
        'events':len(events),'positive_horizon_checks':positive_count,'negative_horizon_checks':negative_count,
        'exact_source_bin_checks':len(expected),'event_sha256':sha256_file(profile/'events.parquet'),
        'reference_sha256':sha256_file(profile/'reference.parquet'),'verifier_sha256':sha256_file(Path(__file__)),
        'does_not_certify_physical_continuity_or_identity':True}
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bins',type=Path,required=True);p.add_argument('--profile',type=Path,required=True)
    p.add_argument('--sampled',action='store_true');p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():raise FileExistsError('Use fresh verification file')
    result=verify(a.bins,a.profile,sampled=a.sampled)
    a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))


if __name__=='__main__':main()
