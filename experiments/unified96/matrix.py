"""Versioned four-model/eight-arm runner; checkpoints F3/F7 before extra arms.

Uses the frozen two-candidate budget, train-only imputer/scaler/model fitting,
validation minimum log loss, no refit and threshold 0.5. All 32 arms are refitted;
old F0/F4 results remain immutable. Inputs/output paths are repository-relative.
"""
from __future__ import annotations

import json
import logging
import platform
import subprocess
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
import sklearn
import xgboost
from sklearn.metrics import log_loss
from threadpoolctl import threadpool_limits

from experiments.unified96.context import C, W, authenticate_bundle, join_context
from experiments.unified96.run import (ROOT, EVENTS, L, H, Q, S, ARMS, MODELS, SPLITS,
                                       load, event_hash)
from traffic_recovery.data.http import sha256_file
from traffic_recovery.models.expanded96 import candidate_models, metrics

LOG = logging.getLogger(__name__)
DATASET = 'expanded96-long-window-v1'


def dump(path: Path, value: object) -> None:
    """Write strict UTF-8 JSON; non-finite values are errors, not silent NaNs."""
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')


def fit_arm(data: pd.DataFrame, columns: list[str], arm: str, experiment_id: str,
            models: tuple[str, ...] = MODELS) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[dict]]:
    """Fit only train rows; return validation/test predictions, metrics, tuning, fit audit.

    No dropna, no event reselection. Entirely missing numeric columns use the
    inherited sklearn imputer policy; other missing values use training means.
    All preprocessing stays inside each fitted pipeline.
    """
    if len(columns) != len(set(columns)) or not set(columns).issubset(data):
        raise ValueError('Missing or duplicate feature columns')
    train, validation = (data.loc[data.split.eq(s)] for s in SPLITS[:2])
    rows, predictions, tuning, fit_audit = [], [], [], []
    for name in models:
        contenders = candidate_models()[name]
        losses = []
        with threadpool_limits(limits=2):
            for idx, model in enumerate(contenders):
                model.fit(train[columns].to_numpy(dtype=float), train.label.to_numpy(dtype=int))
                p = model.predict_proba(validation[columns].to_numpy(dtype=float))[:, 1]
                loss = float(log_loss(validation.label.to_numpy(dtype=int), np.clip(p, 1e-7, 1-1e-7)))
                losses.append(loss)
                tuning.append({'feature_arm': arm, 'model': name, 'candidate': idx,
                               'validation_log_loss': loss})
            choice = int(np.argmin(losses))
            selected = contenders[choice]
            for split in SPLITS[1:]:
                frame = data.loc[data.split.eq(split)]
                y = frame.label.to_numpy(dtype=int)
                p = selected.predict_proba(frame[columns].to_numpy(dtype=float))[:, 1]
                if not np.isfinite(p).all() or not ((p >= 0) & (p <= 1)).all():
                    raise ValueError('Invalid model probabilities')
                pred = (p >= .5).astype(int)
                identity = {'experiment_id': experiment_id, 'dataset_version': DATASET,
                    'population': 'INFERRED_EXPLORATORY', 'target_version': 'recovery_confirmation_v1',
                    'horizon_min': 30, 'model': name, 'feature_arm': arm, 'split': split, 'threshold': .5}
                rows.append({**identity, 'n_events': len(y), 'n_positive': int(y.sum()),
                    'n_negative': int(len(y)-y.sum()), 'event_ids_sha256': event_hash(frame.event_id),
                    'selected_candidate': choice, **metrics(y, p, pred)})
                predictions.append(pd.DataFrame({**identity, 'event_id': frame.event_id.to_numpy(),
                    'prediction_time': frame.prediction_time.to_numpy(),
                    'detector_id': frame.detector_id.to_numpy(), 'y_true': y, 'y_score': p, 'y_pred': pred}))
        # Store actual fitted preprocessing, along with full candidate estimator parameters.
        imputer = selected.steps[0][1]
        fit_audit.append({'model': name, 'feature_arm': arm, 'selected_candidate': choice,
            'fit_split': 'train', 'fit_event_ids_sha256': event_hash(train.event_id),
            'feature_columns': columns,
            'imputer_statistics': [None if np.isnan(x) else float(x) for x in imputer.statistics_],
            'imputer_indicator_columns': imputer.indicator_.features_.tolist(),
            'scaler_n_samples_seen': int(selected.named_steps['standardscaler'].n_samples_seen_) if 'standardscaler' in selected.named_steps else None,
            'candidates': [json.loads(json.dumps(m.steps[-1][1].get_params(), default=str), parse_constant=str) for m in contenders]})
        LOG.info('arm_complete model=%s feature_arm=%s selected=%d validation_log_loss=%.8f', name, arm, choice, losses[choice])
    return pd.concat(predictions, ignore_index=True), pd.DataFrame(rows), pd.DataFrame(tuning), fit_audit


