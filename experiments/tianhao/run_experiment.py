"""Frozen, exploratory 30-minute experiments reusing Tianhao's original engine."""
from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, os, platform, sys, uuid
import shutil, subprocess
import numpy as np
import pandas as pd
from paths import ROOT, BASE, DATA, describe_path
REPO = ROOT
PREP = BASE / 'prepared'
sys.path.insert(0, str(REPO / 'src'))
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / '.cache/matplotlib'))
from traffic_recovery.models.contract import ExperimentContract, validate_event_table
from traffic_recovery.models.dataset import build_model_dataset
from traffic_recovery.models.supervised import SupervisedRules, train_supervised
from traffic_recovery.models.benchmarks import BenchmarkRules, benchmark_predictions
from traffic_recovery.models.evaluation import evaluate_predictions
from sklearn.metrics import f1_score, confusion_matrix
import sklearn
import joblib
STATUS = 'EXPLORATORY — NOT APPROVED AS FINAL RESULTS'
GROUPS = {'local': ['speed_kmh', 'speed_ratio', 'baseline_kmh', 'valid_slots', 'onset_observed_minutes'], 'history': ['speed_change_15m_ratio', 'speed_mean_15m_ratio', 'speed_slope_15m_ratio_per_min', 'speed_trend_observed_bins'], 'flow': ['volume_median_per_observed_30s', 'occupancy_median_pct', 'flow_observed_slots', 'occupancy_observed_slots'], 'calendar': ['hour_sin', 'hour_cos', 'dow_sin', 'dow_cos', 'is_weekend', 'is_public_holiday', 'is_day_before_holiday', 'is_day_after_holiday'], 'weather': ['temperature_c', 'wind_speed_kmh', 'temperature_age_minutes', 'wind_age_minutes', 'temperature_missing', 'wind_missing']}
FEATURE_SETS = [tuple(list(GROUPS)[:i]) for i in range(1, len(GROUPS) + 1)]

