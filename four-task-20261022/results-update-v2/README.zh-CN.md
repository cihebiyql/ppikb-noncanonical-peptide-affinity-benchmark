# 四任务基准结果更新 v2

本批补充最新已审结果，原公开快照保持不变。总状态采用12:31:23UTC实际收据：[最新总报告](collector/阶段结果与未完成清单.md)、[机器状态](collector/STATUS.json)、[独立验收](collector/independent-DELIVERY-RECEIPT.json)。科学结果完成、文件物理回流和公开上传分别记录；本批仅包含小型结果、报告与审计信息。

|部分|已完成范围|主要入口|
|---|---|---|
|五种DTA作者架构|3视图×5方法×10种子=150正式单元，300验证候选；178900项独立指标检查0错误|[完整报告](DTA/完整结果报告.md)、[逐种子](DTA/all-seed-metrics.csv)、[均值/SD](DTA/ten-seed-summary.csv)、[独审](DTA/final-all150-independent-audit.json)|
|相同683/946测试ID的DTA固定应用|100份已有预测精确复核，3600检查0错误；0训练/前向|[共同子集报告](DTA-common-fixed/报告.md)、[每种子](DTA-common-fixed/per-seed-metrics.csv)、[独审](DTA-common-fixed/independent-numerical-audit.json)|
|SWING严格分类|启动哈希受控的10种子；四次原模型仅补缺失测试预测，原partial保留|[分类报告](SWING/classification/REPORT.classification-10seeds.md)、[每种子共同测试](SWING/classification/classification-common-per-seed.csv)|
|SWING连续亲和力适配|source/target各10种子，20表征、40候选回归读出|[亲和力报告](SWING/affinity/REPORT.affinity-20seeds.md)、[每种子](SWING/affinity/affinity-all-per-seed.csv)、[均值/SD](SWING/affinity/affinity-mean-sd-by-cohort.csv)|
|原生RDE组件|10真实随机初始化、20候选、同63条测试；不是完整UniAIR|[组件报告](RDE-component/README.zh-CN.md)、[每种子](RDE-component/all-model-seed-metrics.csv)、[均值/SD](RDE-component/mean-and-sample-SD.csv)|
|PEPBI27条件外测与原始来源复核|100个固定手工模型应用，2700条原预测全部保留；原27候选逐条分轴核验|[条件外测](PEPBI-conditional-external/REPORT.zh-CN.md)、[原始来源](PEPBI-primary/REPORT.zh-CN.md)、[27条资格表](PEPBI-primary/primary-context-index.csv)|

DTA的150个选中模型、全部300个候选检查点、150份测试预测及300份验证预测已有实际本地SHA验收；该判断依据科学资产逐项审计，不从行政日志回流数量推断。300个候选中13个达到20轮上限时尚未耗尽patience5；固定预算完成不等于已证收敛，停止规则和环境差异照常保留。[每候选运行与停止原因](DTA/actual-training-runtime.csv)

SWING分类十种子的大模型及必要sidecar已全本地。SWING亲和力二十种子的科学结果和小型结果收据已闭合；12:31:23UTC已确认13/20个大模型物理本地，其余仍在回流；[回流时点收据](SWING/affinity/mirror-progress-and-ETA.latest.json)是带时间戳的进度快照，不能把科学完成当作所有模型已全本地。全骨干PepInter训练与完整四专家UniAIR/MoFPE两条原生完整训练线仍单列待完成；成功的组件或单步能力检查不补作完整训练。

## 比较的分母与端点

DTA两个完整pKd测试集为1014/1383条，SWING完整可用测试集为774/1177条，不能直接用不同分母的总体MAE排序。跨方法优先查看预先冻结的共同683/946条测试ID，来源、训练观测范围与输入信息的差异仍须保留。DTA五架构属于DTA迁移对照；SWING连续读出属于作者grammar的共同数据适配。

RDE输入为H120/L107抗体变量域与581aa HER2，衡量同一靶标背景中的局部变体。端点为未认证物理单位的author DDG，不能直接称为kcal/mol或短肽亲和力。它与DTA的pKd、metadata-silver ΔpKd及二分类标签分别汇报，各目录ENDPOINT说明提供机器可读范围。

PEPBI的27条相对这100个174维手工特征模型已有监督训练来源分离证据，模型没有PLM预训练编码器。完整构建体/条件/化学认证仍为0；19条原点值与单位已核，2条与原图舍入值相容、6条数值单元未闭合。三个AP2输入额外突变、疑似错肽及下界/点值问题、STAC构建体差别均保留，不按性能修改序列、标签或重跑测试。该来源分离结论不自动继承给预训练模型。

## 已公开的通用结果与权重

1050个通用selected训练条件、2100候选的完整通用指标继续引用[已有汇总](../benchmark/reports/delivery-20261023/generic-completed-metrics-all-panels.csv)，SHA为60f29ff73f66845f580d4f13e0d9abc88717d30192b68c7765f6afadf7e1b447，本批未重复复制。

[通用2100候选权重Release](https://github.com/cihebiyql/ppikb-noncanonical-peptide-affinity-benchmark/releases/tag/four-task-20261022-generic-candidates-v1)已公开，18项Release资产的大小、SHA与tag commit经根验收；[发布收据](published-generic-weight-release.receipt.json)。它覆盖全部通用候选权重，本项目其他作者方法的大权重仍按各自状态另行交付。[官方输入资源获取工具](../official-resources-v1/README.zh-CN.md)负责精确输入获取，不等于一键完整复现。

## 可追溯性

[SOURCE-MAPPING.json](SOURCE-MAPPING.json)保留每份原文件SHA和公开版SHA。公开版本把私人绝对路径替换为record-ref，并将本批已有文件链接转为相对路径；侧车中的原序列字段被移除，位置和差异证据仍保留。记录中的原source-manifest SHA指原始审计文件，公开字节应按本批FILE-MANIFEST核验。CSV科学结果单元与原文件逐项保持一致，本批公开整理未新增训练、调参或模型前向；这描述汇总行为，不将已经完成的科研拟合数量改为0。

[本批校验](VALIDATION.json) · [公开文件SHA清单](FILE-MANIFEST.json)。
