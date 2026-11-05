"""Synthetic availability regression; these rows are not research evidence."""
import pandas as pd
import pytest

from traffic_recovery.models.expanded96 import history_features, metrics


def test_history_rejects_future_available_and_unusable_bins(tmp_path):
    tz = 'Asia/Hong_Kong'
    end = pd.Timestamp('2023-03-01 12:00', tz=tz)
    prediction = end + pd.Timedelta(minutes=10)
    events = pd.DataFrame([{'detector_id': 'synthetic', 'direction': 'E', 'lane_id': '1',
        'event_id': 'synthetic-event', 'onset_confirmed_at': end, 'prediction_time': prediction,
        'baseline_kmh': 100.0}])
    bins = pd.DataFrame([{'detector_id': 'synthetic', 'direction': 'E', 'lane_id': '1',
        'timestamp': end - pd.Timedelta(minutes=i), 'speed_kmh': speed, 'usable': usable,
        'available_at': available, 'last_source_available_at': available}
        for i, speed, usable, available in ((0, 20., True, prediction),
            (5, 40., True, prediction + pd.Timedelta(minutes=1)),
            (10, 60., False, prediction), (15, 80., True, prediction))])
    path = tmp_path / 'bins.parquet'
    bins.to_parquet(path)
    result = history_features(events, path).iloc[0]
    assert result.history_observed_bins == 2
    assert pd.isna(result.lag_5m_ratio)
    assert pd.isna(result.lag_10m_ratio)
    assert result.lag_15m_ratio == 0.8
    assert result.history_trend_ratio == pytest.approx(-0.6)
    assert result.history_latest_available_at == prediction


def test_metrics_confusion_has_fixed_class_order():
    result = metrics(pd.Series([1, 0]).to_numpy(), pd.Series([.8, .2]).to_numpy(),
                     pd.Series([1, 0]).to_numpy())
    assert (result['tn'], result['fp'], result['fn'], result['tp']) == (1, 0, 0, 1)