def sha(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def build_dataset(out: Path):
    source = DATA / 'processed/derived/events.parquet'
    frame = pd.read_parquet(source)
    inputs = {'events': {'path': describe_path(source), 'sha256': sha(source)}}
    for name in ['speed_history_features', 'flow_occupancy_features', 'calendar_event_features', 'weather_event_features']:
        path = PREP / (name + '.parquet')
        feature = pd.read_parquet(path)
        assert set(frame.event_id) == set(feature.event_id) and feature.event_id.is_unique
        assert not set(frame.columns) & set(feature.columns) - {'event_id', 'prediction_time'}
        frame = frame.merge(feature, on=['event_id', 'prediction_time'], how='left', validate='one_to_one')
        snapshot = out / 'inputs' / path.name
        snapshot.parent.mkdir(exist_ok=True)
        shutil.copy2(path, snapshot)
        inputs[name] = {'path': describe_path(snapshot), 'sha256': sha(snapshot)}
    frame['split'] = frame.split_proposal.astype('string')
    for columns in GROUPS.values():
        for col in columns:
            frame[col] = pd.to_numeric(frame[col], errors='raise').astype(float)
    frame['flow_features_available_at'] = frame.flow_max_available_at.fillna(frame.prediction_time)
    frame['weather_features_available_at'] = frame.prediction_time
    for col in ['feature_max_available_at', 'speed_trend_max_available_at', 'flow_features_available_at', 'calendar_max_source_available_at', 'weather_features_available_at']:
        assert frame[col].notna().all() and (frame[col] <= frame.prediction_time).all()
    for kind, value in [('temperature', 'temperature_c'), ('wind', 'wind_speed_kmh')]:
        known = frame[value].notna()
        assert (frame.loc[known, kind + '_available_at'] <= frame.loc[known, 'prediction_time']).all()
        assert (frame.loc[known, kind + '_observed_at'] <= frame.loc[known, 'prediction_time']).all()
        assert frame.loc[known, kind + '_age_minutes'].between(0, 60).all()
    requirements = {'feature_max_available_at': GROUPS['local'], 'speed_trend_max_available_at': GROUPS['history'], 'flow_features_available_at': GROUPS['flow'], 'calendar_max_source_available_at': GROUPS['calendar'], 'weather_features_available_at': GROUPS['weather']}
    payload = json.loads((REPO / 'configs/experiment_contract.json').read_text(encoding='utf-8'))
    payload.update(version='tianhao-long-window-30m-exploratory-v1', scientific_approval='pending_team_review_user_authorized_exploration', horizons_minutes=[30], feature_groups=GROUPS, availability_columns=list(requirements), availability_requirements=requirements, split_boundaries={'validation_start': '2025-01-01T00:00:00+08:00', 'test_start': '2026-01-01T00:00:00+08:00', 'test_end': '2026-10-01T00:00:00+08:00'})
    path = out / 'experiment_contract.json'
    path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    contract = ExperimentContract.from_path(path)
    validation = validate_event_table(frame, contract)
    for split, boundary in [('train', contract.validation_start), ('validation', contract.test_start)]:
        selected = frame.loc[frame.split.eq(split)]
        assert selected.outcome_maturity_at.notna().all() and (selected.outcome_maturity_at < boundary).all()
    for _, unit in frame.groupby(['detector_id', 'direction', 'lane_id']):
        assert unit.prediction_time.sort_values().diff().dropna().gt(pd.Timedelta(minutes=60)).all()
    dataset, report = build_model_dataset(frame, contract)
    dataset.to_parquet(out / 'event_features.parquet', index=False)
    frame.to_parquet(out / 'event_feature_audit.parquet', index=False)
    missing = []
    for split, part in frame.groupby('split'):
        for group, columns in GROUPS.items():
            for col in columns:
                missing.append({'split': split, 'group': group, 'feature': col, 'n': len(part), 'missing': int(part[col].isna().sum())})
    pd.DataFrame(missing).to_csv(out / 'feature_missingness.csv', index=False)
    return (dataset, frame, contract, {'inputs': inputs, 'contract_validation': validation, 'dataset_report': report})

def add_trend(frame: pd.DataFrame):
    eligible = frame.label_30m.notna() & frame.split.isin(['train', 'validation', 'test'])
    train = frame.loc[eligible & frame.split.eq('train')]
    val = frame.loc[eligible & frame.split.eq('validation')]
    majority = int(train.label_30m.mean() > 0.5)
    candidates = []
    for threshold in [-0.8, -0.6, -0.4, -0.2, -0.1, 0, 0.1, 0.2]:
        prediction = val.speed_change_15m_ratio.ge(threshold).astype(int)
        prediction.loc[val.speed_change_15m_ratio.isna()] = majority
        score = f1_score(val.label_30m.astype(int), prediction, average='macro', labels=[0, 1], zero_division=0)
        candidates.append({'model': 'speed_trend_rule', 'feature_set': 'history_rule', 'threshold': threshold, 'validation_macro_f1': score, 'selected': False})
    best = max(range(len(candidates)), key=lambda i: (candidates[i]['validation_macro_f1'], -i))
    candidates[best]['selected'] = True
    threshold = candidates[best]['threshold']
    selected = frame.loc[eligible]
    pred = selected.speed_change_15m_ratio.ge(threshold).astype(int)
    pred.loc[selected.speed_change_15m_ratio.isna()] = majority
    result = selected[['event_id', 'prediction_time', 'split']].copy()
    result['horizon_min'] = 30
    result['model'] = 'speed_trend_rule'
    result['feature_set'] = 'history_rule'
    result['y_true'] = selected.label_30m.astype(int)
    result['y_pred'] = pred
    result['y_score'] = selected.speed_change_15m_ratio.fillna(-1).astype(float)
    result['score_kind'] = 'rule_score'
    result['threshold'] = threshold
    result['n_censored_in_split'] = result.split.map(frame.groupby('split').label_30m.apply(lambda x: int(x.isna().sum())))
    result['n_missing_feature_in_split'] = result.split.map(frame.groupby('split').speed_change_15m_ratio.apply(lambda x: int(x.isna().sum())))
    return (result, pd.DataFrame(candidates))

def metrics_and_errors(predictions, frame, out):
    metrics = evaluate_predictions(predictions, version_column='experiment_version')
    confusions = []
    for (model, features, split), group in predictions.groupby(['model', 'feature_set', 'split']):
        cm = confusion_matrix(group.y_true, group.y_pred, labels=[0, 1])
        confusions.append({'model': model, 'feature_set': features, 'split': split, 'horizon_min': 30, 'tn': int(cm[0, 0]), 'fp': int(cm[0, 1]), 'fn': int(cm[1, 0]), 'tp': int(cm[1, 1]), 'n': len(group)})
    metrics.to_csv(out / 'metrics.csv', index=False)
    pd.DataFrame(confusions).to_csv(out / 'confusion_matrices.csv', index=False)
    wide = metrics.pivot_table(index=['model', 'feature_set', 'split'], columns='metric_name', values='metric_value').reset_index()
    wide.to_csv(out / 'metrics_summary.csv', index=False)
    summaries = []
    metadata = frame[['event_id', 'detector_id', 'prediction_time']].copy()
    metadata['peak'] = np.where(metadata.prediction_time.dt.hour.between(7, 9) | metadata.prediction_time.dt.hour.between(17, 19), 'peak', 'off_peak')
    test = predictions.loc[predictions.split.eq('test')].merge(metadata.drop(columns='prediction_time'), on='event_id', validate='many_to_one')
    test['error_type'] = np.select([(test.y_true == 0) & (test.y_pred == 1), (test.y_true == 1) & (test.y_pred == 0)], ['false_positive', 'false_negative'], default='correct')
    test.to_parquet(out / 'test_error_audit.parquet', index=False)
    for dimension in ['detector_id', 'peak']:
        for (model, features, key), part in test.groupby(['model', 'feature_set', dimension]):
            summaries.append({'model': model, 'feature_set': features, 'dimension': dimension, 'group': key, 'n': len(part), 'errors': int((part.y_true != part.y_pred).sum()), 'error_rate': float((part.y_true != part.y_pred).mean()), 'macro_f1': f1_score(part.y_true, part.y_pred, average='macro', labels=[0, 1], zero_division=0)})
    pd.DataFrame(summaries).to_csv(out / 'error_groups.csv', index=False)
    changes = []
    for model in ['logistic_regression', 'decision_tree']:
        table = wide.loc[(wide.model == model) & (wide.split == 'test')].set_index('feature_set')
        for i, groups in enumerate(FEATURE_SETS[1:], 1):
            now = '+'.join(groups)
            previous = '+'.join(FEATURE_SETS[i - 1])
            for metric in ['macro_f1', 'balanced_accuracy', 'log_loss', 'roc_auc', 'pr_auc']:
                delta = float(table.at[now, metric] - table.at[previous, metric])
                changes.append({'model': model, 'feature_set': now, 'reference': previous, 'metric': metric, 'raw_delta': delta, 'improvement': -delta if metric == 'log_loss' else delta})
    pd.DataFrame(changes).to_csv(out / 'feature_group_comparisons.csv', index=False)
    return wide

def main():
    run = 'run-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:6]
    out = BASE / 'runs' / run
    out.mkdir(parents=True)
    registry = {'status': STATUS, 'target': '30-minute observed recovery confirmation from handed-off labels', 'data_preparation_version': 'v2_cross_midnight_flow_window_reads_previous_day', 'feature_groups': GROUPS, 'feature_sets': [list(x) for x in FEATURE_SETS], 'selection': 'existing engine: validation log loss; trend rule: validation macro-F1', 'classification_threshold': 0.5, 'seed': 42, 'refit_train_plus_validation': False, 'trend_threshold_candidates': [-0.8, -0.6, -0.4, -0.2, -0.1, 0, 0.1, 0.2], 'peak_definition': 'HKT hours [07:00,10:00) or [17:00,20:00)', 'weather': "King's Park temperature and wind regional proxy; archived availability; <=60-minute observation age", 'excluded_families': ['unverified neighboring-road features', 'rainfall', 'humidity', 'incidents', 'major events'], 'test_policy': 'fixed plan; no test-driven retuning or feature changes'}
    (out / 'predeclared_plan.json').write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding='utf-8')
    shutil.copy2(REPO / 'configs/supervised_models.json', out / 'supervised_models.json')
    shutil.copy2(REPO / 'configs/benchmarks.json', out / 'benchmarks.json')
    dataset, audit, contract, manifest = build_dataset(out)
    rules = SupervisedRules.from_path(out / 'supervised_models.json')
    baseline = benchmark_predictions(dataset, contract, BenchmarkRules.from_path(out / 'benchmarks.json'))
    baseline['n_missing_feature_in_split'] = baseline.n_missing_rule_feature_in_split
    trend, trend_tuning = add_trend(dataset)
    predictions = [baseline, trend]
    tuning = []
    interpretation = []
    summaries = []
    fitted = {}
    for groups in FEATURE_SETS:
        for kind in ['logistic', 'tree']:
            print('Fit', kind, '+'.join(groups), flush=True)
            result = train_supervised(dataset, contract, rules, kind=kind, feature_groups=groups)
            predictions.append(result.predictions)
            tuning.append(result.tuning)
            interpretation.append(result.interpretation)
            summaries.extend([{'model': kind, 'feature_set': '+'.join(groups), **s} for s in result.summaries])
            fitted[kind, '+'.join(groups)] = result.fitted[30]
    predictions = pd.concat(predictions, ignore_index=True)
    predictions['experiment_version'] = 'tianhao-30m-v1'
    predictions['result_status'] = STATUS
    for split, part in dataset.groupby('split'):
        expected = set(part.loc[part.label_30m.notna(), 'event_id'])
        for _, arm in predictions.loc[predictions.split.eq(split)].groupby(['model', 'feature_set']):
            assert set(arm.event_id) == expected and arm.event_id.is_unique
    predictions.to_parquet(out / 'predictions.parquet', index=False)
    pd.concat(tuning, ignore_index=True).to_csv(out / 'tuning.csv', index=False)
    trend_tuning.to_csv(out / 'trend_rule_tuning.csv', index=False)
    pd.concat(interpretation, ignore_index=True).to_csv(out / 'interpretation.csv', index=False)
    (out / 'model_summaries.json').write_text(json.dumps(summaries, indent=2), encoding='utf-8')
    joblib.dump(fitted, out / 'fitted_pipelines.joblib')
    wide = metrics_and_errors(predictions, audit, out)
    manifest.update(status=STATUS, created_at_utc=datetime.now(timezone.utc).isoformat(), software={'python': platform.python_version(), 'pandas': pd.__version__, 'numpy': np.__version__, 'scikit_learn': sklearn.__version__}, sources={'traffic_whole_zip_sha256': sha(BASE / 'sources/traffic_prepared.zip'), 'weather_archives': 90, 'holiday_manifest_sha256': sha(PREP / 'holiday_source_manifest.json')}, tests='See verification files alongside the notebook; do not infer approval from test success', predictions_rows=len(predictions), test_event_rows=int(((dataset.split == 'test') & dataset.label_30m.notna()).sum()), outputs={p.name: sha(p) for p in out.iterdir() if p.is_file()})
    git_binary = os.environ.get('GIT_BINARY', 'git')
    manifest['repository'] = {'commit': subprocess.check_output([git_binary, '-C', str(REPO), 'rev-parse', 'HEAD'], text=True).strip(), 'dirty': bool(subprocess.check_output([git_binary, '-C', str(REPO), 'status', '--porcelain'], text=True).strip()), 'uv_lock_sha256': sha(REPO / 'uv.lock')}
    code_dir = out / 'code'
    code_dir.mkdir()
    for script in Path(__file__).resolve().parent.glob('*.py'):
        shutil.copy2(script, code_dir / script.name)
    manifest['experiment_code'] = {p.name: sha(p) for p in code_dir.iterdir()}
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    (BASE / 'latest_run.txt').write_text(str(out.relative_to(BASE)), encoding='utf-8')
    print('RESULTS', out, flush=True)
    print(wide.loc[wide.split.eq('test'), ['model', 'feature_set', 'macro_f1', 'balanced_accuracy', 'roc_auc', 'log_loss']].to_string(index=False), flush=True)
if __name__ == '__main__':
    main()
