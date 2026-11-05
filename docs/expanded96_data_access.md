# 96车道真实长窗口数据：完成与交接

已完成45个月官方ZIP及2026年10月1日边界核验、426候选连续性审计、96车道序列与事件生成、测试及独立Release发布。没有训练模型。

- 96车道：35,782,769行五分钟数据、30,452个恢复事件。
- 事件时间分组：训练14,290、验证8,557、测试7,605；未知标签按时限分别保留。
- 426候选质量：583,194个车道日（426×1369），45个月；原24车道一月参考逐项一致。
- 178项测试通过，1个警告，退出码0。最终独立核验见[final_verification.json](../reports/lane_expansion_execution_20261102/final96/final_verification.json)。

下载[96车道Release](https://github.com/WYJbjtu/traffic/releases/tag/data-expanded-96-2023-2026-v1)中的`HK_Traffic_Expanded_96_Prepared_Data_v1.zip`（870,121,429字节）和相邻SHA文件。组员无需访问数据持有人的D盘。

整包SHA-256：`f5be559a6ad8df69e68fbc382fb609d13fdae40aa044c9d1fe4d7e3b2253b6b8`。已核对GitHub附件大小及服务器digest与本地一致。解压到独立数据目录，读取`processed/cohort_bins.parquet`和`processed/events.parquet`，按`SHARED_DATA_MANIFEST.json`校验包内文件。自动生成的Source code ZIP不含数据。47GB原始档案、426巨大中间表及机器环境不包含在发布包中。

[真实质量报告](../reports/lane_expansion_execution_20261102/final96/report_zh.md)和同目录CSV提供逐月、逐年、时间分组、缺口、身份及速度漂移诊断。报告中的`../pilot96...`等路径指持有人的本地expansion布局；共享ZIP使用上面的processed路径。冻结配置的status仍保留运行前candidate描述，以保留输入哈希；当前完成证据是manifest、最终核验和Release，不能把旧status解释为数据尚未生成。

426候选有效30秒覆盖：2023年79.37%、2024年61.88%、2025年58.82%、2026年1–9月49.05%；五分钟可用箱比例为90.48%、88.64%、90.93%、86.26%。这是不同采样粒度的指标，不能混用。设备身份变化、缺口及参考漂移仍需小组复核，质量诊断不能用于看过验证/测试期后重选队列。

旧[24车道Release](https://github.com/WYJbjtu/traffic/releases/tag/data-long-window-2023-2026-v1)（7,597事件）和73事件短窗保持独立，不能与96数据混算。此次仍沿用冻结阈值、参考和分组，标签表示观测到的持续恢复确认；未知不是负例。

## 四人接手

1. 数据负责人：核对包内SHA、字段与未知标签，说明观测行数和独立事件数的区别；原始档案仍在持有人的数据根raw目录。
2. 空间负责人：按96检测器/方向/车道核验路网版本和上下游连接，复核车道身份；数据完成不代表空间匹配已批准。
3. 外部因素负责人：对新事件按预测时间匹配天气/日历/可核实事件，保留可获取时间，防止事后信息泄漏。
4. 模型负责人：按冻结时间分组分别评估15/30/60分钟任务，排除对应未知标签，训练期拟合预处理；恢复时间、标签、成熟时间和事后质量统计不能作为预测特征。

完整运行包含数次用户主动暂停；每次恢复核验哈希并保留partial及历史attempt。报告路径修复不改变科学口径。详细退出码见同目录run_status.json，逐单元输出哈希见pilot_manifest及原始checkpoint。
