# 共同测试集亲和力比较 v3

在固定的来源隔离 683 条与靶标隔离 946 条测试记录上，每面板比较 27 个方案，每方案种子 0–9，共 540 次已存预测评分。端点为 pKd；本轮复用既有预测，训练、模型推理和 GPU 调用均为 0。

从[中文完整报告](REPORT.zh-CN.md)开始，配套[十种子汇总](ten-seed-mean-sampleSD.csv)、[逐种子指标](per-seed-metrics.csv)、[覆盖清单](coverage.csv)和[全部模型对 MAE 差值汇总](paired-seed-MAE-summary.csv)。439,830 项 ID/标签/端点检查与 49,320 项独立数值检查均为 0 错误。7,020 条同种子 MAE 差值作描述性计算汇总，未进行 p 值分析。

同一测试队列上的各方案沿用原训练覆盖、预训练和验证配置，具体差异见报告与[公开协议](PUBLIC-PROTOCOL.json)。标准注释、非天然残基与 PTM 分层单独报告。RDE 的单 HER2 背景 authorDDG 与效应任务属于其他端点，保留在原任务报告中。完整 PepInter 全骨干与 UniAIR/MoFPE 的正式基准仍待完成。

本目录按源方[19 文件白名单](publication-scope.json)准备，只包含自有代码、汇总指标与审计元数据。原始逐条真值合同和预测缓存保留在本地。脚本为实际工作流的公开存档：机器路径已替换为 `record-ref:` 标识；这些标识指向本地保留的来源，不是下载链接。运行完整流程需要另外恢复有权限的输入并配置路径；本包是结果与流程披露。

[双向来源映射](SOURCE-MAPPING.json)列出每个原文件 SHA 与公开文件 SHA；其中历史收据自身记录的原 SHA 保留原义。路径转换不改 CSV 任一单元格或 JSON 数值。公开包新增清单见 [FILE-MANIFEST.json](FILE-MANIFEST.json)，检查见 [VALIDATION.json](VALIDATION.json)。SWING 已全部物理本地的后续状态见 [STATE-ADDENDUM.json](STATE-ADDENDUM.json) 与[交付闭环补充](../artifact-delivery-v1/README.zh-CN.md)。

历史公开结果与模型权重入口见 [LATEST](../LATEST.md)。本目录的发布事实以 Git 提交与发布收据为准。
