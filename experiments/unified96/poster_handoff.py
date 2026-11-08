"""Build and verify the independent offline poster handoff (no remote writes).

Run only against a completed matrix/analysis/control version; output and ZIP
must not exist. Large probabilities and inputs remain in local research storage.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from html import escape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from urllib.parse import unquote, urlparse
import zipfile
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
from PIL import Image

from experiments.unified96.run import ROOT, MODELS
from experiments.unified96.matrix import dump
from experiments.unified96.poster_analysis import verify_run
from experiments.unified96.poster_figures import build_figures, NAMES
from traffic_recovery.data.http import sha256_file

FIGURES = [
    ('01_spatial_gain_cw','Main result; centre/right, largest result panel',
     'Paired F7 minus F3 ROC-AUC differences for 30-minute recovery confirmation on 3,933 identical P1 retrospective inferred-network test events. F3 includes local, history, observation quality, calendar, temperature and wind; F7 adds inferred spatial features. Bars are unadjusted 95% detector-cluster Bootstrap intervals (1,000 paired draws; 44 target detectors), conditional on fixed fitted models. Shared-neighbor dependence is not fully addressed.'),
    ('02_real_directed_network','Method; upper-left/centre',
     'Official CENTERLINE polylines and real detector positions illustrate inferred directed relationships around AID01104. Colored paths follow adopted official road subsegments, not straight-line detector links. Dotted segments are mapping offsets. Geometry-based, score-independent selection; AID01103 remains ambiguously matched. A 2026 snapshot does not establish historical or legally verified connectivity.'),
    ('03_real_event_case','Data/label explanation; lower-left/centre',
     'The first eligible chronological P1 test event (237614b88349c5712337, AID02110, 2 January 2026 at 08:35 HKT), selected without prediction-score filtering. Speeds are ratios to each unit’s own frozen reference. Neighbor measurements are as-of points, not continuous curves; orange local observations were unavailable at prediction. Thresholds and the 30-minute outcome window are shown. The negative label means no qualifying recovery confirmation within the horizon, not permanent non-recovery.'),
    ('04_full_matrix_auc','Optional supplementary panel; omit if crowded',
     'All 32 refitted model/feature arms on the same P1 test events. Base is local/history/observation quality; C is calendar, W is temperature/wind, and S is inferred spatial. Two fixed candidates per model/arm were selected by validation log loss. These previously examined test data do not select a new best model.'),
    ('05_matched_structure_controls','Optional small sensitivity panel',
     'Current C/W-adjusted RF and XGBoost structure comparisons use F3 plus the same 12 S1 summary fields, not full F7. Directed and pooled representations use identical neighbor observations; geographic neighbors follow the frozen 250 m rule. Geographic availability is 67.2% of test events versus 100% for the other representations. The small directed–pooled differences do not establish a direction-specific effect; the vertical axis is explicitly zoomed.')]


def text(path: Path, value: str) -> None:
    path.write_text(value.strip()+'\n',encoding='utf-8')


def write_documents(out: Path, run: Path, metrics: pd.DataFrame, gains: pd.DataFrame) -> None:
    main=gains.loc[gains.comparison.eq('F7_minus_F3')].set_index('model')
    test=metrics.loc[metrics.split.eq('test')].set_index(['model','feature_arm'])
    table='| Model | F3 AUC | F7 AUC | Paired Δ AUC [95% interval] |\n|---|---:|---:|---|\n'
    for model in MODELS:
        row=main.loc[model]
        table+=f'| {NAMES[model]} | {test.loc[(model,"F3"),"roc_auc"]:.4f} | {test.loc[(model,"F7"),"roc_auc"]:.4f} | {row.delta_roc_auc:+.4f} [{row.ci_95_lower:+.4f}, {row.ci_95_upper:+.4f}] |\n'
    text(out/'00_先读我_给Poster同学.md',f'''# 只用这个版本制作 Poster

交付版本：`{out.name}`。主实验：`{run.name}`。离线双击 `index.html` 即可预览、复制文案；不用 Python、Streamlit、网络地图或现场运行。5分钟只讲 Poster，讲稿目标约4分30秒，必须自行排练。

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

文件哈希在 `07_evidence_manifest.json`、`SHA256SUMS`；完整逐事件概率在本地研究目录，不随包发送。请只手动发送本交接ZIP，不发送.git/.venv/原始交通档案。''')
    text(out/'01_poster_copy_en.md',f'''# Predicting 30-Minute Congestion Recovery Confirmation in Hong Kong

**An exploratory evaluation of inferred spatial features after calendar and temperature/wind adjustment**

Authors / group: **[TEAM TO CONFIRM]** · DSC6004 · City University of Hong Kong

## Research Question
Do inferred neighboring-road conditions improve recovery-confirmation prediction beyond local traffic history, observation quality, calendar and the included weather covariates?

## Data and Target
- Official archived traffic, 2023–September 2026: 96 selected lane units; 30,452 events in the frozen source release.
- P1 retains known 30-minute labels with at least one available inferred neighbor: **7,611 train / 4,680 validation / 3,933 test** events; test positives **689 (17.5%)**.
- Congestion: two usable five-minute bins at speed/reference ≤0.5. Recovery confirmation: three high bins at ≥0.8; confirmation occurs within the next 30 minutes. Gaps censor labels.
- This differs from the original Proposal’s recovery-*start* target. Sparse observations do not establish continuous physical recovery.

## Directed Network Construction
Official CENTERLINE, INTERSECTION and TURN records support a candidate graph. Matching uses metre distance and directional compatibility; transitions check shared endpoints/elevation, intersection evidence and recorded turn restrictions. **2026 inferred relationships are not a verified historical network.**

## Feature Engineering / Experimental Design
- Base: local speed/state + past speed/trends + observation-quality counts (not vehicle flow).
- C: calendar and official holidays. W: King’s Park temperature/wind, ages and missingness.
- S: inferred upstream/downstream summaries, congestion contrasts, distance weighting and past changes.
- Four algorithms × eight feature arms; identical events, train-only imputation/scaling, two candidates selected by validation log loss, no refit; threshold **0.5**.
- Primary comparison: **F3 = Base+C+W; F7 = F3+S**. Chronological splits: 2023–24 / 2025 / 2026 Jan–Sep. The test period was previously examined.

## Key Results
{table}
Intervals use 1,000 paired target-detector Bootstrap draws (44 detectors), without multiple-comparison adjustment. HGB’s interval excludes zero; the other three include zero. RF’s gain shrinks from **+0.0336 without C/W** to **+0.0047 with C/W**. HGB Macro-F1 improves **0.6786→0.6974** and Recall **0.4253→0.4702**. Improvements are not uniform: RF Recall slightly declines and LR probability losses worsen.

## Limitations
Retrospective test reuse; selected lane/neighbor cohort; sparse and censored observations; uncertain historical mappings; regional temperature/wind proxy, no rain or incidents. Bootstrap conditions on fitted models and does not fully address shared-neighbor dependence. No causal or citywide generalisation claim.

## Conclusion
Inferred spatial features provide **model-dependent retrospective incremental information** after the included calendar and temperature/wind covariates. Adjustment attenuates several gains; evidence does not support a universal improvement or certified road connectivity.

## Sources
Hong Kong Transport Department traffic archives and Road Network v2; Hong Kong Observatory temperature/wind archives; official annual General Holidays notices. Versioned data, features, probabilities and figure sources: `07_evidence_manifest.json`.''')
    text(out/'02_claims_and_limits_zh.md',f'''# 科学口径、结果与不得夸大的限制

## 主结果（唯一口径）

`{run.name}`；expanded96-long-window-v1；recovery_confirmation_v1；P1；30分钟；test=3,933，44个目标检测器。32臂全部重新训练，未沿用旧F0/F4拟合结果。全部275,616条验证/测试预测具有同一事件身份、时刻和标签；指标独立复算。AP是sklearn Average Precision，不是梯形PR-AUC。

{table}

C/W加入后空间增量通常减小。不能将HGB从多个模型中事后挑出并包装成预先指定唯一最佳模型。HGB的单个未校正95%区间不跨零，不等于稳健的总体显著性定论。

## 阈值0.5下并非全面改善

- LR：only_spatial_correct=172、only_base_correct=302；AUC/Macro-F1/Recall升高但总正确数减少130，Brier和Log Loss变差。
- RF：111 vs 91；总正确数增加20，但Recall 0.2380→0.2351，Brier/Log Loss略变差。
- XGBoost：143 vs 149；总正确数减少6，Macro-F1/Recall及损失改善，但Precision略降。
- HGB：176 vs 151；总正确数增加25，Macro-F1/Recall/Precision/Brier/Log Loss均改善。
- 正、负例平均概率变化及四类完整计数见 `figure_data/error_transitions.csv`，混淆矩阵计数见最终结果CSV。不要只报AUC。

## Bootstrap与敏感性

主分析：44目标检测器、同抽样两臂、每模型1,000有效重复、0单类无效、seed=42。被重复抽到的检测器完整重复计入。是固定已拟合模型预测的条件区间，不包括重训练/调参的不确定性。不同目标可能共享邻居，跨群依赖未完全处理；四模型区间未多重比较校正。

补充：固定HKT七天块，从2026-01-01锚定，39个非空块、1,000配对重复、seed=20261108。不同依赖假设下区间有变化；不能只选较窄区间替代主结果。原始记录 `evidence/paired_bootstrap.json`。

## 当前结构对照，不冒充旧PR #21

RF/XGB分别重训有向、相同邻居去方向、250m地理近邻，共6臂；三者都使用F3加相同12个S1特征，不用全S1–S4对比简化模型。测试AUC（地理/无向/有向）：RF 0.8103/0.8188/0.8201；XGB 0.8157/0.8279/0.8314。方向相对无向仅+0.0012/+0.0035，没有专门区间，不作方向效果显著性主张。地理观测覆盖67.2%，另两者100%，差异不能全归因拓扑。未新增置换；旧部分置换仅为旧实验的弱控制。

## Proposal差异与实现进度（标签实现 ≠ 模型完成）

已只读核验独立分支b60c5951702657ac44a2654cb997adb06038498a的实际报告/CSV/manifest及Issue #3。库存CSV为256行；unit_quality的bins合计36,099,990、96方向；strict10 700事件，691/9/0；sampled2的30m排除表合计26,306事件，11,865/7,512/6,929，测试已知1,981+3,961=5,942。Jan–Feb 2023同星期/小时参考。**恢复开始并满足随后十分钟条件的标签工程已完成；模型未训练，科学采用待审。**

本次核验的是生产者报告/已发布审核记录，没有下载并重新计算新版本全部源箱。Issue #3读取时OPEN，未勾选、无评论；并非审批。strict10无测试事件，不能称原方案模型成功。sampled2是采样支持持续性，不是完整连续观测，不能接strict10参考或usable。旧C/W的event_id不能贴新事件，旧分数不能移新目标。资料副本在 `evidence/proposal/`。

## 本机执行范围

C/W全包哈希、Release身份、源快照关联、可用时间、冻结源码与当前代码一致性通过：30,452+30,452特征、43,387快照、94来源（90天气月档+4假期公告）。这是核验交付特征及生产者重建记录；**不是本机重新下载90天气ZIP并独立重建**。全队列缺温度18、风116；P1测试缺温度6、风40，保留缺失并仅训练拟合插补。天气年龄≤60分钟，retrieved_at仅溯源。

README冲突内容已合并而非整份ours/theirs；冻结metrics原LF SHA未变。仓库外autocrlf=true精确复现CRLF失败后以目录范围-text修复并重验；不是新Windows CI。没有前端工作、GNN、扩车道或速度插值。P3仍NO-GO；没有部署。所有测试通过也不等于全部原档重建通过。

## 还需人工确认

作者/组号；课程格式；团队同意主Poster使用恢复确认并公开Proposal差异；Member 1/2/4新数据采用和独立地图/曲线审核。不得伪造审核人或把工程通过当科学签字。''')
    captions='\n\n'.join(f'## Figure {i}: {name}\n\n**Placement:** {where}\n\n{caption}\n\nFiles: `figures/{name}.png`, `.svg`, `.pdf`.' for i,(name,where,caption) in enumerate(FIGURES,1))
    text(out/'04_figure_captions_en.md','# Copy-ready figure captions\n\n'+captions)
    speech='''Good afternoon. Our project asks whether neighboring road conditions help predict when congestion will recover in Hong Kong. We focus on a precise question: after including local traffic history, calendar, temperature and wind, do inferred spatial features still add predictive information?

Please start with the data and event panel. Our frozen source release contains ninety-six selected lane units and thirty thousand, four hundred and fifty-two events. For this spatial comparison, we retain events with a known thirty-minute outcome and at least one available inferred neighbor. The resulting training, validation and test sets contain seven thousand, six hundred and eleven; four thousand, six hundred and eighty; and three thousand, nine hundred and thirty-three events.

Our target is recovery confirmation, not recovery start. Two low five-minute bins establish congestion. Three usable bins above eighty percent of the frozen reference establish recovery confirmation. We predict whether that confirmation occurs within thirty minutes. Missing follow-up produces an unknown label, not an automatic negative. Sparse observations support sampled persistence, not proof of uninterrupted physical recovery.

The network panel shows real official road geometry and real detector locations. We constructed inferred directed relationships using distance and direction compatibility, shared endpoints and elevation, intersection evidence, and recorded turn restrictions. The colored links follow road geometry. They are not straight-line geographic neighbors. However, a current official road map does not certify historical detector matching or legal movement. One illustrated upstream match remains ambiguous. We use engineered graph features, not a graph neural network.

The event panel illustrates information timing. Blue local measurements were available at prediction. Orange measurements show retrospective context only. Neighbor observations are isolated points because we do not have a complete neighbor curve for this prediction. The event was selected by chronological order, not because the model performed well.

We trained four algorithms across eight feature combinations, giving thirty-two arms. Every arm used identical events. Imputation and scaling were fitted only on training data. Each algorithm had two fixed candidates, selected using validation log loss. Classification used a common probability threshold of one half. Calendar and weather features were authenticated and joined by event identity and prediction time. Weather means King’s Park temperature and wind, not rainfall or all local road weather.

Now look at the main result. Spatial features increased the AUC point estimate for all four algorithms after adjustment. But the uncertainty and other metrics matter. The random forest increment was only about zero point zero zero five, and the XGBoost increment about zero point zero one zero. Their detector-cluster intervals include zero. HistGradientBoosting improved by about zero point zero one six, with an interval above zero, but these intervals were not adjusted for multiple comparisons. Random forest recall slightly decreased, and logistic regression probability losses worsened.

Our intervals use one thousand paired detector-cluster samples and fixed fitted models. Shared neighbors can create dependence across clusters. A supplementary weekly-block analysis also depends on its grouping assumptions. The test period was previously examined, so this is retrospective exploration rather than a fresh blind test.

We conclude that inferred spatial information can provide model-dependent incremental value after the included calendar and temperature and wind variables, but not a universal improvement. The separate Proposal recovery-start labels are implemented; their models and adoption review remain unfinished. We do not claim causality, citywide generalisation, historical network certification, or deployment. Thank you.'''
    words=len(re.findall(r"\b[\w]+(?:[’'-][\w]+)*\b",speech))
    text(out/'05_presentation_4m30s_en.md',f'# Spoken script — rehearsal target 4m30s\n\nActual script word count (regex tokens): **{words}**. Suggested pace: **{words/4.5:.1f} words/minute**; reserve 30 seconds before the 5-minute hard limit. Not human-timed. Headers/this note excluded. Rehearse against the poster, no slides or live demo.\n\n<!-- SCRIPT_START -->\n{speech}\n<!-- SCRIPT_END -->')
    qa=[
        ('为什么用图而非最近邻？ / Why a graph rather than geographic proximity?', '道路拓扑与方向可区分平行路、立交和潜在上下游，但当前推断仍会错；同维度对照差异小且地理覆盖不同，不能宣称图已被证明更优。', 'Topology and direction can distinguish proximity from plausible connectivity. Our inferred graph can still be wrong. Matched-summary controls show small directed–pooled differences and unequal geographic coverage, not a definitive proof of superiority.'),
        ('是否用了GNN？ / Did you use a GNN?', '没有。使用真实图的工程化邻居特征加LR/RF/实际XGBoost/HGB。', 'No. We used engineered graph summaries with logistic regression, random forest, actual XGBoost and HistGradientBoosting.'),
        ('如何防未来泄漏？ / How is future leakage prevented?', '双键连接，观测/可用时间不晚于预测、天气年龄≤60分钟、邻路年龄≤10分钟、训练拟合、时间分组与冻结purge。2026地图本身仍是回溯代理，不能说全部输入均历史已验证。', 'Event/time joins, observation and availability cutoffs, age limits, training-only fitting and frozen purged temporal splits protect dynamic features. The 2026 static graph is explicitly retrospective and not historically certified.'),
        ('恢复开始与确认区别？ / Start versus confirmation?', '开始是连续高箱的第一箱；确认需要后续高箱见证。旧实验以确认时刻判30分钟；新Proposal以开始及随后持续条件判定，不能换名字套分数。', 'Start is the first high-bin endpoint; confirmation is observed only after the sustaining sequence. They can fall on different sides of the deadline. Our scores belong only to confirmation.'),
        ('2026路网用于早期事件？ / Why use a 2026 network for earlier events?', '作为有明确限制的回溯推断代理；无法核实历史变更、硬件和合法转向。P3未批准。', 'It is a limited retrospective proxy, not proof of historical road or detector identity. The verified historical-network/P3 gate remains NO-GO.'),
        ('稀疏数据持续恢复？ / How is persistence defined with sparse data?', '旧版每5分钟箱至少两个有效正流量槽，三高箱确认，缺口删失。不是完整连续观测。新strict10与sampled2另有规则不能混接。', 'Three consecutive usable high bins establish sampled confirmation. Gaps censor follow-up. Sparse slots do not establish continuous physical recovery. Proposal strict10 and sampled2 are separate definitions.'),
        ('是否控制时间天气？ / Are time and weather controlled?', '主比较F3/F7已含8个日历和6个温度/风速质量字段；无雨量、事故或活动控制，不代表所有混杂已排除。', 'Yes, for the specified calendar and King’s Park temperature/wind covariates. This is not control of all weather, incidents, events, or unmeasured confounding.'),
        ('Bootstrap如何解释？ / What does the Bootstrap interval mean?', '同检测器事件成组抽、两臂同抽、重复抽中按重复权重；44群，1000次。固定模型，不包括训练不确定性；共享邻居跨群依赖与多重比较未完全处理。', 'Both arms share each draw, repeating all events when a detector is sampled again. It measures fixed-model test uncertainty. Shared neighbors and unadjusted multiple comparisons limit interpretation.'),
        ('已完成与未完成？ / What is completed versus future work?', '32臂主实验、6臂结构对照、统计、图表已完成；新Proposal数据标签已实现但采用/模型未完成；P3、部署、未来盲测未完成。', 'The 32-arm confirmation study, six matched structural controls, audits and figures are complete. New Proposal labels exist, but adoption and models are pending; P3, deployment and future blind validation are not delivered.'),
        ('最高AUC是唯一最佳模型吗？ / Is the highest test AUC the best model?', '不是预先选定唯一最佳；展示全矩阵和多指标，候选仅按验证log loss选。', 'No test-selected winner is claimed. Candidate selection used validation log loss, and all algorithms and trade-offs are reported.'),
        ('原始天气是否全部重建？ / Did you independently rebuild all weather archives?', '没有。核验了已交付特征、来源元数据、源快照和值、冻结生产者重建记录及示例原字节；90月ZIP只有URL/SHA链。', 'No. We authenticated the delivered features, source snapshots, metadata, producer reconstruction records and supplied raw examples. We did not independently re-download all 90 monthly archives.'),
        ('为什么不报accuracy为主？ / Why not focus on accuracy?', '测试正例17.5%，多数负类可使accuracy高；同时报告AUC、AP、Macro-F1、Recall、损失和混淆矩阵。', 'Only 17.5% of test events are positive. We report ranking, class-sensitive, calibration and confusion metrics rather than relying on majority-dominated accuracy.')]
    text(out/'06_likely_questions_zh_en.md','# Poster Q&A\n\n'+'\n\n'.join(f'## {i}. {q}\n\n中：{zh}\n\nEN: {en}' for i,(q,zh,en) in enumerate(qa,1)))
    text(out/'08_reproduction.md',f'''# Reproduction and execution scope

Poster users need only this package. Researchers use the repository at `https://github.com/WYJbjtu/traffic`, local finalization branch and code hashes in the evidence manifest. Python 3.12; committed uv.lock; no extra dependencies or browser run. Execute from repository root. Commands below never upload anything. New output paths **must not exist**.

```text
uv sync --locked
uv run --locked pytest -q
uv run --locked python experiments/tianhao/calendar_weather96_20261106/verify_archive.py --extract data/local/poster-reproduction/cw
uv run --locked python data/local/poster-reproduction/cw/calendar_weather96/verify_handoff.py --events data/local/expanded96-release/prepared-v1/processed/events.parquet --repository .
uv run --locked python -m experiments.unified96.run --context data/local/poster-reproduction/cw/calendar_weather96 --out data/local/unified96/poster-reproduction-matrix-v1
uv run --locked python -m experiments.unified96.poster_analysis --run data/local/unified96/poster-reproduction-matrix-v1 --out data/local/unified96/poster-reproduction-analysis-v1
uv run --locked python -m experiments.unified96.poster_controls --run data/local/unified96/poster-reproduction-matrix-v1 --out data/local/unified96/poster-reproduction-controls-v1
uv run --locked python -m experiments.unified96.poster_handoff --run data/local/unified96/poster-reproduction-matrix-v1 --analysis data/local/unified96/poster-reproduction-analysis-v1 --controls data/local/unified96/poster-reproduction-controls-v1 --proposal data/local/poster-finalization/proposal-review-v1 --cw data/local/poster-reproduction/cw/calendar_weather96 --out deliverables/poster_handoff/reproduction-v1
```

## Required local evidence (not bundled large datasets)

- Old96 Release, extracted event/bin tables and frozen history features at the paths recorded in `evidence/main_manifest.json`. Input SHA checks are mandatory. Current release: `https://github.com/WYJbjtu/traffic/releases/tag/data-expanded-96-2023-2026-v1`.
- Authentic inferred-v2 features, lineage, geography controls, mappings and official geometry/index. These are existing ignored research artifacts; their hashes are in main/controls/figure manifests. Acquisition/graph reproduction is documented in repository `reports/spatial96_inferred_v2/network_methodology.md`; do not overwrite that frozen run.
- Proposal evidence snapshots can be recreated with `git show b60c5951702657ac44a2654cb997adb06038498a:<path>` for the source paths in `evidence/proposal/source_receipt.json`; save bytes to a new ignored evidence directory. This is a document audit, not adoption or full Proposal reconstruction. Read-only Issue #3 snapshot is in this package.
- The C/W verifier authenticates delivered features and producer records. No claim to independent complete monthly-weather download/rebuild is made.

## This delivery actually executed

Matrix `{run.name}`: 32 selected fits, 64 candidate fits, 275,616 saved validation/test rows. F3/F7 were fitted first; all F0/F4 were refitted. Six selected matched-control fits (12 candidates) additionally executed. Independently recomputed ROC-AUC, AP, Macro-F1, balanced accuracy, precision, recall, Brier, clipped log loss and TN/FP/FN/TP; checked identical event/time/label populations and train-only imputer means. XGBoost float32 arithmetic causes at most about 3.3e-8 difference after float64 reload; mean losses use 1e-7 absolute audit tolerance, other metrics tighter.

1,000 paired detector-cluster and 1,000 fixed-week-block replicates per model, with seeds recorded. No retraining bootstrap. No new threshold tuning, label permutation, Proposal-target training or live service.

Training source hashes and dirty Git status at execution are preserved rather than misattributed to a later clean commit. The first partial v1 execution failed on serializing an XGBoost NaN parameter sentinel; it is not cited. Fixed serialization records that sentinel as a string; completed v2 uses unchanged candidate parameters. Source `poster_protocol.md` records this incident.

The finalization tests include isolated `autocrlf=true` Git checkout. That is not actual Windows or new remote CI. Unit tests are not evidence of rebuilding the complete traffic/meteorological archives.

## Package integrity

`07_evidence_manifest.json` hashes every payload except itself and SHA256SUMS (avoids self-reference). `SHA256SUMS` also includes the manifest. A separate ZIP receipt records archive size/SHA and actual temporary extraction, file/image/table/reference checks. For metric meaning: ROC-AUC/AP/Macro-F1/Recall higher is better; Brier/Log Loss lower is better; AP is sklearn Average Precision, not trapezoidal PR-AUC. NA is not zero. Final-results paired deltas are spatial minus its matched base; intervals apply only to test F7−F3.
''')


class Links(HTMLParser):
    def __init__(self): super().__init__(); self.links=[]
    def handle_starttag(self, tag, attrs):
        self.links.extend(v for k,v in attrs if k in ('href','src') and v)


def verify_package(folder: Path) -> dict:
    """Verify payload hashes, image decoding, figures/tables and all local HTML links."""
    manifest=json.loads((folder/'07_evidence_manifest.json').read_text(encoding='utf-8'))
    for name,digest in manifest['payload_sha256'].items():
        if sha256_file(folder/name)!=digest:raise ValueError('Package hash mismatch: '+name)
    for line in (folder/'SHA256SUMS').read_text(encoding='utf-8').splitlines():
        digest,name=line.split('  ',1)
        if sha256_file(folder/name)!=digest:raise ValueError('SHA256SUMS mismatch: '+name)
    for path in (folder/'figures').glob('*.png'):
        with Image.open(path) as image:
            image.load()
            if min(image.size)<1000:raise ValueError('Low-resolution figure')
    for path in (folder/'figures').glob('*.svg'):ET.parse(path)
    for path in (folder/'figures').glob('*.pdf'):
        if not path.read_bytes().startswith(b'%PDF'):raise ValueError('Bad PDF')
    links=Links();links.feed((folder/'index.html').read_text(encoding='utf-8'))
    for link in links.links:
        parsed=urlparse(link)
        if parsed.scheme or not parsed.path:continue
        target=(folder/unquote(parsed.path)).resolve()
        if not target.is_relative_to(folder.resolve()) or not target.is_file():raise ValueError('Broken or escaping relative reference: '+link)
    for path in folder.glob('*.md'):
        for link in re.findall(r'\]\(([^)]+)\)',path.read_text(encoding='utf-8')):
            parsed=urlparse(link)
            if not parsed.scheme and parsed.path and not (path.parent/unquote(parsed.path)).is_file():raise ValueError('Broken Markdown reference')
    results=pd.read_csv(folder/'03_final_results.csv')
    if len(results)!=64 or results.duplicated(['model','feature_arm','split']).any():raise ValueError('Wrong final result table')
    saved=pd.read_csv(folder/'evidence/main_metrics.csv')
    for row in results.itertuples():
        ref=saved.loc[saved.model.eq(row.model)&saved.feature_arm.eq(row.feature_arm)&saved.split.eq(row.split)].iloc[0]
        for key in ['roc_auc','average_precision','macro_f1','balanced_accuracy','precision','recall','brier','log_loss','tn','fp','fn','tp']:
            if not np.isclose(getattr(row,key),ref[key],atol=1e-12):raise ValueError('Final table changed from run')
    gain=pd.read_csv(folder/'figure_data/01_spatial_gain.csv')
    for row in gain.itertuples():
        a,b=(results.loc[results.model.eq(row.model)&results.feature_arm.eq(arm)&results.split.eq('test')].iloc[0] for arm in ['F3','F7'])
        if not np.isclose(b.roc_auc-a.roc_auc,row.delta_roc_auc,atol=1e-12) or not np.isclose(b.paired_delta,row.delta_roc_auc):raise ValueError('Figure and final table differ')
        if not np.isclose(b.ci_95_lower,row.ci_95_lower) or not np.isclose(b.ci_95_upper,row.ci_95_upper):raise ValueError('Figure interval differs')
    heat=pd.read_csv(folder/'figure_data/04_auc_matrix.csv').set_index('model')
    for row in results.loc[results.split.eq('test')].itertuples():
        if not np.isclose(heat.loc[row.model,row.feature_arm],row.roc_auc):raise ValueError('Heatmap differs')
    return {'status':'passed','files':sum(p.is_file() for p in folder.rglob('*')),'png_decoded':5,'svg_parsed':5,'pdf_headers_checked':5,'metric_rows_checked':64,'relative_html_references':len(links.links)}


def archive_destination(out: Path) -> Path:
    """Return absolute ZIP destination for relative or absolute handoff directories."""
    return (out.parent.parent/f'poster_handoff_{out.name}.zip').resolve()


def build(run: Path, analysis: Path, controls: Path, proposal: Path, cw: Path, out: Path) -> Path:
    if out.exists():raise FileExistsError(out)
    archive=archive_destination(out)
    if archive.exists():raise FileExistsError(archive)
    _,metrics,manifest=verify_run(run)
    gains=pd.read_csv(analysis/'spatial_contrasts.csv')
    for folder in [out,out/'figures',out/'figure_data',out/'evidence',out/'evidence/proposal']:folder.mkdir(parents=True,exist_ok=False)
    build_figures(run,analysis,controls,out)
    results=metrics.copy()
    results['paired_delta']=np.nan;results['ci_95_lower']=np.nan;results['ci_95_upper']=np.nan
    results['paired_comparison']='NA';results['source_file']='evidence/main_metrics.csv'
    for i,row in results.iterrows():
        if row.feature_arm in ['F4','F5','F6','F7']:
            base=f'F{int(row.feature_arm[1])-4}'
            baseline=results.loc[results.model.eq(row.model)&results.split.eq(row.split)&results.feature_arm.eq(base)].iloc[0]
            results.loc[i,'paired_delta']=row.roc_auc-baseline.roc_auc
            results.loc[i,'paired_comparison']=row.feature_arm+'_minus_'+base
        if row.feature_arm=='F7' and row.split=='test':
            g=gains.loc[gains.model.eq(row.model)&gains.comparison.eq('F7_minus_F3')].iloc[0]
            results.loc[i,['ci_95_lower','ci_95_upper']]=[g.ci_95_lower,g.ci_95_upper]
    results.to_csv(out/'03_final_results.csv',index=False,na_rep='NA')
    write_documents(out,run,metrics,gains)
    copies=[(run/'manifest.json','evidence/main_manifest.json'),(run/'metrics.csv','evidence/main_metrics.csv'),
        (run/'tuning.csv','evidence/main_tuning.csv'),(run/'fit_audit.json','evidence/main_fit_audit.json'),
        (analysis/'paired_bootstrap.json','evidence/paired_bootstrap.json'),(analysis/'verification.json','evidence/prediction_verification.json'),
        (analysis/'spatial_contrasts.csv','figure_data/spatial_contrasts.csv'),(analysis/'error_transitions.csv','figure_data/error_transitions.csv'),
        (controls/'manifest.json','evidence/controls_manifest.json'),(controls/'metrics.csv','evidence/controls_metrics.csv'),
        (controls/'tuning.csv','evidence/controls_tuning.csv'),(controls/'coverage.csv','figure_data/controls_coverage.csv'),
        (cw/'prepared/sources.csv','evidence/calendar_weather_sources.csv'),(cw/'prepared/contract.json','evidence/calendar_weather_contract.json'),
        (ROOT/'experiments/unified96/poster_protocol.md','evidence/poster_protocol.md')]
    for source,name in copies:shutil.copyfile(source,out/name)
    dump(out/'evidence/calendar_weather_verification.json',manifest['cw_verification'])
    for source in proposal.iterdir():
        if source.is_file():shutil.copyfile(source,out/'evidence/proposal'/source.name)
    issue=ROOT/'data/local/poster-finalization/proposal-issue3.json'
    if issue.exists():shutil.copyfile(issue,out/'evidence/proposal/issue3_readonly.json')
    dump(out/'evidence/proposal/source_receipt.json',{'branch':'recovery/feature/member1-proposal-aligned-data-v2',
        'commit':'b60c5951702657ac44a2654cb997adb06038498a','scope':'read-only tracked report/CSV audit; no new full-source reconstruction or adoption',
        'paths':['docs/proposal_member1_v2.md']+[f'reports/proposal_member1_v2/{p.name}' for p in proposal.iterdir() if p.name!='proposal_member1_v2.md']})
    navigation=''.join(f'<li><a href="{escape(p.name)}">{escape(p.name)}</a></li>' for p in sorted(out.glob('*.md')))
    cards=''.join(f'<article><h2>Figure {i} — {escape(name)}</h2><p>{escape(where)}</p><a href="figures/{name}.png"><img src="figures/{name}.png" alt="{escape(name)}"></a><p>{escape(caption)}</p><p><a href="figures/{name}.svg">SVG</a> · <a href="figures/{name}.pdf">PDF</a></p></article>' for i,(name,where,caption) in enumerate(FIGURES,1))
    sections=''.join(f'<section><h2>{escape(p.name)}</h2><pre>{escape(p.read_text(encoding="utf-8"))}</pre></section>' for p in sorted(out.glob('*.md')))
    text(out/'index.html',f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>DSC6004 — offline poster handoff</title><style>body{{font:17px/1.55 system-ui,sans-serif;color:#233440;max-width:1150px;margin:2em auto;padding:0 1em}}h1,h2{{line-height:1.2}}img{{width:100%;height:auto}}article,section{{border-top:1px solid #ccd6da;padding:1.5em 0}}pre{{white-space:pre-wrap;font:inherit;background:#f5f7f8;padding:1em}}a{{color:#176d75}}</style><h1>DSC6004 — Poster handoff</h1><p>本页离线可读，无需安装任何软件。版本：{escape(out.name)}。优先使用图1–3；图4–5可选。可直接从下方复制英文文案及讲稿。</p><p><strong>Recovery confirmation, not recovery start. Retrospective P1, not a new blind test.</strong></p><ul>{navigation}<li><a href="03_final_results.csv">Final results CSV</a></li><li><a href="07_evidence_manifest.json">Evidence manifest</a></li></ul>{cards}<h1>Copy-ready documents</h1>{sections}</html>''')
    code={str(p.relative_to(ROOT)):sha256_file(p) for p in sorted((ROOT/'experiments/unified96').glob('*.py'))}
    evidence={'version':out.name,'created_at_utc':datetime.now(timezone.utc).isoformat(),
        'main_run':str(run.resolve().relative_to(ROOT)),'main_experiment_id':manifest['experiment_id'],
        'dataset_version':manifest['dataset_version'],'target_version':manifest['target'],'population':manifest['population'],'horizon_min':30,
        'git_package_build_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'git_package_build_status':subprocess.check_output(['git','status','--porcelain=v1'],cwd=ROOT,text=True),
        'software':manifest['software'],'code_sha256':code,'inputs_sha256':manifest['inputs_sha256'],
        'large_local_artifacts':{str((run/n).resolve().relative_to(ROOT)):sha256_file(run/n) for n in ['predictions.parquet','event_population.parquet','model_input.parquet']},
        'verification_scope':'delivered feature authentication, all fitted predictions/metrics/preprocessors, source-backed plotting; not full weather/traffic rebuild',
        'payload_sha256':{str(p.relative_to(out)):sha256_file(p) for p in sorted(out.rglob('*')) if p.is_file()}}
    dump(out/'07_evidence_manifest.json',evidence)
    text(out/'SHA256SUMS','\n'.join(f'{sha256_file(p)}  {p.relative_to(out).as_posix()}' for p in sorted(out.rglob('*')) if p.is_file()))
    verify_package(out)
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for path in sorted(out.rglob('*')):
            if path.is_file():z.write(path,arcname=f'{out.name}/{path.relative_to(out).as_posix()}')
    with tempfile.TemporaryDirectory(prefix='poster-handoff-verify-') as tmp:
        with zipfile.ZipFile(archive) as z:
            if z.testzip() is not None:raise ValueError('ZIP CRC failure')
            z.extractall(tmp)
        receipt=verify_package(Path(tmp)/out.name)
    dump(archive.with_suffix('.verification.json'),{**receipt,'zip':str(archive.resolve().relative_to(ROOT)),
        'bytes':archive.stat().st_size,'sha256':sha256_file(archive),'actual_temporary_extraction':True,
        'image_review':'five preview PNGs opened and visually inspected before final package; same source-backed figure generation',
        'remote_writes':False})
    print(json.dumps({'directory':str(out.resolve()),'zip':str(archive.resolve()),'bytes':archive.stat().st_size,'sha256':sha256_file(archive)},indent=2))
    return archive

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['run','analysis','controls','proposal','cw','out']:parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();build(args.run,args.analysis,args.controls,args.proposal,args.cw,args.out)
