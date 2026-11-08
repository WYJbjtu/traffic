# Reproduction and execution scope

Poster users need only this package. Researchers use the repository at `https://github.com/WYJbjtu/traffic`, local finalization branch and code hashes in the evidence manifest. Python 3.12; committed uv.lock; no extra dependencies or browser run. Execute from repository root. Commands below never upload anything. New output paths **must not exist**.

```text
uv sync --locked
uv run --locked pytest -q
uv run --locked python experiments/tianhao/calendar_weather96_20261106/verify_archive.py --extract data/local/poster-reproduction/cw
uv run --locked python data/local/poster-reproduction/cw/calendar_weather96/verify_handoff.py --events data/local/expanded96-release/prepared-v1/processed/events.parquet --repository .
uv run --locked python -m experiments.unified96.run --context data/local/poster-reproduction/cw/calendar_weather96 --out data/local/unified96/poster-reproduction-matrix-v1
uv run --locked python -m experiments.unified96.poster_analysis --run data/local/unified96/poster-reproduction-matrix-v1 --out data/local/unified96/poster-reproduction-analysis-v1
uv run --locked python -m experiments.unified96.poster_controls --run data/local/unified96/poster-reproduction-matrix-v1 --out data/local/unified96/poster-reproduction-controls-v1
uv run --locked python -m experiments.unified96.poster_handoff --run data/local/unified96/poster-reproduction-matrix-v1 --analysis data/local/unified96/poster-reproduction-analysis-v1 --controls data/local/unified96/poster-reproduction-controls-v1 --proposal data/local/poster-finalization/proposal-review-v1 --cw data/local/poster-reproduction/cw/calendar_weather96 --out deliverables/poster_handoff/reproduction-v1
```

## Required local evidence (not bundled large datasets)

- Old96 Release, extracted event/bin tables and frozen history features at the paths recorded in `evidence/main_manifest.json`. Input SHA checks are mandatory. Current release: `https://github.com/WYJbjtu/traffic/releases/tag/data-expanded-96-2023-2026-v1`.
- Authentic inferred-v2 features, lineage, geography controls, mappings and official geometry/index. These are existing ignored research artifacts; their hashes are in main/controls/figure manifests. Acquisition/graph reproduction is documented in repository `reports/spatial96_inferred_v2/network_methodology.md`; do not overwrite that frozen run.
- Proposal evidence snapshots can be recreated with `git show b60c5951702657ac44a2654cb997adb06038498a:<path>` for the source paths in `evidence/proposal/source_receipt.json`; save bytes to a new ignored evidence directory. This is a document audit, not adoption or full Proposal reconstruction. Read-only Issue #3 snapshot is in this package.
- The C/W verifier authenticates delivered features and producer records. No claim to independent complete monthly-weather download/rebuild is made.

## This delivery actually executed

Matrix `p1-cw-matrix-v2-20261108`: 32 selected fits, 64 candidate fits, 275,616 saved validation/test rows. F3/F7 were fitted first; all F0/F4 were refitted. Six selected matched-control fits (12 candidates) additionally executed. Independently recomputed ROC-AUC, AP, Macro-F1, balanced accuracy, precision, recall, Brier, clipped log loss and TN/FP/FN/TP; checked identical event/time/label populations and train-only imputer means. XGBoost float32 arithmetic causes at most about 3.3e-8 difference after float64 reload; mean losses use 1e-7 absolute audit tolerance, other metrics tighter.

1,000 paired detector-cluster and 1,000 fixed-week-block replicates per model, with seeds recorded. No retraining bootstrap. No new threshold tuning, label permutation, Proposal-target training or live service.

Training source hashes and dirty Git status at execution are preserved rather than misattributed to a later clean commit. The first partial v1 execution failed on serializing an XGBoost NaN parameter sentinel; it is not cited. Fixed serialization records that sentinel as a string; completed v2 uses unchanged candidate parameters. Source `poster_protocol.md` records this incident.

The finalization tests include isolated `autocrlf=true` Git checkout. That is not actual Windows or new remote CI. Unit tests are not evidence of rebuilding the complete traffic/meteorological archives.

## Package integrity

`07_evidence_manifest.json` hashes every payload except itself and SHA256SUMS (avoids self-reference). `SHA256SUMS` also includes the manifest. A separate ZIP receipt records archive size/SHA and actual temporary extraction, file/image/table/reference checks. For metric meaning: ROC-AUC/AP/Macro-F1/Recall higher is better; Brier/Log Loss lower is better; AP is sklearn Average Precision, not trapezoidal PR-AUC. NA is not zero. Final-results paired deltas are spatial minus its matched base; intervals apply only to test F7−F3.
