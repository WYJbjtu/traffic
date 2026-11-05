# 96 车道真实道路候选与邻路观测核验（2026-11-05）

**结论：空间模型 NO-GO；这是实际官方数据候选匹配及逐事件观测覆盖，不是合法/历史有效道路连接的批准。** 原 Proposal 恢复开始与现行 `recovery_confirmation_v1` 恢复确认并不等同；原 Proposal PDF 和团队目标审批仍缺。未经审批不计算 Local+History 与 Verified Spatial 模型指标，不将候选速度当训练特征，不用未来或插值。

## 真实来源和冻结队列

- 从 `data-expanded-96-2023-2026-v1` 的原始 ZIP 核对整包 SHA-256 `f5be559a6ad8df69e68fbc382fb609d13fdae40aa044c9d1fe4d7e3b2253b6b8`，核对内部 23 个清单文件 SHA-256（对已解压的三个必要大/小文件逐字节核查）。权威哈希见 [证据清单](evidence_manifest.json)；没有修改 Release。冻结车道 96；产生事件 94；事件 30,452：训练 14,290，验证 8,557，测试 7,605；30 分钟已知标签分别 13,002、7,848、7,008。实际五分钟观测箱 35,782,769 行，按车道分成 96 行组，处理时逐邻居车道读取，未一次加载全部。
- 复用本地已核验 `data/local/network-full/v1/`：36,525 源路段、48,080 F/R 候选有向弧，EPSG:2326，95 个源中心点瓦片；本次没有重新下载 484 MB CENTERLINE 或重建网络。官方 CENTERLINE/INTERSECTION/TURN SHA-256 分别 `4fad0303e65c759ac7abe8eea3920b3ffcfcd5149c978fa9540bf032933a32c2`、`79119240315ea989b18e715d54f7146ff8bcbc9c51aeb91ed46857c0bf72fa5f`、`790ce25722354a796f59becc7c6adf82766ebb4289f96621ef118ed4179a38b0`。官方 URL、HTTP 获取时间/Last-Modified 详见 `data/local/network-full/v1/manifest.json` 和 [审核包](ranked-pair-1.md)。源道路是 2026-10 快照，并非已经证明适用于 2023–2026 的历史版本。

## 实际结果与分母

| 指标 | 计数 / 解释 |
|---|---:|
| 96 车道有官方坐标 | 96 |
| 方向相容的 50m 官方路段候选匹配 | 95 / 96，**候选率** 98.96%，**批准率** 0 / 96 |
| 恰一方向相容路段 / 多个 | 15 / 80 |
| 10m 距离差内多解（上项子集） | 52 |
| 方向冲突（含元数据方向与观察方向不符） | 19；可能与多解重叠 |
| 未匹配 | 1（AID01210，50m 内有 4 路段，但无方向相容候选） |
| 发现 1000m/至多 5 弧内的候选有向车道/检测器对 | 74 / 74；250 条备选路径，71 个 route-sequence 候选走廊 |
| 人工独立核实映射 / 有向连接 | **0 / 0** |
| 有真实邻路 as-of 速度的 *候选级* 事件 | **22,492 / 30,452**（不等于空间模型可用） |
| 历史关系批准且模型可用的 train / validation / test | **0 / 0 / 0** |
| 真实配对空间消融 | **未运行，NO-GO**；Local 与 Spatial 指标均为未定义、非零分 |

预先确定的搜索上限：距离道路中心线 50m，局部切线误差不超过 45°；近似 10m 的多解标记；路径最大 1000m、最多 5 弧。该限制仅发现审查对象，**不是传播阈值**。道路 `TRAVEL_DIRECTION=1` 允许双向 F/R 候选、`3` 只允许数字化方向 F；带级别的厘米级相同端点才构成候选图边。保守阻断源 TURN 禁行记录和 U-turn；没有禁令**不代表**允许通行。保留平行车道、不同层高、错向及名称不合候选供复核，元数据道路名称只是弱线索。检测器无可靠高程信息，故不能自动断言层高相容。候选路径距离按路段投影点计算，不包括检测器离道路的偏移；例如最短候选对 AID02205→AID02114 的两点都距候选道路约 45m，**图像提示可能是错配**。不能因候选路径短而选作科研连接。

### 测得的邻路速度机会（候选限定）

