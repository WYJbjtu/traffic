# Member 4 — threshold tuning on the long-window cohort

Selects a decision threshold per (horizon, feature_set, model) arm on the
validation split (Youden's J), then applies it to the test split. The fixed
0.5 threshold from the original run is kept alongside for comparison.

Status: **EXPLORATORY**.

## Result

Tuning the threshold recovers the signal the fixed 0.5 threshold hid at the two
class-imbalanced horizons. Balanced accuracy rises across the board; the
balanced 30-minute horizon is essentially unchanged, as expected.

### 15m (negative-heavy) — recall recovered

| model | threshold | balanced_accuracy | recall | f1 |
|---|---|---|---|---|
| random_forest (local+history+flow) | 0.5 → 0.251 | 0.507 → 0.589 | 0.015 → 0.512 | 0.030 → 0.396 |
| hist_gradient_boosting (local+history+flow) | 0.5 → 0.175 | 0.511 → 0.634 | 0.030 → 0.780 | 0.057 → 0.456 |

### 60m (positive-heavy) — specificity recovered

| model | threshold | balanced_accuracy | tn (of 311 negatives) |
|---|---|---|---|
| random_forest (local+history+flow) | 0.5 → 0.734 | 0.558 → 0.637 | 50 → 191 |
| hist_gradient_boosting (local+history+flow) | 0.5 → 0.717 | 0.557 → 0.634 | 48 → 186 |

### 30m (balanced) — unchanged

random_forest (local+history+flow) balanced accuracy 0.653 → 0.652.

## Interpretation

The models had learned real signal; the fixed 0.5 threshold was suppressing it
where class prevalence is far from 50%. Threshold selection is a low-cost,
leakage-safe fix (chosen on validation, applied to test only) and should be
reported alongside ROC-AUC for any imbalanced horizon.

Full per-arm comparison: `threshold_comparison.csv`.

## Reproduce

```bash
uv run --locked python experiments/member4/threshold_tuning.py \
  --predictions experiments/member4/comparison-hf-v1/predictions.parquet \
  --output-dir experiments/member4/threshold-tuning-v1
```
