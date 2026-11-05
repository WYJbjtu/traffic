"""Measure real external-feature coverage from a checksum-verified local audit."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
CALENDAR = ['hour_sin', 'hour_cos', 'dow_sin', 'dow_cos', 'is_weekend',
            'is_public_holiday', 'is_day_before_holiday', 'is_day_after_holiday']
FEATURES = {**{name: ('calendar', [name]) for name in CALENDAR},
            'calendar_all_fields': ('calendar', CALENDAR),
            'temperature_c': ('weather', ['temperature_c']),
            'wind_speed_kmh': ('weather', ['wind_speed_kmh']),
            'weather_both_values': ('weather', ['temperature_c', 'wind_speed_kmh'])}


def sha(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def summarise_coverage(frame: pd.DataFrame) -> pd.DataFrame:
    """Keep full-cohort and known-30m-label denominators distinct, before imputation."""
    required = {'event_id', 'split', 'label_30m', *CALENDAR, 'temperature_c', 'wind_speed_kmh'}
    if required - set(frame):
        raise ValueError(f'Missing coverage columns: {sorted(required - set(frame))}')
    if frame.event_id.isna().any() or frame.event_id.duplicated().any():
        raise ValueError('Coverage needs one non-null row per event')
    if frame.split.isna().any() or not frame.split.isin(['train', 'validation', 'test', 'purged']).all():
        raise ValueError('Invalid coverage splits')
    if not frame.label_30m.dropna().isin([0, 1]).all():
        raise ValueError('Coverage labels must be binary or missing')
    rows = []
    for scope in ['all_events', 'known_label_30m']:
        eligible = frame if scope == 'all_events' else frame.loc[frame.label_30m.notna()]
        for split in ['train', 'validation', 'test', 'all']:
            part = eligible if split == 'all' else eligible.loc[eligible.split.eq(split)]
            for feature, (family, columns) in FEATURES.items():
                missing = int(part[columns].isna().any(axis=1).sum())
                rows.append({'scope': scope, 'split': split, 'family': family, 'feature': feature,
                             'n_events': len(part), 'observed': len(part) - missing, 'missing': missing,
                             'missing_rate': missing / len(part) if len(part) else None,
                             'coverage_rate': 1 - missing / len(part) if len(part) else None})
    return pd.DataFrame(rows)


def build(root: Path, audit_path: Path, output: Path) -> dict[str, object]:
    """Check the original local bytes and public summaries, then save small tables."""
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite coverage evidence: {output}')
    base = root / 'experiments/tianhao'
    original = json.loads((base / 'rerun_20261101/original_rerun_manifest.json').read_text(encoding='utf-8'))
    expected = original['outputs_sha256']['models/event_feature_audit.parquet']
    if sha(audit_path) != expected:
        raise ValueError('Event audit SHA256 differs from original real-rerun manifest')
    frame = pd.read_parquet(audit_path)
    coverage = summarise_coverage(frame)
    committed = pd.read_csv(base / 'rerun_20261101/feature_missingness.csv')
    for row in committed.itertuples():
        if row.feature not in frame:
            raise ValueError(f'Feature absent from verified audit: {row.feature}')
        part = frame.loc[frame.split.eq(row.split)]
        if len(part) != row.n or int(part[row.feature].isna().sum()) != row.missing:
            raise ValueError(f'Coverage differs from published summary: {row.split}/{row.feature}')
    cohort = pd.read_csv(base / 'rerun_20261101/cohort_summary.csv').set_index('split')
    for split, part in frame.groupby('split'):
        if len(part) != cohort.at[split, 'events'] or int(part.label_30m.notna().sum()) != cohort.at[split, 'known']:
            raise ValueError(f'Cohort mismatch: {split}')
    pred = pd.read_parquet(base / 'rerun_20261101/predictions.parquet')
    reference = pred.loc[pred.model.eq('logistic_regression') & pred.feature_set.eq('local')].set_index('event_id').sort_index()
    known = frame.loc[frame.label_30m.notna()].set_index('event_id').sort_index()
    if not reference.index.equals(known.index) or not (reference.y_true.to_numpy() == known.label_30m.to_numpy()).all():
        raise ValueError('Known-label audit cohort differs from saved predictions')
    if not reference.prediction_time.eq(known.prediction_time).all() or not reference.split.eq(known.split).all():
        raise ValueError('Known-label audit time/split differs from saved predictions')
    for kind, value in [('temperature', 'temperature_c'), ('wind', 'wind_speed_kmh')]:
        valid = frame[value].notna()
        if not (frame.loc[valid, kind + '_available_at'] <= frame.loc[valid, 'prediction_time']).all():
            raise ValueError(f'Future weather availability: {kind}')
        if not (frame.loc[valid, kind + '_observed_at'] <= frame.loc[valid, 'prediction_time']).all():
            raise ValueError(f'Future weather observation: {kind}')
        if not frame.loc[valid, kind + '_age_minutes'].between(0, 60).all():
            raise ValueError(f'Invalid observation age: {kind}')
    output.mkdir(parents=True)
    coverage.to_csv(output / 'coverage.csv', index=False)
    holidays = json.loads((base / 'results/holiday_source_manifest.json').read_text(encoding='utf-8'))
    pd.DataFrame(holidays).to_csv(output / 'holiday_sources.csv', index=False)
    conditional = json.loads((base / 'results/conditional_source_audit.json').read_text(encoding='utf-8'))
    pd.DataFrame(conditional).to_csv(output / 'conditional_source_checks.csv', index=False)
    lines = ['# 外部特征实测覆盖（原24车道队列）', '',
             '按原始、未插补特征计算。all_events包含未知标签；known_label_30m只包含30分钟已知标签。',
             '分母不等于天气源全部观测数，不代表全港或96车道覆盖。', '',
             '| 分母 | split | 特征 | 事件n | 已观测 | 缺失 | 缺失率 |',
             '|---|---|---|---:|---:|---:|---:|']
    for row in coverage.loc[coverage.feature.isin(['calendar_all_fields', 'temperature_c', 'wind_speed_kmh', 'weather_both_values'])].itertuples():
        rate = 'NA' if pd.isna(row.missing_rate) else f'{row.missing_rate:.4%}'
        lines.append(f'| {row.scope} | {row.split} | {row.feature} | {row.n_events} | {row.observed} | {row.missing} | {rate} |')
    lines += ['', '该表仅是保留来源的历史重算，本次没有重新联网查询。来源、可获取时间、未纳入因素及解释边界见 [交接说明](../../../docs/tianhao_external_data_handoff.md)。', '',
              '本地大型audit未提交。完整复现需取得manifest标识的原始audit字节；全部事件的单列缺失数量也与已提交feature_missingness.csv逐项一致。', '',
              '复现：`uv run --locked python experiments/tianhao/document_external_coverage.py --event-audit <原始event_feature_audit.parquet> --output-dir reports/local/external-coverage-new`。']
    (output / 'README.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    inputs = ['experiments/tianhao/rerun_20261101/original_rerun_manifest.json',
              'experiments/tianhao/rerun_20261101/feature_missingness.csv',
              'experiments/tianhao/rerun_20261101/cohort_summary.csv',
              'experiments/tianhao/rerun_20261101/predictions.parquet',
              'experiments/tianhao/results/holiday_source_manifest.json',
              'experiments/tianhao/results/conditional_source_audit.json']
    manifest = {'version': 'external-coverage-v1', 'scope': 'original_24_lane_events',
                'event_audit_sha256': expected, 'event_audit_committed': False,
                'input_sha256': {name: sha(root / name) for name in inputs},
                'code_sha256': sha(root / 'experiments/tianhao/document_external_coverage.py'),
                'output_sha256': {p.name: sha(p) for p in output.iterdir() if p.is_file()},
                'all_events': len(frame), 'known_label_30m_events': len(known),
                'source_time_and_saved_missingness_checks': 'passed',
                'scientific_approval': 'pending_team_review'}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--event-audit', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(ROOT, args.event_audit, args.output_dir), indent=2))