| 划分 | 全部事件 / 已知 30m | 候选至少一侧有观测 | 上游有观测 | 下游有观测 | 两侧都有 | 已知标签且候选至少一侧有观测 | 已批准模型事件 |
|---|---:|---:|---:|---:|---:|---:|---:|
| train | 14,290 / 13,002 | 10,280 | 7,503 | 5,437 | 2,660 | 9,477 | **0** |
| validation | 8,557 / 7,848 | 6,424 | 4,579 | 3,443 | 1,598 | 5,947 | **0** |
| test | 7,605 / 7,008 | 5,788 | 4,115 | 3,735 | 2,062 | 5,404 | **0** |

使用源 `cohort_bins.parquet` 中真实可用速度，不把 `flow_slots` 当流量；要求 usable、速度非缺失、`timestamp <= prediction_time`、`available_at <= prediction_time`、`last_source_available_at <= prediction_time` 且观测年龄不超过 10 分钟。这里观测年龄实际均为 **10 分钟**（箱结束时间加保守 10 分钟可得时间），并非瞬时观测；`valid_slots / 10` 是原始 30 秒槽覆盖率，不是车流量。无观测速度为 NA，分别记录候选检测器数、年龄、可用时间、参考速度是否存在及缺失理由。独立用 PyArrow 过滤读取六个随机挑选的真实阳性候选事件，两侧 as-of 计数与生成结果一致；仅为抽样复核，**不是全部行独立重建**。完整逐事件 CSV 在被 Git 忽略的 `data/local/spatial96/v1/candidate_neighbor_coverage.csv`；摘要在 [spatial_eligibility_summary.csv](spatial_eligibility_summary.csv)。

已运行 `traffic_recovery.network.spatial_features.neighbor_features` 对所有 30,452 事件按 512 行批次做**空审批输入**核验。结果每行 `mapping_unverified`，邻路速度 NA、经审批邻居数 0；保存在 `data/local/spatial96/v1/spatial_event_eligibility.parquet`，绝不把上表候选机会直接复制为模型特征。

## 人工道路审核资料及版本限制

- 全量候选：[mapping_candidates96.parquet](mapping_candidates96.parquet)（736 点线配对，26 栏：车道、弧、米数、方向误差、名称、源高程、更新时间、审批状态）；[mapping_summary.csv](mapping_summary.csv)、[mapping_ambiguities.csv](mapping_ambiguities.csv)、[detector_locations.geojson](detector_locations.geojson)（WGS84 **仅展示转换**；原网格 EPSG:2326）。
- [candidate_directed_pairs.csv](candidate_directed_pairs.csv) 是每对最短候选路径；`data/local/spatial96/v1/candidate_path_evidence.parquet` 保存 250 条完整备选弧、路线及端点序列。**不应从路线数推断独立连接数**。 [candidate_corridors.csv](candidate_corridors.csv)、[candidate_corridor_coverage_ranking.csv](candidate_corridor_coverage_ranking.csv)（观测机会是走廊检测器在**任一候选下游**的覆盖，不是该指定路径对的可用率）、[candidate_path_sensitivity.csv](candidate_path_sensitivity.csv)（固定 250/500/1000m × 2/3/5 弧），[rejected_connections.csv](rejected_connections.csv) 和 [candidate_detector_disconnections.csv](candidate_detector_disconnections.csv) 记录候选被阻断及搜索上限内未发现路径；缺路径不是永久断开证明。
- 优先复核六个**名称相符、距离/方向较佳且有官方 INTERSECTION 支持**的 [evidence-ranked 审核列表](ranked_pair_selection.csv)：[1](ranked-pair-1.md) · [2](ranked-pair-2.md) · [3](ranked-pair-3.md) · [4](ranked-pair-4.md) · [5](ranked-pair-5.md) · [6](ranked-pair-6.md)。各包附原始官方折线＋弧箭头图 `ranked-directed-pair-N.png`、道路名称、级别、元数据、源更新时间、[交叉口](ranked_pair_intersections.csv)和[转向](ranked_pair_turns.csv)源记录及空白人工审核表。先前单纯按最短距离的 `pair-N` 图保留作**错配风险实例**，不能替代排名。审查包是 AI 整理的待审证据，批准数仍为 0。
- 既往 [39 检测器审查包](../spatial_pair_review/) 六对仅一对两端都在冻结 96 个检测器内，且重新发现同一检测器对；**旧的弧选择不一定相同**。一月 250m 范围的 [29 个地理线索](geographic_review_leads_250m.csv) 都属于冻结 96，但不等于 29 条真实相连道路。详见 [previous_pair_overlap96.csv](previous_pair_overlap96.csv)。
- 两份官方 processed `irnAvgSpeed-all.xml` 样本（2023-05-15、2026-09-15）源 SHA 与本地 XML 重新一致，分别 4,255/4,524 路段、有效数值 4,198/4,458；两者 `irn_version=20221210`，与当前 2026-10 geometry **没有证明兼容**，与本次所有候选路径路由 ID 重叠各 57 个（[独立源重叠审计](processed_candidate_route_overlap.csv)），但版本合格记录 0；只涉及两个时刻，不能代替 2023–2026 时间序列，也不能证明与原始目标检测器独立。[官方速度样本审查](historical_processed_speed_audit.csv)列出其中六包选定路径路由的 ID 重叠各 2 个；ID 相同不等于历史地理一致或可用特征。没有下载更多历史档案，没有插值。

