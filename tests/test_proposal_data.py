"""Synthetic boundary fixtures, not research observations."""
import duckdb
import pandas as pd
import pytest
import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location('proposal_runner',Path(__file__).parents[1]/'scripts/prepare_proposal_data.py')
runner=importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
aggregate_day=runner.aggregate_day
from traffic_recovery.data.proposal import contextual_reference, proposal_events

TZ='Asia/Hong_Kong'


def series(first_high=12, periods=26):
    t=pd.date_range('2024-01-08',periods=periods,freq='5min',tz=TZ)
    speed=[90 if i<3 or i>=first_high else 30 for i in range(periods)]
    b=pd.DataFrame({'detector_id':'D','direction':'N','timestamp':t,
        'available_at':t+pd.Timedelta(minutes=10),'speed_kmh':speed,'usable':True})
    ref=b.assign(weekday=t.dayofweek,hour=t.hour)[['detector_id','direction','weekday','hour']].drop_duplicates()
    ref['baseline_kmh']=100.;ref['reference_fit_end']=t[0]-pd.Timedelta(days=1)
    return b,ref,t[0],t[-1]+pd.Timedelta(minutes=5)


def test_start_at_thirty_can_confirm_at_forty():
    b,r,s,e=series()
    v=proposal_events(b,r,start=s,end=e).iloc[0]
    assert v.recovery_start-v.prediction_time==pd.Timedelta(minutes=30)
    assert v.recovery_confirmed_at-v.prediction_time==pd.Timedelta(minutes=40)
    assert v.label_30m==1 and v.label_15m==0
    assert v.outcome_maturity_at>=v.prediction_time+pd.Timedelta(minutes=80)


def test_gap_during_persistence_censors_not_negative():
    b,r,s,e=series();b.loc[14,'usable']=False
    v=proposal_events(b,r,start=s,end=e).iloc[0]
    assert pd.isna(v.label_30m)
    assert v.label_15m==0


def test_negative_needs_horizon_plus_persistence():
    b,r,s,e=series(first_high=99,periods=14)
    v=proposal_events(b,r,start=s,end=e).iloc[0]
    assert pd.isna(v.label_30m)  # last observation 65, deadline+10=70
    b,r,s,e=series(first_high=99,periods=15)
    assert proposal_events(b,r,start=s,end=e).iloc[0].label_30m==0


def test_already_started_recovery_not_future_positive():
    b,r,s,e=series(first_high=5)
    v=proposal_events(b,r,start=s,end=e).iloc[0]
    assert pd.isna(v.label_30m)
    assert v.reason_30m=='recovery_started_before_prediction'


def test_strict_congestion_and_no_duplicate_event():
    b,r,s,e=series();b.loc[3:11,'speed_kmh']=50
    assert proposal_events(b,r,start=s,end=e).empty
    b,r,s,e=series(first_high=99,periods=100)
    assert len(proposal_events(b,r,start=s,end=e))==1


def test_missing_reference_and_duplicate_input_fail_closed():
    b,r,s,e=series()
    assert proposal_events(b,r.iloc[:0],start=s,end=e).empty
    with pytest.raises(ValueError,match='unique'):
        proposal_events(pd.concat([b,b.iloc[:1]]),r,start=s,end=e)
    r['reference_fit_end']=e
    with pytest.raises(ValueError,match='future'):
        proposal_events(b,r,start=s,end=e)


def test_context_reference_uses_exact_hkt_weekday_hour_and_past():
    t=pd.date_range('2023-01-02',periods=24*12*28,freq='5min',tz=TZ)
    b=pd.DataFrame({'detector_id':'D','direction':'N','timestamp':t,
        'available_at':t+pd.Timedelta(minutes=10),'speed_kmh':50.,'usable':True})
    b.loc[t.dayofweek==0,'speed_kmh']=100
    end=pd.Timestamp('2023-02-01',tz=TZ)
    r=contextual_reference(b,t[0],end)
    assert r.loc[r.weekday==0,'baseline_kmh'].eq(100).all()
    assert r.loc[r.weekday==1,'baseline_kmh'].eq(50).all()
    future=b.iloc[:1].copy();future.timestamp=end;future.available_at=end+pd.Timedelta(minutes=10);future.speed_kmh=9999
    pd.testing.assert_frame_equal(r,contextual_reference(pd.concat([b,future]),t[0],end))
    b.available_at=end
    assert contextual_reference(b,t[0],end).empty


