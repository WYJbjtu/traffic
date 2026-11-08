"""Authenticated Calendar/Weather96 joins, never row-position alignment.

Units: temperature Celsius, wind km/h, observation age minutes. All timestamps
must be timezone-aware. Missing meteorology is preserved, not replaced by zero.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

C = ['hour_sin', 'hour_cos', 'dow_sin', 'dow_cos', 'is_weekend',
     'is_public_holiday', 'is_day_before_holiday', 'is_day_after_holiday']
W = ['temperature_c', 'wind_speed_kmh', 'temperature_age_minutes', 'wind_age_minutes',
     'temperature_missing', 'wind_missing']
KEYS = ['event_id', 'prediction_time']


def join_context(data: pd.DataFrame, calendar: pd.DataFrame, weather: pd.DataFrame) -> pd.DataFrame:
    """Return a one-to-one double-key left join; reject mismatch/overlap/future inputs.

    Context may contain the entire Release while data is the verified P1 subset.
    Neither labels, local/history/spatial fields nor identity can be overwritten.
    Source URLs/hashes/timestamps are audited but not returned as model inputs.
    """
    for name, frame in [('data', data), ('calendar', calendar), ('weather', weather)]:
        if frame[KEYS].isna().any().any() or frame.event_id.duplicated().any():
            raise ValueError(f'Duplicate/missing context identity: {name}')
        if not isinstance(frame.prediction_time.dtype, pd.DatetimeTZDtype):
            raise ValueError(f'Timezone-aware prediction_time required: {name}')
    for frame, columns in [(calendar, C), (weather, W)]:
        if not set(columns).issubset(frame):
            raise ValueError('Context whitelist columns missing')
        overlap = (set(frame) & set(data)) - set(KEYS)
        # Compare every overlap rather than silently accepting suffixes. Identity,
        # labels and L/H/Q/S are always retained from the authoritative data.
        paired = data[KEYS + sorted(overlap)].merge(frame[KEYS + sorted(overlap)],
            on=KEYS, how='left', validate='one_to_one', indicator=True, suffixes=('_base', '_context'))
        if not paired._merge.eq('both').all():
            raise ValueError('Context double-key join lost events or prediction times')
        for col in overlap:
            a, b = paired[col+'_base'], paired[col+'_context']
            if not ((a.eq(b)) | (a.isna() & b.isna())).all():
                raise ValueError(f'Conflicting context overlap: {col}')
        # Even identical pre-existing C/W is rejected: provenance must be explicit.
        if set(columns) & set(data):
            raise ValueError('C/W already present; use the verified L/H/Q/S base')
    watermark = calendar.calendar_max_source_available_at
    if not isinstance(watermark.dtype, pd.DatetimeTZDtype) or watermark.isna().any() or not watermark.le(calendar.prediction_time).all():
        raise ValueError('Future/missing/naive calendar availability')
    if calendar[C].isna().any().any():
        raise ValueError('Calendar feature missing')
    for kind, value in [('temperature', 'temperature_c'), ('wind', 'wind_speed_kmh')]:
        valid = weather[value].notna()
        if not weather[kind+'_missing'].eq((~valid).astype(int)).all():
            raise ValueError('Weather missing flag differs')
        for suffix in ['observed_at', 'available_at']:
            clock = weather[kind+'_'+suffix]
            if not isinstance(clock.dtype, pd.DatetimeTZDtype) or not clock[valid].le(weather.loc[valid, 'prediction_time']).all():
                raise ValueError('Future/missing/naive weather time')
        age = (weather.prediction_time - weather[kind+'_observed_at']).dt.total_seconds()/60
        if not age[valid].between(0, 60).all() or not np.allclose(age[valid], weather.loc[valid, kind+'_age_minutes']):
            raise ValueError('Stale or inconsistent weather age')
    output = data.copy()
    for frame, columns in [(calendar, C), (weather, W)]:
        output = output.merge(frame[KEYS+columns], on=KEYS, how='left', validate='one_to_one')
    if len(output) != len(data):
        raise ValueError('Context changed population')
    return output


def authenticate_bundle(bundle: Path, events: Path, repository: Path) -> dict:
    """Run the producer's frozen verifier against local Release and current code.

    This verifies delivered evidence and producer reconstruction records, not an
    independent download/rebuild of the 90 monthly weather archives.
    """
    spec = importlib.util.spec_from_file_location('cw_handoff_verifier', bundle/'verify_handoff.py')
    if spec is None or spec.loader is None:
        raise ValueError('Missing Calendar/Weather handoff verifier')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.verify_bundle(bundle, events_path=events, repository=repository)
