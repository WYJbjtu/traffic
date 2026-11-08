# 只用这个版本制作 Poster

交付版本：`p1-cw-final-20261108-v2`。主实验：`p1-cw-matrix-v2-20261108`。离线双击 `index.html` 即可预览、复制文案；不用 Python、Streamlit、网络地图或现场运行。5分钟只讲 Poster，讲稿目标约4分30秒，必须自行排练。

## 唯一数字来源

本包 `03_final_results.csv`：同一 old96 / recovery_confirmation_v1 / 30分钟 / P1 inferred-network 群体。完整32臂，验证和测试共64行；主图只比较测试 F3/F7。训练7,611、验证4,680、测试3,933（689正、3,244负）；测试时段2026年1–9月曾被查看，是回溯探索而非新盲测。

C/W不是缺失交接：Tianhao认证包已接收、核验并实际入模。C为日历，W仅京士柏温度/风速及质量字段，不是所有天气。不要将观察槽数Q称为车流量。

## 必用三图（PNG 300 dpi；同名SVG/PDF可编辑）

1. `figures/01_spatial_gain_cw.png`：主结果，占最大结果区域。**保留跨零区间和图下注释**。
2. `figures/02_real_directed_network.png`：真实道路方法图，标注 inferred，不能改成官方认证上下游。
3. `figures/03_real_event_case.png`：真实事件、时间可得性与标签；不是挑选的成功案例。

可选：`04_full_matrix_auc.png`（完整矩阵）、`05_matched_structure_controls.png`（当前同维度结构对照）。篇幅不足就不放；不要挤小主图。每图英文图注见 `04_figure_captions_en.md`，数据源在 `figure_data/`。

建议阅读顺序：问题与定义 → 方法图 → 事件图 → 主结果 → 限制。主文案 `01_poster_copy_en.md`，讲稿 `05_presentation_4m30s_en.md`，问答 `06_likely_questions_zh_en.md`。

## 必须保留的结论边界

四模型AUC点估计均增加，但检测器区间只有HGB不跨零；均未经多重比较校正。RF Recall略降，LR Brier/Log Loss变差。不要写“所有指标一致提升”“控制所有天气”“证明方向/因果关系”“全港泛化”“新盲测”或“已部署”。

## 不得混用

旧24车道、完整96车道A1/A2、PR #21 M0/M1、旧unified F0/F4、Tianhao原独立实验和新Proposal v2都不是本主结果。旧F0/F4区间不能移给F3/F7。新Proposal为detector/direction恢复开始标签，本包主结果为旧lane-level恢复确认。历史材料不用于补齐本表。

## 交付前人工确认

- 作者全部姓名、组号、课程模板要求：待组员填写；目前仅能确认DSC6004 / City University of Hong Kong，不能猜作者名单。
- 团队明确同意以“恢复确认”作为本次实际主实验，并在Poster保留与原Proposal恢复开始的差异。
- 新Proposal v2采用审核：Issue #3读取时仍OPEN，清单未勾选、无评论；不能伪造签字。
- 本轮没有新Proposal模型、P3历史认证、完整90天气原档本机独立重建、新置换负对照或新远端CI；这些不妨碍本包已完成的回溯主实验，但限制其科学表述。

文件哈希在 `07_evidence_manifest.json`、`SHA256SUMS`；完整逐事件概率在本地研究目录，不随包发送。请只手动发送本交接ZIP，不发送.git/.venv/原始交通档案。
