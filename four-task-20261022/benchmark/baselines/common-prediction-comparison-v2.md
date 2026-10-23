# 共同held-out预测比较v2

本比较只提取和重新评分已经保存的预测，新增训练、forward和模型预测均为0。旧`cpu-common-subset-v1`和所有原预测/原指标未改。

## 同分母比较

| 参考cohort | 测试n | 其中NC | 主表方法/表征条件 | 主表训练种子 |
|---|---:|---:|---:|---|
| standard2919 来源冷 | 288 | 0 | 13 | 全部0–9 |
| standard2919 靶标冷 | 425 | 0 | 12 | 全部0–9 |
| backbone6336 来源冷 | 683 | 60 | 12 | 全部0–9 |
| backbone6336 靶标冷 | 946 | 88 | 11 | 全部0–9 |

基础方法为五类传统序列基线、五类手性Morgan/RDKit/蛋白AAC基线。GraphDTA来源冷完整10seed参与两个source cohort；target只有已验收4seed，单列coverage-only，不进入十种子主表。

表征路线不同的常数等对照分别保留，可能产生相同预测；上述数量是计算比较条件，不能解释为13种独立模型架构或13篇论文。

PepInter标准缓存head与backbone投影head在其能完整覆盖的cohort参与。backbone head可覆盖标准cohort；标准缓存head在6336 cohort只覆盖其中288/425个标准残基测试行，因此只记录coverage，不让它把NC参考cohort缩小回标准子集。

资格规则在查看比较指标前固定：同一panel，0–9种子齐全，而且每个种子都覆盖该参考cohort的全部测试ID，才进入该cohort主表；在这些合格模型之间取精确ID交集。其他完整度/覆盖率保留并另行评分，不补样本、不补种子，不混入主表。

## 标签与统计

每个row_id的原始CSV float64 pKd标签和endpoint逐项相同，才采用该预测；没有用float32标签与传统模型比较，也没有用容差悄悄改label。所有数据和预测都有输入SHA。

每seed提供MAE、RMSE、bias、R²、Pearson、Spearman及n，并保留五个互斥原始残基层与NC全部/PTM含混合的汇总层。标准cohort的NC相关分层n=0、指标未定义，不填0分。Ridge、常数等确定性结果仍保留十seed和真实0标准差。

共48个method×cohort主条件、480个主seed评估；另28个覆盖不足/种子不足的seed评估单列。独立标准库解析器核对481源文件SHA、287074条提取记录和28448指标格，全部通过；这些是重复提取的计算记录，不是新生物样本。

## 公平性边界

这里对齐的是测试ID、标签、endpoint和分母，**没有对齐训练覆盖和预训练暴露**。传统序列/Morgan/GraphDTA仍使用完整冻结view训练；PepInter两个组件训练覆盖分别较小，且frozen backbone已有亲和力监督暴露限定。GraphDTA十seed还包含原CPU/GPU运行分层，因此其SD不应全解释为纯随机初始化波动。

backbone6336中的405个NC注释只用于分层，其序列表征不编码相应化学身份。standard20残基也不保证末端/拓扑未修饰。本比较不是全部八篇方法的all-common subset，不据此认定整篇复现或模型架构的因果优势。

## 文件

- `runs/common-prediction-comparison-v2/mean-sd-metrics.csv`：共同分母十seed主指标表。
- `per-seed-metrics.csv`：主表逐seed/逐残基层。
- `unranked-coverage-only-per-seed-metrics.csv`：target Graph部分种子、旧缓存head部分cohort覆盖，单列不排名。
- `coverage-per-method.csv`：每方法实际种子与覆盖率、排除原因。
- `task-contract.json`：参考cohort、模型、训练分母、来源SHA和指标前固定的纳入规则。
- `COMPARISON-RECEIPT.json`及`INDEPENDENT-VERIFICATION.json`：原预测不变和独立复核证据。

早期DTA来源索引使用GB18030编码；本分析进行了严格字节往返解码并保存编码说明，原文件未改。首次UTF8读取失败日志亦保留，未通过损坏字符替换来改变科学路径或数据。
