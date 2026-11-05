"""Synthetic engineering fixtures only; never use as empirical traffic evidence."""
from pathlib import Path
import sqlite3

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from shapely.geometry import LineString

from traffic_recovery.network.spatial96 import match_units, directed_paths
from traffic_recovery.network.spatial96_coverage import candidate_opportunity, verified_zero_eligibility


def detector_fixture():
    units = pd.DataFrame([("A","North","L"),("B","North","L")],columns=["detector_id","direction","lane_id"])
    meta = pd.DataFrame({"AID_ID_Number":["A","B"],"Easting":[5,5],"Northing":[0,40],
        "Direction":["North","North"],"Road_EN":["Main Road northbound","Main Road northbound"]})
    attrs = [{"ROUTE_ID":"1","STREET_ENAME":"Main Road","TRAVEL_DIRECTION":"3","ELEVATION":"0","LAST_UPD_DATE_V":"20261009"},
             {"ROUTE_ID":"2","STREET_ENAME":"Parallel Road","TRAVEL_DIRECTION":"3","ELEVATION":"1","LAST_UPD_DATE_V":"20261009"},
             {"ROUTE_ID":"3","STREET_ENAME":"East Road","TRAVEL_DIRECTION":"3","ELEVATION":"0","LAST_UPD_DATE_V":"20261009"}]
    lines = [LineString([(0,-10),(0,25)]),LineString([(8,-10),(8,25)]),LineString([(0,25),(20,25)])]
    return units,meta,attrs,lines


def test_distance_parallel_grade_and_direction_candidates():
    units,meta,attrs,lines=detector_fixture()
    candidates,summary=match_units(units,meta,attrs,lines,version="current_not_historical")
    assert summary.loc[0,"ambiguous"] and summary.loc[0,"candidate_matched"]
    assert set(candidates.loc[candidates.detector_id.eq("A"),"elevation"]) >= {"0","1"}
    assert candidates.loc[candidates.detector_id.eq("A") & candidates.route_id.eq("1"),"distance_m"].iloc[0] == 5
    assert not candidates.review_status.eq("human_verified").any()
    bad=meta.copy();bad.loc[0,"Direction"]="South"
    _,status=match_units(units,bad,attrs,lines,version="current_not_historical")
    assert status.loc[0,"direction_conflict"]
    reverse=units.copy();reverse.loc[0,"direction"]="South"
    _,status=match_units(reverse,meta,attrs,lines,version="current_not_historical")
    assert not status.loc[0,"candidate_matched"]  # TRAVEL_DIRECTION=3 is forward only
    with pytest.raises(ValueError,match="Duplicate"):
        match_units(pd.concat([units,units.iloc[:1]]),meta,attrs,lines,version="v")


def db_fixture():
    db=sqlite3.connect(":memory:")
    db.execute("CREATE TABLE arcs (arc TEXT, route TEXT, from_node TEXT, to_node TEXT, tile TEXT, length_m REAL)")
    db.execute("CREATE INDEX arc_from ON arcs(from_node)")
    db.execute("CREATE TABLE restrictions(from_route TEXT,to_route TEXT,turn_id TEXT)")
    db.execute("CREATE TABLE intersection_routes(route TEXT,node TEXT,int_id TEXT)")
    db.executemany("INSERT INTO arcs VALUES (?,?,?,?,?,?)",[("1:F","1","0:0:0","0:100:0","x",100.),
        ("2:F","2","0:100:0","0:200:0","x",100.),("3:F","3","0:200:0","0:300:0","x",100.),
        ("4:F","4","0:100:1","0:200:1","x",100.)])
    for route,node in [("1","0:100:0"),("2","0:100:0")]:
        db.execute("INSERT INTO intersection_routes VALUES (?,?,?)",(route,node,"J1"))
    lines={str(i):LineString([(0,(i-1)*100),(0,i*100)]) for i in (1,2,3)}
    lines["4"]=LineString([(1,100),(1,200)])
    candidates=pd.DataFrame([{"detector_id":"A","direction":"North","lane_id":"L","arc_id":"1:F","route_id":"1","orientation":"forward","easting":0,"northing":10,"direction_compatible":True},
        {"detector_id":"B","direction":"North","lane_id":"L","arc_id":"2:F","route_id":"2","orientation":"forward","easting":0,"northing":150,"direction_compatible":True},
        {"detector_id":"C","direction":"North","lane_id":"L","arc_id":"3:F","route_id":"3","orientation":"forward","easting":0,"northing":250,"direction_compatible":True},
        {"detector_id":"D","direction":"North","lane_id":"L","arc_id":"4:F","route_id":"4","orientation":"forward","easting":1,"northing":150,"direction_compatible":True}])
    return db,lines,candidates


