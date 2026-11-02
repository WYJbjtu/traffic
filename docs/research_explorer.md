# SDSC6004 · 11 月 2 日交接 / Research Explorer

## 今日交付 / 启动

新增只读 `apps/research_explorer.py`（统一 Plotly 印刷风格）、`src/traffic_recovery/research_viz.py`（严格按实验加载、筛选、事件历史和时间汇总）、`tests/test_research_viz.py`。未改动 React/FastAPI 或训练流程；无自动下载、无模型重训。独立 Streamlit/Plotly 依赖不改项目锁文件；在仓库根目录**一条命令启动**（Python 3.12、`uv`）：

```bash
uv run --locked --with 'streamlit==1.51.0' --with 'plotly==6.3.1' streamlit run apps/research_explorer.py
```

浏览器访问终端给出的 `http://localhost:8501`。离线首次启动前需要事先缓存以上两个额外包。一般测试：`uv sync --locked && uv run --locked pytest`。无需完整 1.67 GB Release；若团队已**自行取得并校验**长窗口数据，在折叠的 Data & run configuration 输入 `processed/derived/events.parquet` 和 `processed/derived/cohort_bins.parquet` 的本地绝对路径（或仓库相对路径），即可开启事件车道历史曲线与全体事件时间描述；应用不下载任何数据。输入须来自**长窗口**，不能混用 2026 年 10 月短试点。大数据不提交 Git。

## 展示口径

- 首页事件总数 7,597 来自 `experiments/member4/model-dataset-manifest-hf.json`；研究窗口 2023-01—2026-09、24 个选定车道单元来自 `docs/long_window_data_access.md`。测试集预测时间范围单独显示，不冒充研究全期。标签已知数：15/30/60m 分别 6,954/6,799/6,611；未知值独立计数。正例率只对已知测试标签给出，不能解释为全城拥堵发生率。
- Member4 `comparison-hf-v1`：真实保存的 Logistic Regression / Decision Tree / Random Forest / HistGradientBoosting，Local、History、Flow，15/30/60m；只展示 test，模型解释从保存的 `interpretation.csv` 读取。宏 F1 在该指标表**缺失**，不补写成实验指标。图中 ROC/PR 曲线由保存的 test `y_score` 计算，面积引用保存指标，混淆矩阵由同一测试臂逐行统计。
- Tianhao `rerun_20261101`：**单独标明** 30m、逻辑回归与决策树，含 Calendar、Weather、Macro-F1；不合并实验排名。其重跑复现了此前已看过的测试集，不是新的独立盲测。Calendar 混合钟点、星期与官方假期，不能单独归因于假期；天气站只是区域代理。
- 事件浏览器仅从保存的 test 逐事件概率与真实标签选择事件；真实 label 明确写作事后结果。原始事件与 bins 缺失时不显示伪造曲线/探测器信息。输入真实事件表时可按 detector 和日期筛选，历史曲线只使用同车道、预测时点以前的观测；参考速度/阈值仅在表中存在时画出，恢复确认时间只在 outcome 区展示。**不把已知 label 当作预测。**
- 时序页面只有完整事件表才能计算每日时段、周末、月份事件量、已知恢复率和未知标签率；test predictions 丢失缺失标签，不能代替全体事件。假期/相邻日期的真实描述图仍需同事件表匹配已发布版本的官方日历；当前不猜测节假日。

## 静态路网可行性 / 动态邻路阻碍

复用 `docs/spatial_feasibility.md` 与 `reports/spatial_feasibility/` 的已存官方证据：EPSG:2326 中 3,197 条候选路线、4,017 条有向弧、2,709 节点、156 弱连通分量（局部 500m 廊道截取，并非全港路网），39/39 自动候选匹配，23/39 模糊，8/39 现行元数据方向与观测不符；6 个检测器对仅是来源支持的**候选**。地图、候选表、版本标识及 NO-GO 在应用展示。0 人工核准的探测器映射/转向连接；先前 40 条真实事件的可用经核准空间特征为 0。

**静态 A**：官方 LineString 长度、路线 ID、TRAVEL_DIRECTION (1/3)、ELEVATION、部分交点/限制记录可作为**来源字段**复核；候选有向入/出度、路口连接度仅能在人工确认端点/高程、方向、限制、历史版本和路线裁切边界后作为**覆盖受限的图统计量**。弱连通不是可通行连通；当前不把候选图节点度作为正式特征。官方路段分类的可用性及语义尚无证据，保持缺失，不能以道路名称推断。

**动态 B**：上/下游速度、邻路拥堵比、覆盖率必须先审批版本化 detector→carriageway→route 映射、方向、邻路合法转向、历史有效日期，以及 as-of 的 5m 观测和发布可用时间。候选靠近、共端点或同名不是核准。需要 Member 2 人工复核路线/高架/转弯限制和历史版本；Member 1/4 复核事件标签与共同样本；再计算合格邻居/事件覆盖，做配对消融。**Spatial ablation 保持 NO-GO；未加入已发表指标。**

## 时序研究下一步（未调参、未宣称因果）

`src/traffic_recovery/external/calendar.py` 已有预测时可用的 `hour_sin/cos`、星期/周末、官方已公布假期及前后日期。建议冻结配置后在**同一训练/验证/测试事件队列**分组消融：① Intraday（时钟、黎明/早高峰/日间/晚高峰/夜间，并考虑与道路单元的交互，交互只在训练折拟合）；② Weekly（星期/周末）；③ Holiday（官方假期及前后日，记录公告可用性）。依次和 Local+History+Flow 基准比较，不从已查看的 test 选择时间阈值。每组同时报样本数、已知标签率、缺失率、恢复率，控制月份/路段曝光差异；月/季度/年度分析先检查交通可用性和季节覆盖，不能简单以不同年份数值解释季节效应。既有 Calendar 整组提升不等于假期独立贡献。

## 风险与验证

定义仍为采样后的**持续恢复确认**，不是 proposal 的**恢复开始**；保留标签、可用性延迟、局部 24 车道、事件相关性与天气站代表性限制。已保存的真实测试臂只是探索性结果，尚待团队科学审批。需要团队自行提供经过 SHA256 校验的长窗口事件/bins 和版本化官方假期对照，再做完整事件曲线、节假日描述；需要人工网络核准后才有空间实证。

本次检查记录：`uv sync --locked`、`uv run --locked pytest -q`（162 passed，1 条既有 Starlette/httpx deprecation）、`uv run --locked python experiments/tianhao/verify_shared_results.py`（631 checks passed）、Streamlit `AppTest` 七视图离线渲染。实际无头 Chromium 1280×800 打开首页并逐页点击 Event explorer、Model laboratory、Feature ablation、Network evidence、Temporal patterns：各页无 JS exception、无横向溢出、无 Streamlit exception；截图保存在开发机 `/tmp/hk-research-verified-*.png`，未提交。真实全量本地数据输入、地图点选、其它屏幕尺寸和 Windows 浏览器尚未端到端验证。
