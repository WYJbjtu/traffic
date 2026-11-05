# Tianhao 三项整改交付（2026-11-02）

基于main `4309351`，分支 `feature/tianhao-verification-comparison-external`。原工作区暂存修改保留；本次没有训练、改标签、重调参或改写历史预测/manifest。

1. **核验修复**：原 `verify_review.py` 和 `verify_shared_results.py` 默认严格校验不可变结果，README与当前源码变动明确列为工作区诊断。源树严格比对仍可通过 `--strict-snapshot` 启用。参见 [实验说明](../../experiments/tianhao/README.md)。实测两个核验分别632/602项通过；计数变化来自将源码诊断与结果完整性分开。
2. **统一比较**：[报告](comparison/README.md)、[30分钟同特征测试表](comparison/common_30m_test.csv)、[全部指标](comparison/all_metrics.csv)、[混淆矩阵](comparison/confusion_matrices.csv)。177个分组、27个共同臂配对通过、1635个原指标重算一致、补135个Macro-F1；保留实验和特征来源，不混成跨条件排名。
3. **外部说明**：[来源与排除依据](../../docs/tianhao_external_data_handoff.md)、[覆盖报告](external_data/README.md)、[逐列覆盖表](external_data/coverage.csv)。区分7597全事件与6799已知标签分母，标明日历、区域天气代理、雨量/事故/活动未纳入的实际证据和边界。

## 实际验证

`uv sync --locked`成功；`uv run --locked pytest -q`为 **194 passed，1项既有依赖弃用警告**。
18项新增合成回归覆盖README变化、预测改动/丢失、严格快照、事件配对、标签/时间不一致、非法分数、规则概率语义及覆盖分母。
完整记录：[validation.json](validation.json)。两个核验的实测JSON也在本目录。

## 复核命令

在这个独立仓库根目录运行：

```text
uv run --locked python experiments/tianhao/verify_review.py
uv run --locked python experiments/tianhao/verify_shared_results.py
uv run --locked python experiments/tianhao/compare_saved_runs.py --output-dir reports/local/unified-comparison-new
```

外部覆盖的完整重算还需要原始、已核验SHA的本地audit；命令与哈希见来源说明。输出必须采用新目录，保留此前证据。
