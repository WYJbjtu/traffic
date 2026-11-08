# Poster Q&A

## 1. 为什么用图而非最近邻？ / Why a graph rather than geographic proximity?

中：道路拓扑与方向可区分平行路、立交和潜在上下游，但当前推断仍会错；同维度对照差异小且地理覆盖不同，不能宣称图已被证明更优。

EN: Topology and direction can distinguish proximity from plausible connectivity. Our inferred graph can still be wrong. Matched-summary controls show small directed–pooled differences and unequal geographic coverage, not a definitive proof of superiority.

## 2. 是否用了GNN？ / Did you use a GNN?

中：没有。使用真实图的工程化邻居特征加LR/RF/实际XGBoost/HGB。

EN: No. We used engineered graph summaries with logistic regression, random forest, actual XGBoost and HistGradientBoosting.

## 3. 如何防未来泄漏？ / How is future leakage prevented?

中：双键连接，观测/可用时间不晚于预测、天气年龄≤60分钟、邻路年龄≤10分钟、训练拟合、时间分组与冻结purge。2026地图本身仍是回溯代理，不能说全部输入均历史已验证。

EN: Event/time joins, observation and availability cutoffs, age limits, training-only fitting and frozen purged temporal splits protect dynamic features. The 2026 static graph is explicitly retrospective and not historically certified.

## 4. 恢复开始与确认区别？ / Start versus confirmation?

中：开始是连续高箱的第一箱；确认需要后续高箱见证。旧实验以确认时刻判30分钟；新Proposal以开始及随后持续条件判定，不能换名字套分数。

EN: Start is the first high-bin endpoint; confirmation is observed only after the sustaining sequence. They can fall on different sides of the deadline. Our scores belong only to confirmation.

## 5. 2026路网用于早期事件？ / Why use a 2026 network for earlier events?

中：作为有明确限制的回溯推断代理；无法核实历史变更、硬件和合法转向。P3未批准。

EN: It is a limited retrospective proxy, not proof of historical road or detector identity. The verified historical-network/P3 gate remains NO-GO.

## 6. 稀疏数据持续恢复？ / How is persistence defined with sparse data?

中：旧版每5分钟箱至少两个有效正流量槽，三高箱确认，缺口删失。不是完整连续观测。新strict10与sampled2另有规则不能混接。

EN: Three consecutive usable high bins establish sampled confirmation. Gaps censor follow-up. Sparse slots do not establish continuous physical recovery. Proposal strict10 and sampled2 are separate definitions.

## 7. 是否控制时间天气？ / Are time and weather controlled?

中：主比较F3/F7已含8个日历和6个温度/风速质量字段；无雨量、事故或活动控制，不代表所有混杂已排除。

EN: Yes, for the specified calendar and King’s Park temperature/wind covariates. This is not control of all weather, incidents, events, or unmeasured confounding.

## 8. Bootstrap如何解释？ / What does the Bootstrap interval mean?

中：同检测器事件成组抽、两臂同抽、重复抽中按重复权重；44群，1000次。固定模型，不包括训练不确定性；共享邻居跨群依赖与多重比较未完全处理。

EN: Both arms share each draw, repeating all events when a detector is sampled again. It measures fixed-model test uncertainty. Shared neighbors and unadjusted multiple comparisons limit interpretation.

## 9. 已完成与未完成？ / What is completed versus future work?

中：32臂主实验、6臂结构对照、统计、图表已完成；新Proposal数据标签已实现但采用/模型未完成；P3、部署、未来盲测未完成。

EN: The 32-arm confirmation study, six matched structural controls, audits and figures are complete. New Proposal labels exist, but adoption and models are pending; P3, deployment and future blind validation are not delivered.

## 10. 最高AUC是唯一最佳模型吗？ / Is the highest test AUC the best model?

中：不是预先选定唯一最佳；展示全矩阵和多指标，候选仅按验证log loss选。

EN: No test-selected winner is claimed. Candidate selection used validation log loss, and all algorithms and trade-offs are reported.

## 11. 原始天气是否全部重建？ / Did you independently rebuild all weather archives?

中：没有。核验了已交付特征、来源元数据、源快照和值、冻结生产者重建记录及示例原字节；90月ZIP只有URL/SHA链。

EN: No. We authenticated the delivered features, source snapshots, metadata, producer reconstruction records and supplied raw examples. We did not independently re-download all 90 monthly archives.

## 12. 为什么不报accuracy为主？ / Why not focus on accuracy?

中：测试正例17.5%，多数负类可使accuracy高；同时报告AUC、AP、Macro-F1、Recall、损失和混淆矩阵。

EN: Only 17.5% of test events are positive. We report ranking, class-sensitive, calibration and confusion metrics rather than relying on majority-dominated accuracy.
