"""Synthetic coverage rows keep unknown labels separate from missing features."""
import pandas as pd
import pytest
import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    'external_coverage_report',
    Path(__file__).parents[1] / 'experiments/tianhao/document_external_coverage.py',
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
CALENDAR = MODULE.CALENDAR
summarise_coverage = MODULE.summarise_coverage


def events():
    frame = pd.DataFrame({'event_id': ['SYNTHETIC-A', 'SYNTHETIC-B', 'SYNTHETIC-C'],
                          'split': ['train', 'train', 'test'], 'label_30m': [0, pd.NA, 1],
                          'temperature_c': [20, None, 22], 'wind_speed_kmh': [None, 10, 12]})
    for column in CALENDAR:
        frame[column] = 0
    return frame


def test_unknown_labels_and_feature_missingness_have_different_denominators():
    report = summarise_coverage(events()).set_index(['scope', 'split', 'feature'])
    assert report.loc[('all_events', 'train', 'temperature_c'), 'n_events'] == 2
    assert report.loc[('all_events', 'train', 'temperature_c'), 'missing_rate'] == 0.5
    assert report.loc[('known_label_30m', 'train', 'temperature_c'), 'n_events'] == 1
    assert report.loc[('known_label_30m', 'train', 'temperature_c'), 'missing_rate'] == 0
    assert report.loc[('all_events', 'all', 'weather_both_values'), 'missing'] == 2
    assert pd.isna(report.loc[('all_events', 'validation', 'temperature_c'), 'missing_rate'])


def test_duplicate_event_rows_cannot_inflate_coverage():
    with pytest.raises(ValueError, match='one non-null row per event'):
        summarise_coverage(pd.concat([events(), events().iloc[:1]]))