### 解除 NO-GO 的明确证据

1. 成员 2 与交通数据责任人依据上面的六套审核包逐路确认检测器物理方向/身份、平行车道、隧道/天桥、实际转向和官方 INTERSECTION/TURN 约束；提供可核查的审查人、来源 URL/SHA、决定及理由；对所有拟采用的关系指定实际历史生效 `[valid_from, valid_to)`，**不得倒填**。
2. 获取或官方证明对应 2023–2026 的路网版本/旧路段 ID、更新时间及版本间映射；`20221210` 处理后速度版本与 2026 CENTERLINE 的 ID 重合不充分。补充检测器历史更换/位置证据。
3. 独立核实原始车道与处理后路段速度是否共享检测器及真实历史可得时刻。然后仅用**获批有向边**重复逐事件真实邻路测量。先检查 train/validation/test 空间资格、已知标签分母与两类，再用完全一致事件集合和固定训练/验证预算运行 RF/XGBoost/HGB Local+History 与 Local+History+Verified Spatial；当前未运行、没有空间增益、没有空间模型分数。

## 复现（在仓库根目录；输出目录必须不存在）

```text
uv sync --locked
uv run --locked python scripts/spatial96.py --output data/local/spatial96/v2 --report reports/spatial96_v2
uv run --locked python scripts/spatial96_review.py --report reports/spatial96_v2
uv run --locked python scripts/spatial96_review.py --report reports/spatial96_v2 --hash-only
uv run --locked python scripts/spatial96_enrichment.py --report reports/spatial96_v2 --local data/local/spatial96/v2
uv run --locked python scripts/spatial96_enrichment.py --report reports/spatial96_v2 --local data/local/spatial96/v2 --hash-only
uv run --locked python scripts/spatial96_direction_maps.py --report reports/spatial96_v2
uv run --locked python scripts/spatial96_direction_maps.py --report reports/spatial96_v2 --ranked
uv run --locked python scripts/spatial96_ranked_packet.py --report reports/spatial96_v2
uv run --locked python scripts/spatial96_processed_overlap.py --report reports/spatial96_v2
uv run --locked pytest
uv run --locked python scripts/spatial96_code_manifest.py --report reports/spatial96_v2 --local data/local/spatial96/v2
```

须提供已单独解压、哈希匹配的 `processed/{events,cohort_bins}.parquet` 及 `metadata/detectors.csv`；脚本对 ZIP 和所有清单成员（可直接从 ZIP 的小文件）核对 SHA。当前本机既有已解压三文件，无重新下载/覆盖。若官方来源版本发生变化，另建版本审查，不能绕过 SHA。原始快照/模型、PR #19 输出和旧 24 车道结果完全未修改。

### 哈希与 CI 状态

[reproduction_manifest.json](reproduction_manifest.json) 绑定脚本/依赖锁、全部已生成审查输出和当地 3 个结果；[evidence_manifest.json](evidence_manifest.json) 绑定主阶段 Release/官方源、当地 3 个大结果及报告初始文件；[review_evidence_manifest.json](review_evidence_manifest.json)、[enrichment_evidence_manifest.json](enrichment_evidence_manifest.json)、[directional_map_manifest.json](directional_map_manifest.json)、[ranked_packet_manifest.json](ranked_packet_manifest.json)、[processed_candidate_route_overlap_manifest.json](processed_candidate_route_overlap_manifest.json) 分别记录追加审查、地图与处理后速度审计的字节哈希。额外地图 `ranked_directional_map_manifest.json` 分开绑定。新的脚本及测试随专属 PR 复核，CI 在提交/推送后填写；**未经 CI 或人工审查不声称批准**。
