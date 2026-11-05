# Feature-group model comparison

**Status: EXPLORATORY — NOT APPROVED AS FINAL RESULTS**

This report is generated from fingerprinted model outputs. Synthetic or
pending-approval measurements must not be presented as empirical findings.

## Evidence

- Dataset: `experiments/member4/event_features.parquet`
- Dataset SHA-256: `f163c732ba05e00e23802cb3cc390f8c5a8c034975a0ef3524674a3278c346b8`
- Contract status: `pending_team_review`
- Supervised-model status: `pending_real_cohort_and_team_review`
- Comparison status: `pending_team_review`

## Test metrics

| model | horizon | feature set | metric | value | n | undefined reason |
|---|---:|---|---|---:|---:|---|
| decision_tree | 15 | local | balanced_accuracy | 0.5043 | 1396 |  |
| decision_tree | 15 | local | brier_score | 0.1810 | 1396 |  |
| decision_tree | 15 | local | f1 | 0.0345 | 1396 |  |
| decision_tree | 15 | local | log_loss | 0.5469 | 1396 |  |
| decision_tree | 15 | local | pr_auc | 0.2632 | 1396 |  |
| decision_tree | 15 | local | roc_auc | 0.5607 | 1396 |  |
| decision_tree | 30 | local | balanced_accuracy | 0.5826 | 1363 |  |
| decision_tree | 30 | local | brier_score | 0.2396 | 1363 |  |
| decision_tree | 30 | local | f1 | 0.5560 | 1363 |  |
| decision_tree | 30 | local | log_loss | 0.6719 | 1363 |  |
| decision_tree | 30 | local | pr_auc | 0.5480 | 1363 |  |
| decision_tree | 30 | local | roc_auc | 0.6277 | 1363 |  |
| decision_tree | 60 | local | balanced_accuracy | 0.5473 | 1321 |  |
| decision_tree | 60 | local | brier_score | 0.1791 | 1321 |  |
| decision_tree | 60 | local | f1 | 0.8507 | 1321 |  |
| decision_tree | 60 | local | log_loss | 0.6128 | 1321 |  |
| decision_tree | 60 | local | pr_auc | 0.8312 | 1321 |  |
| decision_tree | 60 | local | roc_auc | 0.6427 | 1321 |  |
| hist_gradient_boosting | 15 | local | balanced_accuracy | 0.5000 | 1396 |  |
| hist_gradient_boosting | 15 | local | brier_score | 0.1771 | 1396 |  |
| hist_gradient_boosting | 15 | local | f1 | 0.0000 | 1396 |  |
| hist_gradient_boosting | 15 | local | log_loss | 0.5367 | 1396 |  |
| hist_gradient_boosting | 15 | local | pr_auc | 0.3196 | 1396 |  |
| hist_gradient_boosting | 15 | local | roc_auc | 0.6227 | 1396 |  |
| hist_gradient_boosting | 30 | local | balanced_accuracy | 0.5850 | 1363 |  |
| hist_gradient_boosting | 30 | local | brier_score | 0.2371 | 1363 |  |
| hist_gradient_boosting | 30 | local | f1 | 0.5440 | 1363 |  |
| hist_gradient_boosting | 30 | local | log_loss | 0.6660 | 1363 |  |
| hist_gradient_boosting | 30 | local | pr_auc | 0.5640 | 1363 |  |
| hist_gradient_boosting | 30 | local | roc_auc | 0.6276 | 1363 |  |
| hist_gradient_boosting | 60 | local | balanced_accuracy | 0.5284 | 1321 |  |
| hist_gradient_boosting | 60 | local | brier_score | 0.1759 | 1321 |  |
| hist_gradient_boosting | 60 | local | f1 | 0.8580 | 1321 |  |
| hist_gradient_boosting | 60 | local | log_loss | 0.5360 | 1321 |  |
| hist_gradient_boosting | 60 | local | pr_auc | 0.8340 | 1321 |  |
| hist_gradient_boosting | 60 | local | roc_auc | 0.6505 | 1321 |  |
| logistic_regression | 15 | local | balanced_accuracy | 0.5000 | 1396 |  |
| logistic_regression | 15 | local | brier_score | 0.1814 | 1396 |  |
| logistic_regression | 15 | local | f1 | 0.0000 | 1396 |  |
| logistic_regression | 15 | local | log_loss | 0.5490 | 1396 |  |
| logistic_regression | 15 | local | pr_auc | 0.2663 | 1396 |  |
| logistic_regression | 15 | local | roc_auc | 0.5446 | 1396 |  |
| logistic_regression | 30 | local | balanced_accuracy | 0.5005 | 1363 |  |
| logistic_regression | 30 | local | brier_score | 0.2486 | 1363 |  |
| logistic_regression | 30 | local | f1 | 0.1404 | 1363 |  |
| logistic_regression | 30 | local | log_loss | 0.6903 | 1363 |  |
| logistic_regression | 30 | local | pr_auc | 0.4726 | 1363 |  |
| logistic_regression | 30 | local | roc_auc | 0.5196 | 1363 |  |
| logistic_regression | 60 | local | balanced_accuracy | 0.5000 | 1321 |  |
| logistic_regression | 60 | local | brier_score | 0.1827 | 1321 |  |
| logistic_regression | 60 | local | f1 | 0.8666 | 1321 |  |
| logistic_regression | 60 | local | log_loss | 0.5524 | 1321 |  |
| logistic_regression | 60 | local | pr_auc | 0.7791 | 1321 |  |
| logistic_regression | 60 | local | roc_auc | 0.5311 | 1321 |  |
| majority_class | 15 | none | balanced_accuracy | 0.5000 | 1396 |  |
| majority_class | 15 | none | brier_score | 0.2378 | 1396 |  |
| majority_class | 15 | none | f1 | 0.0000 | 1396 |  |
| majority_class | 15 | none | log_loss | 8.5720 | 1396 |  |
| majority_class | 15 | none | pr_auc | 0.2378 | 1396 |  |
| majority_class | 15 | none | roc_auc | 0.5000 | 1396 |  |
| majority_class | 30 | none | balanced_accuracy | 0.5000 | 1363 |  |
| majority_class | 30 | none | brier_score | 0.4615 | 1363 |  |
| majority_class | 30 | none | f1 | 0.0000 | 1363 |  |
| majority_class | 30 | none | log_loss | 16.6335 | 1363 |  |
| majority_class | 30 | none | pr_auc | 0.4615 | 1363 |  |
| majority_class | 30 | none | roc_auc | 0.5000 | 1363 |  |
| majority_class | 60 | none | balanced_accuracy | 0.5000 | 1321 |  |
| majority_class | 60 | none | brier_score | 0.2354 | 1321 |  |
| majority_class | 60 | none | f1 | 0.8666 | 1321 |  |
| majority_class | 60 | none | log_loss | 8.4857 | 1321 |  |
| majority_class | 60 | none | pr_auc | 0.7646 | 1321 |  |
| majority_class | 60 | none | roc_auc | 0.5000 | 1321 |  |
| random_forest | 15 | local | balanced_accuracy | 0.5000 | 1396 |  |
| random_forest | 15 | local | brier_score | 0.1771 | 1396 |  |
| random_forest | 15 | local | f1 | 0.0000 | 1396 |  |
| random_forest | 15 | local | log_loss | 0.5352 | 1396 |  |
| random_forest | 15 | local | pr_auc | 0.3103 | 1396 |  |
| random_forest | 15 | local | roc_auc | 0.6243 | 1396 |  |
| random_forest | 30 | local | balanced_accuracy | 0.5873 | 1363 |  |
| random_forest | 30 | local | brier_score | 0.2368 | 1363 |  |
| random_forest | 30 | local | f1 | 0.5428 | 1363 |  |
| random_forest | 30 | local | log_loss | 0.6655 | 1363 |  |
| random_forest | 30 | local | pr_auc | 0.5638 | 1363 |  |
| random_forest | 30 | local | roc_auc | 0.6276 | 1363 |  |
| random_forest | 60 | local | balanced_accuracy | 0.5493 | 1321 |  |
| random_forest | 60 | local | brier_score | 0.1768 | 1321 |  |
| random_forest | 60 | local | f1 | 0.8528 | 1321 |  |
| random_forest | 60 | local | log_loss | 0.5326 | 1321 |  |
| random_forest | 60 | local | pr_auc | 0.8505 | 1321 |  |
| random_forest | 60 | local | roc_auc | 0.6584 | 1321 |  |
| speed_ratio_rule | 15 | local_speed_ratio | balanced_accuracy | 0.5296 | 1396 |  |
| speed_ratio_rule | 15 | local_speed_ratio | brier_score | NA | 1396 | score_is_not_probability |
| speed_ratio_rule | 15 | local_speed_ratio | f1 | 0.2360 | 1396 |  |
| speed_ratio_rule | 15 | local_speed_ratio | log_loss | NA | 1396 | score_is_not_probability |
| speed_ratio_rule | 15 | local_speed_ratio | pr_auc | 0.2688 | 1396 |  |
| speed_ratio_rule | 15 | local_speed_ratio | roc_auc | 0.5450 | 1396 |  |
| speed_ratio_rule | 30 | local_speed_ratio | balanced_accuracy | 0.5091 | 1363 |  |
| speed_ratio_rule | 30 | local_speed_ratio | brier_score | NA | 1363 | score_is_not_probability |
| speed_ratio_rule | 30 | local_speed_ratio | f1 | 0.2367 | 1363 |  |
| speed_ratio_rule | 30 | local_speed_ratio | log_loss | NA | 1363 | score_is_not_probability |
| speed_ratio_rule | 30 | local_speed_ratio | pr_auc | 0.4571 | 1363 |  |
| speed_ratio_rule | 30 | local_speed_ratio | roc_auc | 0.4964 | 1363 |  |
| speed_ratio_rule | 60 | local_speed_ratio | balanced_accuracy | 0.4762 | 1321 |  |
| speed_ratio_rule | 60 | local_speed_ratio | brier_score | NA | 1321 | score_is_not_probability |
| speed_ratio_rule | 60 | local_speed_ratio | f1 | 0.2276 | 1321 |  |
| speed_ratio_rule | 60 | local_speed_ratio | log_loss | NA | 1321 | score_is_not_probability |
| speed_ratio_rule | 60 | local_speed_ratio | pr_auc | 0.7376 | 1321 |  |
| speed_ratio_rule | 60 | local_speed_ratio | roc_auc | 0.4768 | 1321 |  |
| train_prevalence | 15 | none | balanced_accuracy | 0.5000 | 1396 |  |
| train_prevalence | 15 | none | brier_score | 0.1835 | 1396 |  |
| train_prevalence | 15 | none | f1 | 0.0000 | 1396 |  |
| train_prevalence | 15 | none | log_loss | 0.5553 | 1396 |  |
| train_prevalence | 15 | none | pr_auc | 0.2378 | 1396 |  |
| train_prevalence | 15 | none | roc_auc | 0.5000 | 1396 |  |
| train_prevalence | 30 | none | balanced_accuracy | 0.5000 | 1363 |  |
| train_prevalence | 30 | none | brier_score | 0.2500 | 1363 |  |
| train_prevalence | 30 | none | f1 | 0.0000 | 1363 |  |
| train_prevalence | 30 | none | log_loss | 0.6932 | 1363 |  |
| train_prevalence | 30 | none | pr_auc | 0.4615 | 1363 |  |
| train_prevalence | 30 | none | roc_auc | 0.5000 | 1363 |  |
| train_prevalence | 60 | none | balanced_accuracy | 0.5000 | 1321 |  |
| train_prevalence | 60 | none | brier_score | 0.1856 | 1321 |  |
| train_prevalence | 60 | none | f1 | 0.8666 | 1321 |  |
| train_prevalence | 60 | none | log_loss | 0.5596 | 1321 |  |
| train_prevalence | 60 | none | pr_auc | 0.7646 | 1321 |  |
| train_prevalence | 60 | none | roc_auc | 0.5000 | 1321 |  |

## Change from local features

Positive improvement means better performance after accounting for whether
the metric is higher-is-better or lower-is-better.

| model | horizon | feature set | metric | improvement |
|---|---:|---|---|---:|

## Interpretation limits

- Model selection used validation log loss; the test split was evaluated once.
- A metric delta is descriptive and is not a confidence interval or significance test.
- Missing context is imputed inside the train-fitted pipeline and missingness counts remain in metrics.
- Every compared model uses the same cohort with observed event-time speed_ratio.
- Final claims require team approval of the cohort, labels, spatial mapping and source coverage.
