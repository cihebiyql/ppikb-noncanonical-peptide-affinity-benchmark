# 外部75条的执行器评分视图

本目录已准备并静态核验，**尚未推理、未加载检查点，也没有产生模型指标**。`scoring-view-manifest.json` 固定输入、金标、ID清单和两个panel的评分规格及SHA。

| 文件 | 含义 |
|---|---|
| `inputs75.jsonl` | 75条唯一record_id，无pKd；完整真实分子SMILES、蛋白参考视图、PTM位点和端基 |
| `gold75.jsonl` | 同75 ID的pKd、原Kd数值和单位、摩尔换算及反算检查、来源和原不确定性 |
| `ids-all75.json` | 全部75条 |
| `ids-primary67.json` | 67条无额外构建体/结合位点条件的主输入 |
| `ids-conditional-sensitivity8.json` | 8条已记录条件的敏感性组 |
| `ids-reference-target-cold2.json` | 2条按冻结参考序列规则为靶标冷，均属于primary67 |
| `*-external75-score.cpu.json` | 两个panel的runner.score_holdout兼容CPU规格，保留200个selection全局冻结屏障 |

每行均为 `NC_core=true`、`evaluation_stratum="PTM"`，与主协议字段一致。8条条件性样本仍完整保留。化学格式由明确实测注释转换，并经过元素计数、构型、端基和位点检查；蛋白为参考全序列，不冒称实际实验克隆。

评分只能在400个候选全部结束、200个独立selection完成冻结后由root统一进行。规格中的 `selection_barrier_path` 指向 `formal-runs-gpu-v4/all-selections-frozen.json`。本目录没有调用评分入口。需要GPU时由root另行绑定资源合同，不能把CPU准备规格当成已发行的GPU运行授权。

每个冻结模型只预测一次75条；67/8/2指标均从同一份75条预测按ID清单汇总，禁止重新训练或根据外部结果更换候选。当前runner只把其固定METADATA白名单带入预测结果，外部分层旗标可用本目录不可变ID清单和record_id回连，避免丢失67/8/2边界。所有10个种子分别保留预测和指标。

这些标签早先已被查看，本次属于回顾性的独立来源外测。输入和金标采用程序与文件隔离，共享账户下没有声称操作系统级访问封锁。原 `acceptance-manifest.json` 及其13项引用文件已逐一复核保持不变；本目录只是新增执行器适配视图。
