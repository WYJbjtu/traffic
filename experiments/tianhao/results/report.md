# Tianhao真实30分钟探索性实验

EXPLORATORY — NOT APPROVED AS FINAL RESULTS

现有暂定恢复确认标签；固定长期划分；训练3,428、验证2,008、测试1,363个已知标签事件。

依据验证集log loss选择decision_tree，特征组local+history+flow+calendar。测试Macro-F1=0.6290、balanced accuracy=0.6384、ROC-AUC=0.7007、log loss=0.6264。这不是按测试分数挑选的模型。

近期速度变化及日历组带来较清楚的描述性改善。S2到S3包含时钟、星期、周末和假期，不可单独解释为假期效应。加入区域温度/风速没有一致改善：逻辑回归Macro-F1小幅提高，但log loss及ROC-AUC未同步改善；所选树未使用天气形成新的测试预测。未作显著性或因果声明。

## 完整测试结果

| model | feature_set | macro_f1 | balanced_accuracy | roc_auc | log_loss |
| --- | --- | --- | --- | --- | --- |
| decision_tree | local | 0.5823 | 0.5826 | 0.6277 | 0.6719 |
| decision_tree | local+history | 0.5966 | 0.5997 | 0.6276 | 0.6542 |
| decision_tree | local+history+flow | 0.6170 | 0.6200 | 0.6637 | 0.6549 |
| decision_tree | local+history+flow+calendar | 0.6290 | 0.6384 | 0.7007 | 0.6264 |
| decision_tree | local+history+flow+calendar+weather | 0.6290 | 0.6384 | 0.7007 | 0.6264 |
| logistic_regression | local | 0.4097 | 0.5005 | 0.5196 | 0.6903 |
| logistic_regression | local+history | 0.6202 | 0.6208 | 0.6672 | 0.6515 |
| logistic_regression | local+history+flow | 0.6241 | 0.6261 | 0.6686 | 0.6518 |
| logistic_regression | local+history+flow+calendar | 0.6395 | 0.6415 | 0.6896 | 0.6450 |
| logistic_regression | local+history+flow+calendar+weather | 0.6414 | 0.6428 | 0.6884 | 0.6457 |
| majority_class | none | 0.3500 | 0.5000 | 0.5000 | 16.6335 |
| speed_ratio_rule | local_speed_ratio | 0.4519 | 0.5091 | 0.4964 | NA |
| speed_trend_rule | history_rule | 0.4123 | 0.4152 | 0.3893 | NA |
| train_prevalence | none | 0.3500 | 0.5000 | 0.5000 | 0.6932 |

## 局限与未完成类别

24车道队列不代表全香港；跨年设备/方向稳定性、固定2023参考漂移、稀疏分箱、未知标签排除、道路间相关及恢复确认与proposal恢复开始的定义差异均未消除。京士柏是区域代理，不是各道路最近站。

雨量路径未建立历史重放；事故源抽查有历史消息但缺全时段回放与地点消歧；当前HKTB活动CSV含事后关闭说明且抽查无历史版本，因此未整合。邻路特征仍依赖人工验证。15/60分钟模型未运行。

## 核验

原始运行在代码提交 `4fd706e` 上通过127项仓库测试及237项真实源/时间/队列/预处理/预测重算核验。原始核验记录见 `verification.json`；它依赖留在本地的大型输入和拟合文件，不能仅凭本仓库的轻量文件重跑。上传后的指标重算与 Notebook 执行记录另见 `review_validation.json`。

## 修正记录

交付前发现并修正3个午夜事件的跨日流量读取问题。保持原特征计划、参数候选及测试规则，新建运行目录重算；旧运行保留且标为superseded/incomplete，不用于交付结果。
