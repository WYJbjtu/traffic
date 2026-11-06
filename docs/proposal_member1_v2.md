# Proposal 数据职责补齐：独立版本 v2

状态：实现与真实数据运行记录随本 PR 提交；科学定义与物理车道身份仍需共同审核。旧 96 车道 Release、旧标签、旧模型指标保持原样。本版本没有训练模型。

## 已核对的原始依据

用户提供的一页原始 Proposal，SHA-256 `c8849206fccae736e1b2075ee37cbcf494b84057b9a8d1d332de4f57d04693d6`，58,292 字节。第 2 节明确要求：按检测器及方向形成五分钟记录；正常速度来自过去相似时段和星期；拥堵为低于正常速度 50% 至少十分钟；未来三十分钟内开始恢复，且达到正常速度 80% 后保持十分钟；在第三十分钟开始需观测至第四十分钟。训练 2023–24、验证 2025、测试 2026 年 1–9 月。第 3 节 Ye LI 负责采集、清洗、汇总、事件标签、质量和阈值影响。全员共同审核标签和空间匹配。

## 本版本的方法选择（供评审，不冒充 Proposal 已规定）

- 保留原冻结 96 个检测器/方向的队列，不根据验证/测试期质量或指标重选。对这些方向，使用 2023 年 1 月 1–7 日观察到的全部车道身份作为冻结库存。不是把原来的一条选中车道改名为检测器总量。新出现或缺失的车道会破坏完整性；同名跨年不代表硬件连续认证。
- 从完整 1,371 个 capture Parquet 分区复用原始字段。验证每个文件的 SHA，对其 source ZIP SHA 和原始生成身份保留完整链。日分区只考虑观测日相交的捕获文件，不按捕获日期误分午夜观测。
- 五分钟右闭区间；固定箱末 +10 分钟为保守可用时刻。先排除晚于该时刻的捕获，再按原始签名消除重复、隔离冲突。不能让后来修订污染先前特征。
- 同一三十秒时槽要求冻结的全部车道在场、有效，且速度、车辆计数和占有率均可用。总计数为各车道源计数之和；速度为按源计数加权的车道速度；占有率为等车道权重平均。五分钟速度为完整、正流量时槽速度的中位数，占有率为完整时槽平均。总计数只加总完整观测时槽，不按覆盖率放大，不称为每小时流率。
- 主版本要求十个完整三十秒时槽，且至少两个正流量时槽；零车辆计数仍是合法零值，无车时速度不参与恢复判断。`volume_observed_count` 与 `complete_30s_slots` 分列。缺失不是零。即使完整采样，仍只是采样观测的持续性，不能证明采样间的物理连续状态。
- 参考预留 2023 年 1–2 月，只使用当时已可用的观测。按 HKT 的相同星期几、相同小时计算 p85，至少十二个有效箱、三个不同日期，无跨时段或全局回退。固定参考不借助验证/测试重新拟合。2023 年 3 月后才生成事件；因此不声称整个 2023 年都参与训练。这是可审核的实现选择，并非 Proposal 唯一允许的参考方案。
- 两个连续五分钟低箱（严格小于 0.5）确认拥堵，先前必须见证恢复状态；按完整箱可用时间预测，每个事件一次。恢复为三个连续高箱端点（相隔十分钟），从第一高箱端点判断是否在未来三十分钟以内；完整观测后才赋正例。预测前已开始的恢复单列未知。负例需持续观察至 horizon +10 分钟；缺口、失效、参考缺失或数据结束不足均保留未知。
- 保留 15/60 分钟作为附加标签，30 分钟是 Proposal 主目标。事件不混入旧 lane-level ID；按独立版本生成稳定 ID。完整最大结果窗口加捕获闭合至少为 prediction +80 分钟，跨分组边界排除；输入窗也不能跨边界。
- 在训练期 2023 年 3–12 月描述性检查 0.4/0.5/0.6 × 0.7/0.8/0.9 九组阈值，不看模型测试表现选阈值；主阈值保留 Proposal 初值。本检查输出事件数和正/负/未知变化，不冒充模型敏感性实验。

## 覆盖敏感性：两个口径并列，不自动挑选

完整十槽是本次保守实现选择，不是原 Proposal 明文规定。真实执行得到 strict10 **700 事件：训练 691、验证 9、测试 0**，不能据此执行约定的跨年模型比较。这是可行性限制，不能拿旧版 30,452 个事件填补。

另提供 `sampled2/` 独立观测口径：每箱至少两个完整且正流量的三十秒槽，仍要求冻结的全部车道同时在场、有效，无冲突和新车道。没有填补其他缺失时槽；重新拟合训练期参考、重新生成标签、使用独立事件 ID 命名空间，并重新计算训练阈值敏感性。它提供**采样观测的持续恢复开始**，不声称物理连续性。两套结果同时发布，不因为测试期样本更多就默认为后者已获科学批准；需团队依据采样频率、误差和研究表述选择。`sampled2` 的参考/事件不能与 strict10 混用。

## 接口与复现

Python 3.12，`uv sync --locked`。原始源分区由资料持有人保留，巨型源表不进 Git。

```text
uv run --locked python -m scripts.prepare_proposal_data --capture-root <verified-continuity426>/processed/lane_snapshots --output <fresh-output>
uv run --locked python -m scripts.proposal_coverage_sensitivity --strict-run <fresh-output> --output <fresh-sampled-output>
uv run --locked python -m scripts.verify_proposal_handoff --bins <fresh-output>/bins --profile <fresh-output> --output <fresh-output>/outcome_verification.json
uv run --locked python -m scripts.verify_proposal_handoff --bins <fresh-output>/bins --profile <fresh-sampled-output> --sampled --output <fresh-sampled-output>/outcome_verification.json
uv run --locked pytest
```

主要交付：`bins/YYYYMMDD.parquet`、`events.parquet`、`reference.parquet`、`frozen_lane_inventory.csv`、`unit_quality.csv`、`training_threshold_sensitivity.csv`、`label_exclusions.csv`、源及输出 SHA 清单。每个日分区有完成检查点；已有未完成文件必须先调查，程序拒绝覆盖。接收者按 manifest 校验，未知标签按时限排除，并报告分母和排除率。

## 仍由相关成员共同完成

1. 对典型正例、负例、缺失和预测前已恢复事件的曲线审核；本 PR 可提供自动生成的曲线和 Agent 检查记录，不冒充独立人工签字。
2. 对检测器/方向、车道历史连续性及源车辆计数单位的独立资料审核；原始 XML 与清洗规则支持区间计数，不能无依据转为 vehicles/hour。
3. Member 1/4 审核聚合权重、参考窗口、稀疏/完整政策和事件边界后，再接入新目标模型。已公开的旧模型分数不能改成此版本的分数。
4. 路网/合法上下游由 Member 2 主责，外部资料由对应成员主责。原 Proposal 的模型与空间实验不属于本次数据工程完成声明。

科学采用检查单：[Issue #3](https://github.com/WYJbjtu/traffic/issues/3)。现有验证/测试时间段已在旧项目中被查看，本版本不是新获得的盲测。最终实际统计见 `reports/proposal_member1_v2/`，包含方向/月完整覆盖与速度参考漂移诊断；这些全期诊断不用于重选队列或阈值。
