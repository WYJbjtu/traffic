# Predicting Congestion Recovery in Hong Kong

<<<<<<< HEAD
DSC6004 research project, City University of Hong Kong. We study whether sampled lane-level congestion **recovery confirmation within 15, 30 or 60 minutes** can be predicted, and whether authentic as-of neighbouring-road measurements improve on local traffic and local history. Results are observational, exploratory and version-specific—not live forecasts or certified road-network relationships.
=======
Current repository: [WYJbjtu/traffic](https://github.com/WYJbjtu/traffic). Data releases and Windows byte-integrity migration are documented in [migration handoff](docs/repository_migration_20261105.md).

## Tianhao96车道重跑与可复核交付（2026-11-04）
>>>>>>> recovery/main

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

<<<<<<< HEAD
Four owners cover traffic data, network, external context and modeling respectively; all share design and scientific review. See [ownership](docs/ownership.md), [shared contract](docs/data_contract.md) and [agent guidelines](AGENTS.md). Results cannot establish citywide generalisation: sample selection, source latency, censored labels, ambiguous historical identity, sparse measured neighbours and reuse of test material remain limitations. No claim is made that the Proposal target, independently verified P3 or a live service has been delivered.
=======
**EXPLORATORY — NOT APPROVED AS FINAL RESULTS**：基于7597个暂定车道事件、6799个已知30分钟标签，14个比较臂。目标是恢复确认，与proposal恢复开始仍有差异；空间实验未完成。不包含大型原始数据、模型文件或缓存。

## 96-lane expansion execution handoff (November 2, 2026)

The completed [96-lane data access and Chinese handoff](docs/expanded96_data_access.md) provide 35,782,769 five-minute rows and 30,452 recovery events, plus the 426-candidate longitudinal quality report. Download the independent [96-lane Release](https://github.com/WYJbjtu/traffic/releases/tag/data-expanded-96-2023-2026-v1). The older 24-lane / 7,597-event release remains separate. The original data audit passed 178 local tests; this is a historical run count, not the current repository CI result. No models were trained by the data audit.

## Long-window data handoff (2023–September 2026)

The [long-window data handoff](docs/long_window_data.md) covers 1,369 days, 24 selected lane units and 7,597 provisional recovery events. This is separate from the **73-event October 2026 short pilot** below. Use `configs/long_window.json` and a separate data root; do not mix their event tables or fitted references. See [data access and prepared-package instructions](docs/long_window_data_access.md). Large datasets are not committed to Git. Download the **[prepared dataset (~1.67 GB)](https://github.com/WYJbjtu/traffic/releases/tag/data-long-window-2023-2026-v1)** from Releases; the release includes usage instructions and SHA-256 verification.

## October 30 short-window pilot handoff

The [selected-detector data pilot](docs/selected_data_pilot.md) adds portable
download/preparation commands and measured coverage/event summaries from 15 real
archive dates. It produced 73 provisional lane-event rows (55 train, 5 validation,
13 test) after unchanged coverage/label rules. This small convenience cohort is
not the final research dataset. No model results, external integration or spatial
approval are included in this handoff; raw/derived data remain local.

Four-member MSc Data Science project: predict recovery **within 15, 30 and 60
minutes**, and test whether neighboring-road conditions improve on local-only
features. Core experiments: **November 4, 2026**; poster: **November 6–7**.
Reproducible, authentic evidence takes priority over complexity.

## Local event explorer — first vertical slice

A read-only FastAPI + DuckDB API and React/TypeScript/Vite + MapLibre/ECharts
frontend can browse **real, provisional medium-pilot events** when the local
checksummed Parquet evidence is present. This is a local development prototype,
not a deployment, final research dataset, live traffic feed or trained model.
It deliberately shows **prediction unavailable** and does not show unverified
upstream/downstream relationships. Shared API/task contracts and parallel work:
[team handoff](docs/team_tasks/README.md).

From the repository root, in separate terminals:

```text
uv sync --locked
uv run --locked uvicorn traffic_recovery.api.app:app --host 127.0.0.1 --port 8000
npm ci --prefix frontend
npm run dev --prefix frontend -- --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173`. Vite proxies `/api` to the local backend. The API
requires `data/local/pilot/medium-40/medium_events.parquet`, three corresponding
`bins-*.parquet`, `reports/medium_pilot/statistics.json` and
`data/sample/verified/detectors.csv` with checksum manifest. These inputs are
verified at each request; missing or changed files return **503**, never synthetic
fallbacks. Reproduce missing local data using [medium_pilot.md](docs/medium_pilot.md)
and [pilot_memory_verification.md](docs/pilot_memory_verification.md). Event outcomes
and curves include future observations and must never be treated as model features.
The map uses external OpenStreetMap raster tiles (network and tile-provider policy
apply); current detector coordinates and their datum/historical validity remain
unverified. If tiles/WebGL fail, coordinates and event details still display.

```text
uv run --locked pytest
npm run build --prefix frontend
```

Do not expose the development servers publicly or deploy them; no authentication,
production hardening or prediction-serving registry exists. See the handoff for
API schemas, known risks and next steps. Six spatial candidates remain pending
human review: [review packets](reports/spatial_pair_review/README.md).

## Milestone 2 — provisional coverage/event/spatial pilot

The pilot implementation adds incremental Parquet ingestion, historical-only
cohort/reference selection, censored 15/30/60-minute **within-horizon** labels,
threshold sensitivity, real-event curves and a small source-topology matching pilot.
The full pipeline was interrupted before completion; these are implemented capabilities,
not verified full-pilot results. The [memory investigation](docs/pilot_memory_verification.md)
records a successful limited real-data coverage benchmark and safe resumption.
No approved real-cohort ML result or dashboard result exists. Definitions and
[contract v0.2](docs/data_contract.md) remain pending team review.

Large raw and derived data stay ignored in `data/local/pilot/`. The intended event
output is `data/local/pilot/derived/events.parquet`, which has **not yet been produced**.
Reports/figures are intended for `reports/milestone2/` after a validated full run.

```text
uv sync --locked
uv run --locked python -m traffic_recovery.data.pilot_ingest --start 2026-10-07 --end 2026-10-21
uv run --locked python -m traffic_recovery.data.pilot
uv run --locked python -m traffic_recovery.network.pilot --acquire
uv run --locked python scripts/verify_pilot.py
uv run --locked pytest
```

Do not restart the full multi-day pipeline before reviewing the bounded-memory
benchmark and constraints in [pilot_memory_verification.md](docs/pilot_memory_verification.md).
The ingestion command acquires **15 archive dates** to cover 14 complete HKT
observation days plus boundary records. Existing milestone-1 ZIPs are checksum-
verified and reused automatically. Others use the official API with preserved
HTTP evidence. Allow tens of minutes; XML is never bulk-extracted. `--acquire`
fetches official TURN/INTERSECTION files and CENTERLINE if not already available
(the latter is ~484 MB). Each module supports `--help` and portable `Path` options.
To resume after interruption, rerun the identical pilot command in the foreground.
Daily coverage checkpoints are fingerprinted and checksum-verified. The optional
`--reuse-coverage` also verifies the aggregate coverage manifest and all daily
checkpoints; it still rebuilds historical references and labels.

**Important:** 90/95% coverage of sparse 5m bins is not continuous 30s coverage.
Bins close at end +10m and require two positive-flow valid slots; a lane-based
pilot is not road-segment ground truth. No spatial match or upstream/downstream
pair is certified from proximity. Inspect the reports before using any labels.

## Milestone 1 — historical verification

Architecture, provisional contracts and a **real official-data feasibility audit**
are implemented. No events/labels, ML training, dashboard or deployment yet.

On October 27, 2026, the audit retrieved and parsed all **3,121** raw traffic
snapshots archived October 19–21: **12,935,754 source lane-period rows**, **782
detectors**, **6,064 conflicting rows quarantined**. Coverage is not continuous:
**28.67%** of expected per-series slots between observed bounds are absent;
archive capture lags observations by **5–8 minutes**. These are quality findings,
not model metrics. Read [the audit](docs/data_audit.md) before designing labels.

## Environment and offline verification

Use Python **3.12** and [uv](https://docs.astral.sh/uv/getting-started/installation/).
From the repository root, in WSL2 Ubuntu or native Windows PowerShell:

```text
uv sync --locked
uv run --locked python --version
uv run --locked pytest
uv run --locked traffic-audit --help
```

Commands are intentionally single-line and shell-independent. `tzdata` is locked
for systems without an OS timezone database. Python uses `pathlib.Path`, UTF-8
and aware Asia/Hong_Kong times. Milestone 2 adds PyArrow (Parquet), Matplotlib
(offline figures) and Shapely (metre geometry/topology) to pandas/tzdata; pytest
is a development dependency. Stages 5–6 use scikit-learn for leakage-safe
logistic-regression and decision-tree experiments. No GeoPandas, NetworkX, API
keys, database or Docker is required.

## Reproduce a small live audit first

**These commands make live requests** and download authentic public government
records. Choose a past inclusive archive date range; yesterday is the documented
latest archive date. Example dates are verified, not fixed inside the pipeline.
Use new output/report names for new runs to avoid replacing recorded findings.

```text
uv run --locked traffic-audit --start 2026-10-19 --end 2026-10-21 --snapshots-per-day 3 --output data/local/smoke-audit --report reports/local/smoke-audit.json
```

This lists versions for each day and parses three selected snapshots per day,
not a continuity audit. It also retrieves catalogues, specifications, CSV metadata,
current raw/processed snapshots and broad historical inventory counts. Empty,
unexpected or incomplete responses fail explicitly; successful HTTP alone does
not imply valid data. Broad timestamp arrays may be truncated and are never used
as a complete acquisition list.

## Reproduce the measured three-day audit

```text
uv run --locked traffic-audit --start 2026-10-19 --end 2026-10-21 --daily --network --output data/local/audit-20261019-21 --report reports/local/reproduced-audit.json
```

`--daily` downloads all three daily raw ZIPs (~111 MB compressed / 2.2 GB XML)
and streams their 3,121 XML members. `--network` adds the **484 MB CENTERLINE
GML** download and a schema/identifier audit, **not spatial matching**. Omit
`--network` to avoid that resource. Allow several minutes for full parsing.
Date ranges are limited to 31 days per run to discourage accidental bulk jobs.

Add `--reuse` to an identical later run to use successful responses only after
URL and SHA-256 verification. Existing originals otherwise cause an explicit
refusal to overwrite. Use a fresh directory to fetch a fresh current snapshot.
Network failures preserve error evidence and yield nonzero exits; partial-stage
failures appear in JSON, never substituted with synthetic records.

The output directory contains unchanged response bodies, `.meta.json` response
metadata, per-attempt metadata/error bodies, `requests.jsonl`, archive listings,
original `sample_YYYYMMDD.xml` files and `cleaned_sample.csv` (**first snapshot
of each day only**). JSON includes aggregate quality, coverage, lag, storage,
conflict examples, errors and response provenance. ZIPs are read without extracting
unsafe URL-shaped directory paths.

### Boundary probes and sample profile

```text
uv run --locked python scripts/probe_archive.py --source raw --time 20210329-0908 --time 20261026-2359 --output data/local/raw-boundary-probe --report reports/local/raw-boundaries.json
uv run --locked python scripts/probe_archive.py --source segment --time 20210330-0909 --output data/local/segment-boundary-probe --report reports/local/segment-boundary.json
uv run --locked python scripts/profile_sample.py --sample data/sample/verified/cleaned_sample.csv.gz --detectors data/sample/verified/detectors.csv --report reports/local/sample-profile.json
```

The first probe deliberately returns exit **1** because the earliest listed raw
file has empty detector lists; the recent version parses. The earliest processed
file parses 63 rows, but **all are offline**, so cleaned speeds are all missing.
Recorded evidence: `reports/evidence/history_boundaries.json`.
The profile describes only the supplied sample, not the full audited period.

## Collaboration and layout

```text
src/traffic_recovery/
  data/        Member 1: acquisition, coverage, provisional events/labels
  network/     Member 2: source topology/matching pilot; certified features pending
  external/    Prediction-time-safe context adapters; real-source handoff pending
  models/      Contract, dataset, baselines, supervised models and ablation runner
tests/         Offline tests; labeled synthetic fixtures + real samples
configs/       Configuration/range policy; no finalized event thresholds
scripts/       Archive-boundary and exported-sample inspection CLIs
docs/          Contracts, ownership, sources, audit and verification
reports/       Portable measured audit JSON and request evidence
figures/       Figure policy; pilot plots live in reports/milestone2/
data/sample/verified/  Small authentic source samples + cleaned export
data/local/           Ignored large evidence stores
```

- [Agent instructions](AGENTS.md) apply to Codex, Pi and contributors.
- [Ownership and handoffs](docs/ownership.md): four independent modules.
- [Initial shared contracts](docs/data_contract.md): keys, units, availability
  and provisional labels; recovery **within** versus **at** a horizon.
- [Official sources](docs/data_sources.md) and [feasibility findings](docs/data_audit.md).
- [Actual verification outcomes](docs/verification.md).
- [External/modeling progress report](docs/external_modeling_progress_report.md):
  implemented files, reproduction steps, validation status and remaining gates.

Use feature branches and reviewed PRs. Coordinate shared interfaces; test before
requesting merge. Never commit secrets, large raw/processed datasets or models.
Small authentic evidence is deliberately curated and checksummed. Synthetic
fixtures are explicitly labeled and never represented as research observations.

## After the pilot (not yet validated)

Review the measured censoring/sensitivity and sparse-bin interpretation; approve
prediction unit, reference/availability rules and event-separated temporal splits.
Manually verify detector matches and reconcile network versions before any spatial
ablation. See the milestone-2 recommendation before authorizing a local baseline.
Optional context features still require separate source verification.

## Tianhao / Fairy-6b exploratory long-window experiment

The [canonical executed 96-lane results notebook](notebooks/Tianhao_新版96车道_完整重跑_20261104.ipynb)
and [reproduction guide](experiments/tianhao/README.md) add real 30-minute
logistic/tree experiments, official calendar/weather integration and small,
checksummed prediction/metric artifacts. These are exploratory results with
provisional confirmation labels; scientific approval and spatial inputs remain pending.
>>>>>>> recovery/main
