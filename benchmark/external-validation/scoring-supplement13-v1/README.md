# 已接受的13条独立补充诊断

Root已依据来源、化学身份转写和输入可追溯性接受本补集，未参考任何模型测试或外测成绩。接受时间、直接任务决定、原候选SHA和本目录8项资产SHA保存在 `root-accepted-manifest.json`。

这是**独立于旧75条的补充诊断**：8条 `synthetic_D_backbone`、5条 `standard20_control`；对应 `NC_core=true/false`。不增加训练数据、不改变模型选择、也不合并到旧75条主外测。

- `inputs/input13.jsonl`：13条唯一record_id，无pKd或其他亲和力金标。原实际分子SMILES、非标准残基、末端、位点和二硫键逐条保留。
- `gold/gold13.jsonl`：原补集金标的逐字节副本，SHA与历史候选相同；含原Kd、单位、换算、原表位置及不确定性。
- `ids-all13.json`、`ids-nc8.json`、`ids-standard5.json`：固定评价分母。
- `provenance/target-reference-multichain.json`：完整重/轻链参考及2H2L组成。模型输入只用已声明的449aa完整重链作为Fc侧reference-view，没有人工拼接两条链。
- 两个 `*-supplement13-score.cpu.json`：runner兼容的CPU准备规格，继续要求全部200个selection冻结屏障。尚未调用模型。

13条均通过独立来源及声明化学图规则下的全PPIKB审查，蛋白参考均与主库存在关系。它们**不是参考靶标冷或家族冷数据**，也不代表已认证实际整抗体、孤立Fc构建体、商业lot或glycoform。

Score-cache协同只接收无标签输入路径和SHA。金标供root在400个候选完成、200个selection全部冻结之后统一评分；每个冻结模型/种子预测13条一次，再从同一预测分出8/5指标。全部10个种子及失败原因保留。

原候选及所有 `not-adopted` 文件保持历史状态。旧75条接受清单SHA仍为 `85973838adc28c0b6b9134a28a90312162a158eafd20f8b2bf14e68e13d36c4d`。本目录建立后也没有加载模型、推理、训练、调参或继续扩充资源。