def run_matrix(output: Path, bundle: Path, arms: list[str], *, root: Path = ROOT) -> None:
    """Authenticate producer and Release, assert frozen P1 IDs, then train fresh arms.

    Refuses any existing output directory. Per-arm checkpoints are independently
    usable if an optional later arm fails; manifest status is COMPLETE only last.
    """
    if output.exists():
        raise FileExistsError(f'Refusing overwrite: {output}')
    if len(arms) != len(set(arms)) or not set(arms).issubset(ARMS):
        raise ValueError('Unknown or duplicate feature arms')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    started = perf_counter()
    receipt = authenticate_bundle(bundle, root/EVENTS, root)
    data, inputs = load(root)
    frozen = json.loads((root/'experiments/unified96/runs/p1-f0-f4-v1/manifest.json').read_text(encoding='utf-8'))
    if {s: event_hash(data.loc[data.split.eq(s), 'event_id']) for s in SPLITS} != frozen['split_event_ids_sha256']:
        raise ValueError('New matrix differs from frozen P1 event population')
    calendar = pd.read_parquet(bundle/'prepared/inputs/calendar_event_features.parquet')
    weather = pd.read_parquet(bundle/'prepared/inputs/weather_event_features.parquet')
    data = join_context(data, calendar, weather)
    groups = {'L': L, 'H': H, 'Q': Q, 'C': C, 'W': W, 'S': S}
    flat = sum(groups.values(), [])
    if len(flat) != len(set(flat)):
        raise ValueError('Feature groups overlap')
    for name in ['manifest.json', 'prepared/manifest.json', 'prepared/contract.json',
                 'prepared/inputs/calendar_event_features.parquet', 'prepared/inputs/weather_event_features.parquet']:
        inputs[str((bundle/name).resolve().relative_to(root))] = sha256_file(bundle/name)
    output.mkdir(parents=True)
    experiment_id = output.name
    data[['event_id', 'prediction_time', 'detector_id', 'direction', 'lane_id', 'split', 'label']].to_parquet(output/'event_population.parquet', index=False)
    # Authenticated prepared matrix retained locally, no hidden row dropping.
    data.to_parquet(output/'model_input.parquet', index=False)
    manifest = {'status': 'RUNNING_RETROSPECTIVE_EXPLORATORY', 'experiment_id': experiment_id,
        'dataset_version': DATASET, 'target': 'recovery_confirmation_v1', 'horizon_min': 30,
        'population': 'INFERRED_EXPLORATORY', 'inputs_sha256': inputs,
        'split_counts': {s: int(data.split.eq(s).sum()) for s in SPLITS},
        'split_event_ids_sha256': {s: event_hash(data.loc[data.split.eq(s), 'event_id']) for s in SPLITS},
        'feature_groups': groups, 'arms': {k: ARMS[k] for k in arms}, 'execution_order': arms,
        'cw_verification': receipt, 'missing_context_by_split': {s: data.loc[data.split.eq(s), W].isna().sum().astype(int).to_dict() for s in SPLITS},
        'selection': 'two inherited candidates/model; minimum validation clipped log loss; no refit; threshold 0.5',
        'seed': 42, 'thread_limit': 2, 'f0_f4_policy': 'refitted, not reused',
        'git_start_sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
        'git_start_status': subprocess.check_output(['git', 'status', '--porcelain=v1'], cwd=root, text=True),
        'software': {'python': platform.python_version(), 'pandas': pd.__version__, 'numpy': np.__version__,
                     'sklearn': sklearn.__version__, 'xgboost': xgboost.__version__},
        'code_sha256': {p: sha256_file(root/p) for p in ['experiments/unified96/run.py', 'experiments/unified96/context.py',
            'experiments/unified96/matrix.py', 'src/traffic_recovery/models/expanded96.py', 'uv.lock']}}
    dump(output/'manifest.json', manifest)
    predictions, results, tuning, audit = [], [], [], []
    for arm in arms:
        p, m, t, a = fit_arm(data, ARMS[arm], arm, experiment_id)
        checkpoint = output/arm
        checkpoint.mkdir()
        p.to_parquet(checkpoint/'predictions.parquet', index=False)
        m.to_csv(checkpoint/'metrics.csv', index=False)
        t.to_csv(checkpoint/'tuning.csv', index=False)
        dump(checkpoint/'fit_audit.json', a)
        predictions.append(p); results.append(m); tuning.append(t); audit.extend(a)
    pd.concat(predictions, ignore_index=True).to_parquet(output/'predictions.parquet', index=False)
    pd.concat(results, ignore_index=True).to_csv(output/'metrics.csv', index=False)
    pd.concat(tuning, ignore_index=True).to_csv(output/'tuning.csv', index=False)
    dump(output/'fit_audit.json', audit)
    manifest.update(status='COMPLETE_RETROSPECTIVE_EXPLORATORY_NOT_BLIND', runtime_seconds=perf_counter()-started,
        trained_arms=len(arms)*len(MODELS), outputs_sha256={str(p.relative_to(output)): sha256_file(p)
            for p in sorted(output.rglob('*')) if p.is_file() and p.name != 'manifest.json'})
    dump(output/'manifest.json', manifest)
