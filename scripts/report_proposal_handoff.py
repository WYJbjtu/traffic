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
    p.add_argument('--sampled-run',type=Path)
    p.add_argument('--source-root',type=Path,required=True,help='Original acquisition root for official URL/HTTP provenance')
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
    source=json.loads((root/'source_manifest.json').read_text(encoding='utf-8'))
    required_source_sha={x['source']['source_sha256'] for x in source['partitions']}
    official=[]
    for meta_path in sorted((a.source_root/'raw').glob('*/*.zip.meta.json')):
        meta=json.loads(meta_path.read_text(encoding='utf-8'))
        if meta.get('sha256') not in required_source_sha:continue
        fields={k:meta.get(k) for k in ('requested_url','final_url','status','bytes','sha256','completed_at','acquisition','headers_origin')}
        fields['headers']={k:v for k,v in meta.get('headers',{}).items() if k.lower() in ('date','etag','last-modified','content-range','content-type')}
        fields['original_metadata_sha256']=sha256_file(meta_path)
        official.append(fields)
    if {x['sha256'] for x in official}!=required_source_sha:raise ValueError('Missing official source HTTP metadata')
    (root/'official_sources.json').write_text(json.dumps({'records':official,
        'scope':'Historical acquisition metadata; capture SHA verified in this run. Raw ZIP bytes are not redistributed.'},indent=2)+'\n',encoding='utf-8')
    for name in ('unit_quality.csv','label_exclusions.csv','frozen_lane_inventory.csv','manifest.json'):
        shutil.copyfile(root/name,report/name)
    strict_verification=json.loads((root/'outcome_verification.json').read_text(encoding='utf-8'))
    if strict_verification['status']!='passed' or strict_verification['event_sha256']!=sha256_file(root/'events.parquet'):
        raise ValueError('Strict source-outcome verification missing or stale')
    shutil.copyfile(root/'outcome_verification.json',report/'strict_outcome_verification.json')
    sensitivity=pd.read_csv(root/'training_threshold_sensitivity.csv').groupby(['congestion','recovery']).agg(
        events=('events','sum'),positive=('positive','sum'),negative=('negative','sum'),unknown=('unknown','sum')).reset_index()
    sensitivity['unknown_fraction']=sensitivity.unknown/sensitivity.events.replace(0,float('nan'))
    sensitivity.to_csv(report/'training_sensitivity_summary.csv',index=False)
    with duckdb.connect() as con:
        con.execute("SET TimeZone='Asia/Hong_Kong'")
        con.execute("SET memory_limit='256MB'");con.execute('SET threads=2')
        paths=[str(x) for x in sorted((root/'bins').glob('*.parquet'))]
        con.execute('CREATE VIEW bins AS SELECT * FROM read_parquet('+repr(paths).replace('\\','/')+')')
        reference=pd.read_parquet(root/'reference.parquet')
        con.register('reference',reference)
        con.execute('''CREATE VIEW diagnosed AS SELECT b.*,r.baseline_kmh FROM bins b LEFT JOIN reference r
            ON b.detector_id=r.detector_id AND b.direction=r.direction
            AND extract(isodow FROM b.timestamp)-1=r.weekday AND extract(hour FROM b.timestamp)=r.hour''')
        monthly=con.execute("""SELECT detector_id,direction,strftime(timestamp-INTERVAL 1 MICROSECOND,'%Y-%m') AS month,
            count(*) AS observed_bins, sum(usable::INTEGER) AS usable_bins,
            sum((complete_30s_slots>=2 AND positive_flow_slots>=2 AND speed_kmh IS NOT NULL
                 AND novel_lane_slots=0 AND conflicting_lane_slots=0)::INTEGER) AS sampled_usable_bins,
            sum((complete_30s_slots=10)::INTEGER) AS full_slot_bins,
            sum((novel_lane_slots>0)::INTEGER) AS novel_lane_bins,
            sum((conflicting_lane_slots>0)::INTEGER) AS conflict_bins,
            sum(volume_observed_count) AS observed_source_count,
            avg(occupancy_pct) AS mean_observed_occupancy,
            median(speed_kmh) FILTER(WHERE usable) AS median_usable_speed_kmh,
            median(speed_kmh/nullif(baseline_kmh,0)) FILTER(WHERE usable) AS median_contextual_speed_ratio
            FROM diagnosed GROUP BY ALL ORDER BY ALL"""
        ).df()
        periods=pd.period_range('2023-01','2026-09',freq='M')
        inventory=pd.read_csv(root/'frozen_lane_inventory.csv',dtype=str)[['detector_id','direction']].drop_duplicates()
        grid=inventory.merge(pd.DataFrame({'month':periods.astype(str),'expected_bins':periods.days_in_month*288}),how='cross')
        monthly=grid.merge(monthly,how='left',on=['detector_id','direction','month'])
        for col in ('observed_bins','usable_bins','sampled_usable_bins','full_slot_bins','novel_lane_bins','conflict_bins'):
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
        if a.sampled_run:
            se=pd.read_parquet(a.sampled_run/'events.parquet')
            sr=pd.read_parquet(a.sampled_run/'reference.parquet')
            selections=[]
            for kind,mask in [('positive',se.label_30m.eq(1)),('negative',se.label_30m.eq(0)),
                ('missing',se.label_30m.isna() & se.termination_reason.ne('recovered')),
                ('prevalent',se.reason_30m.eq('recovery_started_before_prediction'))]:
                for _,row in se.loc[mask & se.split.eq('train')].head(1).iterrows():selections.append((kind,row))
            fig,axes=plt.subplots(len(selections),1,figsize=(12,3*len(selections)),squeeze=False)
            sampled_review=[]
            for ax,(kind,row) in zip(axes[:,0],selections):
                b=con.execute('SELECT * FROM bins WHERE detector_id=? AND direction=? AND timestamp BETWEEN ? AND ? ORDER BY timestamp',
                    [row.detector_id,row.direction,row.onset_time-pd.Timedelta(minutes=30),row.prediction_time+pd.Timedelta(minutes=85)]).df()
                t=b.timestamp.dt.tz_convert('Asia/Hong_Kong');b['weekday']=t.dt.dayofweek;b['hour']=t.dt.hour
                b=b.merge(sr,on=['detector_id','direction','weekday','hour'],how='left',validate='many_to_one')
                use=b.complete_30s_slots.ge(2)&b.positive_flow_slots.ge(2)&b.novel_lane_slots.eq(0)&b.conflicting_lane_slots.eq(0)
                x=(b.timestamp-row.prediction_time).dt.total_seconds()/60
                curve=pd.Series((b.speed_kmh/b.baseline_kmh).where(use).to_numpy(),index=x).reindex(range(-50,86,5))
                ax.plot(curve.index,curve.values,'o-',markersize=3)
                for at,c in ((0,'black'),(30,'red'),(40,'purple')):ax.axvline(at,color=c,linestyle=':')
                for y,c in ((.5,'orange'),(.8,'green')):ax.axhline(y,color=c,linestyle='--')
                ax.set_title(f'SAMPLED2 {kind}: {row.event_id} / label30={row.label_30m}')
                ax.set_ylabel('sampled speed / contextual p85');ax.set_xlabel('minutes from prediction availability')
                sampled_review.append(row.to_dict()|{'review_kind':kind})
            fig.tight_layout();fig.savefig(report/'sampled2_event_review_curves.png',dpi=130);plt.close(fig)
            pd.DataFrame(sampled_review).to_csv(report/'sampled2_event_curve_review.csv',index=False)
    package_files={name:sha256_file(root/name) for name in ('events.parquet','reference.parquet','frozen_lane_inventory.csv',
        'unit_quality.csv','training_threshold_sensitivity.csv','label_exclusions.csv','source_manifest.json','reuse_provenance.json','manifest.json','outcome_verification.json','official_sources.json')}
    provenance=root/'provenance';provenance.mkdir(exist_ok=True)
    generation=json.loads((root/'source_manifest.json').read_text(encoding='utf-8'))['code']
    for name,digest in generation.items():
        normalized=name.replace('\\','/')
        src=Path('scripts/prepare_proposal_data.py') if normalized.endswith('/prepare_proposal_data.py') else Path(normalized)
        if sha256_file(src)!=digest: raise ValueError('Generation code changed since run')
        dest=provenance/src.name;shutil.copyfile(src,dest)
        package_files['provenance/'+src.name]=digest
    shutil.copyfile(Path('docs/proposal_member1_v2.md'),root/'README_zh.md')
    package_files['README_zh.md']=sha256_file(root/'README_zh.md')
    sampled_manifest=None
    if a.sampled_run:
        sampled_manifest=json.loads((a.sampled_run/'manifest.json').read_text(encoding='utf-8'))
        if sampled_manifest['source_bins_sha256']!={Path(k).name:v['sha256'] for k,v in daily.items()}:
            raise ValueError('Sampled profile used different source bins')
        for name,digest in sampled_manifest['outputs_sha256'].items():
            if sha256_file(a.sampled_run/name)!=digest:raise ValueError('Sampled output mismatch')
        sampled_dir=root/'sampled2';sampled_dir.mkdir(exist_ok=True)
        for name in list(sampled_manifest['outputs_sha256'])+['manifest.json']:
            shutil.copyfile(a.sampled_run/name,sampled_dir/name)
            package_files['sampled2/'+name]=sha256_file(sampled_dir/name)
        check=json.loads((a.sampled_run/'outcome_verification.json').read_text(encoding='utf-8'))
        if check['status']!='passed' or check['event_sha256']!=sha256_file(a.sampled_run/'events.parquet'):
            raise ValueError('Sampled source-outcome verification missing or stale')
        shutil.copyfile(a.sampled_run/'outcome_verification.json',sampled_dir/'outcome_verification.json')
        package_files['sampled2/outcome_verification.json']=sha256_file(sampled_dir/'outcome_verification.json')
        shutil.copyfile(a.sampled_run/'outcome_verification.json',report/'sampled2_outcome_verification.json')
        for name in ('coverage_comparison.csv','label_exclusions.csv'):
            shutil.copyfile(a.sampled_run/name,report/('sampled2_'+name))
        sample_sens=pd.read_csv(a.sampled_run/'training_threshold_sensitivity.csv').groupby(['congestion','recovery']).agg(
            events=('events','sum'),positive=('positive','sum'),negative=('negative','sum'),unknown=('unknown','sum')).reset_index()
        sample_sens.to_csv(report/'sampled2_training_sensitivity_summary.csv',index=False)
        src=Path('scripts/proposal_coverage_sensitivity.py')
        code={Path(k.replace('\\','/')).name:v for k,v in sampled_manifest['code_sha256'].items()}
        if sha256_file(src)!=code[src.name]:raise ValueError('Sampled generator changed')
        shutil.copyfile(src,provenance/src.name);package_files['provenance/'+src.name]=sha256_file(src)
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
    if sampled_manifest:
        result['sampled2_events']=sampled_manifest['events'];result['sampled2_labels']=sampled_manifest['labels']
    (report/'package_verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
