"""Standalone source-backed poster figures; no Streamlit or online tiles.

Each plot has small CSV sources. Source hashes and deterministic selection rules
are exported. Uses existing official geometry tiles, never fictitious road lines.
"""
from __future__ import annotations
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
import pyarrow.dataset as ds
from shapely import wkb
from shapely.geometry import Point, box
from shapely.ops import substring

from experiments.unified96.run import ROOT, MODELS
from experiments.unified96.matrix import dump
from traffic_recovery import research96
from traffic_recovery.data.http import sha256_file
from traffic_recovery.network.spatial96 import verify_network

NAMES = {'logistic_regression':'Logistic regression', 'random_forest':'Random forest',
         'xgboost':'XGBoost', 'hist_gradient_boosting':'HistGradientBoosting'}
COLORS = ['#426780','#c07835','#247e75','#795481']
SCOPE = '30-minute recovery confirmation | P1 retrospective inferred-network cohort | test n = 3,933'


def save(fig: plt.Figure, folder: Path, name: str) -> None:
    """High-resolution PNG plus editable SVG/PDF; do not overwrite exports."""
    for ext in ['png','svg','pdf']:
        path=folder/f'{name}.{ext}'
        if path.exists(): raise FileExistsError(path)
        fig.savefig(path,dpi=300,bbox_inches='tight',facecolor='white')
        if ext=='svg':
            path.write_text('\n'.join(x.rstrip() for x in path.read_text(encoding='utf-8').splitlines())+'\n',encoding='utf-8')
    plt.close(fig)


def main_gain(metrics: pd.DataFrame, gains: pd.DataFrame, out: Path) -> None:
    main = gains.loc[gains.comparison.eq('F7_minus_F3')].set_index('model').loc[list(MODELS)].reset_index()
    main.to_csv(out/'figure_data/01_spatial_gain.csv',index=False)
    fig,ax=plt.subplots(figsize=(10.8,4.8))
    y=np.arange(4)
    ax.axvline(0,color='#777777',ls='--',lw=1)
    for i,row in enumerate(main.itertuples()):
        ax.errorbar(row.delta_roc_auc,i,xerr=[[row.delta_roc_auc-row.ci_95_lower],[row.ci_95_upper-row.delta_roc_auc]],
            fmt='o',color=COLORS[i],capsize=5,ms=8,lw=2)
        ax.text(.079,i,f'{row.delta_roc_auc:+.4f}  [{row.ci_95_lower:+.4f}, {row.ci_95_upper:+.4f}]',va='center',fontsize=10)
    ax.set_yticks(y,[NAMES[n] for n in MODELS]);ax.invert_yaxis()
    ax.set_xlim(-.02,.135);ax.set_xticks([-.02,0,.02,.04,.06])
    ax.set_xlabel('ROC-AUC difference: F7 − F3 (added inferred spatial features)')
    ax.set_title('Spatial gains after calendar, temperature and wind adjustment',fontsize=14,pad=16)
    ax.spines[['top','right']].set_visible(False);ax.grid(axis='x',alpha=.15)
    fig.text(.02,.01,SCOPE+'\n95% detector-cluster Bootstrap interval; 1,000 paired draws, 44 detectors. Fixed fitted models.\nShared-neighbor dependence is not fully addressed; no multiple-comparison adjustment.',fontsize=8.5)
    fig.subplots_adjust(bottom=.26,left=.22,right=.98)
    save(fig,out/'figures','01_spatial_gain_cw')


