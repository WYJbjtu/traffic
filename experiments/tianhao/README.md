# Tianhao Wu / Fairy-6b：长期真实数据实验

## 2026-11-02：核验修复、双方统一比较和外部数据交接

- [统一比较与混淆矩阵](../../reports/tianhao_followup_20261102/comparison/README.md)：从双方已有预测重算，保留实验、特征、时限及split，补齐Member4的Macro-F1，不训练或重新选模型。
- [实际外部来源、覆盖/缺失与排除说明](../../docs/tianhao_external_data_handoff.md)：分别列出全部事件和已知30分钟标签事件的分母，含逐split天气缺失率。
- 默认核验严格检查旧 `results/` 和 `rerun_20261101/` 的不可变产物；旧清单记录的README、当前代码和Notebook变化列在 `integrity.workspace_changes` 中，不再令结果核验失败。它不认证当前源代码等于原发布代码，也不代表科学批准。原manifest与结果哈希不改写。
- 可加 `--strict-snapshot` 要求清单中的源代码/文档哈希也匹配；在后续main上源文件已改变时应失败。核对原发布时快照可在冻结提交 `8374dfbec594e1a6392ef356f6b7062c6e65d6bb` 上使用该版本原来的核验脚本。

```text
uv run --locked python experiments/tianhao/verify_review.py
uv run --locked python experiments/tianhao/verify_shared_results.py
uv run --locked python experiments/tianhao/compare_saved_runs.py --output-dir reports/local/unified-comparison-new
```

比较目录必须尚不存在，避免覆盖旧证据。外部覆盖的完整重算需要原始本地audit，命令和哈希见交接说明。过去记录的645/631是当时的文件级检查计数；新核验输出将源码诊断与结果文件计数分开，检查数相应改变。

**EXPLORATORY — NOT APPROVED AS FINAL RESULTS**

这是 PR #5 之后新增的真实数据实验与外部特征整合。复用仓库已有的 `external.calendar`、数据传输和 `models` 训练/评估函数；另包含本次核查发现的calendar/contract/evaluation保护性修复及回归测试；没有重做队友的事件标签、网络或集成模型。基于主分支已合并的 PR #7/#8 建立独立增量。

先打开 [2026-11-01实际重跑 Notebook](../../notebooks/03_Tianhao_真实重跑与模型可视化.ipynb)（含代码及全部图表；Run All需要下载大文件），或用 [离线核验 Notebook](../../notebooks/02_Tianhao_真实模型与外部特征实验.ipynb)，或阅读 [结果说明](results/report.md)。02号Notebook默认离线核对已保存预测与指标；03号Notebook含实际特征准备和训练，Run All会重新运行。两者均可在GitHub直接预览已有输出。

## 本次包含

- 新增：15分钟速度趋势、同车道流量/占有率、官方年度假期与日历、京士柏历史温度/风速整合脚本。
- 30分钟主实验：4个基准、逻辑回归/决策树各5组累加特征；真实7597事件、6799个已知标签、14实验臂。
- `results/predictions.parquet`：原始最终运行的95186条真实预测，约0.93MB，含训练/验证/测试划分、事件键、标签、预测分数和模型版本。规则分数不是概率。
- 小型指标表、调参表、解释、错误分组、冻结计划和来源/核验记录。

历史实验的原始模型引擎提交为 `4fd706e`。2026-11-01另有实际重新准备特征和重新拟合的独立运行，结果见 `rerun_20261101/`；分享版Notebook的22个代码单元也重新执行验证。保持原参数候选，没有按测试结果重新挑模型或调参。历史运行摘要保留原哈希；`provenance.json` 清楚区分已包含文件和留在本地的文件。旧运行、原始档案、完整特征表、拟合模型、缓存、Jupyter token、重复HTML均未上传。原始 Notebook 留在用户本地，仓库版只依赖已提交的轻量产物。

## 阅读与核对

在仓库根目录，Python 3.12：

```bash
uv sync --locked
uv run --locked python experiments/tianhao/verify_review.py
uv run --locked python experiments/tianhao/verify_shared_results.py
uv pip install --python .venv/bin/python -r experiments/tianhao/requirements-notebook.txt
uv run --locked jupyter lab notebooks/02_Tianhao_真实模型与外部特征实验.ipynb
```

Windows 安装可把 `.venv/bin/python` 换成 `.venv/Scripts/python.exe`。可选工具单独列出，不修改全组的 `pyproject.toml` 或锁文件。Notebook 所有代码可重新执行；核心核对脚本不依赖Jupyter。

## 从来源重建完整实验（可选，大文件需下载）

