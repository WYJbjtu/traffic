# Local repository consolidation: delivery and verification

## Before / after

Baseline `8a18594` on clean `integrate-project`, with two other worktrees left untouched. Work carried out on local `refactor/repository-consolidation`. PR #21 inferred-v2 code, #22 error/threshold artifacts and #23 six-page Explorer functionality are present in the local object history and files. No fetch/merge, full retraining, new research definition or remote write was performed.

| Measure | Before | After |
|---|---:|---:|
| Python files | 171 | 171 |
| Python source lines | 20,611 | 20,603 |
| Markdown files | 104 | 107 |
| Duplicated streaming SHA-256 bodies in `data.http` / `research96` | 2 | 1 |
| Offline pytest pass count | 255 | 255 |
| Key research-result consistency | Saved report hashes at baseline | Four saved files hash-identical; P1 M0/M1 event ID SHA matches (no full replay) |

File counts include tracked files and new/moved working files; source line counts use physical lines. No metrics, samples, frozen source hashes, notebooks or model training code were rewritten.

## File operations and structure

- **Deleted as obsolete: 0 tracked files.** A genuinely unused reproducibility script or report was not proven. One old `apps/research_explorer96.py` *path* is removed solely as a move to `src/traffic_recovery/research_explorer96.py` (one moved module); no page was dropped. One redundant function body (`research96.sha256`) was removed and its public symbol retained as an alias to the existing `data.http.sha256_file`. This avoids divergent hashing implementations without modifying digest semantics.
- Launcher `apps/research_explorer.py` now imports the internal package module. Default repository root resolution was adjusted for the move; the `RESEARCH96_DATA_ROOT` override remains unchanged. API/frontend medium-pilot prototype, historical 24-lane adapter and all experiment scripts remain distinct and untouched.
- Rewritten `README.md`; updated `AGENTS.md` and historical-status warning in `docs/research_explorer.md`; added `docs/README.md` topic index and `reports/repository_cleanup/{audit.md,file_manifest.csv,summary.md}`. Historical handoffs and original reports are retained rather than relabelled or erased. Detailed file list: [manifest](file_manifest.csv).

Current main layout: `apps/` launcher; `src/traffic_recovery/{data,network,external,models,api}/` plus `research96.py`, `research_explorer96.py`, historical `research_viz.py`; `scripts/`, `configs/`, `experiments/`, `notebooks/`, `reports/`, `tests/`, `docs/`, historical `frontend/` and verified `data/sample/`; large `data/local/` ignored.

## Actual checks

- `uv sync --locked && uv run --locked pytest -q`: **255 passed** before and after, one existing Starlette/httpx deprecation warning each. CI currently specifies this sync/pytest check on Linux and Windows; no separate formatter/type checker is configured. `git diff --check` passed.
- Streamlit 1.51 / Plotly 6.3 `AppTest` loaded the official launcher without exceptions. Started an actual local Streamlit server and ran Playwright Chromium 1365×850. After a six-page smoke check, **the original full browser validation script** (`scripts/validate_research_explorer96_browser.py`) passed all 14 checks: overview counts, official map canvas, detector selection and inferred path, real event, neighbor curve, future separation, saved spatial features, model metrics and controls, limits, no page errors or horizontal overflow. Output and seven screenshots were redirected to `/tmp/hk-cleanup-browser-nsqli2s1/` to avoid overwriting tracked evidence. Initial browser attempt failed because Playwright 1.58's expected Chromium revision was absent; retry explicitly used the installed headless-shell revision and passed. Original prior acceptance remains in `reports/research_explorer_96_integration/browser-validation.json`.
- Before/after SHA-256 identical: `reports/spatial96_inferred_v2/paired_spatial_metrics.csv` (`d527b47a0dcef587b84d75078ad37d1e384f751e3b32ea680b237acdef126b5b`), `reports/spatial96_inferred_v2/output_sha256.json` (`a6d7c6d2049e89f38515cca80042f9fb9f913cf618fec5ee74e54d15a8f9fbea`), `reports/nov04_integrated_delivery/model_metrics.csv` (`5d9aec9336811dc83c6f973464961a4a79db765dbc86d780805e3e6dfdae081f`), Tianhao96 `metrics.csv` (`83d2378923474ad5cad18517f35fb1e9ac8b6a7242df6a76879e91b1a59db431`). Read-only saved P1 test RF M0/M1: same 3,933 events, 689 positives, 3,244 negatives, event SHA `c6aaae1e81fd1fe9e1309d1068b5e05431823ddb49d3710f62b4ebddde554ef3`; ROC-AUC 0.724992/0.752259. These checks do not constitute re-training or independent reconstruction.
- The local original expanded96 and inferred-v2 inputs exist, but full 35.8m-row replay, source/release ZIP re-verification, recomputation of all labels and 96-lane model probabilities were **not** run. Existing frozen artifacts and tests are preserved. No new dependency or lock change. Documentation links in changed overview/index/audit/summary were checked locally.

## Unresolved / next steps

- P3 still has zero independently approved historical network connections; P1/P2 use inferred retrospective topology and distinct eligible populations. Unimplemented `recovery_start_sustained_v1` requires a new approved target, not renaming current `recovery_confirmation_v1` results.
- `docs/data_contract.md` has a missing `docs/milestone2.md` reference and pilot-era status wording. This shared scientific contract needs owner review, not a cosmetic edit in a code cleanup. Several experiment scripts contain similar-looking metric and time handling tied to different published experiments; consolidation would require byte-for-byte replay against their original data and manifests before modification. No additional tracked file deletion was justified.
- When resources/owners allow, independently verify the Release archive and event/label lineage, model predictions and source network hashes; retain the temporary full-browser screenshots outside the tracked frozen report unless reviewed for publication. Coordinate scientific rule changes in separately versioned experiments. No remote upload is authorized by this report.
