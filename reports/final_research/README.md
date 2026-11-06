# DSC6004 retrospective research integration — partial final handoff

**Status: P1 F0/F4 comparison executed and validated; eight-arm C/W factorial and Proposal-aligned recovery-start target NOT RUN.** This is a transparent presentation of authentic exploratory evidence, **not** a claim that the complete primary question has been answered or that the 2026 test set was untouched. Source code, frozen model metrics and original reports remain unmodified. [Feature audit and missing sources](../../experiments/unified96/feature_audit.md).

## Objective, sources and target

Question: does a *retrospectively inferred directed-road* feature set add predictive association beyond observed local traffic, local history and observation quality? The larger question **after controlling for authenticated calendar and weather** remains open. The expanded96 Release contains 96 frozen lane units, 35,782,769 five-minute bins and 30,452 events over 2023–September 2026; only 94 units have observed events ([release](../../docs/expanded96_data_access.md)). Source archive hashes and time policy are frozen; [events/lineage source hashes](../../experiments/unified96/runs/p1-f0-f4-v1/manifest.json) are checked at runtime. Official CENTERLINE / INTERSECTION / TURN use EPSG:2326 metres; the **2026** candidate arc graph and matching heuristics are not independently verified historical/legally traversable links ([method](../spatial96_inferred_v2/network_methodology.md)).

The only evaluated target here is `recovery_confirmation_v1`: sampled sustained confirmation **within 30 minutes**, not the Proposal's `recovery_start_sustained_v1`. Three high usable five-minute bins confirm recovery; missing follow-up censors labels. The Proposal source PDF and approved start/persistence interpretation were not available, so no start label or fabricated comparison was introduced ([target review](../nov04_integrated_delivery/target_definition_review.md)). The 2026 test set was previously reviewed: **all new comparisons are retrospective exploratory analyses**, not fresh blind confirmation.

## Feature engineering, populations and model selection

One event ID joined to one history row and one event/population spatial row at the same prediction timestamp. Multiple authentic neighbour observations may map to one event; detector/direction/lane, source timestamps, as-of availability and hashes are verified. L = local speed/ratio/reference and witnessed onset duration; H = available local lags/trend/mean; Q = valid slots and history bin counts (**not traffic volume**); S = inferred upstream/downstream speed, missingness, network distance, congestion gradient and neighbour trend. NA speeds stay NA. No future or retrospective outcome measurements enter predictive input. [Exact ordered columns and availability rules](../../experiments/unified96/feature_manifest.json).

Matched P1 = known 30-minute labels **and ≥1 real as-of inferred neighbour**: train 7,611, validation 4,680, test 3,933 (44 target detectors in test). P2 is a smaller **different** high-confidence inferred population; P3 has **zero independently approved links (NO-GO)**. Full 96-lane cohort is distinct; neither was re-trained here. All four models and both arms use the exact same event IDs per split. Feature groups C/W cannot be authenticated locally: saved Tianhao96 model scores are not event-level weather/holiday inputs. **F0 (L+H+Q) and F4 (F0+S) were executed; F1–F3/F5–F7, especially F3 vs F7, were not.** The [32-row experiment matrix](experiment_matrix.csv) marks 8 executed and 24 blocked model/arm cells without inventing values.

Reuse `traffic_recovery.models.expanded96.candidate_models`: two fixed candidate pipelines per Logistic Regression, Random Forest, XGBoost and HistGradientBoosting. Fit and preprocessing on train only; validation minimum log loss selects one candidate; no refit; fixed threshold 0.5, no test optimization. Seed 42 and software versions are in the [run manifest](../../experiments/unified96/runs/p1-f0-f4-v1/manifest.json). The original spatial PR #21 experiment has different feature ordering and model selection by arm; **do not overwrite or identify these scores with its saved M0/M1 metrics**. Majority/prevalence reference results in [original 96-lane report](../nov04_integrated_delivery/README.md) are on the *full cohort* and cannot be paired with P1 here.

## Actual P1 test results (n=3,933; 689 positive, 3,244 negative)

All values below are from `unified96-p1-f0-f4-v1`, `recovery_confirmation_v1`, 30-minute test split, **not C/W-adjusted**. Full precision, balanced accuracy, recall, ROC-AUC, PR-AUC, macro-F1, Brier, log loss and TN/FP/FN/TP for each validation/test arm: [metrics.csv](../../experiments/unified96/runs/p1-f0-f4-v1/metrics.csv); [authentic event-level scores](../../experiments/unified96/runs/p1-f0-f4-v1/predictions.parquet).

| Model | F0 ROC-AUC / PR-AUC / macro-F1 | F4 ROC-AUC / PR-AUC / macro-F1 | Paired Δ ROC-AUC (95% detector-bootstrap CI) |
|---|---|---|---|
| Logistic regression | .6604 / .3283 / .5194 | .7033 / .3613 / .5900 | +.0428 [−.0081, .0844] |
| Random forest | .7221 / .3865 / .5821 | .7557 / .4245 / .5874 | +.0336 [.0070, .0615] |
| XGBoost | .7290 / .3842 / .6127 | .7612 / .4257 / .6380 | +.0323 [.0091, .0538] |
| HistGradientBoosting | .7302 / .3958 / .6169 | .7608 / .4289 / .6580 | +.0307 [.0084, .0536] |

