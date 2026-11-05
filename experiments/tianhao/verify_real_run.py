"""Meaningful real-input/output checks; no synthetic performance assertions."""
from pathlib import Path
import hashlib, io, json, zipfile
import numpy as np
import pandas as pd
import joblib
from sklearn.metrics import f1_score, balanced_accuracy_score, log_loss
from paths import ROOT, BASE, DATA
RUN = BASE / Path((BASE / 'latest_run.txt').read_text(encoding='utf-8').strip())
manifest = json.loads((RUN / 'manifest.json').read_text(encoding='utf-8'))
checks = []

def check(name, passed, detail=''):
    assert bool(passed), name + ': ' + detail
    checks.append({'check': name, 'status': 'passed', 'detail': detail})
for name, digest in manifest['outputs'].items():
    with (RUN / name).open('rb') as f:
        actual = hashlib.file_digest(f, 'sha256').hexdigest()
    check('output SHA256: ' + name, actual == digest)
events = pd.read_parquet(RUN / 'event_feature_audit.parquet')
pred = pd.read_parquet(RUN / 'predictions.parquet')
metrics = pd.read_csv(RUN / 'metrics_summary.csv')
check('cohort rows and unique IDs', len(events) == 7597 and events.event_id.is_unique)
check('known-label count', events.label_30m.notna().sum() == 6799)
check('prediction arms', pred.groupby(['model', 'feature_set']).ngroups == 14)
for (model, features, split), part in pred.groupby(['model', 'feature_set', 'split']):
    selected = events.loc[events.split.eq(split) & events.label_30m.notna()]
    check(f'paired cohort: {model}/{features}/{split}', set(part.event_id) == set(selected.event_id) and part.event_id.is_unique)
    row = metrics.loc[metrics.model.eq(model) & metrics.feature_set.eq(features) & metrics.split.eq(split)].iloc[0]
    check(f'macro-F1 recompute: {model}/{features}/{split}', np.isclose(row.macro_f1, f1_score(part.y_true, part.y_pred, average='macro', labels=[0, 1], zero_division=0)))
    check(f'balanced accuracy recompute: {model}/{features}/{split}', np.isclose(row.balanced_accuracy, balanced_accuracy_score(part.y_true, part.y_pred)))
for column in ['feature_max_available_at', 'speed_trend_max_available_at', 'flow_features_available_at', 'calendar_max_source_available_at', 'weather_features_available_at']:
    check('watermark <= prediction: ' + column, (events[column] <= events.prediction_time).all())
for kind, value in [('temperature', 'temperature_c'), ('wind', 'wind_speed_kmh')]:
    known = events[value].notna()
    check('weather raw time: ' + kind, (events.loc[known, kind + '_available_at'] <= events.loc[known, 'prediction_time']).all() and events.loc[known, kind + '_age_minutes'].between(0, 60).all())
with zipfile.ZipFile(BASE / 'sources/traffic_prepared.zip') as z:
    midnight = events.index[events.onset_confirmed_at.dt.hour.eq(0) & events.onset_confirmed_at.dt.minute.eq(0)].tolist()
    for index in sorted(set(np.linspace(0, len(events) - 1, 8, dtype=int).tolist() + midnight)):
        event = events.iloc[index]
        d = pd.read_parquet(io.BytesIO(z.read('processed/derived/cleaned-' + event.onset_confirmed_at.strftime('%Y%m%d') + '.parquet')))
        if (event.onset_confirmed_at - pd.Timedelta(minutes=5)).date() != event.onset_confirmed_at.date():
            previous = (event.onset_confirmed_at - pd.Timedelta(days=1)).strftime('%Y%m%d')
            prior = pd.read_parquet(io.BytesIO(z.read('processed/derived/cleaned-' + previous + '.parquet')))
            d = pd.concat([prior, d], ignore_index=True)
        sample = d.loc[d.detector_id.eq(event.detector_id) & d.direction.eq(event.direction) & d.lane_id.eq(event.lane_id) & d.timestamp.gt(event.onset_confirmed_at - pd.Timedelta(minutes=5)) & d.timestamp.le(event.onset_confirmed_at) & d.available_at.le(event.prediction_time)]
        invalid = ~sample.valid.eq('Y') | sample.conflict.fillna(False).astype(bool)
        check('offline/conflict measurements masked: ' + event.event_id, sample.loc[invalid, ['volume_count', 'occupancy_pct']].isna().all().all())
        for raw, feature in [('volume_count', 'volume_median_per_observed_30s'), ('occupancy_pct', 'occupancy_median_pct')]:
            actual = sample[raw].median()
            check('raw flow recomputation: ' + event.event_id + '/' + raw, np.isclose(actual, event[feature], equal_nan=True))
w = pd.read_parquet(BASE / 'prepared/weather_event_features.parquet')
for kind, value, position in [('temperature', 'temperature_c', 2), ('wind', 'wind_speed_kmh', 3)]:
    for index in np.linspace(0, len(w) - 1, 6, dtype=int):
        event = w.iloc[index]
        if pd.isna(event[value]):
            continue
        with zipfile.ZipFile(BASE / 'sources' / event[kind + '_archive_file']) as z:
            payload = z.read(event[kind + '_archive_member'])
        check('weather member hash: ' + event.event_id + '/' + kind, hashlib.sha256(payload).hexdigest() == event[kind + '_source_sha256'])
        raw = pd.read_csv(io.BytesIO(payload))
        observed = raw.loc[raw.iloc[:, 1].eq("King's Park")].iloc[0, position]
        check('weather raw value: ' + event.event_id + '/' + kind, np.isclose(float(observed), event[value]))
pipelines = joblib.load(RUN / 'fitted_pipelines.joblib')
plan = json.loads((RUN / 'predeclared_plan.json').read_text(encoding='utf-8'))
for (kind, features), pipeline in pipelines.items():
    columns = [c for g in features.split('+') for c in plan['feature_groups'][g]]
    train = events.loc[events.split.eq('train') & events.label_30m.notna(), columns]
    transformer = pipeline.named_steps['preprocess'].named_transformers_['numeric']
    imputer = transformer.named_steps['impute']
    check('train-only imputation: ' + kind + '/' + features, np.allclose(imputer.statistics_, train.median().to_numpy(), equal_nan=True))
    if kind == 'logistic':
        expected = imputer.transform(train).mean(axis=0)
        check('train-only scaling: ' + features, np.allclose(transformer.named_steps['scale'].mean_, expected))
    sample = events.loc[events.split.eq('test') & events.label_30m.notna()].head(8)
    probability = pipeline.predict_proba(sample[columns])[:, 1]
    model = 'logistic_regression' if kind == 'logistic' else 'decision_tree'
    stored = pred.loc[pred.model.eq(model) & pred.feature_set.eq(features)].set_index('event_id').loc[sample.event_id, 'y_score']
    check('saved pipeline reproduces predictions: ' + kind + '/' + features, np.allclose(probability, stored))
result = {'status': 'passed', 'checks': len(checks), 'results': checks, 'note': 'Source hashes, temporal checks, paired cohorts and output recomputation; not scientific approval.'}
(RUN / 'verification.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print('Real-run checks passed:', len(checks))
