# Tianhao：96车道 Calendar / Weather 整合交接包

**先把本目录的4个 `.zip.part01`～`.zip.part04` 分卷、`ARCHIVE.json`、`SHA256SUMS`和`verify_archive.py`下载到同一目录**，或直接clone本分支。完整ZIP为20.82 MB；上传接口整包返回HTTP500，因此用字节分卷交付，内容和完整ZIP的SHA保持一致。所有资料放在一个包中，避免组员再次漏拷文件；原有共享代码、配置、依赖和历史结果没有改动。

## 解压后先找这些文件

| 路径（均相对于解压后的calendar_weather96/） | 内容 |
|---|---|
| `prepared/inputs/calendar_event_features.parquet` | 30,452行Calendar原始特征，有event_id、prediction_time |
| `prepared/inputs/weather_event_features.parquet` | 30,452行Weather原始特征，含京士柏观测时间、档案可用时间、年龄、缺失标志和原成员SHA |
| `prepared/inputs/weather_station_snapshots.parquet` | 43,387条事件需求快照；原值、精确历史下载链接、观测/可用/获取时间 |
| `prepared/inputs/official_holiday_editions.parquet` | 2023–2026年度官方General holidays，277个唯一日期（包括星期日） |
| `raw_holidays/`、`source_metadata/` | 4份原始公告HTML和94个来源的原下载元数据 |
| `prepared/sources.csv`、`raw_weather_examples/` | 90个月ZIP原下载链接/SHA，加4份原CSV完整字节；约582.53 MB月档未写入Git |
| `prepared/event_features.parquet`、`prepared/manifest.json` | 完整未插补模型输入和按当前main重建的认证记录，供Member4现有脚本门禁核验 |
| `reproduction/`、`handoff_config.json` | 实际生成Python代码、配置、pyproject、uv.lock冻结副本 |
| `Calendar_Weather96_交接核验.ipynb`、同名HTML | 已执行的6代码单元/1图教学核验，每段都有中文说明，可离线阅读/执行 |
| `history/` | 原实验Notebook、调参/指标汇总和运行记录；本次不重训 |
| `README.md`、`manifest.json`、`SHA256SUMS` | 完整字段、来源、时间规则、复现方法与逐文件SHA |

## 核验与接入

在仓库根目录执行：

```text
uv sync --locked
uv run --locked python experiments/tianhao/calendar_weather96_20261106/verify_archive.py --extract <不存在的新目录>
uv run --locked python <新目录>/calendar_weather96/verify_handoff.py --events <96车道Release>/processed/events.parquet --repository .
```

脚本自动按顺序合并4卷、核验每卷及完整ZIP的SHA-256和CRC，再解压；也可加 `--assemble <不存在的ZIP路径>` 保存单个完整ZIP。只验证和合并ZIP可直接用Python3.12标准库，不依赖pandas。包内verify核查所有事件、来源和可用时间；未提供events时只对照包内事件索引，未随包提供的90个月ZIP不会被假称重新认证。

**按event_id和prediction_time双键一对一连接，禁止按行号或仅时间合并。** 使用prepared/contract.json白名单；标签、未来恢复字段、来源URL和SHA不是模型特征。天气是King's Park区域代理；available_at是保守档案捕获时间，retrieved_at仅为下载溯源。Calendar实际使用年度政府公告，不把通用pilot的1823配置当作长期实验来源。

全部30,452事件中，Calendar入模字段无缺失；温度缺18（0.0591%），风速缺116（0.3809%）。分split、已知标签子集率见prepared/coverage.csv。缺失未填0；无插补、无虚构雨量/事故/活动字段。

本次基于main `2d75381` 完整重建，Calendar/Weather/合并表与原实验文件SHA完全一致；原运行身份另存，不伪称本次训练。恢复开始/确认口径、站点代理和既往测试接触限制保留。

SHA-256：`cdb5f9a9a704cd2bcd823e4a7ba2615319c026f0311e2be55fa998b0418513c0`。
完整文件目录与每项大小/哈希：[CONTENTS.csv](CONTENTS.csv)。解压后的README提供新[Release](https://github.com/WYJbjtu/traffic/releases/tag/data-expanded-96-2023-2026-v1)入口、4份Holiday官方链接、90个月天气ZIP下载清单和从真实缓存重建命令。

最终核验：已无文本冲突同步main `993a9eb`；特征准备源码/锁未变，当前main完整275项测试通过。新增7项交接测试覆盖真实ZIP、事件错配、文件篡改和Notebook源代码/输出边界；另有从独立解压目录顺序执行6代码单元/1图和Member4事件对齐验证。见[VALIDATION.json](VALIDATION.json)。

新合并的unified96目前仍仅F0/F4；对接本包C/W需要新实验版本，不得把旧结果改称已控制天气。详见[最新整合说明](INTEGRATION_latest_main.md)。

单独下载本目录时，在该目录执行：

```text
python verify_archive.py --extract ./unpacked --assemble ./Tianhao_Calendar_Weather_96_20261106.zip
```

两个输出路径都必须尚不存在。Windows、macOS与Linux均不需要系统cat命令。若使用“Download ZIP”下载整个GitHub分支，解压仓库后进入本目录执行同一命令即可。
