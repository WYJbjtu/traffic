# Tianhao96车道实际结果：审查与复现

本PR对应2026-11-04实际完成的实验：30452事件（96冻结车道，94有事件），27858个已知30分钟标签，224候选、16监督臂+4基准，557160条预测。测试n=7008。历史运行Git为36eafd…且dirty=true，如实保留；初审基于main c5e0bd…，上传前同步到main 3a184aa…，不是篡改历史身份。

## main已有的时间与天气特征

| 内容 | main位置 | 本PR处理 |
|---|---|---|
| 小时/星期sin-cos、周末、一般假期、假期前后日 | src/traffic_recovery/external/calendar.py | 原函数保留，未另造定义 |
| 年度假期源与温度/风速历史档案匹配 | experiments/tianhao/prepare_external.py | 保留公式，去除未声明HTML库依赖、支持两种Release路径 |
| 通用天气安全适配器 | src/traffic_recovery/external/weather.py | 未修改 |
| 15分钟历史速度与流量适配 | experiments/tianhao/prepare_local.py | 历史读取支持跨Parquet行组及96目录；本轮不使用flow |
| 原L2/树/RF/HGB接口 | src/traffic_recovery/models/supervised.py | 未修改共享分发；L1/SVM独立扩展 |

main已包含时间/天气的代码，并不意味着已包含本轮96事件的已计算特征和结果。96需重新匹配事件，不能复用24车道特征或分数。

## 实际审查与已修复问题

- 原个人Notebook/run_release96.py依赖project.local.json和私人目录，且准备阶段使用符号链接；现公开Notebook默认离线核验，CLI要求显式Release/缓存/输出路径，Windows普通账户无需symlink。
- 原train只核验准备产物，未重新认证被链接的Release；现prepare/train均检查仓库固定的Release清单和所有文件SHA。
- 原天气解析用glob发现文件；现先要求匹配已认证的90个天气ZIP完整集合，额外未认证文件明确失败。
- 原Notebook显示实时配置/源码而读取旧拟合；现读取实际训练冻结配置，核验历史源码SHA及发布源码SHA；有意的可移植变更单独记录，不伪称同一次训练。
- 原制备源码清单覆盖不完整；公开准备过程纳入路径、契约、数据集、日历与连接等依赖；锁文件也核验。
- 预测/指标/混淆矩阵/参数及来源清单与历史manifest对应，并在publication_manifest.json中重新逐文件列出SHA；原始manifest保留完整，包括仅留本地的产物清单。

## 默认离线核验

在仓库根目录：

```text
uv sync --locked
uv run --locked python experiments/tianhao/verify_release96.py
uv run --locked python -m pytest
```

在已有Jupyter的Python3.12内核打开notebooks/Tianhao_新版96车道_完整重跑_20261104.ipynb，Run All可离线重算图表/指标。缺少Jupyter可先安装Notebook前端；它不是核心CLI运行依赖。若从仓库外部运行Notebook，设置TRAFFIC_REPOSITORY为当前克隆位置。

离线核验不需要模型二进制，**不假称重做概率重放**。完整模型的train/validation/test概率重放已在原始本地运行验证，记录为original_local_verification.json；重新重放需要下面的完整重训。

## 完整重建、调参与训练

从[新Release](https://github.com/WYJbjtu/traffic/releases/tag/data-expanded-96-2023-2026-v1)下载并解压96车道数据。外部缓存须包含sources.csv中的4份官方年度公告、90个月ZIP及EvidenceClient生成的.meta.json；每份URL及原字节SHA均核对。重新获取的retrieved_at如实记录为新证据，不冒充原运行时间。

```text
uv run --locked python experiments/tianhao/acquire_sources.py probe
uv run --locked python experiments/tianhao/acquire_sources.py weather
uv run --locked python experiments/tianhao/run_release96.py prepare --release-dir <解压目录> --source-cache <认证外部缓存> --output-dir <新准备目录>
uv run --locked python experiments/tianhao/run_release96.py train --release-dir <解压目录> --prepared-dir <准备目录> --output-dir <新模型目录>
uv run --locked python experiments/tianhao/verify_workflow.py --run-dir <模型目录> --dataset <准备目录/event_features.parquet> --events <解压目录/processed/events.parquet>
uv run --locked python experiments/tianhao/verify_release96.py --release-dir <解压目录> --source-cache <认证外部缓存>
```

acquire_sources默认将缓存写到data/local/tianhao_experiment/sources，可用TIANHAO_WORK_DIR调整；若同URL档案的字节在来源端改变，需审核新版本而非绕过SHA。所有重建/模型输出目录必须不存在。

## 结果边界

- 四组：本地→历史→日历→天气。包不含逐日volume_count/occupancy_pct，flow_slots只是观测计数，不能当流量数值。原24五组与本96四组不是同条件比较。
- 30分钟持续恢复确认；Proposal恢复开始、参考速度方案、跨年身份与邻居匹配仍待全组确认。既往测试接触状态保留。
- 温度/风速为King’s Park区域代理，不宣称最近站。雨量、事故、活动、邻路未输入；缺失不填造全0。
- 各模型同外层事件队列；SVM训练期前段基础拟合、后段sigmoid校准，样本分配与其他模型不同，不能仅凭事件配对声称所有训练条件相同。
- PR #17已合并，包含其他96模型、XGBoost、空间审查和依赖更新。本PR同步该main，不修改其expanded96.py、pyproject.toml、uv.lock或共享接口。原实验锁文件以original_uv.lock单独保留，发布核验分别绑定历史锁和当前锁，不把后来的XGBoost环境伪称原训练环境；没有现成事件级同口径预测时不混排模型。

## 审查范围

按code-review的Standards与Spec两轴分别审查。初查发现的是复现/来源绑定问题，没有发现已保存96结果伪造或复用了旧24预测。修复后的最终验证结果见结果目录的publication_review.json与publication_manifest.json。

## 最终主线兼容检查

上传期间PR #17合并，分支已无冲突重放到3a184aa。当前237项完整测试通过，1条既有Starlette弃用提示。原运行与可移植重训均在此前锁文件上完成，历史锁保留为original_uv.lock；同步后全部旧依赖版本保持不变，新添XGBoost及Linux的NCCL依赖。

本机macOS缺系统OpenMP，uv子进程未保留动态库路径。最终测试使用uv sync --locked同步的隔离Python直接执行python -m pytest，并仅在该命令上临时指定已安装scikit-learn自带.dylibs路径。没有改系统或队友代码；Linux/Windows遵循当前main的标准uv测试入口。

## Windows字节一致性修复

PR #18首轮Linux CI通过，但Windows为235通过、1失败：Git自动将feature_group_comparisons.csv的LF转换为CRLF，破坏原字节SHA。现仅对本结果目录及manifest绑定的代码、配置、Notebook和锁文件设置-text，保持Git原字节；不放宽哈希、不改变历史结果。新增core.autocrlf=true实际checkout回归，修复前复现相同CSV字节差异，修复后通过；完整本地测试237通过。最新跨平台CI结果以PR checks为准。
