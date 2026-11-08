# Predicting 30-Minute Congestion Recovery Confirmation in Hong Kong

**An exploratory evaluation of inferred spatial features after calendar and temperature/wind adjustment**

Authors / group: **[TEAM TO CONFIRM]** · DSC6004 · City University of Hong Kong

## Research Question
Do inferred neighboring-road conditions improve recovery-confirmation prediction beyond local traffic history, observation quality, calendar and the included weather covariates?

## Data and Target
- Official archived traffic, 2023–September 2026: 96 selected lane units; 30,452 events in the frozen source release.
- P1 retains known 30-minute labels with at least one available inferred neighbor: **7,611 train / 4,680 validation / 3,933 test** events; test positives **689 (17.5%)**.
- Congestion: two usable five-minute bins at speed/reference ≤0.5. Recovery confirmation: three high bins at ≥0.8; confirmation occurs within the next 30 minutes. Gaps censor labels.
- This differs from the original Proposal’s recovery-*start* target. Sparse observations do not establish continuous physical recovery.

## Directed Network Construction
Official CENTERLINE, INTERSECTION and TURN records support a candidate graph. Matching uses metre distance and directional compatibility; transitions check shared endpoints/elevation, intersection evidence and recorded turn restrictions. **2026 inferred relationships are not a verified historical network.**

## Feature Engineering / Experimental Design
- Base: local speed/state + past speed/trends + observation-quality counts (not vehicle flow).
- C: calendar and official holidays. W: King’s Park temperature/wind, ages and missingness.
- S: inferred upstream/downstream summaries, congestion contrasts, distance weighting and past changes.
- Four algorithms × eight feature arms; identical events, train-only imputation/scaling, two candidates selected by validation log loss, no refit; threshold **0.5**.
- Primary comparison: **F3 = Base+C+W; F7 = F3+S**. Chronological splits: 2023–24 / 2025 / 2026 Jan–Sep. The test period was previously examined.

## Key Results
| Model | F3 AUC | F7 AUC | Paired Δ AUC [95% interval] |
|---|---:|---:|---|
| Logistic regression | 0.6670 | 0.7033 | +0.0363 [-0.0039, +0.0737] |
| Random forest | 0.8105 | 0.8151 | +0.0047 [-0.0133, +0.0269] |
| XGBoost | 0.8189 | 0.8290 | +0.0101 [-0.0029, +0.0249] |
| HistGradientBoosting | 0.8144 | 0.8302 | +0.0159 [+0.0027, +0.0291] |

Intervals use 1,000 paired target-detector Bootstrap draws (44 detectors), without multiple-comparison adjustment. HGB’s interval excludes zero; the other three include zero. RF’s gain shrinks from **+0.0336 without C/W** to **+0.0047 with C/W**. HGB Macro-F1 improves **0.6786→0.6974** and Recall **0.4253→0.4702**. Improvements are not uniform: RF Recall slightly declines and LR probability losses worsen.

## Limitations
Retrospective test reuse; selected lane/neighbor cohort; sparse and censored observations; uncertain historical mappings; regional temperature/wind proxy, no rain or incidents. Bootstrap conditions on fitted models and does not fully address shared-neighbor dependence. No causal or citywide generalisation claim.

## Conclusion
Inferred spatial features provide **model-dependent retrospective incremental information** after the included calendar and temperature/wind covariates. Adjustment attenuates several gains; evidence does not support a universal improvement or certified road connectivity.

## Sources
Hong Kong Transport Department traffic archives and Road Network v2; Hong Kong Observatory temperature/wind archives; official annual General Holidays notices. Versioned data, features, probabilities and figure sources: `07_evidence_manifest.json`.
