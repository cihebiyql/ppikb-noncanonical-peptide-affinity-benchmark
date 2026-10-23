# 肽—蛋白质四任务基准：首批公开快照

本目录独立保存2026-10-22开始的新基准，保留仓库原有NC实验。快照准备时间：2026-10-23T10:04:57.518593+00:00。

本批交付包含可核查的自有训练/评价代码、任务协议、数据分析、完整通用基准汇总、部分逐条预测、独立验收和进度说明。完整模型权重、其余逐行预测、特征缓存及全部成功/失败日志保留在后续交付队列，详见[待交付资产](delivery/PENDING-ASSETS.json)。本目录不代表本地约108.6GB资产已全部上传。

## 任务与结果入口

|内容|快照状态|入口|
|---|---|---|
|四类任务、四个主来源|绝对亲和力／改动效应／是否相互作用／接触位点；按真实标签适用性划分|[任务定义](benchmark/protocol/task_definitions.json)、[数据规则](benchmark/protocol/data_protocol.md)、[来源与任务表](benchmark/reports/delivery-20261023/source-task-eligibility.csv)|
|通用基准|1050个selected训练条件、2100个候选拟合；105个模型×视图组合，各10种子；1350行指标汇总|[全部汇总](benchmark/reports/delivery-20261023/generic-completed-metrics-all-panels.csv)、[独立验收](benchmark/reports/root-generic-aggregation-independent-v1/REPORT.zh-CN.md)|
|八项前人方法的适用范围|5个DTA架构属于迁移对照，另有SWING、PepInter、UniAIR；组件与全链复现分别报告|[方法登记](benchmark/protocol/method_registry.json)、[方法范围](benchmark/reports/goal-acceptance-ledger-v2/method-scope-matrix.csv)|
|DTA共同数据重训|09:55UTC接受144/150个逻辑条件；该时点尚有6个待完成，后续进展单列|[144条逐种子指标](delivery/DTA-accepted144-per-seed.csv)、[15组合种子覆盖](delivery/DTA-accepted144-view-method-coverage.csv)、[训练与验收代码](benchmark/methods/dta/)|
|SWING／PepInter分类|各10种子；PepInter为固定回归监督骨干＋原生Focal分类头的条件组件基准|[范围与结果](benchmark/methods/interaction/continuation-20261023/REPORT.classification-10seeds.md)、[每种子指标](benchmark/methods/interaction/continuation-20261023/classification-common-per-seed.csv)|
|UniAIR RDE组件|真实10种子、20候选、固定同一63条测试；author DDG单位未认证|[报告](benchmark/methods/uniair/continuation-20261023/rde-ten-seed-report-v1/README.zh-CN.md)、[均值与样本SD](benchmark/methods/uniair/continuation-20261023/rde-ten-seed-report-v1/mean-and-sample-SD.csv)、[仅预测列](benchmark/methods/uniair/continuation-20261023/rde-ten-seed-report-v1/prediction-only/)|
|HER2传统对照|相同严格局部分组；抗体变量域—HER2任务，保留author DDG与绝对pKd的端点差异|[指标报告](benchmark/reports/her2-strict-local/REPORT.zh-CN.md)|
|ProfAff HU条件外测|100个已有固定手工模型应用；HU与直接FP分轨，不参与调参|[外测报告](benchmark/reports/profaff-HU-external/REPORT.zh-CN.md)|
|PEPBI条件外测|100个已有模型×27候选，新增拟合0；全部结果保留|[外测报告](benchmark/reports/pepbi-conditional-external-v1/REPORT.zh-CN.md)、[原始来源复核](benchmark/data/pepbi-primary-context-20261023/REPORT.zh-CN.md)|
|接触位点图|12个测试复合物的自有可视化与独立审核|[12页图册](benchmark/reports/contact-site-gallery-v3/report.pdf)、[审核](benchmark/reports/contact-site-gallery-v3/REVIEW.zh-CN.md)|
|近五年前作|可审计检索范围、直接PepPI方法与DTA/general-PPI对照分栏|[文献总报告](benchmark/literature/systematic-2021-2026/REPORT.zh-CN.md)|

各文档带有各自的统计时点。历史报告按原样保留；最新状态以相应owner的有时间戳证据为准，不能把单步运行、固定推理或组件十种子当成整篇论文的完整训练复现。完整UniAIR四专家链、SWING亲和力等任务仍在推进。本批没有为发布新增拟合或模型前向。

## 数据与复现边界

数据标签按测量端点和真实实验关系使用。Kd、Ki、IC50、筛选分数及author DDG分别解释；构造负例与同条件实测不结合分别记录。标准残基序列输入不能代替非天然残基、PTM或末端的完整化学身份。

PEPBI的27条已经做过条件外测，后续补原文用于核验全部候选，并非按预测表现挑行。原数据和预测保持不变；构建体、删失值、疑似表格映射等问题进入侧车。对100个纯手工模型，来源分离依据其实际监督训练数据，不使用不存在的预训练编码器暴露门槛。该判断不继承给PLM或其他作者模型。

自有代码位于benchmark/baselines/及各方法/分析目录。本批不包含原作者vendor源码、官方大权重或受限原始数据。运行这些代码前，应按[任务协议](benchmark/protocol/EXECUTION_PLAN.md)恢复规定输入和依赖；本批尚不是所有八项方法均可一键完整恢复的最终包。

RDE逐条导出仅包含source ID、组件ID、保存的预测、seed、split和endpoint；原作者HER2表、真标签及抗体变量域/靶标完整序列未复制。源文件SHA与投影规则见[导出谱系](delivery/generated-files.provenance.json)。

## 许可、校验与后续资产

本目录未设置统一MIT许可。自有研究产物按用户既有公开授权准备发布，第三方资产遵循各自来源许可。PPIKB数据CC BY4.0、PEPBI官方页面CC0；PepInter代码MIT、官方模型CC BY4.0分别有证据。DGDTA GPL3、MGraphDTA MIT、原RDE Apache2以及UniAIR/ESM相关许可分别记录。HER2数据包未取得明确dataset许可；完整frozen-base checkpoint发布须绑定组件许可或用自有增量与固定官方base恢复。

- [首批源复制清单](delivery/source-copy-manifest.json)：原文件字节身份与来源路径。
- [首批完整文件SHA清单](delivery/FILE-MANIFEST.json)：最终命名空间内实际文件校验。
- [校验结果](delivery/VALIDATION.json)：JSON/CSV/端点、代码语法、秘密指示与旧仓库保护。
- [官方资源锁草案](delivery/readiness/upstream-fetch-lock.draft.json)：固定URL／revision／hash；明确pending项。
- [后续Release与官方fetch](delivery/PENDING-ASSETS.json)：权重、缓存、逐行结果、失败日志及其owner索引。

后续大文件采用不超过1,900,000,000字节分卷的流式Release方案，保留逐文件和逐卷SHA，避免再复制整份几十GB模型。当前仅为首批自有内容快照，后续资产交付状态逐项更新。

DTA的accepted-current指针保留原本地path作为谱系；本公开快照的逐种子指标与覆盖表已物化在delivery/，无需访问私有路径。其不可变详细JSON也随本批保存在benchmark/methods/dta/，按指针path的文件名即可定位。
