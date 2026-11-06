# Predicting Congestion Recovery in Hong Kong

DSC6004 research project, City University of Hong Kong. We study whether sampled lane-level congestion **recovery confirmation within 15, 30 or 60 minutes** can be predicted, and whether authentic as-of neighbouring-road measurements improve on local traffic and local history. Results are observational, exploratory and version-specific—not live forecasts or certified road-network relationships.

## Research questions and contributions

1. How does prediction change across the three within-horizon targets?
2. On *the same eligible events*, do inferred upstream/downstream conditions add information beyond local and historical conditions?

The repository contains evidence-preserving official traffic acquisition, five-minute aggregation, censored lane-event labels, temporal model comparisons, a directed **candidate** road graph, a separate inferred-network spatial ablation with negative controls, and a read-only Research Explorer. The strict independently verified historical-network experiment remains **NO-GO**; that decision does not negate the separately labelled retrospective inferred-network experiment.

## Data, coverage and target

The frozen expanded release covers **96 lane units** over 2023–2026, **35,782,769 five-minute records** and **30,452 events** (94 lanes with events). These are published release checks, not statistics regenerated in this checkout: [release and provenance](docs/expanded96_data_access.md), [dataset verification](reports/nov04_integrated_delivery/dataset_verification.json). Original source bytes, metadata, SHA-256 and availability times must be preserved; large datasets belong in ignored `data/local/`. The historical **24-lane / 7,597-event** long-window study and the October 2026 small pilots are different cohorts, not pooled comparison groups ([long-window handoff](docs/long_window_data.md)).

The published 96-lane target, `recovery_confirmation_v1` (`lane-observed-confirmation-v1` in event data), records a witnessed sustained recovery confirmation, not necessarily the first recovery observation. Two consecutive low usable five-minute bins confirm onset; three consecutive high usable bins confirm recovery. Prediction time includes a conservative archive-availability delay; follow-up gaps yield unknown, not negative labels. A positive within a horizon is not a positive *at its endpoint*. Thresholds, purging and censoring are versioned in the [data contract](docs/data_contract.md) and [target review](reports/nov04_integrated_delivery/target_definition_review.md). The Proposal's `recovery_start_sustained_v1` is **not implemented or evaluated**; no current metric belongs to that target.

## Method and saved results

Temporal splits, event-level pairing, prediction-time availability, training-only fits and fixed validation selection are documented in the [96-lane experiment report](reports/nov04_integrated_delivery/README.md). The saved local/history comparisons include majority and speed-trend baselines, logistic regression, decision tree, random forest, XGBoost and HistGradientBoosting; a [separate verified 96-lane run](experiments/tianhao/expanded96_20261104/README.md) includes logistic L1 and SVM. These runs have distinct arms and provenance: do not rank their test scores as though they came from one search. Full per-horizon metrics and counts remain in the linked CSVs.

| Exploratory 30-minute test comparison | Events | ROC-AUC | Macro-F1 | Evidence |
|---|---:|---:|---:|---|
| Expanded96 A1 local XGBoost | 7,008 | 0.7338 | 0.6078 | [frozen model metrics](reports/nov04_integrated_delivery/model_metrics.csv) |
| Expanded96 A2 local + history XGBoost | 7,008 | 0.7692 | 0.6637 | [same report](reports/nov04_integrated_delivery/README.md) |
| Inferred P1, refitted M0 RF | 3,933 | 0.7250 | — | [paired spatial report](reports/spatial96_inferred_v2/research_summary_zh.md) |
| Inferred P1, M1 directed RF | 3,933 | 0.7523 | — | [paired metrics](reports/spatial96_inferred_v2/paired_spatial_metrics.csv) |

