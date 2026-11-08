"""Synthetic fixtures for C/W guards and train-only matrix preprocessing."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from experiments.unified96.context import C, W, join_context
from experiments.unified96.run import ARMS, L, H, Q, S
from experiments.unified96.matrix import fit_arm, dump

T = pd.Timestamp('2026-01-01 12:00', tz='Asia/Hong_Kong')


def inputs():
    data = pd.DataFrame({'event_id': ['a', 'b'], 'prediction_time': [T, T], 'speed_kmh': [1., 2.]})
    cal = data[['event_id', 'prediction_time']].assign(**{c: 0. for c in C}, calendar_max_source_available_at=T-pd.Timedelta(days=30))
    weather = data[['event_id', 'prediction_time']].assign(temperature_c=[20., np.nan], wind_speed_kmh=[5., 6.],
        temperature_missing=[0, 1], wind_missing=[0, 0], temperature_age_minutes=10., wind_age_minutes=10.)
    for kind in ['temperature', 'wind']:
        weather[kind+'_observed_at'] = T-pd.Timedelta(minutes=10)
        weather[kind+'_available_at'] = T-pd.Timedelta(minutes=5)
    return data, cal, weather


def test_double_key_alignment_preserves_missing_and_base():
    data, cal, weather = inputs()
    result = join_context(data, cal.iloc[::-1], weather.iloc[::-1])
    assert result.event_id.tolist() == ['a', 'b']
    assert result.temperature_c.iloc[0] == 20 and pd.isna(result.temperature_c.iloc[1])
    pd.testing.assert_frame_equal(result[data.columns], data)


@pytest.mark.parametrize('which,column,value', [
    (1, 'prediction_time', T+pd.Timedelta(minutes=1)),
    (2, 'event_id', 'unknown'),
    (1, 'calendar_max_source_available_at', T+pd.Timedelta(days=1)),
    (2, 'temperature_available_at', T+pd.Timedelta(minutes=1)),
    (2, 'wind_observed_at', T+pd.Timedelta(minutes=1)),
    (2, 'temperature_age_minutes', 61),
    (2, 'temperature_missing', 1),
])
def test_context_rejects_identity_future_and_age(which, column, value):
    frames = list(inputs())
    frames[which].loc[0, column] = value
    with pytest.raises(ValueError):
        join_context(*frames)


def test_reject_duplicate_conflict_and_whitelist_exclusion():
    data, cal, weather = inputs()
    with pytest.raises(ValueError, match='Duplicate'):
        join_context(data, pd.concat([cal, cal]), weather)
    with pytest.raises(ValueError, match='overlap'):
        join_context(data, cal.assign(speed_kmh=99.), weather)
    result = join_context(data, cal.assign(secret_source_url='not a feature'), weather)
    assert 'secret_source_url' not in result
    groups = L+H+Q+C+W+S
    assert len(groups) == len(set(groups))
    assert len(ARMS) == 8 and ARMS['F7'] == ARMS['F3']+S
    for columns in ARMS.values():
        assert len(columns) == len(set(columns))
        assert not any('source' in x or 'label' in x or 'retrieved' in x for x in columns)


@pytest.mark.parametrize('model_name', ['logistic_regression', 'xgboost'])
def test_preprocessing_is_train_only_no_dropna(tmp_path, model_name):
    # Deliberately different train/validation/test distributions; one missing row.
    data = pd.DataFrame({'event_id': [f'e{i}' for i in range(12)],
        'prediction_time': [T]*12, 'detector_id': ['d1', 'd2']*6,
        'split': ['train']*6+['validation']*4+['test']*2, 'label': [0,1]*6,
        'x': [1.,2.,3.,4.,5.,np.nan,100.,101.,102.,103.,1000.,np.nan]})
    pred, metrics, tuning, audit = fit_arm(data, ['x'], 'synthetic', 'synthetic', (model_name,))
    dump(tmp_path/'audit.json', audit)  # XGBoost NaN missing-value sentinel is a string, valid JSON.
    assert audit[0]['imputer_statistics'] == [3.]
    assert audit[0]['scaler_n_samples_seen'] == (6 if model_name == 'logistic_regression' else None)
    assert len(pred) == 6 and len(tuning) == 2
    assert pred.groupby('split').size().to_dict() == {'test': 2, 'validation': 4}
    assert np.isfinite(pred.y_score).all()
