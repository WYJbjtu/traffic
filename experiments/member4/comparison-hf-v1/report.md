# Feature-group model comparison

**Status: EXPLORATORY — NOT APPROVED AS FINAL RESULTS**

This report is generated from fingerprinted model outputs. Synthetic or
pending-approval measurements must not be presented as empirical findings.

## Evidence

- Dataset: `experiments/member4/event_features_hf.parquet`
- Dataset SHA-256: `8202a4b7afed01770dc362d9f71b2867d4f1db5d0f5d1e649a861c9517173c67`
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
| decision_tree | 15 | local+history | balanced_accuracy | 0.5057 | 1396 |  |
| decision_tree | 15 | local+history | brier_score | 0.1792 | 1396 |  |
| decision_tree | 15 | local+history | f1 | 0.0783 | 1396 |  |
| decision_tree | 15 | local+history | log_loss | 0.5365 | 1396 |  |
| decision_tree | 15 | local+history | pr_auc | 0.2989 | 1396 |  |
| decision_tree | 15 | local+history | roc_auc | 0.6246 | 1396 |  |
| decision_tree | 15 | local+history+flow | balanced_accuracy | 0.5141 | 1396 |  |
| decision_tree | 15 | local+history+flow | brier_score | 0.1767 | 1396 |  |
| decision_tree | 15 | local+history+flow | f1 | 0.0822 | 1396 |  |
| decision_tree | 15 | local+history+flow | log_loss | 0.5343 | 1396 |  |
| decision_tree | 15 | local+history+flow | pr_auc | 0.3326 | 1396 |  |
| decision_tree | 15 | local+history+flow | roc_auc | 0.6560 | 1396 |  |
| decision_tree | 30 | local | balanced_accuracy | 0.5826 | 1363 |  |
| decision_tree | 30 | local | brier_score | 0.2396 | 1363 |  |
| decision_tree | 30 | local | f1 | 0.5560 | 1363 |  |
| decision_tree | 30 | local | log_loss | 0.6719 | 1363 |  |
| decision_tree | 30 | local | pr_auc | 0.5480 | 1363 |  |
| decision_tree | 30 | local | roc_auc | 0.6277 | 1363 |  |
| decision_tree | 30 | local+history | balanced_accuracy | 0.5997 | 1363 |  |
| decision_tree | 30 | local+history | brier_score | 0.2325 | 1363 |  |
| decision_tree | 30 | local+history | f1 | 0.5221 | 1363 |  |
| decision_tree | 30 | local+history | log_loss | 0.6542 | 1363 |  |
| decision_tree | 30 | local+history | pr_auc | 0.5505 | 1363 |  |
| decision_tree | 30 | local+history | roc_auc | 0.6276 | 1363 |  |
| decision_tree | 30 | local+history+flow | balanced_accuracy | 0.6200 | 1363 |  |
| decision_tree | 30 | local+history+flow | brier_score | 0.2318 | 1363 |  |
| decision_tree | 30 | local+history+flow | f1 | 0.6133 | 1363 |  |
| decision_tree | 30 | local+history+flow | log_loss | 0.6549 | 1363 |  |
| decision_tree | 30 | local+history+flow | pr_auc | 0.5809 | 1363 |  |
| decision_tree | 30 | local+history+flow | roc_auc | 0.6637 | 1363 |  |
| decision_tree | 60 | local | balanced_accuracy | 0.5473 | 1321 |  |
| decision_tree | 60 | local | brier_score | 0.1791 | 1321 |  |
| decision_tree | 60 | local | f1 | 0.8507 | 1321 |  |
| decision_tree | 60 | local | log_loss | 0.6128 | 1321 |  |
| decision_tree | 60 | local | pr_auc | 0.8312 | 1321 |  |
| decision_tree | 60 | local | roc_auc | 0.6427 | 1321 |  |
| decision_tree | 60 | local+history | balanced_accuracy | 0.5000 | 1321 |  |
| decision_tree | 60 | local+history | brier_score | 0.1743 | 1321 |  |
| decision_tree | 60 | local+history | f1 | 0.8666 | 1321 |  |
| decision_tree | 60 | local+history | log_loss | 0.5263 | 1321 |  |
| decision_tree | 60 | local+history | pr_auc | 0.8388 | 1321 |  |
| decision_tree | 60 | local+history | roc_auc | 0.6558 | 1321 |  |
| decision_tree | 60 | local+history+flow | balanced_accuracy | 0.5000 | 1321 |  |
| decision_tree | 60 | local+history+flow | brier_score | 0.1805 | 1321 |  |
| decision_tree | 60 | local+history+flow | f1 | 0.8666 | 1321 |  |
| decision_tree | 60 | local+history+flow | log_loss | 0.5396 | 1321 |  |
| decision_tree | 60 | local+history+flow | pr_auc | 0.8274 | 1321 |  |
| decision_tree | 60 | local+history+flow | roc_auc | 0.6230 | 1321 |  |
| hist_gradient_boosting | 15 | local | balanced_accuracy | 0.5000 | 1396 |  |
| hist_gradient_boosting | 15 | local | brier_score | 0.1771 | 1396 |  |
| hist_gradient_boosting | 15 | local | f1 | 0.0000 | 1396 |  |
| hist_gradient_boosting | 15 | local | log_loss | 0.5367 | 1396 |  |
| hist_gradient_boosting | 15 | local | pr_auc | 0.3196 | 1396 |  |
| hist_gradient_boosting | 15 | local | roc_auc | 0.6227 | 1396 |  |
| hist_gradient_boosting | 15 | local+history | balanced_accuracy | 0.5109 | 1396 |  |
| hist_gradient_boosting | 15 | local+history | brier_score | 0.1718 | 1396 |  |
| hist_gradient_boosting | 15 | local+history | f1 | 0.0620 | 1396 |  |
| hist_gradient_boosting | 15 | local+history | log_loss | 0.5206 | 1396 |  |
| hist_gradient_boosting | 15 | local+history | pr_auc | 0.3637 | 1396 |  |
| hist_gradient_boosting | 15 | local+history | roc_auc | 0.6636 | 1396 |  |
| hist_gradient_boosting | 15 | local+history+flow | balanced_accuracy | 0.5108 | 1396 |  |
| hist_gradient_boosting | 15 | local+history+flow | brier_score | 0.1709 | 1396 |  |
| hist_gradient_boosting | 15 | local+history+flow | f1 | 0.0570 | 1396 |  |
| hist_gradient_boosting | 15 | local+history+flow | log_loss | 0.5160 | 1396 |  |
| hist_gradient_boosting | 15 | local+history+flow | pr_auc | 0.3659 | 1396 |  |
| hist_gradient_boosting | 15 | local+history+flow | roc_auc | 0.6763 | 1396 |  |
| hist_gradient_boosting | 30 | local | balanced_accuracy | 0.5850 | 1363 |  |
| hist_gradient_boosting | 30 | local | brier_score | 0.2371 | 1363 |  |
| hist_gradient_boosting | 30 | local | f1 | 0.5440 | 1363 |  |
| hist_gradient_boosting | 30 | local | log_loss | 0.6660 | 1363 |  |
| hist_gradient_boosting | 30 | local | pr_auc | 0.5640 | 1363 |  |
| hist_gradient_boosting | 30 | local | roc_auc | 0.6276 | 1363 |  |
| hist_gradient_boosting | 30 | local+history | balanced_accuracy | 0.6419 | 1363 |  |
| hist_gradient_boosting | 30 | local+history | brier_score | 0.2187 | 1363 |  |
| hist_gradient_boosting | 30 | local+history | f1 | 0.5966 | 1363 |  |
| hist_gradient_boosting | 30 | local+history | log_loss | 0.6250 | 1363 |  |
| hist_gradient_boosting | 30 | local+history | pr_auc | 0.6266 | 1363 |  |
| hist_gradient_boosting | 30 | local+history | roc_auc | 0.6968 | 1363 |  |
| hist_gradient_boosting | 30 | local+history+flow | balanced_accuracy | 0.6477 | 1363 |  |
| hist_gradient_boosting | 30 | local+history+flow | brier_score | 0.2197 | 1363 |  |
| hist_gradient_boosting | 30 | local+history+flow | f1 | 0.6129 | 1363 |  |
| hist_gradient_boosting | 30 | local+history+flow | log_loss | 0.6275 | 1363 |  |
| hist_gradient_boosting | 30 | local+history+flow | pr_auc | 0.6359 | 1363 |  |
| hist_gradient_boosting | 30 | local+history+flow | roc_auc | 0.6959 | 1363 |  |
| hist_gradient_boosting | 60 | local | balanced_accuracy | 0.5284 | 1321 |  |
| hist_gradient_boosting | 60 | local | brier_score | 0.1759 | 1321 |  |
| hist_gradient_boosting | 60 | local | f1 | 0.8580 | 1321 |  |
| hist_gradient_boosting | 60 | local | log_loss | 0.5360 | 1321 |  |
| hist_gradient_boosting | 60 | local | pr_auc | 0.8340 | 1321 |  |
| hist_gradient_boosting | 60 | local | roc_auc | 0.6505 | 1321 |  |
| hist_gradient_boosting | 60 | local+history | balanced_accuracy | 0.5570 | 1321 |  |
| hist_gradient_boosting | 60 | local+history | brier_score | 0.1671 | 1321 |  |
| hist_gradient_boosting | 60 | local+history | f1 | 0.8633 | 1321 |  |
| hist_gradient_boosting | 60 | local+history | log_loss | 0.5103 | 1321 |  |
| hist_gradient_boosting | 60 | local+history | pr_auc | 0.8607 | 1321 |  |
| hist_gradient_boosting | 60 | local+history | roc_auc | 0.6853 | 1321 |  |
| hist_gradient_boosting | 60 | local+history+flow | balanced_accuracy | 0.5569 | 1321 |  |
| hist_gradient_boosting | 60 | local+history+flow | brier_score | 0.1656 | 1321 |  |
| hist_gradient_boosting | 60 | local+history+flow | f1 | 0.8644 | 1321 |  |
| hist_gradient_boosting | 60 | local+history+flow | log_loss | 0.5060 | 1321 |  |
| hist_gradient_boosting | 60 | local+history+flow | pr_auc | 0.8660 | 1321 |  |
| hist_gradient_boosting | 60 | local+history+flow | roc_auc | 0.6900 | 1321 |  |
| logistic_regression | 15 | local | balanced_accuracy | 0.5000 | 1396 |  |
| logistic_regression | 15 | local | brier_score | 0.1814 | 1396 |  |
| logistic_regression | 15 | local | f1 | 0.0000 | 1396 |  |
| logistic_regression | 15 | local | log_loss | 0.5490 | 1396 |  |
| logistic_regression | 15 | local | pr_auc | 0.2663 | 1396 |  |
| logistic_regression | 15 | local | roc_auc | 0.5446 | 1396 |  |
| logistic_regression | 15 | local+history | balanced_accuracy | 0.5108 | 1396 |  |
| logistic_regression | 15 | local+history | brier_score | 0.1753 | 1396 |  |
| logistic_regression | 15 | local+history | f1 | 0.0570 | 1396 |  |
| logistic_regression | 15 | local+history | log_loss | 0.5327 | 1396 |  |
| logistic_regression | 15 | local+history | pr_auc | 0.3358 | 1396 |  |
| logistic_regression | 15 | local+history | roc_auc | 0.6294 | 1396 |  |
| logistic_regression | 15 | local+history+flow | balanced_accuracy | 0.5129 | 1396 |  |
| logistic_regression | 15 | local+history+flow | brier_score | 0.1745 | 1396 |  |
| logistic_regression | 15 | local+history+flow | f1 | 0.0676 | 1396 |  |
| logistic_regression | 15 | local+history+flow | log_loss | 0.5301 | 1396 |  |
| logistic_regression | 15 | local+history+flow | pr_auc | 0.3398 | 1396 |  |
| logistic_regression | 15 | local+history+flow | roc_auc | 0.6354 | 1396 |  |
| logistic_regression | 30 | local | balanced_accuracy | 0.5005 | 1363 |  |
| logistic_regression | 30 | local | brier_score | 0.2486 | 1363 |  |
| logistic_regression | 30 | local | f1 | 0.1404 | 1363 |  |
| logistic_regression | 30 | local | log_loss | 0.6903 | 1363 |  |
| logistic_regression | 30 | local | pr_auc | 0.4726 | 1363 |  |
| logistic_regression | 30 | local | roc_auc | 0.5196 | 1363 |  |
| logistic_regression | 30 | local+history | balanced_accuracy | 0.6208 | 1363 |  |
| logistic_regression | 30 | local+history | brier_score | 0.2293 | 1363 |  |
| logistic_regression | 30 | local+history | f1 | 0.5988 | 1363 |  |
| logistic_regression | 30 | local+history | log_loss | 0.6515 | 1363 |  |
| logistic_regression | 30 | local+history | pr_auc | 0.6058 | 1363 |  |
| logistic_regression | 30 | local+history | roc_auc | 0.6672 | 1363 |  |
| logistic_regression | 30 | local+history+flow | balanced_accuracy | 0.6261 | 1363 |  |
| logistic_regression | 30 | local+history+flow | brier_score | 0.2294 | 1363 |  |
| logistic_regression | 30 | local+history+flow | f1 | 0.6145 | 1363 |  |
| logistic_regression | 30 | local+history+flow | log_loss | 0.6518 | 1363 |  |
| logistic_regression | 30 | local+history+flow | pr_auc | 0.6048 | 1363 |  |
| logistic_regression | 30 | local+history+flow | roc_auc | 0.6686 | 1363 |  |
| logistic_regression | 60 | local | balanced_accuracy | 0.5000 | 1321 |  |
| logistic_regression | 60 | local | brier_score | 0.1827 | 1321 |  |
| logistic_regression | 60 | local | f1 | 0.8666 | 1321 |  |
| logistic_regression | 60 | local | log_loss | 0.5524 | 1321 |  |
| logistic_regression | 60 | local | pr_auc | 0.7791 | 1321 |  |
| logistic_regression | 60 | local | roc_auc | 0.5311 | 1321 |  |
| logistic_regression | 60 | local+history | balanced_accuracy | 0.5107 | 1321 |  |
| logistic_regression | 60 | local+history | brier_score | 0.1746 | 1321 |  |
| logistic_regression | 60 | local+history | f1 | 0.8488 | 1321 |  |
| logistic_regression | 60 | local+history | log_loss | 0.5288 | 1321 |  |
| logistic_regression | 60 | local+history | pr_auc | 0.8446 | 1321 |  |
| logistic_regression | 60 | local+history | roc_auc | 0.6530 | 1321 |  |
| logistic_regression | 60 | local+history+flow | balanced_accuracy | 0.5124 | 1321 |  |
| logistic_regression | 60 | local+history+flow | brier_score | 0.1731 | 1321 |  |
| logistic_regression | 60 | local+history+flow | f1 | 0.8542 | 1321 |  |
| logistic_regression | 60 | local+history+flow | log_loss | 0.5254 | 1321 |  |
| logistic_regression | 60 | local+history+flow | pr_auc | 0.8462 | 1321 |  |
| logistic_regression | 60 | local+history+flow | roc_auc | 0.6512 | 1321 |  |
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
| random_forest | 15 | local+history | balanced_accuracy | 0.5093 | 1396 |  |
| random_forest | 15 | local+history | brier_score | 0.1703 | 1396 |  |
| random_forest | 15 | local+history | f1 | 0.0514 | 1396 |  |
| random_forest | 15 | local+history | log_loss | 0.5165 | 1396 |  |
| random_forest | 15 | local+history | pr_auc | 0.3761 | 1396 |  |
| random_forest | 15 | local+history | roc_auc | 0.6619 | 1396 |  |
| random_forest | 15 | local+history+flow | balanced_accuracy | 0.5071 | 1396 |  |
| random_forest | 15 | local+history+flow | brier_score | 0.1696 | 1396 |  |
| random_forest | 15 | local+history+flow | f1 | 0.0296 | 1396 |  |
| random_forest | 15 | local+history+flow | log_loss | 0.5128 | 1396 |  |
| random_forest | 15 | local+history+flow | pr_auc | 0.3812 | 1396 |  |
| random_forest | 15 | local+history+flow | roc_auc | 0.6642 | 1396 |  |
| random_forest | 30 | local | balanced_accuracy | 0.5873 | 1363 |  |
| random_forest | 30 | local | brier_score | 0.2368 | 1363 |  |
| random_forest | 30 | local | f1 | 0.5428 | 1363 |  |
| random_forest | 30 | local | log_loss | 0.6655 | 1363 |  |
| random_forest | 30 | local | pr_auc | 0.5638 | 1363 |  |
| random_forest | 30 | local | roc_auc | 0.6276 | 1363 |  |
| random_forest | 30 | local+history | balanced_accuracy | 0.6391 | 1363 |  |
| random_forest | 30 | local+history | brier_score | 0.2203 | 1363 |  |
| random_forest | 30 | local+history | f1 | 0.5835 | 1363 |  |
| random_forest | 30 | local+history | log_loss | 0.6296 | 1363 |  |
| random_forest | 30 | local+history | pr_auc | 0.6116 | 1363 |  |
| random_forest | 30 | local+history | roc_auc | 0.6964 | 1363 |  |
| random_forest | 30 | local+history+flow | balanced_accuracy | 0.6528 | 1363 |  |
| random_forest | 30 | local+history+flow | brier_score | 0.2189 | 1363 |  |
| random_forest | 30 | local+history+flow | f1 | 0.6307 | 1363 |  |
| random_forest | 30 | local+history+flow | log_loss | 0.6263 | 1363 |  |
| random_forest | 30 | local+history+flow | pr_auc | 0.6323 | 1363 |  |
| random_forest | 30 | local+history+flow | roc_auc | 0.7040 | 1363 |  |
| random_forest | 60 | local | balanced_accuracy | 0.5493 | 1321 |  |
| random_forest | 60 | local | brier_score | 0.1768 | 1321 |  |
| random_forest | 60 | local | f1 | 0.8528 | 1321 |  |
| random_forest | 60 | local | log_loss | 0.5326 | 1321 |  |
| random_forest | 60 | local | pr_auc | 0.8505 | 1321 |  |
| random_forest | 60 | local | roc_auc | 0.6584 | 1321 |  |
| random_forest | 60 | local+history | balanced_accuracy | 0.5134 | 1321 |  |
| random_forest | 60 | local+history | brier_score | 0.1662 | 1321 |  |
| random_forest | 60 | local+history | f1 | 0.8652 | 1321 |  |
| random_forest | 60 | local+history | log_loss | 0.5084 | 1321 |  |
| random_forest | 60 | local+history | pr_auc | 0.8653 | 1321 |  |
| random_forest | 60 | local+history | roc_auc | 0.6974 | 1321 |  |
| random_forest | 60 | local+history+flow | balanced_accuracy | 0.5576 | 1321 |  |
| random_forest | 60 | local+history+flow | brier_score | 0.1638 | 1321 |  |
| random_forest | 60 | local+history+flow | f1 | 0.8626 | 1321 |  |
| random_forest | 60 | local+history+flow | log_loss | 0.5010 | 1321 |  |
| random_forest | 60 | local+history+flow | pr_auc | 0.8750 | 1321 |  |
| random_forest | 60 | local+history+flow | roc_auc | 0.6999 | 1321 |  |
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
| decision_tree | 15 | local+history | balanced_accuracy | 0.0013 |
| decision_tree | 15 | local+history+flow | balanced_accuracy | 0.0098 |
| decision_tree | 15 | local+history | brier_score | 0.0018 |
| decision_tree | 15 | local+history+flow | brier_score | 0.0043 |
| decision_tree | 15 | local+history | f1 | 0.0438 |
| decision_tree | 15 | local+history+flow | f1 | 0.0477 |
| decision_tree | 15 | local+history | log_loss | 0.0104 |
| decision_tree | 15 | local+history+flow | log_loss | 0.0127 |
| decision_tree | 15 | local+history | pr_auc | 0.0357 |
| decision_tree | 15 | local+history+flow | pr_auc | 0.0694 |
| decision_tree | 15 | local+history | roc_auc | 0.0639 |
| decision_tree | 15 | local+history+flow | roc_auc | 0.0953 |
| decision_tree | 30 | local+history | balanced_accuracy | 0.0171 |
| decision_tree | 30 | local+history+flow | balanced_accuracy | 0.0374 |
| decision_tree | 30 | local+history | brier_score | 0.0071 |
| decision_tree | 30 | local+history+flow | brier_score | 0.0078 |
| decision_tree | 30 | local+history | f1 | -0.0339 |
| decision_tree | 30 | local+history+flow | f1 | 0.0573 |
| decision_tree | 30 | local+history | log_loss | 0.0176 |
| decision_tree | 30 | local+history+flow | log_loss | 0.0170 |
| decision_tree | 30 | local+history | pr_auc | 0.0025 |
| decision_tree | 30 | local+history+flow | pr_auc | 0.0329 |
| decision_tree | 30 | local+history | roc_auc | -0.0000 |
| decision_tree | 30 | local+history+flow | roc_auc | 0.0360 |
| decision_tree | 60 | local+history | balanced_accuracy | -0.0473 |
| decision_tree | 60 | local+history+flow | balanced_accuracy | -0.0473 |
| decision_tree | 60 | local+history | brier_score | 0.0049 |
| decision_tree | 60 | local+history+flow | brier_score | -0.0013 |
| decision_tree | 60 | local+history | f1 | 0.0159 |
| decision_tree | 60 | local+history+flow | f1 | 0.0159 |
| decision_tree | 60 | local+history | log_loss | 0.0865 |
| decision_tree | 60 | local+history+flow | log_loss | 0.0732 |
| decision_tree | 60 | local+history | pr_auc | 0.0076 |
| decision_tree | 60 | local+history+flow | pr_auc | -0.0038 |
| decision_tree | 60 | local+history | roc_auc | 0.0131 |
| decision_tree | 60 | local+history+flow | roc_auc | -0.0197 |
| hist_gradient_boosting | 15 | local+history | balanced_accuracy | 0.0109 |
| hist_gradient_boosting | 15 | local+history+flow | balanced_accuracy | 0.0108 |
| hist_gradient_boosting | 15 | local+history | brier_score | 0.0053 |
| hist_gradient_boosting | 15 | local+history+flow | brier_score | 0.0062 |
| hist_gradient_boosting | 15 | local+history | f1 | 0.0620 |
| hist_gradient_boosting | 15 | local+history+flow | f1 | 0.0570 |
| hist_gradient_boosting | 15 | local+history | log_loss | 0.0161 |
| hist_gradient_boosting | 15 | local+history+flow | log_loss | 0.0207 |
| hist_gradient_boosting | 15 | local+history | pr_auc | 0.0440 |
| hist_gradient_boosting | 15 | local+history+flow | pr_auc | 0.0463 |
| hist_gradient_boosting | 15 | local+history | roc_auc | 0.0409 |
| hist_gradient_boosting | 15 | local+history+flow | roc_auc | 0.0536 |
| hist_gradient_boosting | 30 | local+history | balanced_accuracy | 0.0569 |
| hist_gradient_boosting | 30 | local+history+flow | balanced_accuracy | 0.0627 |
| hist_gradient_boosting | 30 | local+history | brier_score | 0.0184 |
| hist_gradient_boosting | 30 | local+history+flow | brier_score | 0.0174 |
| hist_gradient_boosting | 30 | local+history | f1 | 0.0527 |
| hist_gradient_boosting | 30 | local+history+flow | f1 | 0.0689 |
| hist_gradient_boosting | 30 | local+history | log_loss | 0.0409 |
| hist_gradient_boosting | 30 | local+history+flow | log_loss | 0.0385 |
| hist_gradient_boosting | 30 | local+history | pr_auc | 0.0626 |
| hist_gradient_boosting | 30 | local+history+flow | pr_auc | 0.0719 |
| hist_gradient_boosting | 30 | local+history | roc_auc | 0.0692 |
| hist_gradient_boosting | 30 | local+history+flow | roc_auc | 0.0683 |
| hist_gradient_boosting | 60 | local+history | balanced_accuracy | 0.0286 |
| hist_gradient_boosting | 60 | local+history+flow | balanced_accuracy | 0.0284 |
| hist_gradient_boosting | 60 | local+history | brier_score | 0.0088 |
| hist_gradient_boosting | 60 | local+history+flow | brier_score | 0.0103 |
| hist_gradient_boosting | 60 | local+history | f1 | 0.0052 |
| hist_gradient_boosting | 60 | local+history+flow | f1 | 0.0064 |
| hist_gradient_boosting | 60 | local+history | log_loss | 0.0257 |
| hist_gradient_boosting | 60 | local+history+flow | log_loss | 0.0300 |
| hist_gradient_boosting | 60 | local+history | pr_auc | 0.0266 |
| hist_gradient_boosting | 60 | local+history+flow | pr_auc | 0.0320 |
| hist_gradient_boosting | 60 | local+history | roc_auc | 0.0348 |
| hist_gradient_boosting | 60 | local+history+flow | roc_auc | 0.0395 |
| logistic_regression | 15 | local+history | balanced_accuracy | 0.0108 |
| logistic_regression | 15 | local+history+flow | balanced_accuracy | 0.0129 |
| logistic_regression | 15 | local+history | brier_score | 0.0060 |
| logistic_regression | 15 | local+history+flow | brier_score | 0.0069 |
| logistic_regression | 15 | local+history | f1 | 0.0570 |
| logistic_regression | 15 | local+history+flow | f1 | 0.0676 |
| logistic_regression | 15 | local+history | log_loss | 0.0163 |
| logistic_regression | 15 | local+history+flow | log_loss | 0.0189 |
| logistic_regression | 15 | local+history | pr_auc | 0.0695 |
| logistic_regression | 15 | local+history+flow | pr_auc | 0.0734 |
| logistic_regression | 15 | local+history | roc_auc | 0.0848 |
| logistic_regression | 15 | local+history+flow | roc_auc | 0.0907 |
| logistic_regression | 30 | local+history | balanced_accuracy | 0.1203 |
| logistic_regression | 30 | local+history+flow | balanced_accuracy | 0.1256 |
| logistic_regression | 30 | local+history | brier_score | 0.0194 |
| logistic_regression | 30 | local+history+flow | brier_score | 0.0192 |
| logistic_regression | 30 | local+history | f1 | 0.4584 |
| logistic_regression | 30 | local+history+flow | f1 | 0.4741 |
| logistic_regression | 30 | local+history | log_loss | 0.0388 |
| logistic_regression | 30 | local+history+flow | log_loss | 0.0386 |
| logistic_regression | 30 | local+history | pr_auc | 0.1333 |
| logistic_regression | 30 | local+history+flow | pr_auc | 0.1322 |
| logistic_regression | 30 | local+history | roc_auc | 0.1476 |
| logistic_regression | 30 | local+history+flow | roc_auc | 0.1490 |
| logistic_regression | 60 | local+history | balanced_accuracy | 0.0107 |
| logistic_regression | 60 | local+history+flow | balanced_accuracy | 0.0124 |
| logistic_regression | 60 | local+history | brier_score | 0.0081 |
| logistic_regression | 60 | local+history+flow | brier_score | 0.0095 |
| logistic_regression | 60 | local+history | f1 | -0.0178 |
| logistic_regression | 60 | local+history+flow | f1 | -0.0123 |
| logistic_regression | 60 | local+history | log_loss | 0.0236 |
| logistic_regression | 60 | local+history+flow | log_loss | 0.0270 |
| logistic_regression | 60 | local+history | pr_auc | 0.0655 |
| logistic_regression | 60 | local+history+flow | pr_auc | 0.0671 |
| logistic_regression | 60 | local+history | roc_auc | 0.1219 |
| logistic_regression | 60 | local+history+flow | roc_auc | 0.1201 |
| random_forest | 15 | local+history | balanced_accuracy | 0.0093 |
| random_forest | 15 | local+history+flow | balanced_accuracy | 0.0071 |
| random_forest | 15 | local+history | brier_score | 0.0068 |
| random_forest | 15 | local+history+flow | brier_score | 0.0075 |
| random_forest | 15 | local+history | f1 | 0.0514 |
| random_forest | 15 | local+history+flow | f1 | 0.0296 |
| random_forest | 15 | local+history | log_loss | 0.0187 |
| random_forest | 15 | local+history+flow | log_loss | 0.0224 |
| random_forest | 15 | local+history | pr_auc | 0.0657 |
| random_forest | 15 | local+history+flow | pr_auc | 0.0709 |
| random_forest | 15 | local+history | roc_auc | 0.0375 |
| random_forest | 15 | local+history+flow | roc_auc | 0.0399 |
| random_forest | 30 | local+history | balanced_accuracy | 0.0519 |
| random_forest | 30 | local+history+flow | balanced_accuracy | 0.0655 |
| random_forest | 30 | local+history | brier_score | 0.0165 |
| random_forest | 30 | local+history+flow | brier_score | 0.0179 |
| random_forest | 30 | local+history | f1 | 0.0408 |
| random_forest | 30 | local+history+flow | f1 | 0.0879 |
| random_forest | 30 | local+history | log_loss | 0.0359 |
| random_forest | 30 | local+history+flow | log_loss | 0.0392 |
| random_forest | 30 | local+history | pr_auc | 0.0478 |
| random_forest | 30 | local+history+flow | pr_auc | 0.0685 |
| random_forest | 30 | local+history | roc_auc | 0.0689 |
| random_forest | 30 | local+history+flow | roc_auc | 0.0764 |
| random_forest | 60 | local+history | balanced_accuracy | -0.0360 |
| random_forest | 60 | local+history+flow | balanced_accuracy | 0.0083 |
| random_forest | 60 | local+history | brier_score | 0.0106 |
| random_forest | 60 | local+history+flow | brier_score | 0.0130 |
| random_forest | 60 | local+history | f1 | 0.0124 |
| random_forest | 60 | local+history+flow | f1 | 0.0099 |
| random_forest | 60 | local+history | log_loss | 0.0243 |
| random_forest | 60 | local+history+flow | log_loss | 0.0316 |
| random_forest | 60 | local+history | pr_auc | 0.0148 |
| random_forest | 60 | local+history+flow | pr_auc | 0.0245 |
| random_forest | 60 | local+history | roc_auc | 0.0390 |
| random_forest | 60 | local+history+flow | roc_auc | 0.0415 |

## Interpretation limits

- Model selection used validation log loss; the test split was evaluated once.
- A metric delta is descriptive and is not a confidence interval or significance test.
- Missing context is imputed inside the train-fitted pipeline and missingness counts remain in metrics.
- Every compared model uses the same cohort with observed event-time speed_ratio.
- Final claims require team approval of the cohort, labels, spatial mapping and source coverage.
