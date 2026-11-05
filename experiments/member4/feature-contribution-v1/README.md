# Member 4 — feature-group contribution on the long-window cohort

Aggregates the random forest's feature importances from the saved
`interpretation.csv` into local / history / flow group shares, per horizon.

Status: **EXPLORATORY**.

## Result

The `history` group (15-minute pre-onset speed trend) is the single largest
contributor to the random forest at every horizon, ahead of both `local` and
`flow`. This backs the ROC-AUC lift observed when `history` was added in the
earlier run — the model is not picking it up by accident.

| horizon | local | history | flow |
|---|---|---|---|
| 15m | 33.9% | 38.3% | 27.8% |
| 30m | 35.8% | 40.8% | 23.4% |
| 60m | 33.0% | 42.8% | 24.2% |

Two features contribute nothing to the random forest across all horizons:
`onset_observed_minutes` and `speed_trend_observed_bins`.

## Reproduce

```bash
uv run --locked python experiments/member4/feature_contribution.py \
  --interpretation experiments/member4/comparison-hf-v1/interpretation.csv \
  --output-dir experiments/member4/feature-contribution-v1
```
