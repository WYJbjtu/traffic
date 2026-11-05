"""Produce a reproducible, offline joint comparison from both saved real runs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys

import numpy as np
import pandas as pd
import sklearn

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from traffic_recovery.models.saved_comparison import ARM, compare_saved_runs

SOURCES = {
    'tianhao': ('experiments/tianhao/rerun_20261101', 'metrics_summary.csv'),
    'member4': ('experiments/member4/comparison-hf-v1', 'metrics.csv'),
}


def sha(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def build(root: Path, output: Path) -> dict[str, object]:
    """Refuse overwrite, verify pairing, recompute all splits, reconcile old metrics."""
    if output.exists():
        raise FileExistsError(f'Refusing to overwrite comparison: {output}')
    frames = {name: pd.read_parquet(root / folder / 'predictions.parquet')
              for name, (folder, _) in SOURCES.items()}
    metrics, confusion, pairs = compare_saved_runs(frames)
    reconciliation = []
    for name, (folder, filename) in SOURCES.items():
        saved = pd.read_csv(root / folder / filename)
        if name == 'tianhao':
            saved['horizon_min'] = 30
            saved = saved.melt(id_vars=ARM, var_name='metric_name', value_name='saved_value')
        else:
            saved = saved.rename(columns={'metric_value': 'saved_value'})
        saved = saved.set_index([*ARM, 'metric_name'])
        part = metrics.loc[metrics.experiment.eq(name)]
        names = ['accuracy', 'precision', 'recall', 'f1', 'macro_f1', 'balanced_accuracy',
                 'roc_auc', 'pr_auc', 'brier_score', 'log_loss']
        for row in part.to_dict('records'):
            for metric in names:
                key = tuple(row[column] for column in ARM) + (metric,)
                exists = key in saved.index
                old = saved.at[key, 'saved_value'] if exists else np.nan
                if exists and not np.isclose(old, row[metric], rtol=1e-9, atol=1e-12, equal_nan=True):
                    raise ValueError(f'Recomputed metric disagrees with source: {name}/{key}')
                reconciliation.append({'experiment': name, **{column: row[column] for column in ARM},
                                       'metric_name': metric, 'recomputed_value': row[metric],
                                       'saved_value': old,
                                       'status': 'matched_saved_metric' if exists else 'new_from_saved_predictions'})
    common_features = ['local', 'local+history', 'local+history+flow']
    test = metrics.loc[metrics.horizon_min.eq(30) & metrics.split.eq('test')]
    common = test.loc[test.feature_set.isin(common_features) & test.model.isin(
        ['logistic_regression', 'decision_tree', 'random_forest', 'hist_gradient_boosting'])]
    external = test.loc[test.experiment.eq('tianhao') & test.model.isin(['logistic_regression', 'decision_tree'])]
    output.mkdir(parents=True)
    tables = {'all_metrics.csv': metrics, 'confusion_matrices.csv': confusion,
              'pairing_audit.csv': pairs, 'common_30m_test.csv': common,
              'tianhao_external_30m_test.csv': external,
              'metric_reconciliation.csv': pd.DataFrame(reconciliation)}
    for name, table in tables.items():
        table.to_csv(output / name, index=False)
    lines = ['# 双方已保存预测的统一比较（2026-11-02）', '',
             '**EXPLORATORY — NOT APPROVED AS FINAL RESULTS**', '',
             '本次只重算已保存的预测，没有训练、选参、改标签或重新挑选展示模型；测试集此前已被查看。',
             '所有输出保留 experiment、model、feature_set、horizon_min、split，不跨时限/特征组混排。', '',
             f'- 共 {len(metrics)} 个实验臂/时限/split汇总，混淆矩阵逐行保存。',
             f'- {len(pairs)} 个双方同名实验臂的事件、标签和预测时间全部对齐。',
             f'- 新补算 {sum(r["status"] == "new_from_saved_predictions" for r in reconciliation)} 个指标；其他现有指标均重算一致。', '',
             '## 同一local+history+flow特征、30分钟、test（Member4四模型）', '',
             '| 模型 | n | Macro-F1 | Balanced accuracy | ROC-AUC | TN / FP / FN / TP |',
             '|---|---:|---:|---:|---:|---|']
    selected = common.loc[common.experiment.eq('member4') & common.feature_set.eq('local+history+flow')]
    for row in selected.to_dict('records'):
        cm = confusion.loc[confusion.experiment.eq('member4') & confusion.horizon_min.eq(30)
                           & confusion.split.eq('test') & confusion.feature_set.eq(row['feature_set'])
                           & confusion.model.eq(row['model'])].iloc[0]
        lines.append(f"| {row['model']} | {row['n_rows']} | {row['macro_f1']:.4f} | {row['balanced_accuracy']:.4f} | {row['roc_auc']:.4f} | {cm.tn} / {cm.fp} / {cm.fn} / {cm.tp} |")
    lines += ['', '## 使用与边界', '',
              '- `common_30m_test.csv`保留双方相同三组特征的行，重复来源不会合并成新样本。',
              '- `tianhao_external_30m_test.csv`单列日历/天气消融；Member4尚无对应外部特征模型，不能据此宣称四模型外部因素比较已完成。',
              '- `all_metrics.csv`包含各时限和split，train成绩是样本内描述，不能当作泛化结果。',
              '- `n_censored`为原预测表记录的split计数，不是从只含已知标签的预测表重新推断；未知标签不计入评估分母。',
              '- PR-AUC沿用共享评估定义，即average precision。规则分数的Brier/log loss保持空值。',
              '- 当前任务仍是恢复确认，未解决proposal恢复开始定义与经验证邻路特征问题。', '',
              '复现：`uv run --locked python experiments/tianhao/compare_saved_runs.py --output-dir reports/local/unified-comparison-new`。']
    (output / 'README.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    inputs = {}
    for folder, filename in SOURCES.values():
        for name in ['predictions.parquet', filename]:
            path = root / folder / name
            inputs[path.relative_to(root).as_posix()] = sha(path)
    manifest = {'version': 'saved-prediction-comparison-v1', 'scientific_approval': 'pending_team_review',
                'input_sha256': inputs, 'output_sha256': {p.name: sha(p) for p in output.iterdir() if p.is_file()},
                'metric_groups': len(metrics), 'paired_groups': len(pairs),
                'metric_reconciliation': pd.Series([r['status'] for r in reconciliation]).value_counts().to_dict(),
                'code_sha256': {name: sha(root / name) for name in [
                    'experiments/tianhao/compare_saved_runs.py', 'src/traffic_recovery/models/saved_comparison.py',
                    'src/traffic_recovery/models/evaluation.py']},
                'software': {'python': platform.python_version(), 'pandas': pd.__version__, 'sklearn': sklearn.__version__}}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(ROOT, args.output_dir), indent=2))
