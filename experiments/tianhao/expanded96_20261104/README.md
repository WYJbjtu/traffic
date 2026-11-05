# Tianhao96车道真实结果与SHA-256清单

**EXPLORATORY — NOT APPROVED AS FINAL RESULTS**。30452事件、27858已知30分钟标签，224候选，20比较臂，557160预测；测试n7008。四组是本地/历史/日历/天气，不含flow、邻居或未经验证的外部数据。

- [已执行Notebook](../../../notebooks/Tianhao_新版96车道_完整重跑_20261104.ipynb)
- [审查和完整复现](../../../docs/tianhao_release96_review.md)
- [逐文件及代码SHA-256](publication_manifest.json)、[校验文本](SHA256SUMS)
- [237测试与双轴审查结果](publication_review.json)、[真实重新构建/训练对照](publication_reproduction.json)
- [来源URL/获取时间/原字节SHA](sources.csv)、[新队列覆盖](coverage.csv)
- [预测](predictions.parquet)、[指标](metrics.csv)、[混淆矩阵](confusion_matrices.csv)、[候选](tuning.csv)、[选中参数](selected_parameters.csv)

original_training_manifest.json和training_code保留原始运行身份、原始源代码与完整产物清单。该清单也记录了仅留本地的模型、原始数据和校准表；不声称那些文件随PR上传。publication_manifest.json列出实际提交文件，publication_training_manifest.json记录可移植修复后的本地真实复现。两次预测完全一致，未重写历史时间或Git身份。

默认离线核验重算预测指标/样本数/混淆矩阵/验证选择；没有模型二进制时不假称重做概率重放。可用公开CLI和显式Release/缓存输入重建并重训，详见复现说明。全部恢复开始/确认、参考速度、跨年身份和天气站代理等限制保留。

上传前PR #17合并，现已同步main 3a184aa。original_uv.lock保留原训练锁，publication_manifest另绑定当前锁；原有包版本不变，仅新增XGBoost相关依赖。最新main的237项测试通过。