P1's RF ROC-AUC difference is **+0.0273** on the paired P1 test subset, *not* relative to the full-cohort A1/A2 above. P2 is a smaller, different inferred subset (191 test events); P3 has zero independently approved links and **no formal spatial-model result**. The P1 permutation control retains substantial signal; no cluster-aware interval, causal effect, historical-road validation or deployment claim follows from these point estimates. Official 2026 CENTERLINE / INTERSECTION / TURN geometry and EPSG:2326 distances are genuine; inferred graph transitions and detector matches are **not** official certified relationships. Missing neighbouring speed is missing, not zero. See [method and negative controls](reports/spatial96_inferred_v2/network_methodology.md) and [strict spatial gate](reports/nov04_integrated_delivery/spatial_gate_decision.md).

## New retrospective P1 comparison (local research branch)

An additional authenticated event-level analysis compares **F0 = Local + History + Observation Quality** against **F4 = F0 + inferred spatial S1–S4**, on 3,933 identical P1 test events using logistic regression, random forest, XGBoost and HistGradientBoosting. XGBoost ROC-AUC changed from 0.7290 to 0.7612 (paired detector-bootstrap 95% percentile interval for the difference: 0.0091–0.0538). This does **not** control for calendar or weather: their original authenticated event-level inputs are unavailable locally. F3/F7 and the original Proposal recovery-start target were **not run**. The previously examined test set makes this retrospective, not new blind validation. [Full run, hashes, limits and figures](reports/final_research/README.md); [feature audit](experiments/unified96/feature_audit.md).

## Research Explorer

The single launch entry is `apps/research_explorer.py`; the six evidence-backed views are Overview, Road Network, Event Explorer, Spatial Features, Model Comparison and Research Methodology. The UI implementation is `traffic_recovery.research_explorer96`, and authenticated read-only data adapters are in `traffic_recovery.research96`. Published metrics are available from tracked reports; full event curves, road tiles and inferred paths require separately obtained, checksum-verified local files. Missing evidence is reported rather than synthesized. The historical 24-lane visualization adapter remains for research reproduction but is **not** a second application mode. [Files, launch and browser checks](docs/research_explorer_96.md).

## Install and verify

From the repository root, with Python 3.12 and `uv`:

```text
uv sync --locked
uv run --locked pytest -q
uv run --locked --with 'streamlit==1.51.0' --with 'plotly==6.3.1' streamlit run apps/research_explorer.py
```

The last command resolves optional UI dependencies (first run may need network access) and opens `http://localhost:8501`. Routine tests are offline; they do not reproduce all long-window training or constitute browser acceptance. Download and hash-check official/release inputs **only** following the relevant versioned handoff. Never overwrite frozen output directories. To reproduce the inferred experiment, follow its [prerequisites and scripts](reports/spatial96_inferred_v2/network_methodology.md); missing local input is a blocker, not a reason to substitute test data. See [documentation index](docs/README.md) for other workflows.

## Repository map and team

- `apps/`: official read-only Explorer entry; `src/traffic_recovery/`: `data/` (acquisition, quality, labels), `network/` (official sources and inferred graph), `external/` (context adapters), `models/` (dataset and evaluation), `research96.py`/`research_explorer96.py` (Explorer).
- `scripts/`, `configs/`: versioned CLI workflows and research contracts; `experiments/`, `notebooks/`: distinct reproducible model histories; `reports/`: original metrics, provenance and decisions.
- `tests/`: offline checks with explicitly synthetic fixtures and small authentic samples; `data/sample/verified/`: checksummed examples; `data/local/`: ignored private working evidence. `frontend/` and `src/traffic_recovery/api/` are retained historical local pilot prototypes, not the current Explorer entry.

Four owners cover traffic data, network, external context and modeling respectively; all share design and scientific review. See [ownership](docs/ownership.md), [shared contract](docs/data_contract.md) and [agent guidelines](AGENTS.md). Results cannot establish citywide generalisation: sample selection, source latency, censored labels, ambiguous historical identity, sparse measured neighbours and reuse of test material remain limitations. No claim is made that the Proposal target, independently verified P3 or a live service has been delivered.
