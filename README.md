# Predicting Congestion Recovery in Hong Kong

DSC6004 research project, City University of Hong Kong. We study whether sampled lane-level congestion **recovery confirmation within 15, 30 or 60 minutes** can be predicted, and whether authentic as-of neighbouring-road measurements improve on local traffic and history. Results are retrospective, exploratory and version-specific—not live forecasts or certified road relationships.

Current repository: [WYJbjtu/traffic](https://github.com/WYJbjtu/traffic). Valid release links and byte-integrity migration records: [migration handoff](docs/repository_migration_20261105.md).

## Research questions and contributions

1. How does prediction change across within-horizon targets?
2. On *identical eligible events*, do inferred upstream/downstream conditions add information beyond local history, calendar and the included temperature/wind covariates?

Evidence-preserving official traffic acquisition, five-minute aggregation, censored event labels, temporal comparisons and a directed **inferred** graph support the research. The strict independently verified historical-network/P3 experiment remains **NO-GO**; this does not prevent the separately labelled retrospective P1 study.

## Data and target versions — do not mix

The frozen expanded release contains **96 lane units**, **35,782,769 five-minute records** and **30,452 events** (94 lanes with events): [data access](docs/expanded96_data_access.md), [Release](https://github.com/WYJbjtu/traffic/releases/tag/data-expanded-96-2023-2026-v1). The historical **24-lane / 7,597-event** [Release](https://github.com/WYJbjtu/traffic/releases/tag/data-long-window-2023-2026-v1) and October pilots are separate.

The old96 main target is `recovery_confirmation_v1` (`lane-observed-confirmation-v1` in event data). Two low usable five-minute bins confirm onset; three high usable bins confirm recovery. Prediction includes conservative archive latency. Gaps yield unknown, not negative labels; recovery *within* a horizon is not recovery *at* its endpoint. Sparse sampling does not prove continuous physical recovery. [Contract](docs/data_contract.md), [target review](reports/nov04_integrated_delivery/target_definition_review.md).

**Member 1's Proposal detector/direction v2 data and recovery-start labels have been implemented**, in the separate `feature/member1-proposal-aligned-data-v2` branch and [review Release](https://github.com/WYJbjtu/traffic/releases/tag/data-proposal-detector-direction-2023-2026-v2). Its model experiment is not complete and scientific adoption requires the [Issue #3 review](https://github.com/WYJbjtu/traffic/issues/3). strict10 and sampled2 are independent definitions, not replacements for old96 labels. No old confirmation score belongs to the new recovery-start target.

## Frozen experiments and current integration

- [Original 96-lane horizon experiments](reports/nov04_integrated_delivery/README.md) and [Tianhao's separate reviewed results](experiments/tianhao/expanded96_20261104/README.md) retain their own cohorts, arms and provenance.
- [PR #21 inferred spatial v2](reports/spatial96_inferred_v2/research_summary_zh.md): P1 has 3,933 paired test events; P2 is smaller and different; P3 is unapproved. Its negative controls remain historical, not calendar/weather-adjusted results.
- [Frozen unified F0/F4](reports/final_research/README.md): four-model local/history/quality versus inferred S1–S4. **No C/W adjustment in this historical run.** Its original metrics and hashes are preserved.
- [Authenticated Calendar/Weather handoff](experiments/tianhao/calendar_weather96_20261106/README.md): 30,452 rows each, official holidays, King's Park temperature/wind, provenance and frozen code. It is now available; historical reports mentioning missing inputs describe their original execution date.
- **Final local poster delivery (2026-11-08):** [offline handoff](deliverables/poster_handoff/p1-cw-final-20261108-v2/index.html), [Chinese first-read](deliverables/poster_handoff/p1-cw-final-20261108-v2/00_先读我_给Poster同学.md), [execution/verification report](reports/poster_finalization_20261108/README.md). `p1-cw-matrix-v2-20261108` completed the full 32-arm feature matrix, including C/W-adjusted comparisons, plus six matched S1 structural controls. F7−F3 test AUC gains are +0.0363 / +0.0047 / +0.0101 / +0.0159 (LR/RF/XGB/HGB); only HGB's unadjusted detector-cluster interval excludes zero. Gains and other metrics are model-dependent, not universal. The handoff freezes one current numerical source; historical reports remain unchanged. No front-end work or live service is part of this milestone.

The test period was previously examined: these are **retrospective exploratory evaluations, not new blind tests**. Official 2026 geometry is real; inferred historical connections are not independently verified. Missing neighbouring speed remains missing. Calendar and temperature/wind do not control all weather, incidents or events. Observation-slot counts are not traffic volume.

## Install and verify

Python 3.12 and `uv`, from the repository root:

```text
uv sync --locked
uv run --locked pytest -q
```

Routine tests are offline; they do not reproduce all source acquisition or model training. Preserve original bytes and SHA-256. Large inputs stay ignored in `data/local/`; all new experiments require new output directories.

## Research Explorer and repository layout

The sole current Explorer entry is `apps/research_explorer.py`; its implementation is `traffic_recovery.research_explorer96`, with authenticated read-only adapters in `research96`. [Explorer instructions](docs/research_explorer_96.md). Poster readers need neither this app nor Python.

- `src/traffic_recovery/`: `data/`, `network/`, `external/`, `models/` retain research responsibilities.
- `scripts/`, `configs/`: workflows and contracts; `experiments/`, `reports/`, `notebooks/`: versioned evidence.
- `tests/`: offline and labelled synthetic checks; `data/sample/verified/`: authentic small fixtures.
- `frontend/` and `src/traffic_recovery/api/`: preserved historical prototype, not the current research entry.

Four owners cover traffic, network, external context and modeling; all share scientific review. [Ownership](docs/ownership.md), [documentation index](docs/README.md), [agent guidelines](AGENTS.md). Citywide generalisation, causal effects, historical network certification and deployment are not established. Remote uploads are manual and require explicit authorization; this finalization performs no remote writes.
