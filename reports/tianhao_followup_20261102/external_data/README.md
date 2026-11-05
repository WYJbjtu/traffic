# 外部特征实测覆盖（原24车道队列）

按原始、未插补特征计算。all_events包含未知标签；known_label_30m只包含30分钟已知标签。
分母不等于天气源全部观测数，不代表全港或96车道覆盖。

| 分母 | split | 特征 | 事件n | 已观测 | 缺失 | 缺失率 |
|---|---|---|---:|---:|---:|---:|
| all_events | train | calendar_all_fields | 3833 | 3833 | 0 | 0.0000% |
| all_events | train | temperature_c | 3833 | 3830 | 3 | 0.0783% |
| all_events | train | wind_speed_kmh | 3833 | 3831 | 2 | 0.0522% |
| all_events | train | weather_both_values | 3833 | 3829 | 4 | 0.1044% |
| all_events | validation | calendar_all_fields | 2235 | 2235 | 0 | 0.0000% |
| all_events | validation | temperature_c | 2235 | 2235 | 0 | 0.0000% |
| all_events | validation | wind_speed_kmh | 2235 | 2229 | 6 | 0.2685% |
| all_events | validation | weather_both_values | 2235 | 2229 | 6 | 0.2685% |
| all_events | test | calendar_all_fields | 1529 | 1529 | 0 | 0.0000% |
| all_events | test | temperature_c | 1529 | 1527 | 2 | 0.1308% |
| all_events | test | wind_speed_kmh | 1529 | 1515 | 14 | 0.9156% |
| all_events | test | weather_both_values | 1529 | 1515 | 14 | 0.9156% |
| all_events | all | calendar_all_fields | 7597 | 7597 | 0 | 0.0000% |
| all_events | all | temperature_c | 7597 | 7592 | 5 | 0.0658% |
| all_events | all | wind_speed_kmh | 7597 | 7575 | 22 | 0.2896% |
| all_events | all | weather_both_values | 7597 | 7573 | 24 | 0.3159% |
| known_label_30m | train | calendar_all_fields | 3428 | 3428 | 0 | 0.0000% |
| known_label_30m | train | temperature_c | 3428 | 3425 | 3 | 0.0875% |
| known_label_30m | train | wind_speed_kmh | 3428 | 3426 | 2 | 0.0583% |
| known_label_30m | train | weather_both_values | 3428 | 3424 | 4 | 0.1167% |
| known_label_30m | validation | calendar_all_fields | 2008 | 2008 | 0 | 0.0000% |
| known_label_30m | validation | temperature_c | 2008 | 2008 | 0 | 0.0000% |
| known_label_30m | validation | wind_speed_kmh | 2008 | 2003 | 5 | 0.2490% |
| known_label_30m | validation | weather_both_values | 2008 | 2003 | 5 | 0.2490% |
| known_label_30m | test | calendar_all_fields | 1363 | 1363 | 0 | 0.0000% |
| known_label_30m | test | temperature_c | 1363 | 1361 | 2 | 0.1467% |
| known_label_30m | test | wind_speed_kmh | 1363 | 1352 | 11 | 0.8070% |
| known_label_30m | test | weather_both_values | 1363 | 1352 | 11 | 0.8070% |
| known_label_30m | all | calendar_all_fields | 6799 | 6799 | 0 | 0.0000% |
| known_label_30m | all | temperature_c | 6799 | 6794 | 5 | 0.0735% |
| known_label_30m | all | wind_speed_kmh | 6799 | 6781 | 18 | 0.2647% |
| known_label_30m | all | weather_both_values | 6799 | 6779 | 20 | 0.2942% |

该表仅是保留来源的历史重算，本次没有重新联网查询。来源、可获取时间、未纳入因素及解释边界见 [交接说明](../../../docs/tianhao_external_data_handoff.md)。

本地大型audit未提交。完整复现需取得manifest标识的原始audit字节；全部事件的单列缺失数量也与已提交feature_missingness.csv逐项一致。

复现：`uv run --locked python experiments/tianhao/document_external_coverage.py --event-audit <原始event_feature_audit.parquet> --output-dir reports/local/external-coverage-new`。
