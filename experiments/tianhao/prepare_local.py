"""Past-only speed-window and flow/occupancy features; no label alteration."""
from __future__ import annotations
from pathlib import Path
import argparse, hashlib, io, json, zipfile
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from paths import ROOT, BASE, DATA
PREP = BASE / 'prepared'
PREP.mkdir(parents=True, exist_ok=True)
KEY = ['detector_id', 'direction', 'lane_id']

def speed_features():
    events = pd.read_parquet(DATA / 'processed/derived/events.parquet').sort_values('prediction_time').reset_index(drop=True)
    rows = []
    parquet = pq.ParquetFile(DATA / 'processed/derived/cohort_bins.parquet')
    groups = {k: d for k, d in events.groupby(KEY)}
    seen = set()
    for rg in range(parquet.num_row_groups):
        part = parquet.read_row_group(rg, columns=KEY + ['timestamp', 'available_at', 'speed_kmh', 'usable', 'last_source_available_at']).to_pandas()
        for key, bins in part.groupby(KEY, sort=False):
            if key not in groups:
                continue
            assert key not in seen, 'Lane spans multiple rowgroups; use a lane-level scanner instead'
            seen.add(key)
            bins = bins.sort_values('timestamp').set_index('timestamp')
            assert bins.index.is_unique
            for event in groups[key].itertuples():
                end = event.onset_confirmed_at
                index = pd.date_range(end - pd.Timedelta(minutes=15), end, freq='5min')
                window = bins.reindex(index)
                valid = window.usable.fillna(False).astype(bool) & window.speed_kmh.notna() & window.available_at.le(event.prediction_time) & window.last_source_available_at.le(event.prediction_time)
                ratio = window.speed_kmh.where(valid) / event.baseline_kmh
                complete = bool(valid.all())
                observed = window.loc[valid, 'available_at']
                rows.append({'event_id': event.event_id, 'prediction_time': event.prediction_time, 'speed_change_15m_ratio': float(ratio.iloc[-1] - ratio.iloc[0]) if complete else np.nan, 'speed_mean_15m_ratio': float(ratio.mean()) if complete else np.nan, 'speed_slope_15m_ratio_per_min': float(np.polyfit(np.arange(4) * 5, ratio, 1)[0]) if complete else np.nan, 'speed_trend_observed_bins': int(valid.sum()), 'speed_trend_window_end': end, 'speed_trend_max_available_at': observed.max() if len(observed) else pd.NaT})
        print(f'Speed rowgroup {rg + 1}/{parquet.num_row_groups}', flush=True)
    features = pd.DataFrame(rows)
    assert features.event_id.is_unique and set(features.event_id) == set(events.event_id)
    known = features.speed_trend_max_available_at.notna()
    assert (features.loc[known, 'speed_trend_max_available_at'] <= features.loc[known, 'prediction_time']).all()
    features.to_parquet(PREP / 'speed_history_features.parquet', index=False)
    print('speed complete windows:', int(features.speed_change_15m_ratio.notna().sum()), flush=True)

def flow_features():
    events = pd.read_parquet(DATA / 'processed/derived/events.parquet')
    events['feature_date'] = events.onset_confirmed_at.dt.strftime('%Y%m%d')
    path = BASE / 'sources/traffic_prepared.zip'
    rows = []
    manifest = json.loads((DATA / 'SHARED_DATA_MANIFEST.json').read_text(encoding='utf-8'))['files']
    with zipfile.ZipFile(path) as z:
        for j, (date, day_events) in enumerate(events.groupby('feature_date'), 1):
            member = f'processed/derived/cleaned-{date}.parquet'
            payload = z.read(member)
            assert hashlib.sha256(payload).hexdigest() == manifest[member]['sha256']
            daily = pd.read_parquet(io.BytesIO(payload))
            crosses_midnight = (day_events.onset_confirmed_at - pd.Timedelta(minutes=5)).dt.date.ne(day_events.onset_confirmed_at.dt.date).any()
            if crosses_midnight:
                previous = (pd.Timestamp(date) - pd.Timedelta(days=1)).strftime('%Y%m%d')
                prior_member = f'processed/derived/cleaned-{previous}.parquet'
                prior_payload = z.read(prior_member)
                assert hashlib.sha256(prior_payload).hexdigest() == manifest[prior_member]['sha256']
                daily = pd.concat([pd.read_parquet(io.BytesIO(prior_payload)), daily], ignore_index=True)
                assert not daily.duplicated(KEY + ['timestamp']).any(), 'Unexpected overlap between cleaned day partitions'
            if j == 1:
                (PREP / 'cleaned_daily_schema.json').write_text(json.dumps({c: str(t) for c, t in daily.dtypes.items()}, indent=2), encoding='utf-8')
                print('Daily schema:', daily.columns.tolist(), flush=True)
            available_col = 'available_at' if 'available_at' in daily else 'archive_time'
            if available_col not in daily:
                raise ValueError('Cannot verify raw measurement availability')
            by_unit = {k: d for k, d in daily.groupby(KEY, sort=False)}
            for event in day_events.itertuples():
                local = by_unit.get(tuple((getattr(event, k) for k in KEY)), daily.iloc[:0])
                window = local.loc[(local.timestamp > event.onset_confirmed_at - pd.Timedelta(minutes=5)) & local.timestamp.le(event.onset_confirmed_at) & local[available_col].le(event.prediction_time)]
                observed = window.loc[window.source_valid] if 'source_valid' in window else window
                invalid = ~observed.valid.eq('Y') | observed.conflict.fillna(False).astype(bool)
                assert observed.loc[invalid, ['volume_count', 'occupancy_pct']].isna().all().all()
                volume = pd.to_numeric(observed.volume_count, errors='coerce').dropna()
                occupancy = pd.to_numeric(observed.occupancy_pct, errors='coerce').dropna()
                populated = observed.loc[observed.volume_count.notna() | observed.occupancy_pct.notna()]
                rows.append({'event_id': event.event_id, 'prediction_time': event.prediction_time, 'volume_median_per_observed_30s': float(volume.median()) if len(volume) else np.nan, 'occupancy_median_pct': float(occupancy.median()) if len(occupancy) else np.nan, 'flow_observed_slots': int(len(volume)), 'occupancy_observed_slots': int(len(occupancy)), 'flow_max_available_at': populated[available_col].max() if len(populated) else pd.NaT})
            if j % 100 == 0:
                print(f'Flow/occupancy {j} days; {len(rows)} events', flush=True)
    features = pd.DataFrame(rows)
    assert features.event_id.is_unique and len(features) == len(events)
    known = features.flow_max_available_at.notna()
    assert (features.loc[known, 'flow_max_available_at'] <= features.loc[known, 'prediction_time']).all()
    features.to_parquet(PREP / 'flow_occupancy_features.parquet', index=False)
    print('Flow/occupancy features:', features.shape, flush=True)
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('step', choices=['speed', 'flow'])
    args = parser.parse_args()
    {'speed': speed_features, 'flow': flow_features}[args.step]()
