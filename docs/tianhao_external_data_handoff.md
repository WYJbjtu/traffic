# Tianhao：真实外部特征来源、覆盖与排除说明（2026-11-02）

**范围：原24车道、7,597事件、30分钟恢复确认实验。EXPLORATORY — NOT APPROVED AS FINAL RESULTS。**
本说明汇总原2026-10-30来源缓存和2026-11-01真实重跑；本次未重新联网探查历史服务、改标签或训练模型。
96车道扩展尚未接入，本表不能外推到新队列或全香港。

## 1. 实际使用的日历来源与定义

长期实验使用香港政府新闻公告的**年度General holidays**表，按年份版本解析，而不是把2026年当前1823 JSON回填到过去四年。
年度公告已保存HTML字节、源URL、检索时间、SHA256及发布时间，见 [年度来源表](../reports/tianhao_followup_20261102/external_data/holiday_sources.csv)。

| 年份 | 官方年度公告 | 发布时间（HKT） |
|---|---|---|
| 2023 | [General holidays for 2023](https://www.info.gov.hk/gia/general/202205/13/P2022051000340.htm) | 2022-05-13 11:00 |
| 2024 | [General holidays for 2024](https://www.info.gov.hk/gia/general/202305/25/P2023052500208p.htm) | 2023-05-25 11:00 |
| 2025 | [General holidays for 2025](https://www.info.gov.hk/gia/general/202405/03/P2024043000417.htm) | 2024-05-03 11:00 |
| 2026 | [General holidays for 2026](https://www.info.gov.hk/gia/general/202505/16/P2025051300353.htm) | 2025-05-16 11:00 |

解析器核对每年17个具名假期、日期对应星期和公告时间；公告还包括Every Sunday，脚本将星期日一并展开，四年共277个唯一日期。
因此 `is_public_holiday` 应按这个实际来源定义解释，不可当成只表示额外具名假期、也不可单归因于假期。
入模日历组还包括小时与星期的sin/cos、周末、假期前后一天，均以香港民用日期计算。
必须满足 `published_at <= prediction_time`；相邻日跨年时分别确认其年度版本。未覆盖年份保留NA，不能默认非假期。

## 2. 实际使用的天气来源、单位与回放

- 提供者：香港天文台；站点：**King's Park（京士柏）**，作为整个选定队列的区域代理，不是按道路匹配的最近站。
- 温度：源文件 [latest one-minute mean air temperature CSV](https://data.weather.gov.hk/weatherAPI/hko_data/regional-weather/latest_1min_temperature.csv)，字段 `temperature_c`，单位°C。
- 风：源文件 [latest ten-minute wind CSV](https://data.weather.gov.hk/weatherAPI/hko_data/regional-weather/latest_10min_wind.csv)，使用十分钟平均风速，`wind_speed_kmh`，单位km/h；未把风向或阵风当成平均风速。
- 实验回放的是 [DATA.GOV.HK历史档案API](https://data.gov.hk/en/help/api-spec) 中上述URL的历史字节，不是当前CSV本身。2023年1月至2026年9月，每种来源45个月，共90个ZIP；原字节与下载元数据留在本地，逐档SHA见 `experiments/tianhao/results/weather_archive_inventory.csv`，逐来源URL与检索时间见 `rerun_20261101/original_source_checks.json`。
- 仅保留在预测时点之前捕获的快照；观测时间也必须不晚于预测，观测年龄0–60分钟。捕获时间是保守可用性代理，不等于已验证的天文台精确发布时间或实时服务延迟。
- 温度解析范围[-20,60]°C、风速非负；无法解析值、站点缺失/歧义、过期或不合时间顺序的值保留缺失。没有插值，也没有把缺失天气补0。
- 保留原始观测时间、档案可用时间、年龄、missing标志、ZIP成员和成员校验值。模型中位数插补仅在训练集拟合；以下覆盖全部在**插补前**计算。年龄字段存在不代表对应数值有效，缺失率要看温度/风速本身。

90个月ZIP只证明已保留这些月的来源，并不证明每条事件都有有效天气，也不代表全站点/全时段连续覆盖。

## 3. 覆盖分母和缺失率

`all_events`包括未知标签；`known_label_30m`只包括实际参与30分钟训练/验证/测试的已知标签事件。
`weather_both_values`要求温度与风速同时有效；联合缺失数不是简单把两个单列缺失数相加。

| 分母 | 特征 | n | 已观测 | 缺失 | 缺失率 |
|---|---|---:|---:|---:|---:|
| all_events | calendar_all_fields | 7597 | 7597 | 0 | 0.0000% |
| all_events | temperature_c | 7597 | 7592 | 5 | 0.0658% |
| all_events | wind_speed_kmh | 7597 | 7575 | 22 | 0.2896% |
| all_events | weather_both_values | 7597 | 7573 | 24 | 0.3159% |
| known_label_30m | calendar_all_fields | 6799 | 6799 | 0 | 0.0000% |
| known_label_30m | temperature_c | 6799 | 6794 | 5 | 0.0735% |
| known_label_30m | wind_speed_kmh | 6799 | 6781 | 18 | 0.2647% |
| known_label_30m | weather_both_values | 6799 | 6779 | 20 | 0.2942% |

### 各split的天气缺失（温度 / 风速）

| 分母 | split | n | 温度缺失 | 风速缺失 |
|---|---|---:|---:|---:|
| all_events | train | 3833 | 3 | 2 |
| all_events | validation | 2235 | 0 | 6 |
| all_events | test | 1529 | 2 | 14 |
| known_label_30m | train | 3428 | 3 | 2 |
| known_label_30m | validation | 2008 | 0 | 5 |
| known_label_30m | test | 1363 | 2 | 11 |

完整逐列率表：[coverage.csv](../reports/tianhao_followup_20261102/external_data/coverage.csv)。
源audit SHA256为 `fe00cb25ee7048011956f9dd47a3c73241b35a854fd993941809f8d30996a49d`，对应原重跑manifest；本次逐项核对已提交feature_missingness、cohort_summary、已知标签预测ID/时间/split，以及天气源时间约束。
大型audit未提交；仅凭轻量包可以复核全部事件的单列缺失计数，完整重算已知标签子集率需要该原始audit或依原脚本重建后核对版本。

## 4. 未纳入因素与证据边界

以下是**2026-10-30缓存检查**，不是全时段穷尽搜索或本次实时可用性检查。[原始记录](../experiments/tianhao/results/conditional_source_audit.json)及[轻量表](../reports/tianhao_followup_20261102/external_data/conditional_source_checks.csv)可追溯查询URL与状态。

| 因素 | 实际检查证据 | 未纳入的原因 | 后续通过条件 |
|---|---|---|---|
| 雨量 | 对 `hourlyRainfall.php?lang=en` 查询2023-02-01、2026-09-30历史版本，两次404 | 该查询路径未建立安全历史回放；这不足以证明所有历史雨量源不存在。温度/风速不能替代雨量 | 核实确切资源URL/归档参数、保留历史响应和单位，匹配合适站点，验证观测/发布时间并量测事件覆盖 |
| 事故/STN | 运输署 `trafficnews.xml` 两日版本清单分别152与71条 | 首尾日期抽查不代表四年完整回放；消息选择性、地点文本消歧、方向匹配与后续关闭状态回填仍未解决 | 时点版本完整性、预测前公告、可审核地点/方向，缺报与无事故分开，禁止事后更新泄漏 |
| 重大活动 | HKTB活动CSV两日版本清单均0；当前表含事后临时关闭说明 | 不能证明完整历史版本在预测前已公布；日期范围和场地不能变成猜测的小时影响 | 取得可证明发布时间的日程版本，核实日期/场地，只有日期的记录最多作日级指标，保留覆盖限制 |

未纳入不表示这些因素没有预测价值；不生成全0雨量、无事故或无活动列。
先前 `docs/external_data_source_audit.md` 的GO/CONDITIONAL属于2026年10月短pilot来源可行性，不代表本次长期实验已经整合这些类别。

## 5. 对模型比较和新队列的交接

- Calendar组同时含时钟、星期、周末与假期；整组增益不能归因为假期，当前不作显著性或因果声明。
- 天气站只作为区域代理，且缺失模式可能携带来源覆盖差异；保留missing指标，并报告其作用范围。
- Member4当前仅有local/history/flow，四模型的Calendar/Weather统一消融仍待使用相同表、事件和split后另跑；本次未训练这些缺少的实验臂。
- 96车道新事件和地点改变后须重新构建背景特征，核对schema/时间，并重新报告覆盖；不得照搬本表数值。
- 目标仍是交接的恢复确认，标签与proposal恢复开始的取舍由全组冻结，本次不修改标签。

## 6. 复现

在仓库根目录，已有项目Python 3.12环境时运行：

```text
uv run --locked python experiments/tianhao/document_external_coverage.py --event-audit <原始event_feature_audit.parquet> --output-dir reports/local/external-coverage-new
```

输出目录必须尚不存在，程序先核对原manifest中的audit哈希，再生成率表、来源表、排除记录和input/output校验清单；不联网、不训练、不覆盖历史产物。
