# 原生 CPU 成本验证与冻结 ESM 条件外测

本包补交两组已终态、已独立核验的结果。

- **UniAIR 原四专家 MoFPE 的 CPU FP32 一轮成本验证**：原 B8，293 条 train、63 条唯一 validation，保留原两次验证，37 Adam、0 test；自然退出0，耗时7008.262449496426秒，峰RSS14805962752字节。验证 MAE1.5575887871691905、MSE3.3528807010881527，端点为未认证物理单位的 authorDDG。本轮为单上下文成本证据，正式20候选仍为0；CPU FP32不作为GPU精度等价证据。checkpoint仅登记SHA，本包不复制24MB检查点。见 [成本与指标](uniair/CPU16-epoch-local-cost-and-metrics.json)、[独审](uniair/CPU16-epoch-independent-audit.json)、[自然终态](uniair/CPU16-natural-terminal.json)。
- **冻结 ESM2 与100个既有预测头在27条 PEPBI 候选上的固定外测**：2训练划分×5模型×10种子，100次应用、2700条预测，新增fit/tune为0；Node23与Windows各18580指标单元独立核对通过。见 [完整报告](external/REPORT.zh-CN.md)、[逐种子](external/fixed-head-results-v1/per-seed-metrics.csv)、[十种子mean/sampleSD](external/fixed-head-results-v1/mean-sd-metrics.csv)、[每组指标](external/fixed-head-results-v1/per-group-per-seed.csv)、[无原标签的自有预测](external/own-predictions-only.csv)。

外测的source/target监督训练中分别有887/816条记录无可解析DOI，来源分离只在已核已知轴上成立。25条独特序列中6条复用CPU缓存、19条由GPU补算，不承诺两后端逐位等价。27条候选的化学身份、部分构建体、缓冲液和原文单元映射尚未完全认证；认证完整独立外测为0。本包不称盲测、新家族或非天然残基独立验证，也不把同批manual与ESM候选相加。多个种子描述计算波动，不替代独立生物实验。

100次固定应用不增加通用1050个已选模型或2100次候选拟合计数。CPU24成本门不纳本包成果，也未计成完整原生基准。

公开预测只保留原row_id/prediction和目录导出的panel/model/seed，移除原label及其他列；聚合CSV所有单元原值不变。原报告仅遮蔽一处实际进程ID，科学数值未改。原始数据、序列清单、完整合同/inventory、特征缓存、原权重和第三方全文不在本包。报告中的未附原路径是来源标识，访问控制以原资产许可为准。

[DELIVERY-RECEIPT](external/DELIVERY-RECEIPT.json)、[双端独审](external/independent-fixed100-audit.json)、[Windows独审](external/independent-fixed100-audit.windows.json)、[来源审计](external/training-source-overlap-audit.json)均保留科学字段。原/公开SHA映射见 [SOURCE-MAPPING](SOURCE-MAPPING.json)，本轮只做准备、未上传的校验见 [VALIDATION](VALIDATION.json)和 [FILE-MANIFEST](FILE-MANIFEST.json)。


后续输入核查发现3条AP2记录的蛋白输入与原文实体不符。原27条成绩保留；请同时参阅[输入勘误与27／24／PTPA4固定预测敏感性更新](https://github.com/cihebiyql/ppikb-noncanonical-peptide-affinity-benchmark/blob/main/four-task-20261022/pepbi-input-erratum-v1/勘误与敏感性更新.zh-CN.md)。该更新没有重新训练模型。
