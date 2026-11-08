# Spoken script — rehearsal target 4m30s

Actual script word count (regex tokens): **553**. Suggested pace: **122.9 words/minute**; reserve 30 seconds before the 5-minute hard limit. Not human-timed. Headers/this note excluded. Rehearse against the poster, no slides or live demo.

<!-- SCRIPT_START -->
Good afternoon. Our project asks whether neighboring road conditions help predict when congestion will recover in Hong Kong. We focus on a precise question: after including local traffic history, calendar, temperature and wind, do inferred spatial features still add predictive information?

Please start with the data and event panel. Our frozen source release contains ninety-six selected lane units and thirty thousand, four hundred and fifty-two events. For this spatial comparison, we retain events with a known thirty-minute outcome and at least one available inferred neighbor. The resulting training, validation and test sets contain seven thousand, six hundred and eleven; four thousand, six hundred and eighty; and three thousand, nine hundred and thirty-three events.

Our target is recovery confirmation, not recovery start. Two low five-minute bins establish congestion. Three usable bins above eighty percent of the frozen reference establish recovery confirmation. We predict whether that confirmation occurs within thirty minutes. Missing follow-up produces an unknown label, not an automatic negative. Sparse observations support sampled persistence, not proof of uninterrupted physical recovery.

The network panel shows real official road geometry and real detector locations. We constructed inferred directed relationships using distance and direction compatibility, shared endpoints and elevation, intersection evidence, and recorded turn restrictions. The colored links follow road geometry. They are not straight-line geographic neighbors. However, a current official road map does not certify historical detector matching or legal movement. One illustrated upstream match remains ambiguous. We use engineered graph features, not a graph neural network.

The event panel illustrates information timing. Blue local measurements were available at prediction. Orange measurements show retrospective context only. Neighbor observations are isolated points because we do not have a complete neighbor curve for this prediction. The event was selected by chronological order, not because the model performed well.

We trained four algorithms across eight feature combinations, giving thirty-two arms. Every arm used identical events. Imputation and scaling were fitted only on training data. Each algorithm had two fixed candidates, selected using validation log loss. Classification used a common probability threshold of one half. Calendar and weather features were authenticated and joined by event identity and prediction time. Weather means King’s Park temperature and wind, not rainfall or all local road weather.

Now look at the main result. Spatial features increased the AUC point estimate for all four algorithms after adjustment. But the uncertainty and other metrics matter. The random forest increment was only about zero point zero zero five, and the XGBoost increment about zero point zero one zero. Their detector-cluster intervals include zero. HistGradientBoosting improved by about zero point zero one six, with an interval above zero, but these intervals were not adjusted for multiple comparisons. Random forest recall slightly decreased, and logistic regression probability losses worsened.

Our intervals use one thousand paired detector-cluster samples and fixed fitted models. Shared neighbors can create dependence across clusters. A supplementary weekly-block analysis also depends on its grouping assumptions. The test period was previously examined, so this is retrospective exploration rather than a fresh blind test.

We conclude that inferred spatial information can provide model-dependent incremental value after the included calendar and temperature and wind variables, but not a universal improvement. The separate Proposal recovery-start labels are implemented; their models and adoption review remain unfinished. We do not claim causality, citywide generalisation, historical network certification, or deployment. Thank you.
<!-- SCRIPT_END -->
