# Tianhao Wu（Fairy-6b）按 proposal 核查与修正

核查日期：2026-11-01。依据工作区 `DSC6004_Congestion_Recovery_Proposal.pdf`
全文、GitHub PR #5、当前远端 main `bb4170a`，以及本地尚未提交的真实实验交付包。
保留了开始核查时已经暂存的修改；本次没有提交、推送或合并。

## 结论与责任边界

Proposal 第3节明确把**外部数据核查/整合、benchmarks、逻辑回归、决策树、特征组比较**
分配给 Tianhao。数据清洗/事件标签属于 Ye Li，路网/邻路属于 Yijie Wang，
RF/XGBoost 属于 Baixin Wang；标签与空间匹配审阅是共同责任。
仓库的 Member 编号、临时 frontend 分工与 proposal 的姓名分工不完全一致，
不能据此把队友的任务算成 Tianhao 未完成，也不应单方面改写团队分工。

你的工程实现和真实探索性实验已有可复核证据。现有结果没有因本次发现的代码问题
而失效；但它回答的是**暂定恢复确认目标**，不能直接作为 proposal 的恢复开始目标结果。
科学定义、空间验证和团队审批仍须明确区分于软件测试通过。

## 已修复的实现问题

| 问题 | 原行为与风险 | 修正与验证 |
|---|---|---|
| 缺失中间标签绕过单调性校验 | `[label_15m, label_30m, label_60m] = [1, NA, 0]` 被接受，违反 within 标签逻辑 | 检查所有已知长短时限组合；保留合法缺失，不填0 |
| 特征配置能绕过结果字段保护 | `select_model_rows` 有防护，但实际训练不经该函数；把 label/recovery 字段写入配置即可进入训练路径 | 在配置加载及事件校验入口统一拒绝结果字段，包括 `outcome_maturity_at` 和 split 字段；同时覆盖直接构造的 contract |
| 缺少当年日历被误当作非假期 | 只要存在任何早年可用假期行，就把未覆盖年份输出为 False/0 | 按日期所属年份判断年度来源是否可用；跨年相邻日分别检查；未知保留 NA。前提是 staging 提供完整年度表，不能用零散假期行冒充完整表 |
| 通用评估漏掉 Macro-F1 | 正类 `f1` 不是 proposal 要求的两类 Macro-F1；独立真实实验虽另算了 Macro-F1，通用比较入口没有 | 共享评估新增 `macro_f1`，固定类 `[0,1]`、`zero_division=0`；比较配置加入该指标；真实实验删除重复计算路径 |

增加12项针对这些行为的合成回归用例，先确认旧实现失败，再修复至通过。
修改限于你的 external/models 代码、实验脚本、相应配置和测试；未更改队友的标签或路网模块。
这些是防止未来无效输入通过的修正，不是发现当前实验已经使用结果字段泄漏的证据。

## 与 proposal 的符合程度和剩余缺口

