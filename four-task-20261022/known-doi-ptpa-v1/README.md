# 来源受控的PTPA补充基准

已完成两种划分、五类基准各10种子：100个选定模型、200次候选拟合。全部结果与预测已核验；原1050个模型主表保持原样。

[完整报告](REPORT.zh-CN.md) · [逐种子结果](RESULTS-per-seed.csv) · [均值与样本标准差](RESULTS-mean-sd.csv) · [200份权重清单](WEIGHTS-MANIFEST.public.json)

权重单独保存于[GitHub Release](https://github.com/cihebiyql/ppikb-noncanonical-peptide-affinity-benchmark/releases/tag/four-task-20261022-known-doi-ptpa-weights-v1)，发布状态以该Release为准。归档仅含200份原字节joblib及清单。

外测为此前已评估过的1篇研究、1个蛋白背景中的4条未修饰肽测量；训练来源经DOI元数据控制，不据此声称前瞻盲测、冷靶标家族或非天然残基外部验证。模型依赖与HPO、来源控制和限制均见报告。
