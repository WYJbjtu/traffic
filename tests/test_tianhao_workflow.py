"""SYNTHETIC boundary fixtures, never observations or reported model evidence."""
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

import numpy as np
import pandas as pd
import pytest

from traffic_recovery.models.experiment_diagnostics import exact_feature_join, feature_gains, error_diagnostics

SCRIPTS=Path(__file__).resolve().parents[1]/'experiments/tianhao'


@pytest.mark.parametrize('failure',['duplicate','time','ids'])
def test_feature_join_rejects_misaligned_data(failure):
    a=pd.DataFrame(dict(event_id=['SYNTHETIC-1','SYNTHETIC-2'],prediction_time=pd.date_range('2024-01-01',periods=2,tz='Asia/Hong_Kong')))
    b=a.assign(value=[1,2])
    if failure=='duplicate':b.loc[1,'event_id']=b.event_id.iloc[0]
    if failure=='time':b.loc[1,'prediction_time']+=pd.Timedelta(minutes=1)
    if failure=='ids':b.loc[1,'event_id']='WRONG'
    with pytest.raises(ValueError):exact_feature_join(a,b)


@pytest.mark.parametrize('missing',[False,True])
def test_speed_history_spans_rowgroups_and_preserves_missing(tmp_path,monkeypatch,missing):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    from prepare_local import speed_features
    d=tmp_path/'data/processed/derived';d.mkdir(parents=True)
    times=pd.date_range('2024-01-01 23:45',periods=4,freq='5min',tz='Asia/Hong_Kong')
    e=pd.DataFrame(dict(event_id=['SYNTHETIC-1'],prediction_time=[times[-1]+pd.Timedelta(minutes=10)],
        onset_confirmed_at=[times[-1]],baseline_kmh=[100.],detector_id=['D'],direction=['N'],lane_id=['L']))
    e.to_parquet(d/'events.parquet')
    bins=pd.DataFrame(dict(timestamp=times,available_at=times+pd.Timedelta(minutes=10),
        last_source_available_at=times+pd.Timedelta(minutes=5),speed_kmh=[100.,80.,30.,20.],usable=[True]*4,
        detector_id=['D']*4,direction=['N']*4,lane_id=['L']*4))
    if missing:bins=bins.drop(index=1)
    bins.to_parquet(d/'cohort_bins.parquet',row_group_size=1)
    out=tmp_path/'features';speed_features(data_dir=tmp_path/'data',output_dir=out)
    row=pd.read_parquet(out/'speed_history_features.parquet').iloc[0]
    assert row.speed_trend_observed_bins==(3 if missing else 4)
    assert pd.isna(row.speed_change_15m_ratio) if missing else np.isclose(row.speed_change_15m_ratio,-.8)


def test_midnight_flow_reads_previous_partition_and_masks_invalid(tmp_path,monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    from prepare_local import flow_features
    d=tmp_path/'data/processed/derived';d.mkdir(parents=True)
    end=pd.Timestamp('2024-01-02',tz='Asia/Hong_Kong')
    pd.DataFrame(dict(event_id=['SYNTHETIC-1'],prediction_time=[end+pd.Timedelta(minutes=10)],
        onset_confirmed_at=[end],detector_id=['D'],direction=['N'],lane_id=['L'])).to_parquet(d/'events.parquet')
    cache=tmp_path/'cache';cache.mkdir();files={}
    with zipfile.ZipFile(cache/'traffic_prepared.zip','w') as z:
        for date,minutes,volumes,occupancy,valid in [('20240101',[-1],[2.],[10.],['Y']),('20240102',[0,0],[4.,np.nan],[30.,np.nan],['Y','N'])]:
            times=[end+pd.Timedelta(minutes=t) for t in minutes]
            if len(times)>1:times[-1]+=pd.Timedelta(seconds=30)
            table=pd.DataFrame(dict(timestamp=times,available_at=[t+pd.Timedelta(minutes=1) for t in times],
                volume_count=volumes,occupancy_pct=occupancy,valid=valid,conflict=[False]*len(times),
                detector_id=['D']*len(times),direction=['N']*len(times),lane_id=['L']*len(times)))
            payload=table.to_parquet(index=False);name=f'processed/derived/cleaned-{date}.parquet'
            z.writestr(name,payload);files[name]={'sha256':hashlib.sha256(payload).hexdigest()}
    (tmp_path/'data/SHARED_DATA_MANIFEST.json').write_text(json.dumps({'files':files}))
    out=tmp_path/'out';flow_features(data_dir=tmp_path/'data',source_cache=cache,output_dir=out)
    row=pd.read_parquet(out/'flow_occupancy_features.parquet').iloc[0]
    assert row.volume_median_per_observed_30s==3 and row.occupancy_median_pct==20


def test_gain_sign_and_all_four_models():
    summary=pd.DataFrame([dict(model=model,feature_set=group,split='test',macro_f1=f1,
        balanced_accuracy=f1,log_loss=1-f1,roc_auc=f1,pr_auc=f1)
        for model in ['logistic_regression','decision_tree','logistic_l1','svm_rbf']
        for group,f1 in [('local',.5),('local+history',.6)]])
    gains=feature_gains(summary,[('local',),('local','history')])
    assert len(gains)==20 and np.allclose(gains.improvement,.1)


def test_error_counts_and_hkt_peak_boundaries():
    t=pd.to_datetime(['2026-01-02 06:59','2026-01-02 07:00','2026-01-02 10:00','2026-01-02 19:59','2026-01-02 20:00']).tz_localize('Asia/Hong_Kong')
    e=pd.DataFrame(dict(event_id=[f'SYNTHETIC-{i}' for i in range(5)],prediction_time=t,
        detector_id=['D']*5,direction=['N']*5,lane_id=['L']*5))
    p=e[['event_id','prediction_time']].assign(split='test',model='svm_rbf',feature_set='local',horizon_min=30,y_true=[0,0,1,1,0],y_pred=[0,1,0,1,0])
    errors,groups=error_diagnostics(p,e)
    assert errors.peak.tolist()==['off_peak','peak','off_peak','peak','off_peak']
    detector=groups.loc[groups.dimension.eq('detector_id')].iloc[0]
    assert (detector.tn,detector.fp,detector.fn,detector.tp)==(2,1,1,1)
    assert groups.loc[groups.dimension.eq('peak'),'n'].sum()==5