def network_map(out: Path) -> dict:
    """Apply preregistered geometric rule, export actual road vertices and path IDs."""
    network=ROOT/'data/local/network-full/v1'
    source_manifest=verify_network(network)
    pairs=research96.neighbors(ROOT)
    mappings=research96.mappings(ROOT)
    chosen=None
    for target in sorted(set(pairs.upstream_detector)&set(pairs.downstream_detector)):
        valid=pairs.path_distance_m.ge(100)&pairs.upstream_offset_m.le(25)&pairs.downstream_offset_m.le(25)
        incoming=pairs.loc[valid & pairs.downstream_detector.eq(target)].sort_values('upstream_detector')
        outgoing=pairs.loc[valid & pairs.upstream_detector.eq(target)].sort_values('downstream_detector')
        if len(incoming) and len(outgoing):
            chosen=pd.concat([incoming.head(1),outgoing.head(1)]);break
    if chosen is None: raise ValueError('No map meets predeclared criteria')
    ids=[chosen.iloc[0].upstream_detector,target,chosen.iloc[1].downstream_detector]
    points=mappings.loc[mappings.detector_id.isin(ids)&mappings['rank'].eq(1)].set_index('detector_id').loc[ids].reset_index()
    if len(points)!=3: raise ValueError('Missing unique selected mapping')
    pts={r.detector_id:Point(r.easting,r.northing) for r in points.itertuples()}
    minx,maxx=points.easting.min()-100,points.easting.max()+100
    miny,maxy=points.northing.min()-120,points.northing.max()+120
    extent=box(minx,miny,maxx,maxy)
    # Selected area lies in one 4km tile; include surrounding tiles for crossing geometries.
    geometry, tile_hashes={},{}
    for folder in sorted((network/'geometry').glob('tile=*')):
        tx,ty=map(int,folder.name.split('=')[1].split('_'))
        if not (minx-6000<=tx*4000<=maxx+6000 and miny-6000<=ty*4000<=maxy+6000):continue
        for path in sorted(folder.glob('*.parquet')):
            tile_hashes[str(path.relative_to(ROOT))]=sha256_file(path)
        table=ds.dataset(folder,format='parquet').to_table(columns=['route_id','geometry_wkb_2326'])
        for row in table.to_pylist():
            line=wkb.loads(row['geometry_wkb_2326'])
            if line.intersects(extent):geometry[str(row['route_id'])]=line
    routes=set('|'.join(chosen.route_sequence).split('|'))
    if not routes.issubset(geometry):raise ValueError('Missing official map route')
    fig,ax=plt.subplots(figsize=(9.5,6.8))
    vertices=[]
    for route,line in geometry.items():
        # Render-only 5cm generalization removes extremely dense background
        # vertices. Model/path geometry and every selected segment stay original.
        displayed = line if route in routes else line.intersection(extent).simplify(.05, preserve_topology=True)
        for part_idx, part in enumerate(getattr(displayed, 'geoms', [displayed])):
            if part.geom_type != 'LineString':
                continue
            xy=np.array(part.coords);ax.plot(xy[:,0],xy[:,1],color='#ced3d6',lw=1.2,zorder=1)
            for i,(x,y,*_) in enumerate(part.coords):
                vertices.append({'route_id':route,'part':part_idx,'vertex':i,'easting_m':x,'northing_m':y,
                    'selected_relation_segment':route in routes,'render_simplification_m':0 if route in routes else .05})
    path_lengths=[]
    for row,color in zip(chosen.itertuples(),['#247e75','#795481']):
        arcs=row.arc_sequence.split('|'); total=0.
        for idx,arc in enumerate(arcs):
            route,direction=arc.split(':');line=geometry[route]
            if direction=='R':line=type(line)(list(line.coords)[::-1])
            start=line.project(pts[row.upstream_detector]) if idx==0 else 0.
            end=line.project(pts[row.downstream_detector]) if idx==len(arcs)-1 else line.length
            part=substring(line,start,end)
            if part.geom_type!='LineString':continue
            total+=part.length
            xy=np.array(part.coords);ax.plot(xy[:,0],xy[:,1],color=color,lw=3,zorder=3)
            if part.length>25:
                a,b=part.interpolate(.38,normalized=True),part.interpolate(.62,normalized=True)
                ax.annotate('',xy=(b.x,b.y),xytext=(a.x,a.y),arrowprops={'arrowstyle':'->','color':color,'lw':2},zorder=4)
        path_lengths.append({'upstream':row.upstream_detector,'downstream':row.downstream_detector,
            'saved_path_distance_m':row.path_distance_m,'drawn_official_subsegments_m':total})
        if not np.isclose(total,row.path_distance_m,atol=.05):raise ValueError('Drawn path distance differs from adopted path')
    for idx,row in enumerate(points.itertuples()):
        color=['#247e75','#c07835','#795481'][idx]
        ax.scatter(row.easting,row.northing,c=color,marker='*' if idx==1 else 'o',s=200 if idx==1 else 80,zorder=6,edgecolors='white')
        line=geometry[str(row.route_id)];projection=line.interpolate(line.project(pts[row.detector_id]))
        ax.plot([row.easting,projection.x],[row.northing,projection.y],':',color='#555555',lw=1,zorder=5)
        dx,dy=[(-95,-65),(-130,55),(25,30)][idx]
        ax.annotate(f'{["Upstream","Target","Downstream"][idx]}: {row.detector_id}\noffset {row.distance_m:.1f} m',
            (row.easting,row.northing),xytext=(row.easting+dx,row.northing+dy),fontsize=9,
            bbox={'facecolor':'white','alpha':.9,'edgecolor':'none'},zorder=8)
    ax.set(xlim=(minx,maxx),ylim=(miny,maxy),xlabel='HK1980 Easting (m; EPSG:2326)',ylabel='HK1980 Northing (m; EPSG:2326)')
    ax.set_aspect('equal');ax.ticklabel_format(useOffset=False,style='plain');ax.tick_params(axis='x',rotation=15)
    ax.set_title('Official road geometry, inferred directed relationships',fontsize=14)
    ax.legend(handles=[Line2D([0],[0],color='#ced3d6',label='Official CENTERLINE'),
        Line2D([0],[0],color='#247e75',lw=3,label='Inferred upstream → target'),
        Line2D([0],[0],color='#795481',lw=3,label='Inferred target → downstream'),
        Line2D([0],[0],color='#555555',ls=':',label='Detector-to-road offset (not path length)')],fontsize=8,loc='upper left')
    fig.text(.02,.01,'2026 official geometry is a retrospective proxy, not a verified historical network.\nAID01103 mapping remains ambiguous; arrowed paths are inferred, not officially verified.\nSelection is geometric and score-independent; not the short-path / large-offset counterexample.',fontsize=8.5)
    fig.subplots_adjust(bottom=.21)
    save(fig,out/'figures','02_real_directed_network')
    pd.DataFrame(vertices).to_csv(out/'figure_data/02_official_road_vertices.csv',index=False)
    points.drop(columns=['longitude','latitude']).to_csv(out/'figure_data/02_detector_mappings.csv',index=False)
    chosen.to_csv(out/'figure_data/02_inferred_relationships.csv',index=False)
    pd.DataFrame(path_lengths).to_csv(out/'figure_data/02_path_length_check.csv',index=False)
    return {'target':target,'selection':'first lexicographic target with incoming/outgoing >=100m, all offsets <=25m',
        'official_sources':source_manifest['sources'],'geometry_tiles_sha256':tile_hashes,
        'network_manifest_sha256':sha256_file(network/'manifest.json'),
        'render_geometry_policy':'background clipped to axes and simplified at 0.05m for file size; selected road/path geometry unchanged; no network-rule or speed changes'}


