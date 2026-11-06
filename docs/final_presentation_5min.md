# Five-minute poster presentation — draft in English

**Recommended poster headline:** Version B in [poster copy](final_poster_content.md). This script discusses the completed P1 F0/F4 experiment, **not** an unrun calendar/weather-adjusted result. Suggested allocation: speaker 1 (0:00–1:05), speaker 2 (1:05–2:05), speaker 3 (2:05–3:25), speaker 4 (3:25–4:30); leave 30 seconds for transition and questions. At ~115–125 words per minute, rehearse with the actual poster.

## Script (~4 minutes 30 seconds)

**0:00–1:05 — Question and data.** “When congestion appears on a Hong Kong road, can we predict whether its observed speed will show sustained recovery confirmation within the next thirty minutes? Our second question is whether measurements on inferred upstream and downstream roads help once we account for what the local lane already tells us. We use authentic Hong Kong Transport Department observations from a frozen 96-lane release covering 2023 to September 2026. The release contains about 35.8 million five-minute records and 30,452 congestion events. A missing follow-up does not mean no recovery: it remains unknown. Our result concerns confirmation of sustained recovery, not the first moment when recovery begins.”

**1:05–2:05 — Network and feature controls.** “We constructed a candidate directed graph from official road centerlines, intersections and turn records. We map detectors to compatible arcs and follow candidate directed paths. Speed features come only from genuine neighbour observations whose measurement time and source-availability time precede the prediction time; missing neighbours are not assigned zero speed. The road geometry is official, but the inferred detector relationships have not been independently validated for past years or legal turning. Our matched P1 population has 7,611 training, 4,680 validation and 3,933 test events. We compare exactly the same event IDs with and without spatial features.”

**2:05–3:25 — Results and uncertainty.** “We reused four small predeclared modeling pipelines: logistic regression, random forest, XGBoost and histogram gradient boosting. We fit on training data, select candidates by validation log loss and evaluate the already reviewed 2026 test set; this is retrospective exploration, not a new blind test. With local speed, history and observation-quality counts, XGBoost reached 0.729 ROC-AUC. Adding inferred spatial features gave 0.761, an increase of 0.032 on the same 3,933 test events. Random forest rose from 0.722 to 0.756. A paired bootstrap resampling 44 target detectors gives a 95-percent percentile interval from 0.009 to 0.054 for XGBoost's ROC-AUC change. This interval does not account for shared neighbouring roads or multiple comparisons; the logistic regression interval crosses zero.”

**3:25–4:30 — Controls and conclusion.** “In an earlier, separately fitted network experiment, geographic and undirected neighbours also had predictive signal. A partially shuffled control retained much of the apparent gain. These are warnings against interpreting our improvement as causal traffic propagation. More importantly, the event-level official holiday and historical station-weather inputs needed to compare full models with and without spatial features were not present locally. We did not substitute guessed holidays or new weather feeds. The original Proposal's recovery-start target has also not been validated; the strictly verified historical network category P3 has zero approved connections. Our conclusion is narrow: on the matched inferred P1 subset, spatial measurements add retrospective predictive information beyond local history and quality, but their added value *after calendar and weather control*, and the historical road validity, remain open research questions.”

## Three results to emphasize

1. Matched P1 test: XGBoost F0/F4 ROC-AUC .7290/.7612; paired Δ +.0323, detector-bootstrap 95% interval [.0091, .0538], 44 target detectors, 1,000 draws.
2. RF F0/F4 .7221/.7557; different frozen PR #21 geographic/undirected/shuffled controls have substantial signal, limiting directional interpretation.
3. The essential F3 vs F7 C/W-adjusted contrast was **not executed**, because the authenticated event-level calendar and weather source files were unavailable. P3 is NO-GO. These are limitations, not negative model scores.

## Likely questions and short answers

1. **Is this a causal upstream effect?** No. Same-event predictive association on a retrospectively inferred graph; shared time, region and unverified historical links may confound it.
2. **Why not add weather and holidays now?** The earlier Tianhao96 results include saved predictions, not the original authenticated per-event C/W features and release-time source watermarks in this checkout. Combining its model scores with P1 features would be invalid.
3. **Are your train and test roads independent?** No. Splits are chronological; detectors can recur across time and neighbouring detectors can share road context. The bootstrap clusters target detectors but does not remove cross-cluster dependence.
4. **How is a positive label defined?** A witnessed sustained high-speed confirmation within 30 minutes, after low-speed onset confirmation; a gap before outcome maturity means unknown. This is not recovery *starting* within the horizon.
5. **Why is P3 missing while you show spatial gain?** P1/P2 are heuristic retrospective candidate relationships; P3 requires independently reviewed historical connectivity, which currently has zero approved links. No P3 model was fit.

Sources and exact metric table: [final research report](../reports/final_research/README.md). Poster diagrams/figures must keep their caveats visible. No remote submission is performed.