| Proposal 要求 | 已有证据 | 仍需处理 |
|---|---|---|
| 30分钟内持续恢复开始，持续10分钟 | 当前交接标签以连续3个5分钟高速度箱的**确认时点**定义恢复；预测还包含可用性延迟 | **P0：与 Ye Li 及全组统一目标后重新冻结标签和评估。** 开始在第29分钟、确认在第39分钟的事件，在两个目标下可能有不同标签。不能简单把确认时间减10分钟当作修正：须重新处理起点、持续时间、缺失、确认随访至第40分钟及边界 purge |
| 历史正常速度参考与 comparable time/weekday | 当前使用2023年固定窗口的车道85分位参考 | 记录方法偏离与漂移风险；参考规则需在训练数据上审阅，不能看测试指标后选择 |
| 按 detector/direction 聚合 | 当前是24个选定 lane-unit | lane 与道路级结果不可等同；聚合和历史设备身份需数据负责人确认 |
| 2023–24训练、2025验证、2026年1–9月测试 | 当前已知标签样本分别3428 / 2008 / 1363；参考与队列选择占用2023年1月 | 三个时间段与 proposal 基本一致；明确训练事件从2023年2月起。未知标签共798/7597（10.50%），已按 split 报告，不能忽略排除偏差 |
| majority、speed-trend、logistic、tree | 当前真实实验均有；同一6799个已知标签事件、14个实验臂 | 维持训练拟合、验证选择、测试仅评估；验证选择 tree/calendar 与测试 Macro-F1 最高的 logistic/weather 是不同概念，不能事后换展示模型 |
| local → local+neighbor → 加外部因素 | 当前是 local → history → flow → calendar → weather 的累加比较 | 这能说明当前特征组的描述性增益，**未完成空间增益问题**。待 Yijie 提供验证映射后，需在相同事件、split、非空间特征及调参预算上比较；不可用距离邻近替代已验证的上下游 |
| 外部来源核查后决定是否纳入 | 有年度官方假期、京士柏温度/风速；雨量、事故、活动有来源抽查和排除说明 | 温度/风速不能替代 proposal 的雨量。雨量两次404只说明被查URL/日期失败，不能证明所有历史雨量不存在；事故只有端点日期抽查，活动无历史版本证据，均不能宣称全时段已核查。若无法安全整合，应在最终报告明确缩减范围及影响 |
| 误差分组、阈值敏感性、恢复曲线 | 已有 detector/peak 误差分析、混淆矩阵和模型解释 | detector 不能未经映射称为 road；标签阈值敏感性和人工恢复曲线复核尚未形成完整证据。由数据负责人提供训练期候选标签与曲线，你复核后再比较模型 |

这份 proposal **只要求30分钟主任务**。15/60分钟是仓库扩展目标；未运行它们不是原 proposal 的必选任务缺漏。
RF/HGB 已由队友实现；HGB 不等于 proposal 的 XGBoost，是否替代须由该负责人和全组说明。
日历组同时含 hour、weekday、weekend 和假期，不能把整组增益单独归因于假期。

## 本次实际验证

- Python 3.12.14，现有 `.venv-notebook` 环境；已安装且出现在 `uv.lock` 中的 registry 包版本逐项比较无差异，`pip check` 无依赖冲突。本次没有执行 `uv sync --locked`。
- 在仓库根目录、PATH 指向已有 Git 包装器，运行 `python -m pytest -q`：**157 passed，1个 Starlette/httpx 依赖弃用警告**。最初沙箱运行有5项 localhost 测试无法绑定端口、3项 Git 路径失败；使用正确 Git 路径并允许本地测试服务器后完整重跑通过。
- `python experiments/tianhao/verify_review.py`：修复前603项通过；共享评估增加Macro-F1后**645项通过**。原始预测仍为95186行、14臂。
- 新增 `review_existing_run.py` 对本地真实输入/模型进行476项只读核查：7597事件、三时限已知标签单调性、outcome maturity、天气源时间、训练中位数/缩放、420行指标重算、**67990条拟合模型预测分数**重算均通过。
- 用修正后的日历重新计算全部7597事件，8个入模日历特征的变化行数均为0。当前历史预测与指标无需因此重训；本次未重新调参或训练模型。
- `git diff --check` 通过。机器可读证据：[real_input_review.json](../reports/tianhao_review/real_input_review.json)。

原历史结果、来源快照和 `provenance.json` 保留不动。
`package_manifest.json` 仅更新已修改实验脚本的当前哈希，并在 `review_revision` 中保留此前哈希和原因；没有重写历史结果的哈希。

在仓库根目录可按标准锁定环境复核：

```text
uv sync --locked
uv run --locked pytest -q
uv run --locked python experiments/tianhao/verify_review.py
```

对当前工作区已保留的大型输入与拟合文件，额外运行（输出路径必须尚不存在）：

```text
uv run --locked python experiments/tianhao/review_existing_run.py --run ../experiments/tianhao/runs/run-20261030T141916Z-36b86a --prepared ../experiments/tianhao/prepared --output reports/local/tianhao-review-new.json
```

该命令只加载本团队可信、已通过原 manifest 校验的模型文件，不联网、不训练、不覆盖历史记录。
所有通过项都是工程/一致性证据，不代表团队已批准科学定义，也不消除标签目标偏差。
