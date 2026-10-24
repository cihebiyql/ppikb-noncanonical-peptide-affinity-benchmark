# 跨任务防火墙冻结协议 v1（revision 2）

本协议在既有数据、分区和全部旧结果之外建立新版本。划分以身份、来源、结构和既有依赖为依据，不使用数值标签或模型预测决定角色。既有测试曾被评估过，新版本不是新的前瞻盲测。

## 1. 实际数据与边

纳入PPIKB点Kd、编辑配对、64实验复合物；PepInter二分类、PepAff混合亲和力；ProfAff直接162、PTM42、holdup16806；PEPBI329背景及27候选；HER2严格419。残基表先以实验复合物为单元，避免将8625残基误当8625独立结构。PEPBI329作为外测保护背景，不能自动全部转作训练或正式外测。

真身份和强依赖键包括：原观测ID/WT与变体引用、DOI/PMID/title别名、完整化学iso与achiral实体、原肽字符串、精确序列对、PDB。缺失字符串不建共同token；missing_source哨兵不是已知论文来源。PPIKB原568化学图/注释冲突flag保留，不依据模型误差修正化学实体。

两个面板边集分开：

- **source面板**：真身份/强依赖键、PPIKB旧source组件、已冻结Morgan无手性指纹Tanimoto>=0.8近邻边、实验接触组件。
- **target面板**：真身份/强依赖键、PPIKB旧target组件、作者PepInter/PepAff靶标组件、相同target及前1000AA、已有PPIKB target局部比对边、所有已纳入target序列的精确包含（短链>=40AA）。

target面板不宣称Morgan近邻肽隔离，source面板不宣称新靶标隔离。target对跨源新序列的非精确局部同源比对覆盖尚不完整，不能称普适protein-family-cold。模型原始无监督预训练成员仍未知。

## 2. 全局连通与角色优先级

在每个面板上，以上述边的最大传递闭包形成global_group_id。

1. ProfAff和PEPBI预留外测背景的组件优先保护；开发数据若落入同组件则quarantine。
2. 保留Kd原test锚点；同组件Kd validation或其他训练记录隔离，不将旧test移训练。
3. 保留Kd原validation锚点；同组件训练记录隔离。
4. 其他任务旧validation/test保护所在组件；新模型不在其关联组件上预训练。
5. 未触及保护组件的Kd旧train且来源可解析，分配fine_train。其余任务同组件记录预留给微调关联，不计独立pretrain。
6. 其余旧train且来源可解析者可分配pretrain；源未知者quarantine。HER2属于单背景抗体支线，整体不投入本次短肽预训练。

同一节点只有一个角色。共享原测量通过token连接。预训练与微调训练的组件分开，验证、测试、外测保护组件也分开；预训练不可直接使用旧任意任务全量train。

## 3. 外测与化学资格

ProfAff162、42、16806分别冻结external角色，保留其端点和共享观测关系。PEPBI正式可评分候选使用已存在、以输入实体冲突为依据的24条敏感性ID；4条PTPA为其嵌套子集，27条原候选表另存historical。role表中27个external candidate表示保护身份，并不表示27个无输入冲突的正式测试点。

这些资源在当前监督防火墙上受到隔离，实际构建体、完整化学实体/实验条件及基础模型预训练暴露仍分轴保留未知。源与角色冻结不能使未知变为金标准。化学模型没有实际SMILES时，报告外测化学可编码覆盖为0，不用MolFromSequence合成骨架冒充实际PTM分子。

## 4. 实际可执行性

最大闭包source面板没有剩余fine_train，必须标blocked，不通过修改阈值或丢弃困难外测恢复训练量。target面板保留非空微调/验证/测试，是首个可推进的严格化学表征基准。

输入和所有输出逐SHA绑定。正式revision落盘后不可覆盖；修订必须另建版本，保留旧manifest与源文件。首次初稿在科学训练前被审查拒绝，完整保全于data/global-freeze-20261024-v1/pre-review-initial-20261025T0010，原因和hash见PRE-REVIEW-REJECTED.json。

训练使用global_group_id；CSV的group_id仍保留对应legacy面板原值，便于来源宏指标。split使用fine_train、validation、test；只有验证集选择参数，十种子0–9使用同一冻结ID。新模型暂不加入创新架构，DTA只作补充。
