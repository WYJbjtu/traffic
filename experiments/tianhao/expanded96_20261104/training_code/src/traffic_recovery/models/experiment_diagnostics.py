"""Paired ablation and descriptive error diagnostics; never used for selection."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, f1_score, balanced_accuracy_score


def feature_gains(summary: pd.DataFrame, feature_sets: list[tuple[str, ...]]) -> pd.DataFrame:
    """Adjacent test-group changes; positive improvement always means better.

    Caller must establish identical event cohorts before computing these changes.
    Values are descriptive; no significance, causality or independence is implied.
    """
    rows = []
    for model, part in summary.loc[summary.split.eq('test')].groupby('model'):
        table = part.set_index('feature_set')
        for previous, current in zip(feature_sets, feature_sets[1:]):
            before, after = '+'.join(previous), '+'.join(current)
            if before not in table.index or after not in table.index:
                continue
            for metric in ['macro_f1', 'balanced_accuracy', 'log_loss', 'roc_auc', 'pr_auc']:
                delta = float(table.at[after, metric] - table.at[before, metric])
                rows.append(dict(model=model, feature_set=after, reference=before,
                                 metric=metric, raw_delta=delta,
                                 improvement=-delta if metric == 'log_loss' else delta))
    return pd.DataFrame(rows, columns=['model','feature_set','reference','metric','raw_delta','improvement'])


def error_diagnostics(predictions: pd.DataFrame, events: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Join test predictions to verified detector keys and HKT peak periods.

    Peak = [07:00,10:00) or [17:00,20:00). Unit is detector, not an assumed road.
    Return event errors and grouped counts/recalls/F1; both classes use fixed labels.
    """
    keys = ['event_id', 'prediction_time', 'detector_id', 'direction', 'lane_id']
    if set(keys) - set(events) or events.event_id.duplicated().any():
        raise ValueError('Error diagnostics require unique events and detector/lane/time metadata')
    test = predictions.loc[predictions.split.eq('test')].merge(
        events[keys], on=['event_id', 'prediction_time'], how='left', validate='many_to_one', indicator=True)
    if not test._merge.eq('both').all():
        raise ValueError('Error metadata does not match prediction IDs and times')
    test = test.drop(columns='_merge')
    hour = test.prediction_time.dt.tz_convert('Asia/Hong_Kong').dt.hour
    test['peak'] = np.where(hour.between(7, 9) | hour.between(17, 19), 'peak', 'off_peak')
    test['error_type'] = np.select([(test.y_true == 0) & (test.y_pred == 1),
                                  (test.y_true == 1) & (test.y_pred == 0)],
                                 ['false_positive', 'false_negative'], default='correct')
    rows = []
    for dimension in ['detector_id', 'peak']:
        for (model, features, horizon, group), part in test.groupby(['model','feature_set','horizon_min',dimension]):
            tn, fp, fn, tp = confusion_matrix(part.y_true, part.y_pred, labels=[0,1]).ravel()
            rows.append(dict(model=model, feature_set=features, horizon_min=horizon,
                             dimension=dimension, group=group, n=len(part), n_positive=int(part.y_true.sum()),
                             tn=int(tn), fp=int(fp), fn=int(fn), tp=int(tp),
                             errors=int(fp+fn), error_rate=float((fp+fn)/len(part)),
                             macro_f1=f1_score(part.y_true, part.y_pred, average='macro', labels=[0,1], zero_division=0),
                             balanced_accuracy=balanced_accuracy_score(part.y_true, part.y_pred)
                             if part.y_true.nunique() == 2 else np.nan))
    return test, pd.DataFrame(rows)


def exact_feature_join(events: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
    """One-to-one event/time join; reject silent dropped/misaligned feature rows."""
    keys = ['event_id', 'prediction_time']
    for frame in [events, features]:
        if frame.event_id.isna().any() or frame.event_id.duplicated().any():
            raise ValueError('Feature joins require unique non-null event IDs')
    overlap = (set(events) & set(features)) - set(keys)
    if overlap or set(events.event_id) != set(features.event_id):
        raise ValueError(f'Feature schema/ID mismatch; overlapping columns={sorted(overlap)}')
    result = events.merge(features, on=keys, how='left', validate='one_to_one', indicator=True)
    if not result._merge.eq('both').all():
        raise ValueError('Feature prediction times do not exactly match events')
    return result.drop(columns='_merge')
