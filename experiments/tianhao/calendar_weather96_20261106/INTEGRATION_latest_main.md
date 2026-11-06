# 对接2026-11-06新合并的统一实验

打包时main已从`2d75381`推进到`993a9eb`（PR #5）。本包数据实际由`2d75381`的代码重建；新main没有修改manifest绑定的特征准备源码或uv.lock，已核对新main通过`verify_handoff.py --repository`。冻结源码保留真实基准，不冒充后来的运行。

## 现有两个入口不要混淆

- `experiments/member4/ensemble_external96.py`已支持Tianhao完整prepared矩阵、原Release及外部缓存门禁。本次实际调用其`aligned_features`通过：27,858个已知标签事件，train/validation/test为13,002/7,848/7,008。它仍需原ZIP来源缓存，不因收到本包而自动跳过门禁。
- 新`experiments/unified96/run.py`目前**只声明F0和F4**，不读取Calendar/Weather参数。不能只把文件拷入某个目录就宣称旧结果已控制日历/天气。F1–F3/F5–F7需组员另开新实验版本，接入本包并按原有时间划分重新拟合和评估；本次仅交接数据，不运行这些实验。

## 与统一实验P1/P2子集连接

先对完整Release运行包内核验，再把context按双键连接到已经由统一实验验证过的目标事件子集。完整表有30,452事件，P1/P2样本更少，这是资格筛选差异，不能拿全队列成绩当作同样本对照。

```python
from pathlib import Path
import json
import pandas as pd
from verify_handoff import verify_bundle

B = Path('<解压目录>/calendar_weather96')
verify_bundle(B, events_path=Path('<Release>/processed/events.parquet'))
calendar = pd.read_parquet(B/'prepared/inputs/calendar_event_features.parquet')
weather = pd.read_parquet(B/'prepared/inputs/weather_event_features.parquet')
keys = ['event_id', 'prediction_time']
context = calendar.merge(weather, on=keys, validate='one_to_one')

# p1_frame是组员现有load/merge_verified返回的已验证子集，非按位置截取。
# 以下代码在组员取得p1_frame后执行。
joined = p1_frame.merge(context, on=keys, how='left',
                       validate='one_to_one', indicator='context_join')
assert joined.context_join.eq('both').all()
assert len(joined) == len(p1_frame)
groups = json.loads((B/'prepared/contract.json').read_text(encoding='utf-8'))['feature_groups']
C = groups['calendar']
W = groups['weather']
# 仅C/W白名单进入模型；各自来源、观测/可用时间只用于门禁和审计。
```

若p1_frame已带同名C/W字段，先核对其来源与值，不能接受pandas自动生成的_x/_y后随意择一。time、split、标签和原车道继续以验证过的Release为准，不用本包重写。

## 字段与安全规则

| 含义 | 原表字段 |
|---|---|
| 双键 | `event_id`、香港时区的`prediction_time` |
| Calendar入模 | hour_sin、hour_cos、dow_sin、dow_cos、is_weekend、is_public_holiday、is_day_before_holiday、is_day_after_holiday |
| Calendar公告水位 | `calendar_max_source_available_at`，必须不晚于prediction_time |
| Weather入模 | temperature_c、wind_speed_kmh、temperature_age_minutes、wind_age_minutes、temperature_missing、wind_missing |
| 温度时间 | `temperature_observed_at`、`temperature_available_at` |
| 风时间 | `wind_observed_at`、`wind_available_at` |
| 来源核验 | 各kind的archive_file、archive_member、source_sha256；站点快照另有source_url、source_retrieved_at |

对非缺失的天气值，观测/可用时间均不得晚于prediction_time，观测年龄0–60分钟。missing=1不是气象值；有age不一定有有效值。缺失不补0，不把retrieved_at当历史可用时间。不将Tianhao的history比值特征替换成统一实验已有的H，也不将valid_slots当车辆流量。

本包补齐了C/W数据来源缺失条件，**没有**完成日历/天气调整后的空间消融，也不改变旧F0/F4或poster指标。Proposal恢复开始与当前持续恢复确认仍不同；P3验证状态不因取得天气而改变。