def test_censored_outcome_survives_later_episode_separation():
    b,r,s,e=series();b.loc[8,'usable']=False
    v=proposal_events(b,r,start=s,end=e).iloc[0]
    assert pd.isna(v.label_30m)
    assert pd.isna(v.recovery_start)
    assert pd.notna(v.episode_separated_at)
    assert v.split=='train'


def test_outcome_maturity_crossing_split_is_purged():
    b,r,s,e=series()
    shift=pd.Timestamp('2024-12-31T23:00',tz=TZ)-s
    b.timestamp+=shift;b.available_at+=shift
    t=b.timestamp.dt
    r=b.assign(weekday=t.dayofweek,hour=t.hour)[['detector_id','direction','weekday','hour']].drop_duplicates()
    r['baseline_kmh']=100.;r['reference_fit_end']=pd.Timestamp('2023-03-01',tz=TZ)
    v=proposal_events(b,r,start=s+shift,end=e+shift).iloc[0]
    assert v.prediction_time.year==2024 and v.outcome_maturity_at.year==2025
    assert v.split=='purged'


def test_missing_followup_at_dataset_end_not_a_negative():
    b,r,s,e=series(first_high=99,periods=7)
    v=proposal_events(b,r,start=s,end=e).iloc[0]
    assert pd.isna(v.label_15m) and pd.isna(v.label_30m)
    assert v.split=='purged'


def test_direction_aggregation_uses_counts_not_coverage_and_asof_conflicts(tmp_path):
    day=pd.Timestamp('2023-01-01',tz=TZ);stamp=day+pd.Timedelta(minutes=5)
    rows=[]
    for lane,speed,volume,occ in [('L',50,10,20),('R',70,30,40)]:
        rows.append(dict(detector_id='D',direction='N',lane_id=lane,timestamp=stamp,
            available_at=stamp+pd.Timedelta(minutes=6),signature=lane,conflict=False,
            valid='Y',speed_kmh=float(speed),volume_count=float(volume),occupancy_pct=float(occ)))
    # A later conflicting revision must not contaminate the earlier cutoff.
    rows.append(rows[0]|{'available_at':stamp+pd.Timedelta(minutes=11),'signature':'late','speed_kmh':1.})
    path=tmp_path/'raw.parquet';pd.DataFrame(rows).to_parquet(path,index=False)
    inv=pd.DataFrame([{'detector_id':'D','direction':'N','lane_id':x} for x in ['L','R']])
    with duckdb.connect() as con:
        con.execute("SET TimeZone='Asia/Hong_Kong'")
        b=aggregate_day(con,[str(path)],inv,day).iloc[0]
    assert b.complete_30s_slots==1 and b.volume_observed_count==40
    assert b.speed_kmh==65 and b.occupancy_pct==30
    rows[-1]['available_at']=stamp+pd.Timedelta(minutes=9)
    pd.DataFrame(rows).to_parquet(path,index=False)
    with duckdb.connect() as con:
        b=aggregate_day(con,[str(path)],inv,day).iloc[0]
    assert b.complete_30s_slots==0 and pd.isna(b.volume_observed_count)


@pytest.mark.parametrize('case',['absent_lane','offline','novel_lane','zero_flow'])
def test_lane_inventory_and_zero_missing_distinction(tmp_path,case):
    day=pd.Timestamp('2023-01-01',tz=TZ);stamp=day+pd.Timedelta(minutes=5)
    rows=[dict(detector_id='D',direction='N',lane_id=x,timestamp=stamp,
        available_at=stamp+pd.Timedelta(minutes=6),signature=x,conflict=False,
        valid='Y',speed_kmh=50.,volume_count=10.,occupancy_pct=20.) for x in ['L','R']]
    if case=='absent_lane':rows=rows[:1]
    if case=='offline':rows[1]['valid']='N'
    if case=='novel_lane':rows.append(rows[0]|{'lane_id':'NEW','signature':'NEW'})
    if case=='zero_flow':
        for r in rows:r['volume_count']=0.
    path=tmp_path/'raw.parquet';pd.DataFrame(rows).to_parquet(path,index=False)
    inv=pd.DataFrame([{'detector_id':'D','direction':'N','lane_id':x} for x in ['L','R']])
    with duckdb.connect() as con:
        b=aggregate_day(con,[str(path)],inv,day).iloc[0]
    if case=='zero_flow':
        assert b.complete_30s_slots==1 and b.volume_observed_count==0
        assert pd.isna(b.speed_kmh)
    else:
        assert b.complete_30s_slots==0 and pd.isna(b.volume_observed_count)
