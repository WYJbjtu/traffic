# 96 车道空间研究浏览器：本地运行与科学口径

## 运行

从仓库根目录使用 Python 3.12 与已提交的 `uv.lock`：

```bash
uv sync --locked
uv run --locked pytest
uv run --locked --with 'streamlit==1.51.0' --with 'plotly==6.3.1' streamlit run apps/research_explorer.py
```

打开终端显示的 `http://localhost:8501`。浏览器检查需要 Playwright/Chromium，见下文；常规研究与测试不依赖浏览器。应用只读，不下载数据、不训练模型、不写本地研究产物。缺少文件时明确显示「不可用」。

默认从仓库根目录发现产物。若本地真实产物保存在另一个根目录，可在启动前设置 `RESEARCH96_DATA_ROOT` 为该目录；其下须保持下表的相对路径与 SHA-256 清单，不能只放一份无来源说明的 Parquet。空目录可用于验证缺失状态，应用不会填充演示数据。

## 来源与本地文件

Git 中可直接查看 `reports/spatial96_inferred_v2/paired_spatial_metrics.csv`、`spatial_negative_controls.csv`、质量表、方法说明和 SHA-256 清单。Tianhao 已发表的 96 车道逐事件预测在 `experiments/tianhao/expanded96_20261104/predictions.parquet`，只在独立折叠面板画 ROC/PR 曲线；历史 24 车道实验不参与本应用比较。

完整地图与事件需先按团队原流程取得、校验并放置以下**真实**本地文件；路径均相对仓库根目录，不提交 Git：

| 用途 | 路径 | 核验依据 |
|---|---|---|
| 96 车道事件 | `data/local/expanded96-release/prepared-v1/processed/events.parquet` | Release/model manifest SHA-256、30,452 事件、94 事件车道、目标版本 |
| 五分钟交通 | `data/local/expanded96-release/prepared-v1/processed/cohort_bins.parquet` | Release/model manifest SHA-256、35,782,769 行；按车道和时间窗口查询 |
| 冻结本地模型清单 | `data/local/expanded96-release/model-a0-a2-v2/manifest.json` | 原始 Release 来源哈希、目标 `recovery_confirmation_v1` |
| 官方全网 | `data/local/network-full/v1/manifest.json`、`topology_index.sqlite`、`geometry/tile=*/*.parquet` | 36,525 段、48,080 候选弧；道路为 EPSG:2326，显示几何 EPSG:4326 |
| 推断 v2 | `data/local/spatial96/inferred-v2/{mapping_scores,inferred_detector_neighbors,event_neighbor_lineage,event_spatial_features}.parquet` | `reports/spatial96_inferred_v2/output_sha256.json` |

空间模型**逐事件概率文件没有发布**。目前不存在可供本应用核验的该文件；概览会明确报缺失，模型页面只展示原始汇总指标和保存的混淆计数。不能根据 AUC 重建曲线，不能把 Tianhao 或 Member4 的概率代替空间模型概率。如以后提供空间预测产物，须带事件 ID、群体、模型、特征臂、split、30 分钟时窗、目标版本、来源哈希和逐组事件 ID 哈希，经校验后才可接入。

## 六个视图

1. **概览**：区分 Git 轻量指标、真实本地事件/路网、缺失的空间逐事件概率。
2. **道路网络**：每次读取一个 4 km 官方源分块的真实折线；96 个车道单位以源探测器坐标叠加，展示物理探测器数；筛选 ID、路名、方向、车道、匹配等级及邻路资格。选中单位显示源坐标、道路弧、点线偏移、方位差、路名证据、评分、备选弧和真实弧序列路径。地图路径显示完整源道路几何；保存的 `path_distance_m` 是探测器投影间沿路部分距离，**不等于**图上所有完整折线长度。
3. **事件浏览**：从认证事件表选择真实事件。按一个车道与最多 8 小时窗口查询五分钟 Parquet；实线为观测与来源可得时间均不晚于预测时点的输入，虚线为事后解释。显示真实上/下游速度、缺失间隙、年龄、来源哈希与确认结果；不插值或补零。
4. **空间特征**：按同一 `event_id`/预测时间和 P1/P2 读取冻结 S1–S4 值与邻路来源明细。未观测保持空值。
5. **模型比较**：M0–M5 只在同群体、同 split、同目标、同 event-ID SHA-256、同正负支持下配对；30 分钟 RF/XGBoost 原报告指标与 C1–C5 负对照。P1/P2 样本不同，P3 0 获批连接。Tianhao 已发表模型另设独立面板，不混排。
6. **研究方法**：目标、源路网建图、预测时可用性、评估边界与历史连接限制。

坐标源 HK1980 Grid（EPSG:2326，米），地图转换 EPSG:4326；时间统一 `Asia/Hong_Kong`。地图矢量叠加来自本地官方路网，底图由 CARTO/OpenStreetMap 提供；底图联网失败时，本地来源几何仍为研究证据。单个道路分块的显示简化仅作用于浏览器，不改动官方源文件或模型路径计算。

## 浏览器复核

启动应用后，另一个终端运行：

```bash
uv run --locked --with 'streamlit==1.51.0' --with 'plotly==6.3.1' --with 'playwright==1.58.0' python scripts/validate_research_explorer96_browser.py
```

若 Playwright 的 Chromium 位于非默认位置，设置 `PLAYWRIGHT_CHROMIUM_EXECUTABLE` 为浏览器可执行文件路径。该脚本在 1365×850 浏览器打开六页，检查地图 canvas、真实事件曲线、S1–S4 内容、已保存 RF P1 指标、脚本异常和横向溢出，并把截图及 JSON 记录写入 `reports/research_explorer_96_integration/`。截图是浏览器呈现证据，不是新的科学观测。

可另以空 `RESEARCH96_DATA_ROOT` 在其他端口启动同一应用，再将 `RESEARCH_EXPLORER_URL` 指向该端口运行脚本的 `--missing` 模式；它只检查文件缺失提示，并保存独立的 `browser-missing-validation.json`，不会改动真实数据。

## 当前科学限制

当前暂定目标 `recovery_confirmation_v1` 是持续恢复确认；Proposal 的 `recovery_start_sustained_v1` 是恢复开始，二者不等价。推断模型使用 2026 官方路网快照回溯 2023–2026 事件，端点/路口/转向资料只构成算法候选；物理路口、历史映射、主辅路、立交和条件转向未独立获批。P3 核准关系为 0，严格历史实验 NO-GO。P1 方向模型的回溯点估计高于无向与地理对照，但置换对照也保留较强信号；未估计检测器聚类置信区间，不宣称因果、统计显著或部署就绪。
