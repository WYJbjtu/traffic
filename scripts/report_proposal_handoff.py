"""Generate measured data-only review tables/curves from a completed v2 run."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
import zipfile

import duckdb
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

from traffic_recovery.data.http import sha256_file


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    p.add_argument('--archive',type=Path,required=True)
    a=p.parse_args();root=a.run;report=a.report
    if report.exists() or a.archive.exists(): raise FileExistsError('Use fresh report/archive')
    manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    for name,digest in manifest['outputs'].items():
        if sha256_file(root/name)!=digest: raise ValueError('Output SHA mismatch: '+name)
    daily={}
    for path in sorted((root/'bins').glob('*.parquet')):
        check=json.loads(path.with_suffix('.json').read_text(encoding='utf-8'))
        if sha256_file(path)!=check['sha256']: raise ValueError('Bin SHA mismatch')
        daily['bins/'+path.name]={'sha256':check['sha256'],'rows':check['rows']}
    if len(daily)!=1369: raise ValueError('Incomplete day grid')
    report.mkdir(parents=True)
    for name in ('unit_quality.csv','label_exclusions.csv','frozen_lane_inventory.csv','manifest.json'):
        shutil.copyfile(root/name,report/name)
    sensitivity=pd.read_csv(root/'training_threshold_sensitivity.csv').groupby(['congestion','recovery']).agg(
        events=('events','sum'),positive=('positive','sum'),negative=('negative','sum'),unknown=('unknown','sum')).reset_index()
    sensitivity['unknown_fraction']=sensitivity.unknown/sensitivity.events.replace(0,float('nan'))
    sensitivity.to_csv(report/'training_sensitivity_summary.csv',index=False)
    with duckdb.connect() as con:
        con.execute("SET TimeZone='Asia/Hong_Kong'")
        con.execute("SET memory_limit='256MB'");con.execute('SET threads=2')
        paths=[str(x) for x in sorted((root/'bins').glob('*.parquet'))]
        con.execute('CREATE VIEW bins AS SELECT * FROM read_parquet('+repr(paths).replace('\\','/')+')')
        monthly=con.execute("""SELECT detector_id,direction,strftime(timestamp-INTERVAL 1 MICROSECOND,'%Y-%m') AS month,
            count(*) AS observed_bins, sum(usable::INTEGER) AS usable_bins,
            sum((complete_30s_slots=10)::INTEGER) AS full_slot_bins,
            sum((novel_lane_slots>0)::INTEGER) AS novel_lane_bins,
            sum((conflicting_lane_slots>0)::INTEGER) AS conflict_bins,
            sum(volume_observed_count) AS observed_source_count,
            avg(occupancy_pct) AS mean_observed_occupancy
            FROM bins GROUP BY ALL ORDER BY ALL""
        ).df()
        periods=pd.period_range('2023-01','2026-09',freq='M')
        inventory=pd.read_csv(root/'frozen_lane_inventory.csv',dtype=str)[['detector_id','direction']].drop_duplicates()
        grid=inventory.merge(pd.DataFrame({'month':periods.astype(str),'expected_bins':periods.days_in_month*288}),how='cross')
        monthly=grid.merge(monthly,how='left',on=['detector_id','direction','month'])
        for col in ('observed_bins','usable_bins','full_slot_bins','novel_lane_bins','conflict_bins'):
            monthly[col]=monthly[col].fillna(0).astype(int)
        monthly['usable_fraction']=monthly.usable_bins/monthly.expected_bins
        monthly.to_csv(report/'direction_month_quality.csv',index=False)
        events=pd.read_parquet(root/'events.parquet')
        if events.empty: raise ValueError('No real events; report this blocker separately')
        events['hour']=events.prediction_time.dt.tz_convert('Asia/Hong_Kong').dt.hour
        events['period']=events.hour.map(lambda h:'AM_peak' if 7<=h<10 else 'PM_peak' if 17<=h<20 else 'off_peak')
        strata=[]
        for cols in (['split'],['split','period'],['split','detector_id','direction']):
            for keys,g in events.groupby(cols,dropna=False):
                if not isinstance(keys,tuple):keys=(keys,)
                strata.append({'stratum':'+'.join(cols),**dict(zip(cols,keys)),'events':len(g),
                    'positive_30m':int(g.label_30m.eq(1).sum()),'negative_30m':int(g.label_30m.eq(0).sum()),
                    'unknown_30m':int(g.label_30m.isna().sum())})
        pd.DataFrame(strata).to_csv(report/'event_strata.csv',index=False)
        review=[]
        groups=[('positive',events.label_30m.eq(1)),('negative',events.label_30m.eq(0)),
                ('missing',events.label_30m.isna() & events.termination_reason.ne('recovered')),
                ('prevalent',events.reason_30m.eq('recovery_started_before_prediction'))]
        chosen=[]
        for kind,mask in groups:
            for _,row in events.loc[mask & events.split.eq('train')].head(2 if kind in ('positive','negative') else 1).iterrows():
                chosen.append((kind,row))
        fig,axes=plt.subplots(len(chosen),1,figsize=(12,3*len(chosen)),squeeze=False)
        ref=pd.read_parquet(root/'reference.parquet')
        for ax,(kind,row) in zip(axes[:,0],chosen):
            b=con.execute('SELECT * FROM bins WHERE detector_id=? AND direction=? AND timestamp BETWEEN ? AND ? ORDER BY timestamp',
                [row.detector_id,row.direction,row.onset_time-pd.Timedelta(minutes=30),row.prediction_time+pd.Timedelta(minutes=85)]).df()
            t=b.timestamp.dt.tz_convert('Asia/Hong_Kong');b['weekday']=t.dt.dayofweek;b['hour']=t.dt.hour
            b=b.merge(ref,on=['detector_id','direction','weekday','hour'],how='left',validate='many_to_one')
            x=(b.timestamp-row.prediction_time).dt.total_seconds()/60
            y=(b.speed_kmh/b.baseline_kmh).where(b.usable)
            # Reindex to the complete 5m window so an absent bin breaks the line.
            curve=pd.Series(y.to_numpy(),index=x).reindex(range(-50,86,5))
            ax.plot(curve.index,curve.values,'o-',markersize=3)
            ax.axhline(.5,color='orange',linestyle='--');ax.axhline(.8,color='green',linestyle='--')
            for at,c in ((0,'black'),(30,'red'),(40,'purple')):ax.axvline(at,color=c,linestyle=':')
            ax.set_title(f'{kind}: {row.event_id} / {row.detector_id} {row.direction} / label30={row.label_30m}')
            ax.set_ylabel('speed / contextual p85');ax.set_xlabel('minutes relative to prediction availability')
            rec=row.to_dict();rec['review_kind']=kind;review.append(rec)
        fig.tight_layout();fig.savefig(report/'event_review_curves.png',dpi=130);plt.close(fig)
        pd.DataFrame(review).to_csv(report/'event_curve_review.csv',index=False)
    package_files={name:sha256_file(root/name) for name in ('events.parquet','reference.parquet','frozen_lane_inventory.csv',
        'unit_quality.csv','training_threshold_sensitivity.csv','label_exclusions.csv','source_manifest.json','reuse_provenance.json','manifest.json')}
    provenance=root/'provenance';provenance.mkdir(exist_ok=True)
    generation=json.loads((root/'source_manifest.json').read_text(encoding='utf-8'))['code']
    for name,digest in generation.items():
        src=Path(name)
        if sha256_file(src)!=digest: raise ValueError('Generation code changed since run')
        dest=provenance/src.name;shutil.copyfile(src,dest)
        package_files['provenance/'+src.name]=digest
    package_manifest={'dataset':'proposal-detector-direction-v2','scientific_status':'candidate_awaiting_joint_review',
        'daily_bins':daily,'files':package_files,'no_model_training':True}
    (root/'PACKAGE_MANIFEST.json').write_text(json.dumps(package_manifest,indent=2)+'\n',encoding='utf-8')
    with zipfile.ZipFile(a.archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=4) as z:
        for name in package_files: z.write(root/name,name)
        for name in daily:z.write(root/name,name)
        z.write(root/'PACKAGE_MANIFEST.json','PACKAGE_MANIFEST.json')
        for path in report.iterdir():z.write(path,'review/'+path.name)
    digest=sha256_file(a.archive)
    a.archive.with_suffix(a.archive.suffix+'.sha256').write_text(digest+'  '+a.archive.name+'\n',encoding='utf-8')
    result={'archive':a.archive.name,'bytes':a.archive.stat().st_size,'sha256':digest,'directions':manifest['directions'],
            'lane_inventory':manifest['lane_inventory'],'observed_bins':sum(r['rows'] for r in daily.values()),
            'events':manifest['events'],'label_exclusions':manifest['labels'],'review_curves':len(review)}
    (report/'package_verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
