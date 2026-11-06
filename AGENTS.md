# Project instructions (Codex and Pi)

## Purpose and scope
Predict congestion recovery **within** 15/30/60 minutes on Hong Kong roads.
RQ1 compares horizons; RQ2 compares local-only with neighboring-road features.
Authentic, traceable data and valid reproducible experiments outrank complexity.
Core experiments: **November 4, 2026**. Poster: **November 6–7, 2026**.
Outputs: audited datasets, justified event/label definitions, temporal evaluation,
spatial ablation, documented limitations, reproducible reports and poster.
Current delivery includes a frozen exploratory 96-lane confirmation-target experiment
and a separate retrospective inferred-network spatial study. The strict verified
historical-network/P3 gate is NO-GO; Proposal recovery-start is NOT RUN. Historical
24-lane results and earlier pilots are separate. No live prediction service is claimed.

## Engineering
- Python **3.12**, `uv`, `pyproject.toml` and committed `uv.lock`.
- `apps/research_explorer.py` is the sole current Explorer entry; implementation
  is `src/traffic_recovery/research_explorer96.py`, read-only adapters in
  `research96.py`. `data/`, `network/`, `external/`, `models/` retain research
  responsibilities. `scripts/` are versioned workflows; `experiments/` and
  `reports/` are research evidence. Preserve the historical API/frontend prototype.
- Keep the simple modular Python package. Avoid new dependencies without a need.
- Type public interfaces; document contracts, units, failure modes and return values.
- Use `pathlib.Path`, UTF-8 and timezone-aware timestamps; support WSL2 and Windows.
  No machine-specific absolute paths or shell-only assumptions in Python.
- Use structured logging fields and explicit errors. Never silently swallow failures.
- Document exact reproduction commands. Standard check: `uv sync --locked` then
  `uv run --locked pytest`. Routine tests are offline; label synthetic fixtures.

## Data integrity
- Never fabricate observations or metrics, or silently substitute synthetic data.
- Preserve original bytes, source URLs, source timestamps, retrieval times,
  response metadata and checksums. Keep observed and derived fields distinct.
- Missing is missing, **not zero**. Respect source validity flags and report
  coverage, invalid values, gaps, schema drift and quality limitations.
- Features must be available at prediction time: no future observations,
  retrospective context or full-dataset fitted transformations.
- Prevent temporal and event-level leakage; purge overlapping label windows.
- Do not change frozen congestion/recovery thresholds, cohort, labels, hashes,
  splits or published metrics under a refactor. Version new scientific definitions.
  Recovery within a horizon is not recovery at its endpoint. Do not equate
  `recovery_confirmation_v1` with unimplemented `recovery_start_sustained_v1`.
- Inferred 2026 graph is not a validated historical network: P1/P2 are distinct
  retrospective subsets; P3 remains unapproved. Never fill missing speed with zero.

## Collaboration
See `docs/ownership.md` and follow `docs/data_contract.md`.
1. Member 1: `data/` — traffic acquisition, cleaning, events and labels.
2. Member 2: `network/` — roads, matching, direction and spatial features.
3. Member 3: `external/` — weather, holidays, verified incidents/context.
4. Member 4: `models/` — baselines, temporal evaluation, ablation, interpretation.
All four own research design, verification, documentation and poster work.
Avoid unnecessary edits to another member's module. Coordinate shared interface
changes in a PR before adoption; proposals in the contract are not final schemas.
Use feature branches and reviewed PRs; run tests before requesting merge.
Never commit credentials, large raw/processed datasets or large model artifacts.
Do not push or merge without authorization. **This repository consolidation task
prohibits every remote push or other remote write. Future remote operations require
explicit authorization in that request.** No forced checkout, hard reset or clean.
Avoid committing large data, credentials and unrelated agent work.

## Agent workflow
Inspect git status, code and docs first; preserve pre-existing user changes.
Make a short plan and implement one verifiable milestone at a time.
Run checks and inspect actual outputs. Distinguish succeeded, failed and unverified;
never claim tests ran when they did not. Keep provenance and blockers in reports.
Stop after the requested milestone; do not expand scope autonomously.

## Agent skills

### Issue tracker

Track issues and specifications in this repository's GitHub Issues. Read `docs/agents/issue-tracker.md` before creating, updating or triaging issues.

### Triage labels

Use the five canonical triage roles mapped to the repository's GitHub labels. Read `docs/agents/triage-labels.md` before changing triage state.

### Domain docs

Use the single-context domain documentation layout. Before domain-sensitive work, read `docs/agents/domain.md` and the domain material it points to.