def event_case(run: Path, out: Path) -> dict:
    data=pd.read_parquet(run/'model_input.parquet')
    event=None
    for _,candidate in data.loc[data.split.eq('test')].sort_values(['prediction_time','event_id']).iterrows():
        local=research96.observed_bins(ROOT,candidate.detector_id,candidate.direction,candidate.lane_id,
            candidate.prediction_time-pd.Timedelta(minutes=65),candidate.prediction_time+pd.Timedelta(minutes=45))
        lines=research96.event_lineage(ROOT,candidate,'INFERRED_EXPLORATORY')
        available=local.usable & local.speed_kmh.notna() & local.available_at.le(candidate.prediction_time) & local.last_source_available_at.le(candidate.prediction_time)
        if available.any() and len(lines):event=candidate;break
    if event is None:raise ValueError('No complete-provenance case')
    grid=pd.date_range(event.prediction_time-pd.Timedelta(minutes=65),event.prediction_time+pd.Timedelta(minutes=45),freq='5min')
    curve=local.set_index('timestamp').reindex(grid).rename_axis('timestamp').reset_index()
    curve['minutes_from_prediction']=(curve.timestamp-event.prediction_time).dt.total_seconds()/60
    curve['speed_ratio']=curve.speed_kmh.where(curve.usable.fillna(False).astype(bool))/event.baseline_kmh
    curve['available_at_prediction']=curve.available_at.le(event.prediction_time)&curve.last_source_available_at.le(event.prediction_time)
    curve['event_id']=event.event_id
    curve['prediction_time']=event.prediction_time
    curve['baseline_kmh']=event.baseline_kmh
    curve.to_csv(out/'figure_data/03_local_event_bins.csv',index=False)
    lines['minutes_from_prediction']=(lines.observed_at-event.prediction_time).dt.total_seconds()/60
    lines.to_csv(out/'figure_data/03_asof_neighbor_points.csv',index=False)
    predictions=pd.read_parquet(run/'predictions.parquet')
    probabilities=predictions.loc[predictions.event_id.eq(event.event_id)&predictions.feature_arm.isin(['F3','F7'])]
    probabilities.to_csv(out/'figure_data/03_event_probabilities.csv',index=False)
    fig,(ax,tableax)=plt.subplots(2,1,figsize=(10.5,7),gridspec_kw={'height_ratios':[3.2,1.2]})
    for mask,label,color,ls in [(curve.available_at_prediction,'Local: available input','#426780','-'),
        (~curve.available_at_prediction,'Local: retrospective, NOT input','#c07835','--')]:
        ax.plot(curve.minutes_from_prediction,curve.speed_ratio.where(mask),marker='o',ls=ls,ms=4,color=color,label=label)
    for side,color,marker in [('upstream','#247e75','x'),('downstream','#795481','+')]:
        rows=lines.loc[lines.side.eq(side)]
        ax.scatter(rows.minutes_from_prediction,rows.speed_ratio,marker=marker,s=95,color=color,zorder=5,label=side.title()+' as-of points')
        for i,row in enumerate(rows.itertuples()):
            ax.annotate(row.neighbor_detector,(row.minutes_from_prediction,row.speed_ratio),xytext=(-95,8+12*i),textcoords='offset points',fontsize=8,color=color)
    ax.axvline(0,color='#333333',lw=1.4,label='Prediction time')
    ax.axvspan(0,30,color='#dfe5ed',alpha=.6,label='30-minute outcome window')
    ax.axvspan(-10,0,color='#dddddd',alpha=.35)
    ax.axhline(.5,color='#b35b55',ls=':',label='Congestion ratio ≤ 0.5')
    ax.axhline(.8,color='#608151',ls=':',label='Recovery ratio ≥ 0.8')
    ax.set(xlim=(-65,45),ylim=(0,max(1.2,float(curve.speed_ratio.max())+.1)),ylabel='Speed / own frozen reference',xlabel='Observation end relative to prediction time (minutes)')
    ax.set_title(f'First eligible test event: {event.detector_id} | {event.prediction_time:%Y-%m-%d %H:%M} HKT\n30-minute confirmation label = {int(event.label)} (no confirmation within horizon)',fontsize=12)
    ax.legend(fontsize=7.8,ncol=2,loc='lower right');ax.grid(alpha=.15)
    tableax.axis('off')
    tab=probabilities.pivot(index='model',columns='feature_arm',values='y_score').loc[list(MODELS)]
    table=tableax.table(cellText=[[NAMES[n],f'{tab.loc[n,"F3"]:.3f}',f'{tab.loc[n,"F7"]:.3f}'] for n in MODELS],
        colLabels=['Saved model probability','F3','F7'],colWidths=[.6,.2,.2],loc='center',cellLoc='center')
    table.auto_set_font_size(False);table.set_fontsize(9);table.scale(1,1.2)
    fig.text(.02,.01,'Case chosen chronologically, not for prediction success. Neighbor values are points, not complete curves.\nArchive closure leaves the final 10 minutes unavailable at prediction. Missing/unusable bins remain gaps.\nRetrospective observations illustrate outcomes only; three high usable bins are required for confirmation.',fontsize=8.5)
    fig.subplots_adjust(bottom=.17,hspace=.42)
    save(fig,out/'figures','03_real_event_case')
    source_event=research96.release_events(ROOT).loc[lambda d:d.event_id.eq(event.event_id)].iloc[0]
    return {'event_id':event.event_id,'prediction_time':event.prediction_time.isoformat(),'label_30m':int(event.label),
        'selection':'first chronological eligible test event, tie event_id; local as-of + true neighbor required',
        'termination_reason':str(source_event.termination_reason),'recovery_time':str(source_event.recovery_time),
        'event_snapshot':{k:str(v) for k,v in source_event.to_dict().items()}}


