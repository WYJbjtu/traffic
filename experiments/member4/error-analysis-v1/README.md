# Member 4 — error analysis on the long-window cohort

Recomputes confusion matrices and imbalance-aware metrics from the saved
`comparison-hf-v1` predictions. Nothing is re-fitted. Status: **EXPLORATORY**.

## What the ROC-AUC headline hid

The earlier headline (random forest ROC-AUC 0.704 at 30 minutes) is real but
one-sided. The three horizons have class imbalance pointing in *opposite*
directions, and the models collapse toward the majority class at the two
imbalanced horizons.

| horizon | positive share | imbalance direction |
|---|---|---|
| 15m | 20.9% | negative-heavy (≈5:1) |
| 30m | 43.7% | roughly balanced |
| 60m | 71.5% | positive-heavy (≈2.5:1) |

## The core finding

**At 15 minutes the models barely find any true positives, and at 60 minutes
they barely find any true negatives.** The balanced accuracy near 0.50 at both
ends is not a coincidence: the classifier has learned to predict the majority
class.

### 15m (negative-heavy) — recall collapses to ~0

Best tree-family model (`local+history+flow`, random forest) reaches recall
0.015: 5 true positives out of 332, with 327 positives missed. Every other
ensemble predicts *zero* positives. ROC-AUC 0.66 looks acceptable only because
the 1064 negatives dominate.

### 60m (positive-heavy) — specificity collapses to ~0

The same models predict almost everything positive. `decision_tree` and
`logistic_regression` at 60m have 0 true negatives (311 negatives all
misclassified). ROC-AUC 0.70 reflects the 1010 positives being mostly right,
while negative events are essentially ignored.

### 30m is the only horizon where the model is honest

Prevalence 43.7% and the confusion matrices are roughly symmetric (e.g. rf
`local+history+flow`: tp 403 / fp 246 / fn 226 / tn 488). This is also the only
horizon where precision and recall both stay useful.

## What this means

1. The headline "ROC-AUC 0.70" is dominated by the majority class and is not a
   fair summary of the 15m and 60m tasks.
2. `balanced_accuracy` already hinted at this (0.50–0.55 at 15m/60m) but was not
   surfaced in the earlier report.
3. Decision threshold is fixed at 0.5. At the two imbalanced horizons the
   optimal operating point is far from 0.5; threshold tuning is a concrete,
   low-cost next step before any claim about model quality.

## Reproduce

```bash
uv run --locked python experiments/member4/error_analysis.py \
  --predictions experiments/member4/comparison-hf-v1/predictions.parquet \
  --output-dir experiments/member4/error-analysis-v1
```

## Artifacts

- `metrics_all_splits.csv` — full metrics across train/validation/test.
- `test_metrics.csv` — test-split metrics including pr_auc, precision, recall, f1.
- `test_confusion.csv` — per-arm tn/fp/fn/tp.
- `pairing_audit.csv` — cross-run pairing check.
