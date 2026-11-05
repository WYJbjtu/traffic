# 仓库迁移与数据交接（2026-11-05）

当前项目为 https://github.com/WYJbjtu/traffic 。原账号不可用后，源码迁移不会自动迁移Release二进制附件。本次重新发布原始24和96车道压缩包，未改包内字节或重新计算数据。

## 当前数据入口

| 队列 | 事件 | 包大小（字节） | Release |
|---|---:|---:|---|
| 96车道 | 30,452 | 870,121,429 | [data-expanded-96-2023-2026-v1](https://github.com/WYJbjtu/traffic/releases/tag/data-expanded-96-2023-2026-v1) |
| 原24车道 | 7,597 | 1,669,288,966 | [data-long-window-2023-2026-v1](https://github.com/WYJbjtu/traffic/releases/tag/data-long-window-2023-2026-v1) |

96包SHA-256：`f5be559a6ad8df69e68fbc382fb609d13fdae40aa044c9d1fe4d7e3b2253b6b8`。

24包SHA-256：`53688e6e095798f50c124376da1f0f354ca4b2aedf9e83e960fef04fc7298bc9`。

下载Release附件中的数据ZIP和相邻SHA文件，使用Get-FileHash核对；Source code ZIP不包含数据。不同队列应解压到独立目录。详见[96车道使用说明](expanded96_data_access.md)与[原24车道使用说明](long_window_data_access.md)。

原47GB官方ZIP不包含在这两个共享包内，仍在数据持有人的原始数据根raw目录。包内旧仓库地址、本机绝对路径及旧PR号属于历史来源；当前下载使用上方新仓库链接。历史清单不改写，保留原始SHA可追溯性。迁移Release标签指向新仓库迁移时的代码提交421aa49，不应将其Source code误认为原始数据生成版本；数据生成版本仍以包内manifest及原审计报告为准。

## Windows校验修复

原冻结结果在Git中使用LF，但Windows检出转换为CRLF，导致paired_spatial_metrics.csv字节校验失败；Ubuntu测试通过。已为output_sha256.json列出的全部已提交空间结果设置-text，保留仓库原始字节。未更改结果数字、冻结SHA或校验函数，未跳过测试。

旧scripts导入修复已经保留，本次不是同一个问题。README的178通过是原数据审计本地历史记录，不能作为最新仓库CI结果。当前测试和发布证据随本PR提供。
