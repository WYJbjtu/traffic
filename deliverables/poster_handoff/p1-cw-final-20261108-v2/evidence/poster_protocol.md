# Poster finalization protocol — independent version, 2026-11-08

Before inspecting new test scores: old96 confirmation target, horizon 30m, P1 known-label/as-of-neighbor eligibility; exact frozen split event hashes required. All F0–F7 arms refitted with original two candidates per model, train-only means/indicators (and LR scaling), minimum validation clipped log loss, no refit, threshold .5. F3/F7 first, then F0/F4/F1/F5/F2/F6. Original results untouched. No test-selected model, parameters, feature changes or cohort changes.

C/W are producer-authenticated delivered features, not a claim to independently re-download 90 weather archives. Double-key event/time join, strict allowlists, timestamp and age gates. Keep genuine missing weather. Calendar and King's Park temperature/wind are not all weather; Q counts observation slots, not vehicles.

## Statistical and diagnostic plan

- 1,000 paired target-detector-cluster bootstrap draws, seed 42, F7 minus F3 ROC-AUC and AP, per model. Repeat drawn detectors with all their events. Count single-class invalid replicates. Percentile intervals conditional on fixed fitted models; shared-neighbor dependence not fully handled; no multiplicity correction.
- Supplementary fixed HKT 7-day blocks anchored 2026-01-01, seed 20261108, 1,000 paired draws. This tests a different dependence assumption, not a replacement interval. No precise interval if fewer than ten occupied groups.
- All four same-event spatial contrasts, all metrics; Brier/log loss lower is better. Report error transitions and class-conditional probability changes, not only AUC.
- Current RF/XGBoost structural controls: F3 plus *only the same 12 S1 fields* for directed, pooled undirected, and geographic representations. Pool the exact available directed observations, preserving missingness. Geographic uses previously frozen 250m EPSG:2326 nearest-detector definition with no event reselection. No comparing full S1–S4 F7 to speed-only control as evidence of direction. Duplicate pooled slots encode one undirected set, not two independent sets. Coverage differences remain a limitation. No new permutation search; old partial shuffle is historical and weak.

## Figures (rules independent of prediction success)

- Primary: F3→F7 AUC differences with detector intervals, zero line, cohort/target/n and dependence caveats on figure.
- Case: first chronological P1 test event (tie event_id) with authentic available local observation and >=1 authentic as-of neighbor. Known label by eligibility. No success-score selection. Plot ratio to each unit's own frozen reference, real gaps, local input versus retrospective outcome, 0.5/0.8 thresholds and saved four-model probabilities.
- Map: choose lexicographically first P1 target with both incoming and outgoing canonical paths, all three selected mapping offsets <=25m and each path >=100m; if unavailable, report and relax neither criteria nor historical approval. Draw official polylines; relationship arrows explicitly schematic, never claimed road routing. Mapping remains inferred and may be ambiguous. This is not the known short-path/large-offset counterexample.
- Optional: 4×8 AUC heatmap and matched S1 structural controls, each with CSV source.

## Execution incidents

Initial `p1-cw-matrix-v1-20261108` stopped after F3 fitting because strict JSON rejected XGBoost's NaN **parameter sentinel** in the fit audit (not a missing prediction). That partial run is retained, not cited. The serializer now records the sentinel as the literal string `NaN`; feature/model parameters and metrics are unchanged. A regression test exercises this model serialization. The complete rerun uses a new `p1-cw-matrix-v2-20261108` directory. No test results were used to change the protocol.
