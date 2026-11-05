"""Synthetic selection fixtures; never use test rows as empirical lane counts."""
from datetime import timedelta
from pathlib import Path

import pandas as pd
import pytest

from traffic_recovery.data.events import UNIT, fit_reference
from traffic_recovery.data.lane_expansion import AuditInputs, audit, selection_table
from traffic_recovery.data.pilot import select_cohort


CONFIG = {'observation_start': '2023-01-01T00:00:00+08:00',
          'selection_end': '2023-01-08T00:00:00+08:00', 'reference_end': '2023-02-01T00:00:00+08:00',
          'valid_5m_mean_min': .95, 'valid_5m_daily_min': .90, 'flow_5m_mean_min': .80,
          'max_units': 1, 'min_reference_bins': 300}
DAYS = pd.date_range(CONFIG['observation_start'], periods=7, freq='D')


def profile() -> pd.DataFrame:
    records = []
    for detector, lane, flow in [('A', 'Fast', .90), ('A', 'Slow', .85), ('B', 'Fast', .82), ('C', 'Slow', .87)]:
        for day in DAYS:
            missing = detector == 'C' and day == DAYS[3]
            records.append({'detector_id': detector, 'direction': 'North', 'lane_id': lane, 'day': day,
                'valid_coverage': 0 if missing else .97, 'valid_5m_coverage': 0 if missing else .97,
                'usable_5m_coverage': 0 if missing else flow, 'conflict_slots': int(detector == 'B'),
                'offline_slots': int(missing), 'present_slots': 0 if missing else 2793,
                'valid_slots': 0 if missing else 2793, 'valid_5m_bins': 0 if missing else 280,
                'usable_5m_bins': 0 if missing else 250, 'max_invalid_or_absent_gap_seconds': 86400 if missing else 30})
    return pd.DataFrame(records)


def test_uncap_does_not_change_conditions_or_lane_policy():
    frame = profile()
    table = selection_table(frame, CONFIG)
    capped, _ = select_cohort(frame, DAYS[-1] + timedelta(days=1), CONFIG)
    uncapped, _ = select_cohort(frame, DAYS[-1] + timedelta(days=1), CONFIG | {'max_units': 99})
    assert capped[UNIT].to_dict('records') == [{'detector_id':'A','direction':'North','lane_id':'Fast'}]
    assert uncapped[UNIT].to_dict('records') == capped[UNIT].to_dict('records')
    assert len(table.loc[table.passes_all]) == 2  # two real-like lanes of same detector
    assert len(table.loc[table.one_lane_chosen]) == 1
    assert table.loc[table.detector_id.eq('A') & table.lane_id.eq('Slow'), 'exclusion_reasons'].iloc[0] == 'eligible_other_lane_preferred'
    assert 'no_source_conflicts' in table.loc[table.detector_id.eq('B'), 'exclusion_reasons'].iloc[0]
    assert 'valid_5m_daily_min' in table.loc[table.detector_id.eq('C'), 'exclusion_reasons'].iloc[0]


def test_missing_day_or_future_day_cannot_select():
    frame = profile()
    with pytest.raises(ValueError, match='Missing explicit zero-coverage days'):
        selection_table(frame.loc[~((frame.detector_id == 'A') & (frame.day == DAYS[2]))], CONFIG)
    future = frame.iloc[[0]].copy().assign(day=DAYS[-1] + timedelta(days=1))
    with pytest.raises(ValueError, match='future-day leakage'):
        selection_table(pd.concat([frame, future], ignore_index=True), CONFIG)


def test_existing_published_outputs_are_never_overwritten(tmp_path):
    existing = tmp_path / 'published'
    existing.mkdir()
    marker = existing / 'cohort.csv'
    marker.write_text('original,unchanged\\n', encoding='utf-8')
    missing = tmp_path / 'missing'
    with pytest.raises(FileExistsError, match='refusing overwrite'):
        audit(AuditInputs(*([missing]*6)), existing)
    assert marker.read_text(encoding='utf-8') == 'original,unchanged\\n'


def test_reference_needs_positive_available_history_and_processed_is_not_lane():
    stamp = pd.Timestamp('2023-01-03T12:00:00+08:00')
    bins = pd.DataFrame({'detector_id':['A']*302, 'direction':['North']*302, 'lane_id':['Fast']*302,
        'timestamp':pd.date_range(stamp, periods=302, freq='5min'),
        'available_at':pd.date_range(stamp+timedelta(minutes=10), periods=302, freq='5min'),
        'usable':[True]*302, 'speed_kmh':[45.]*302})
    bins.loc[0, 'speed_kmh'] = 0
    bins.loc[1, 'available_at'] = pd.Timestamp('2023-02-01T01:00:00+08:00')
    assert len(fit_reference(bins, fit_start=pd.Timestamp(CONFIG['observation_start']),
        fit_end=pd.Timestamp(CONFIG['reference_end']), min_bins=300)) == 1
    assert fit_reference(bins, fit_start=pd.Timestamp(CONFIG['observation_start']),
        fit_end=pd.Timestamp(CONFIG['reference_end']), min_bins=301).empty
    assert 'segment_id' not in UNIT  # road segment never adds a detector/lane identity
