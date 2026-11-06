# DSC6004 poster copy — three horizontal columns (draft, English)

**Title:** Does an Inferred Directed Road Network Add Predictive Information for Hong Kong Congestion Recovery?

## Column 1 — Question, data, network

**Problem.** Predict whether sampled lane congestion shows sustained *recovery confirmation within 30 minutes*; this is not the Proposal's recovery-start target.

**Data.** Hong Kong Transport Department lane observations, expanded96 release (2023–September 2026): 96 frozen lane units, 35,782,769 five-minute rows and 30,452 events. Missing follow-up is censored, not labelled non-recovery. P1 inferred-network matched subset: 7,611 train / 4,680 validation / 3,933 test events; test includes 44 target detectors. *This selected subset does not represent all Hong Kong roads.*

**Network.** Official 2026 CENTERLINE/INTERSECTION/TURN geometry (EPSG:2326); direction-compatible candidate map matching and endpoint/turn-filtered inferred paths. Real neighbour speed is joined only when its observation and availability precede the prediction time. Geometry is official; inferred detector connections are **not independently verified historical or legally traversable links**. See Figures 1–3 in [figure index](../reports/final_research/README.md).

## Column 2 — Design and results

**Feature groups.** L: local speed and reference; H: available local history; Q: observation slot counts (not vehicle flow); S: upstream/downstream speed, missingness, network distance, congestion gradient and trend. Intended C (official calendar) and W (King's Park regional weather) could **not** be authenticated at event level in this checkout. Eight-arm factorial F0–F7 and especially F3 vs F7 were **not run**. We executed F0=L+H+Q and F4=F0+S only.

**Evaluation.** Four models, two fixed candidate pipelines each; fit on train, choose minimum validation log loss; held-out chronological 2026 test previously inspected (retrospective exploratory evidence). Same event IDs for both arms; fixed threshold 0.5. ROC-AUC is ranking, not a causal effect.

| P1 test, recovery confirmation within 30 min | F0 ROC-AUC | F4 ROC-AUC | Δ, detector-bootstrap 95% CI |
|---|---:|---:|---:|
| Logistic regression | .6604 | .7033 | +.0428 [−.0081, .0844] |
| Random forest | .7221 | .7557 | +.0336 [.0070, .0615] |
| XGBoost | .7290 | .7612 | +.0323 [.0091, .0538] |
| HistGradientBoosting | .7302 | .7608 | +.0307 [.0084, .0536] |

Source: [run metrics and paired intervals](../reports/final_research/README.md); n=3,933 test events, 44 target-detector clusters, 1,000 bootstrap resamples. The intervals do not model shared neighbour dependencies or adjust for multiple comparisons. Show Figures 4–5.

## Column 3 — Controls, limitations, conclusion

**Network alternatives (different frozen PR #21 run):** P1 RF test ROC-AUC geographic nearest .7304, undirected .7413, inferred directed .7523 and partially shuffled .7466; the shuffle changed only a subset of rows. These controls do not isolate causal propagation (Figure 6). P2 is much smaller; P3 has **zero approved historical connections, NO-GO**.

**Limitations.** Heuristic map matching; 2026 network projected backwards over 2023–26; sparse neighbours; event dependence; regional weather absent in the new paired study; recovery-start label not implemented; test set not a new blind evaluation. No claim about all Hong Kong roads or deployability.

**Headline A (use only if a later fully authenticated C/W-adjusted factorial shows stable gain):** “On matched inferred-network events, spatial features retain a positive detector-clustered predictive gain after controlling for verified local history, calendar, weather and quality; historical network validity remains unconfirmed.” **Not supported by the current run.**

**Headline B (current recommendation):** “In a retrospective matched P1 subset, inferred-neighbour features improved ROC-AUC beyond local history and observation quality, but calendar/weather-adjusted incremental value and historical network validity remain unresolved.”

**Do not use A for this poster without a new F3/F7 experiment.** Cite authentic saved data, event hashes, methods and caveats via [final research handoff](../reports/final_research/README.md). A single poster is the deliverable; no slides or remote submission are automated.
