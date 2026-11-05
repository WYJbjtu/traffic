# 96-lane integrated delivery — partial, evidence-backed (2026-11-04)

**Status: P0 PARTIAL; spatial ablation NO-GO; Proposal-aligned recovery-start NOT RUN.** This folder contains authentic **exploratory** 96-lane `recovery_confirmation_v1` results, not approved recovery-start findings. The original Proposal PDF was not found; see `docs/proposal_experiment_compliance.md`. Historical 24-lane outputs remain separate and unchanged.

## Authentic results (test, 30-minute, known labels = 7,008; unknown = 597)

| Model | A1 local Macro-F1 / ROC-AUC | A2 local + history Macro-F1 / ROC-AUC |
|---|---:|---:|
| Majority | A0: 0.4352 / 0.5000 | — |
| Speed trend | A0: 0.4410 / 0.4974 | — |
| Logistic regression | 0.4352 / 0.5250 | 0.6127 / 0.7062 |
| Decision tree | 0.6442 / 0.7424 | 0.6418 / 0.7262 |
| Random forest | 0.5888 / 0.7383 | 0.6405 / 0.7614 |
| Actual XGBoost | 0.6078 / 0.7338 | 0.6637 / 0.7692 |
| HistGradientBoosting (additional) | 0.6229 / 0.7308 | 0.6652 / 0.7685 |

These are descriptive paired *feature-set* results on identical event IDs for a given horizon, but no correlation-aware intervals or significance test was run. The validation-log-loss winner need not be the highest test-score model. Threshold 0.5 was fixed. Results are not a new blind test or Proposal-compliant start-target results. Full metrics, 15/60-minute extensions, confusion counts and censoring denominators: [`model_metrics.csv`](model_metrics.csv). The runnable model's exact hashed event-level predictions and history are under ignored `data/local/expanded96-release/model-a0-a2-v2/`. `model_tuning.csv` records all two-candidate validation searches.

## Identity and spatial gate

ZIP SHA `f5be559a6ad8df69e68fbc382fb609d13fdae40aa044c9d1fe4d7e3b2253b6b8`; 23 internal files verified; 35,782,769 five-minute bins, 30,452 events, 96 frozen lane units, **94 with events**. Train 14,290, validation 8,557, test 7,605. `dataset_verification.json` records counts; `feature_coverage_by_split.csv` is measured from the independently hashed run.

`network_construction_validation.json` confirms the local official CENTERLINE/INTERSECTION/TURN bytes against their source manifest and verifies SQLite roads/arcs counts (36,525/48,080). The graph remains a **2026 candidate**; no approved historical detector-to-arc match or human-reviewed directed relationship was supplied. All 30,452 events are listed in `spatial_event_eligibility.csv`, with zero admitted spatial model events (0 / 0 / 0 train/validation/test). These zeroes reflect the *approval gate*, not evidence that roads or neighbors do not exist. No fabricated network values, map certification or spatial model training. See `spatial_gate_decision.md`.

## Exact reproduction (from repo root, Python 3.12)

```text
uv sync --locked
uv run --locked pytest -q
uv run --locked python -m pytest -q
gh release download data-expanded-96-2023-2026-v1 --pattern 'HK_Traffic_Expanded_96_Prepared_Data_v1.zip*' --dir data/local/expanded96-release
```

Verify the ZIP digest printed by `sha256sum` (or use `hashlib.file_digest` on Windows), then extract its `processed/events.parquet`, `processed/cohort_bins.parquet` and `metadata/detectors.csv` into `data/local/expanded96-release/prepared-v1/` retaining ZIP paths. The report command independently verifies the full ZIP and **all** internal members, both extracted Parquet hashes and all three official network source hashes before writing. Network inputs must be placed at the source paths referenced by its existing `data/local/network-full/v1/manifest.json`; if those original artifacts are unavailable, network validation remains blocked rather than silently substituting another file.

```text
uv run --locked python -m traffic_recovery.models.expanded96 --events data/local/expanded96-release/prepared-v1/processed/events.parquet --bins data/local/expanded96-release/prepared-v1/processed/cohort_bins.parquet --output data/local/expanded96-release/model-a0-a2-NEW
uv run --locked python scripts/report_expanded96_delivery.py --archive data/local/expanded96-release/HK_Traffic_Expanded_96_Prepared_Data_v1.zip --prepared data/local/expanded96-release/prepared-v1 --run data/local/expanded96-release/model-a0-a2-NEW --network data/local/network-full/v1 --out reports/local/expanded96-NEW
```

Use fresh directories; never overwrite a published run. Compare hashes and metrics with this delivery. The script checks input hashes, IDs, split counts, prediction-time watermark, bin availability and outputs. The additional uncommitted model run is intentionally ignored; regenerate it before claiming independent replication. No flow/occupancy measurements exist in the prepared ZIP; bin `flow_slots` are **counts of observed intervals**, not volume. A3–A13 and the Proposal-start target remain explicitly not run/no-go as recorded in `experiment_matrix.csv`.