The F4–F0 difference is paired by event IDs. [spatial_marginal_gain.csv](spatial_marginal_gain.csv) records all four differences and 1,000 target-detector cluster-resamples per model (44 clusters, 0 single-class invalid replicates in these observed runs). The percentile intervals **do not account for dependence across different target detectors sharing neighbouring roads** or multiple comparisons, and do not confer scientific approval or causality. Logistic regression's interval crosses zero. Lower Brier/log loss in some arms is not proof of calibrated probabilities; no reliability analysis was run.

## Ablation, negative controls, heterogeneity and error analysis

The only new ablation is the S group, F0→F4. Calendar/weather main effects and interactions are **not measurable** here; the historical Tianhao96 run studied C/W without this spatial cohort and cannot be subtracted as if paired. Frozen PR #21 *different* P1 study ([original metrics](../spatial96_inferred_v2/paired_spatial_metrics.csv), [negative controls](../spatial96_inferred_v2/spatial_negative_controls.csv)) reports RF ROC-AUC geographic .7304, undirected .7413, directed .7523, time-region shuffle .7466 on its P1 test population; XGBoost .7325/.7470/.7588/.7516. The shuffled control swapped only part of the full dataset; contemporaneous/regional confounding remains plausible. P2 test has 191 events from 9 target detectors; do not compare its point estimate directly with P1. No stronger permutation, corridor, hour-of-day or time-specific interaction was executed.

[Event-level error transitions](error_transitions.csv) use independently saved F0/F4 probabilities and fixed threshold 0.5 on exact paired event IDs. For XGBoost, 175 test events are correct only with F4 while 169 are correct only with F0; RF has 106 vs 107. Average probability shifts are descriptive; these figures cannot establish detector-level significance. No spatial scores were reverse engineered from frozen PR #21 aggregate AUC.

## Poster figures and Explorer

[Figures](figures/) are generated from authenticated sources. Figure 1 is a workflow schematic; Figure 2 is a **copied, hashed official-geometry review image**, not proof of approved road relationships; Figure 3 shows actual first-by-event-ID P1 test local observations (future local points explicitly retrospective) and authentic as-of neighbour *points*; Figures 4–5 show this new F0/F4 run and detector uncertainty; Figure 6 uses frozen PR #21 controls (not the new run). See [`figure_manifest.json`](figures/figure_manifest.json) for event ID, source hashes and caveats. Where supported, SVG and PNG are available; Figure 2 is a source PNG, not a fabricated vector road map. The Streamlit Model Comparison page now includes the separate new experiment; Event Explorer shows new F0/F4 probabilities where event IDs match. It must retain P3 NO-GO and clearly mark the old PR #21 as aggregate-only.

## Reproduction (repository root, Python 3.12)

```text
uv sync --locked
uv run --locked pytest -q
uv run --locked python -m experiments.unified96.run --out data/local/unified96/new-f0-f4-run
uv run --locked python -m experiments.unified96.analyze --out reports/local/new-unified-analysis
uv run --locked python -c 'from pathlib import Path; from experiments.unified96.analyze import build_matrix; build_matrix(Path("reports/local/new-unified-analysis/experiment_matrix.csv"))'
uv run --locked python -m experiments.unified96.figures --out reports/local/new-unified-figures
uv run --locked --with 'streamlit==1.51.0' --with 'plotly==6.3.1' streamlit run apps/research_explorer.py
```

The analysis/figure commands use the already verified **published new run** in `experiments/unified96/runs/p1-f0-f4-v1/`; they do not automatically use the alternate rerun path. Compare new run hashes/metrics manually before replacing any reference. Commands refuse existing output files/directories. Source inputs live under ignored `data/local/`; download/reconstruct them only with the exact versioned [expanded96 handoff](../../docs/expanded96_data_access.md) and [inferred-v2 method](../spatial96_inferred_v2/network_methodology.md). Do not substitute a live weather feed or modify frozen SHA-256. Peak memory and Windows end-to-end training were not measured; training completed in ~21 seconds locally on the event-level subset, excluding source hashing and figure generation.

## Conclusion and remaining work

On matched P1 events, the **observed retrospective** F0→F4 spatial-group ROC-AUC point estimate rose for all four models; detector-cluster uncertainty supports only limited robustness, with overlapping geographic/undirected/shuffle signals. This does **not** answer whether spatial information remains after properly controlling for authenticated C and W, whether P1 links were legal historically, or whether all Hong Kong roads benefit. Obtain exact hashed original C/W feature inputs and approval of the Proposal target; then run a separately versioned eight-arm factorial and start-target experiment, not a silent rewrite of existing results. Team review of source versions, historical detector identities, event labels and cluster dependence remains necessary.
