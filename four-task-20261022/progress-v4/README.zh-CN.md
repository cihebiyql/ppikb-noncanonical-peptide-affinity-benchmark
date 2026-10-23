# 四任务基准：进展补充 v4

本页分别记录公开上传、科学执行和本地资产交付，历史结果快照保持冻结。详细字段与原收据 SHA 见 [进展收据](PROGRESS-RECEIPT.json)和[来源映射](SOURCE-MAPPING.json)。

| 项目 | 本时点证据 |
|---|---|
| [DTA 候选权重 Release](https://github.com/cihebiyql/ppikb-noncanonical-peptide-affinity-benchmark/releases/tag/four-task-20261022-dta-candidates-v1) | 已真实发布；19 项资产、4,405,802,642 字节、300 个候选权重。根发布收据确认全部资产 SHA256 与 tag commit，见 [发布收据](DTA-PUBLISHED-RECEIPT.json)。这是 DTA 权重交付范围。 |
| UniAIR 四专家 MoFPE | 原 B8 的第一轮完整训练已通过：293 train、63 validation、0 test、37 个 Adam 步。20 个本地导出文件 SHA 与退出状态已核。正式计划的 20 次候选拟合仍处准备阶段，尚未形成完整十种子基准。 |
| SWING | 严格分类 10 个种子和亲和力 20 个种子，共 30 个科学种子条件已完成；亲和力模型与配套文件 43,372,437,689 字节已全量本地 SHA/数值闭环。分类资产另有 27,275,710,590 字节本地交付。原时点快照保留，本地交付不代替公开上传。 |
| PDZ 2026 内源人源候选 | 当前可用实验标签及认证独立外测均为 0。摘要的 7 个内源 PBM×8 个 PDZ 只给出 56 个候选格数上界，原表、实际人源身份、序列、构建体与测量复用关系仍待核定。 |

UniAIR 的一轮工程验证与正式多种子评价按不同计数保存；RDE 组件原十种子结果仍沿用独立报告。当前两条待完成的完整原生基准为 PepInter 全骨干正式训练与 UniAIR/MoFPE 正式十种子训练。本页不含肽/靶标原序列、逐条真值、第三方全文或实际进程/设备信息。

文件校验见 [FILE-MANIFEST](FILE-MANIFEST.json)与[验证收据](VALIDATION.json)，统一公开入口见 [LATEST](../LATEST.md)。
