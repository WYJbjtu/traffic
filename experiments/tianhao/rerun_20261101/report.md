# New real-data notebook rerun

EXPLORATORY — NOT APPROVED AS FINAL RESULTS

本次重新训练的验证集选定展示模型为 **decision_tree / local+history+flow+calendar**。
已知测试标签 **1,363** 个；Macro-F1 **0.6290**、balanced accuracy **0.6384**、ROC-AUC **0.7007**。

从S3加天气到S4，逻辑回归Macro-F1变化 **+0.0019**，
树Macro-F1变化 **+0.0000**。
这只是既定队列上的描述性变化，不能解释为天气因素的显著或因果影响。

所有成绩对应**恢复确认标签**。要回答proposal的恢复开始问题，须先由全组统一定义和随访窗口后重新生成标签、冻结划分并重跑。