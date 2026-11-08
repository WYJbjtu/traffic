# 最终实验与 Poster 本地交接验收 — 2026-11-08

## 唯一最终交付

- 分支：`research/poster-finalization`。生成代码冻结于 `501779ccc00736b1f3d89f13eec37b4aced66c21`；最终交接提交位于其后，查询 `git log -1`。不改变运行时真实的Git状态记录。
- [离线交接首页](../../deliverables/poster_handoff/p1-cw-final-20261108-v2/index.html)。全部主数字来自 [03_final_results.csv](../../deliverables/poster_handoff/p1-cw-final-20261108-v2/03_final_results.csv)，同学不需要安装Python或运行前端。
- ZIP：`deliverables/poster_handoff_p1-cw-final-20261108-v2.zip`，**1,584,127 bytes**。
- SHA-256：`ca99602acb5010b1e014862c164667c7e2554f7285e92e665ed2f00d98df7f4a`。
- [实际临时解压验证收据](../../deliverables/poster_handoff_p1-cw-final-20261108-v2.verification.json)：64文件、5PNG解码、5SVG解析、5PDF文件头、64结果行及29相对HTML引用通过。五张最终PNG另逐张实际打开检查过，英文标签/单位/图例无裁切；不是仅检查文件存在。没有浏览器验收声明。
- 英文讲稿实际 **553词**，建议122.9词/分钟、4分30秒排练目标；没有真人计时声明。

## 接收与必要修复

初始目录是原项目，工作区干净，分支`research/unified-feature-experiments`、HEAD `53ab8e7`；没有MERGE_HEAD/CHERRY_PICK_HEAD/rebase。只读`git fetch recovery`后新建专用分支并快进到`7b0d3f9`。没有修改remote URL，没有访问旧origin获取数据，没有新建worktree。

README的冲突标记是**已经提交的内容**，不是正在进行的merge。仓库外`/tmp/poster-finalization-backup/`保存当前、HEAD和recovery/main版本后按内容整合：保留研究说明、迁移有效链接，去除冲突带来的过时重复和矛盾段落；原历史报告没有改写。

冻结`p1-f0-f4-v1/metrics.csv`原字节仍为`a263659e54dedefde9a3ce801dbff09d09c0e181b62ad5546d63b1cfa887dcbf`。仓库外Git索引checkout在`autocrlf=true`下复现`c13ec2e0e447b56aed981b349275ef10532a3bce5dc6b3f3bc28948efb229b7e`失败。最初试加根属性规则被历史Tianhao源码哈希门禁拒绝；**根.gitattributes自身也被冻结**，因此恢复根文件原字节，在`experiments/unified96/.gitattributes`加入局部`runs/** -text`，交接包在`deliverables/.gitattributes`保护。没有改期望哈希、删除测试或全库重新归一化。后续模拟通过，但不代表实际Windows或新的远端CI。

## 真实输入与实验

Tianhao四分卷/完整ZIP核验通过：20,822,076 bytes，SHA `cdb5f9a9a704cd2bcd823e4a7ba2615319c026f0311e2be55fa998b0418513c0`。解压到全新ignored目录`data/local/poster-finalization/cw-authenticated-v1/`。包内verify_handoff对真实旧Release和当前仓库通过：C/W各30,452行，43,387来源快照，94来源，4份官方假期公告。冻结源码和当前绑定代码一致；无需解除门禁。核验的是已交付特征、来源值/时刻及生产者重建记录，不是本机重下90月天气ZIP独立重建。

主运行：`data/local/unified96/p1-cw-matrix-v2-20261108/`。

- 目标：`recovery_confirmation_v1`，30分钟，旧96车道P1推断网络资格群体。
- 训练7,611／验证4,680／测试3,933，冻结事件ID哈希完全一致；测试689正、3,244负、44目标检测器。
- 先四模型F3/F7，后F0/F4/F1/F5/F2/F6，**32臂全部重拟合**，每臂两个候选、仅训练拟合插补/缩放；验证最小log loss、无重拟合，阈值0.5。保存275,616条逐事件验证/测试概率，未按天气dropna。
- C/W按event_id+prediction_time双键一对一连接；白名单、同名冲突、可用性、年龄门禁。P1测试温度缺6、风缺40，是真缺失，训练插补不是零。
- 模型输入、event_population.parquet、predictions.parquet、metrics.csv、tuning.csv、fit_audit.json、manifest.json及逐臂检查点均已保存。本包只携带轻量证据，不带完整输入/概率。
- 全部指标从保存概率独立复算，32臂训练插补均值与训练行直接对照；XGBoost在拼表前float32、拼表后float64导致均值损失约3.3e-8差异，审计容差1e-7，排名/计数指标更严格。AP不是梯形PR-AUC。

### 主比较：F7 − F3

| 模型 | F3 AUC | F7 AUC | 差值 | 95%检测器配对区间 | F3→F7 Macro-F1 | F3→F7 Recall |
|---|---:|---:|---:|---|---|---|
| Logistic Regression | 0.666964 | 0.703253 | +0.036289 | [-0.003889, 0.073699] | 0.559799→0.601141 | 0.152395→0.309144 |
| Random Forest | 0.810464 | 0.815116 | +0.004651 | [-0.013312, 0.026934] | 0.618261→0.621940 | 0.238026→0.235123 |
| XGBoost | 0.818871 | 0.829019 | +0.010148 | [-0.002943, 0.024914] | 0.682812→0.693493 | 0.403483→0.447025 |
| HistGradientBoosting | 0.814373 | 0.830243 | +0.015870 | [0.002659, 0.029106] | 0.678594→0.697386 | 0.425254→0.470247 |

