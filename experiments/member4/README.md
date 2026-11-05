# Member 4 — ensemble models on the long-window cohort

Exploratory run of the proposal's Member 4 scope (random forest + boosted trees)
on the approved long-window cohort (7,597 recovery events, 2023-01 — 2026-09).

Status: **EXPLORATORY — NOT APPROVED AS FINAL RESULTS**. Feature engineering and
model families only; no scientific conclusion is claimed.

## What this covers

The ensemble families added in PR #8 (`rf` and `hgb`) had only been verified on
synthetic data and the 73-row short pilot. This run is their first exercise on
the real long-window cohort, and it adds two past-only feature groups so the
incremental value of each group can be read off.

- `local` — speed_kmh, speed_ratio, baseline_kmh, valid_slots, onset_observed_minutes
- `history` — 15-minute pre-onset speed trend (change, mean, slope, observed bins)
- `flow` — pre-onset volume and occupancy (median per 30s slot, observed slots)

## Files

- `prepare_features.py` — builds `speed_history_features` and
  `flow_occupancy_features` from the prepared release (leakage-safe: every value
  is computed from observations at or before `prediction_time`).
- `build_dataset_hf.py` — merges the feature tables onto events and writes the
  model dataset + manifest.
- `experiment_contract_hf.json` — contract with the three feature groups and the
  2025/2026 split boundaries.
- `comparison_hf.json` — three incremental feature sets, four model families,
  reference = `local`.
- `comparison-hf-v1/` — metrics, interpretations, tuning, and report artifacts.

## Reproduce

```bash
uv run --locked python experiments/member4/prepare_features.py \
  --data-root D:/HK_Traffic_Recovery_Long_Window \
  --out-dir experiments/member4/prepared --step all

uv run --locked python experiments/member4/build_dataset_hf.py \
  --data-root D:/HK_Traffic_Recovery_Long_Window \
  --prepared experiments/member4/prepared \
  --contract experiments/member4/experiment_contract_hf.json \
  --output experiments/member4/event_features_hf.parquet \
  --manifest experiments/member4/model-dataset-manifest-hf.json

uv run --locked python -m traffic_recovery.models.comparison \
  --dataset experiments/member4/event_features_hf.parquet \
  --dataset-manifest experiments/member4/model-dataset-manifest-hf.json \
  --contract experiments/member4/experiment_contract_hf.json \
  --comparison-rules experiments/member4/comparison_hf.json \
  --output-dir experiments/member4/comparison-hf-v1
```

## Headline (test split, 30-minute horizon)

Adding `history` lifts every model; the ensemble families benefit most. On
`local + history + flow`, `random_forest` reaches ROC-AUC 0.704 and balanced
accuracy 0.653, `hist_gradient_boosting` ROC-AUC 0.696 / balanced accuracy 0.648,
versus decision tree 0.664 / 0.620 on the same features.

See `comparison-hf-v1/metrics.csv` for the full table across 15/30/60 minutes.
