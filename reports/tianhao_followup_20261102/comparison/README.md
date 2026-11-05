# 双方已保存预测的统一比较（2026-11-02）

**EXPLORATORY — NOT APPROVED AS FINAL RESULTS**

本次只重算已保存的预测，没有训练、选参、改标签或重新挑选展示模型；测试集此前已被查看。
所有输出保留 experiment、model、feature_set、horizon_min、split，不跨时限/特征组混排。

- 共 177 个实验臂/时限/split汇总，混淆矩阵逐行保存。
- 27 个双方同名实验臂的事件、标签和预测时间全部对齐。
- 新补算 135 个指标；其他现有指标均重算一致。

## 同一local+history+flow特征、30分钟、test（Member4四模型）

| 模型 | n | Macro-F1 | Balanced accuracy | ROC-AUC | TN / FP / FN / TP |
|---|---:|---:|---:|---:|---|
| decision_tree | 1363 | 0.6170 | 0.6200 | 0.6637 | 427 / 307 / 215 / 414 |
| hist_gradient_boosting | 1363 | 0.6480 | 0.6477 | 0.6959 | 512 / 222 / 253 / 376 |
| logistic_regression | 1363 | 0.6241 | 0.6261 | 0.6686 | 443 / 291 / 221 / 408 |
| random_forest | 1363 | 0.6524 | 0.6528 | 0.7040 | 488 / 246 / 226 / 403 |

## 使用与边界

- `common_30m_test.csv`保留双方相同三组特征的行，重复来源不会合并成新样本。
- `tianhao_external_30m_test.csv`单列日历/天气消融；Member4尚无对应外部特征模型，不能据此宣称四模型外部因素比较已完成。
- `all_metrics.csv`包含各时限和split，train成绩是样本内描述，不能当作泛化结果。
- `n_censored`为原预测表记录的split计数，不是从只含已知标签的预测表重新推断；未知标签不计入评估分母。
- PR-AUC沿用共享评估定义，即average precision。规则分数的Brier/log loss保持空值。
- 当前任务仍是恢复确认，未解决proposal恢复开始定义与经验证邻路特征问题。

复现：`uv run --locked python experiments/tianhao/compare_saved_runs.py --output-dir reports/local/unified-comparison-new`。