每模型1,000目标检测器聚类配对重复，seed42，44群，1,000有效、0单类无效。重复抽中的群完整重复计入。**固定模型条件区间，未完全处理共享邻居依赖，未多重比较校正。** HGB是四模型之一，不是测试后挑选的预定唯一最佳模型。RF Recall下降、LR Brier/Log Loss恶化。测试期早已查看，是回溯探索而非新盲测。

其余三组空间对比已全部计算。未控制C/W的F4−F0 AUC增量分别+0.042839/+0.033566/+0.032278/+0.030658；控制后尤其RF/XGB减小。只有Calendar、只有Weather对比见包内`figure_data/spatial_contrasts.csv`，不根据测试修改规则。

### 稳健性、结构与错误

- 固定七天HKT块（2026-01-01锚定），39非空群，seed20261108，每模型1,000次配对重复；单独记录，不替换检测器主区间。
- 当前结构对照：`data/local/unified96/p1-cw-controls-v1-20261108/`，RF/XGB × 有向/同邻居去方向/250m地理，共6臂。三种都F3+同样12个S1字段，不用全S1–S4与简化控制混比。
- 测试AUC（地理/无向/有向）：RF 0.810339/0.818830/0.820062；XGB 0.815663/0.827906/0.831434。方向相对无向差异小、无专门区间，不宣称方向效应。地理观测仅覆盖67.2%，其余100%，限制结构归因。
- only_spatial_correct / only_base_correct：LR172/302，RF111/91，XGB143/149，HGB176/151。全部四分类计数、正负例概率变化及混淆计数随包。
- 没有新置换实验；旧PR #21部分置换保留旧身份，不当本次C/W控制结果。

## 图与交接材料

必用`01_spatial_gain_cw.png`、`02_real_directed_network.png`、`03_real_event_case.png`；另有矩阵与匹配结构对照。PNG300dpi及SVG/PDF，CSV图源、图注、manifest齐全。

地图按预先规定的几何规则选择AID01103→AID01104→AID01105；偏移约6.0/9.5/10.6m，采用路径382.392/320.630m，绘制原始官方子段长度与保存路径复核一致。上游匹配仍模糊，图中明确标注；不是45m偏移短路径反例。背景仅为控制图源体积以5cm容差作显示简化，不改变选中道路子段、图规则或任何速度输入，政策写入figure_provenance。

事件按预测时刻/event_id选首个合格测试事件`237614b88349c5712337`，AID02110，2026-01-02 08:35HKT。标签0。邻居只画真实as-of点，本地后验曲线与可得输入不同色，真实缺测不补线。四模型概率取本次保存文件，不依成功与否筛案例。

完整英文文案、553词讲稿、12组中英问答、中文科学限制与Proposal差异、复现命令、来源链以及单一数字入口均已交付。

## Proposal v2采用状态

只读检查独立分支`b60c5951702657ac44a2654cb997adb06038498a`实际文件和Issue #3：库存CSV256行，unit_quality合计36,099,990方向箱，96方向；strict10 700（691/9/0），sampled2 26,306（11,865/7,512/6,929），30分钟已知测试1,981+3,961=5,942。新标签工程确已实现，模型未完成。Issue仍OPEN、清单未勾选、无评论；未得到团队采用意见，不另开新目标训练。此次是报告/CSV审计，不是本机重建新Release全部数据。没有把旧C/W event_id、标签、模型分数或新版本流量/占有率混入主实验。

## 验收与执行中的失败记录

最终命令`uv sync --locked`、`uv run --locked pytest -q`：**294 passed，1个既有Starlette/httpx弃用警告，65.45秒**。包含C/W双键、未来时间/年龄/缺失、白名单、训练拟合、32臂实际事件一致性、独立指标、bootstrap重复权重、图表表格一致性、冻结哈希、冲突标记、跨平台原字节保护。测试日志见`pytest-final.txt`。浏览器没有运行，因为没有新前端。

保留而不粉饰的中间失败：
1. 初次`p1-cw-matrix-v1-20261108`在F3完成后严格JSON拒绝XGBoost参数里的NaN sentinel；修成字面字符串而非改模型，保留失败目录，完整结果来自新v2。
2. 根.gitattributes受历史哈希约束，最初修复位置触发2个历史回归失败；恢复原字节，改用子目录规则后全量通过。
3. 交接草稿v1的ZIP已解压验证，但最后receipt对相对/绝对Path转换失败；增加真实回归测试、修复路径，旧草稿搬入ignored `data/local/poster-finalization/package-receipt-failed-v1/`。最终仅v2进入deliverables。草稿原图源含大量不需展示的道路顶点，最终仅背景显示简化，科学路径和模型无变化。

暂存最终文件后，又在仓库外完整索引`autocrlf=true` checkout验证：旧unified全部产物哈希和最终交接64文件、图片、表格及相对引用再次通过。这仍是Linux Git换行模拟，不是实际Windows CI。

以上均没有通过改历史哈希、移除测试或换测试群体解决。没有全量重新下载交通、天气或新Proposal原档，没有独立人审签字、P3批准、GNN、部署、新盲测或远端CI声明。

## 用户下一步

从WSL执行`explorer.exe "$(wslpath -w deliverables/poster_handoff/p1-cw-final-20261108-v2)"`，或在Windows资源管理器打开实际wslpath结果：

```text
\\wsl.localhost\Ubuntu\root\projects\hk-traffic-recovery-prediction\deliverables\poster_handoff\p1-cw-final-20261108-v2
```

手动发送上述ZIP即可。作者/组号、采用恢复确认口径和对Proposal差异的披露须团队确认；不要扩大结论。**本次未执行任何远程Push、PR操作、Release上传或其他远程写入。全部成果保存在本地。**