def supplementary(metrics: pd.DataFrame, controls: pd.DataFrame, out: Path) -> None:
    table=metrics.loc[metrics.split.eq('test')].pivot(index='model',columns='feature_arm',values='roc_auc').loc[list(MODELS),[f'F{i}' for i in range(8)]]
    table.to_csv(out/'figure_data/04_auc_matrix.csv')
    fig,ax=plt.subplots(figsize=(10,4.4))
    image=ax.imshow(table.to_numpy(),vmin=.5,vmax=1,cmap='Blues',aspect='auto')
    for i in range(4):
        for j in range(8):ax.text(j,i,f'{table.iloc[i,j]:.3f}',ha='center',va='center',color='white' if table.iloc[i,j]>.8 else '#222222',fontsize=11)
    ax.set_xticks(range(8),['F0\nBase','F1\n+C','F2\n+W','F3\n+C+W','F4\n+S','F5\n+C+S','F6\n+W+S','F7\n+C+W+S'])
    ax.set_yticks(range(4),[NAMES[n] for n in MODELS]);ax.set_title('Complete 32-arm retrospective comparison (ROC-AUC)',pad=16)
    fig.colorbar(image,ax=ax,label='ROC-AUC',shrink=.8)
    fig.text(.02,.01,SCOPE+'\nBase = local + history + observation quality. C = calendar; W = temperature/wind; S = inferred spatial.\nEach cell refitted using train data; two candidates selected by validation log loss. Test does not select a winner.',fontsize=8.3)
    fig.subplots_adjust(left=.22,bottom=.30)
    save(fig,out/'figures','04_full_matrix_auc')
    c=controls.loc[controls.split.eq('test')]
    c.to_csv(out/'figure_data/05_current_controls.csv',index=False)
    fig,ax=plt.subplots(figsize=(9,4.6))
    arms=['CW_S1_geographic','CW_S1_undirected','CW_S1_directed']
    for i,model in enumerate(['random_forest','xgboost']):
        values=c.loc[c.model.eq(model)].set_index('feature_arm').loc[arms,'roc_auc']
        ax.plot(range(3),values,marker='o',label=NAMES[model],color=COLORS[i+1])
        for j,value in enumerate(values):ax.annotate(f'{value:.4f}',(j,value),xytext=(0,9 if i else -16),textcoords='offset points',ha='center',fontsize=9)
    ax.set_xticks(range(3),['Geographic (250 m)','Same neighbors, pooled','Inferred directed'])
    ax.set(ylim=(.75,.86),ylabel='ROC-AUC (zoomed axis: 0.75–0.86)',title='Current C/W-adjusted structural controls: matched S1 fields')
    ax.legend(loc='upper left');ax.grid(alpha=.15)
    fig.text(.02,.01,SCOPE+'\nAll three use F3 + the same 12 S1 summary fields, not full F7. Fixed threshold 0.5.\nGeographic neighbors observed for 67.2% of test events versus 100% directed/pooled; missingness is retained.\nSmall directed–pooled differences do not establish a direction-specific or causal effect.',fontsize=8.4)
    fig.subplots_adjust(bottom=.27)
    save(fig,out/'figures','05_matched_structure_controls')


def build_figures(run: Path, analysis: Path, controls: Path, out: Path) -> None:
    """Build figures inside a newly created handoff with empty figures/data folders."""
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False})
    metrics=pd.read_csv(run/'metrics.csv');gains=pd.read_csv(analysis/'spatial_contrasts.csv')
    main_gain(metrics,gains,out)
    net=network_map(out);case=event_case(run,out)
    supplementary(metrics,pd.read_csv(controls/'metrics.csv'),out)
    dump(out/'figure_data/figure_provenance.json',{'main_run_manifest_sha256':sha256_file(run/'manifest.json'),
        'map':net,'case':case,'figures_sha256':{p.name:sha256_file(p) for p in sorted((out/'figures').iterdir())},
        'csv_sha256':{p.name:sha256_file(p) for p in sorted((out/'figure_data').glob('*.csv'))}})