def test_directed_multihop_turn_and_separate_grade():
    db,lines,c=db_fixture()
    paths,_=directed_paths(db,c,lines)
    assert ((paths.upstream_detector=="A")&(paths.downstream_detector=="C") & paths.arc_sequence.eq("1:F|2:F|3:F")).any()
    assert not ((paths.upstream_detector=="C")&(paths.downstream_detector=="A")).any()
    assert not ((paths.upstream_detector=="A")&(paths.downstream_detector=="D")).any()
    assert "J1" in paths.loc[(paths.upstream_detector=="A")&(paths.downstream_detector=="B"),"intersection_ids"].iloc[0]
    assert paths.historical_status.eq("historical_network_version_unverified").all()
    assert paths.connection_status.eq("CANDIDATE_ONLY_NOT_MODEL_APPROVED").all()
    db.execute("INSERT INTO restrictions VALUES ('1','2','T1')")
    paths,rejected=directed_paths(db,c,lines)
    assert not ((paths.upstream_detector=="A")&(paths.downstream_detector=="B")).any()
    assert rejected.turn_ids.eq("T1").any()
    assert directed_paths(db,c,lines,max_arcs=1)[0].empty
    db.close()


def test_asof_and_archive_availability_do_not_leak(tmp_path:Path):
    stamp=pd.Timestamp("2025-06-01 12:00",tz="Asia/Hong_Kong")
    events=pd.DataFrame({"event_id":["e1","e2"],"detector_id":["A","A"],"direction":["North","North"],"lane_id":["L","L"],
        "prediction_time":[stamp,stamp+pd.Timedelta(minutes=5)],"split_proposal":["validation"]*2,"label_30m":pd.Series([1,pd.NA],dtype="Int8")})
    pairs=pd.DataFrame({"upstream_detector":["B"],"upstream_direction":["North"],"upstream_lane":["L"],
        "downstream_detector":["A"],"downstream_direction":["North"],"downstream_lane":["L"]})
    # First bin ends before e1 but archive closes after e1; second bin is future
    # for e1. e2 can only see the first bin. No missing=zero fallback.
    bins=pd.DataFrame({"detector_id":["B","B"],"direction":["North"]*2,"lane_id":["L"]*2,
        "timestamp":[stamp-pd.Timedelta(minutes=5),stamp+pd.Timedelta(minutes=5)],
        "available_at":[stamp+pd.Timedelta(minutes=1),stamp+pd.Timedelta(minutes=10)],
        "last_source_available_at":[stamp+pd.Timedelta(minutes=1),stamp+pd.Timedelta(minutes=10)],
        "usable":[True,True],"speed_kmh":[40.,70.],"valid_slots":[2,2],"present_slots":[4,4]})
    path=tmp_path/"bins.parquet";pq.write_table(pa.Table.from_pandas(bins,preserve_index=False),path)
    refs=pd.DataFrame({"detector_id":["B"],"direction":["North"],"lane_id":["L"],
        "baseline_kmh":[80.],"reference_fit_end":[pd.Timestamp("2023-02-01",tz="Asia/Hong_Kong")]})
    out=candidate_opportunity(events,pairs,path,refs)
    assert out.upstream_available_speed_count.tolist()==[0,1]
    assert pd.isna(out.iloc[0].upstream_latest_speed_kmh)
    assert out.iloc[1].upstream_latest_speed_kmh == 40
    assert out.feature_status.eq("CANDIDATE_ONLY_NOT_MODEL_APPROVED").all()
    assert out.iloc[1].upstream_mean_valid_slot_fraction == .2
    verified=verified_zero_eligibility(events,refs,version="unapproved")
    assert not verified.spatial_model_eligible.any()
    assert verified.upstream_mean_speed_kmh.isna().all()