默认所有大文件写入被 Git 忽略的 `data/local/tianhao_experiment/`。可用环境变量 `TIANHAO_WORK_DIR` 自定缓存目录，`TIANHAO_DATA_DIR` 指向已有共享Release解压目录。路径支持 `pathlib`，不依赖作者电脑的目录。每次训练新建运行目录；不会覆盖已提交的历史结果。

在仓库根目录，依次执行（每行均以 `uv run --locked python` 开头）：

```bash
uv run --locked python experiments/tianhao/acquire_sources.py probe
uv run --locked python experiments/tianhao/acquire_sources.py traffic
uv run --locked python experiments/tianhao/stage_release.py
uv run --locked python experiments/tianhao/acquire_sources.py weather
uv run --locked python experiments/tianhao/acquire_sources.py conditional-audit
uv run --locked python experiments/tianhao/prepare_local.py speed
uv run --locked python experiments/tianhao/prepare_local.py flow
uv run --locked python experiments/tianhao/prepare_external.py calendar
uv run --locked python experiments/tianhao/prepare_external.py weather
uv run --locked python experiments/tianhao/run_experiment.py
uv run --locked python experiments/tianhao/verify_real_run.py
```

来源是 [小组长期数据Release](https://github.com/CityuHK-wyj/hk-traffic-recovery-prediction/releases/tag/data-long-window-2023-2026-v1)、[香港政府历史档案API](https://data.gov.hk/en/help/api-spec)、政府公告年度假期及香港天文台历史温度/风速。交通ZIP约1.67GB，先核验发布SHA256，再核验共享清单中使用的成员；天气约90个月档案。HTTP证据、失败响应、捕获时间和原始字节保留在本地。后续来源可能变化，重取的哈希不保证与历史快照相同；必须报告差异。

原始运行的参数配置可通过 `results/provenance.json` 指向的引擎提交获取。当前分支已包含队友新增RF/HGB配置；脚本仍只拟合logistic/tree，后续运行应核对配置和软件哈希，不宣称与历史结果逐字节相同。原始脚本哈希与当前移植脚本哈希分别记录；主要移植为路径配置、相对运行指针、发布包分阶段提取，以及让必要来源下载失败时显式中止。

## 边界和队友依赖

使用交接的“持续恢复确认”标签，与proposal“恢复开始”仍有差异；只跑30分钟，没有运行15/60分钟。24车道选择偏差、2023固定参考漂移、跨年设备身份、稀疏分箱、未知标签排除、事件相关性均未解决。参考速度、标签与划分需队友共同确认。

日历整组同时加入小时、星期、周末与假期，改善不能单归因于假期。京士柏是区域代理，未证明各道路最近站；天气没有一致提升。雨量未建立安全历史重放，事故缺全时段重放与地点消歧，活动缺预测时点可用证据，邻路特征缺人工验证，因此均未当成0或加入模型。RF/HGB来自队友PR #8，本次不重复实现或声称已经比较。

验证集log loss选择的展示模型是 `decision_tree / local+history+flow+calendar`。测试Macro-F1 0.6290、balanced accuracy 0.6384、ROC-AUC 0.7007；不作显著性、因果或全香港泛化声明。通过测试和哈希核验不等于科学批准。


## 2026-11-01分享包与实际重跑

- `rerun_20261101/` 是重新从已校验Release和真实外部来源准备特征、拟合模型后的轻量结果；`results/` 保留原历史运行。
- 新旧预测的事件、时间、标签、分数与决策均一致；不同运行的版本/manifest字段不能要求逐字节相同。
- 03号Notebook是仓库可移植版本，全部22个代码单元已执行，10张图已嵌入；机器路径仅在输出文字中作匿名化处理。默认用 `data/local/tianhao_experiment/`，支持 `TIANHAO_WORK_DIR` / `TIANHAO_DATA_DIR`，无需作者目录。
- 本地原Notebook及HTML、数据ZIP、90个月天气ZIP、完整特征表、拟合模型、缓存和Jupyter运行文件不上传。原始manifest中留在本地的文件/路径仅为历史来源记录；不是可下载附件。
- `verify_shared_results.py` 无需大数据或拟合模型即可核对新预测指标、配对样本、新旧结果一致性和分享文件哈希。
- `share_manifest.json` 记录本次交付文件SHA256；`rerun_20261101/shared_notebook_validation.json` 记录仓库版Notebook实际执行核验。`original_*` 记录原本地运行，其Notebook哈希不用于仓库移植版。
- 重跑03号Notebook前，按上面的下载/提取命令准备来源；`stage_release.py` 还提取前半部分审查所需的CSV和检测器元数据。运行中不会下载47GB完整原始数据，也不批准标签定义。

代码审查报告在 `docs/tianhao_proposal_review.md`。其中“尚未提交/推送”描述核查当时状态；本分享包在独立PR供小组审阅，尚未合并，不代表科学审批。
