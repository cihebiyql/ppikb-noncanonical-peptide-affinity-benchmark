# 非PTM外源补集：已完成输入审计，尚未采用

本目录是原75条外测冻结之后的独立补充调查。当前候选为 **8条非蛋白源/D型/立体异构残基肽＋5条标准残基对照，共13个实测Kd点值**。未训练、未推理、未改动当前75条输入或任何主模型选择。

来源为2025年12月的人源IgG Fc亲和力研究，DOI `10.1248/cpb.c25-00637`。现已从期刊官方页面公开的补充材料接口取得完整16页SI；先前普通supplement地址的404记录仍保留，未覆盖旧冻结信息。[官方论文](https://www.jstage.jst.go.jp/article/cpb/73/12/73_c25-00637/_html/-char/en)

| 筛查阶段 | 数量 |
|---|---:|
| 原表新实体，不含5个历史引用数值槽 | 23 |
| 新实测点值Kd | 19：13非标准、6标准 |
| 原注释与端点规则后，尝试格式转换 | 14：9非PTM NC、5标准 |
| 化学式、端基、二硫键和构型校验通过 | **13：8非PTM NC、5标准** |
| 格式验证后仍有作者化学式冲突 | 1，保留隔离，不修造 |

原13个非标准点值减少为8个可审查非PTM输入的原因：2个Cya盐态/离子身份未解，2个复杂Tpi实体未完成严格格式转写，1个Abu实体的明确原残基注释与作者质谱式不一致。6个标准点值中另有1个SI序列长度矛盾。2个删失值和2个没有测得数值的实体也保留原记录，没有当作点值训练标签。所有去留理由见 `chemistry-exclusions-preserved.jsonl` 和 `runtime-conversion-v1/author-entity-conversion-summary.json`。

13条均保留实际N-acetyl、C-amide或C-acid端基、具体二硫键与实际非标准残基连接、D构型或alloThr立体信息。转换只是对**已经测量、已经公开的固定实体**作机器可读格式记录，没有生成或优化候选肽。元素计数与作者明确的[M+H]+式比较，逐个alpha碳和alloThr构型也核对通过。

独立性审计实际结果：

- 对PPIKB全21,845条，原研究DOI、PMID和完整标题匹配均为0。
- 对全库11,256个图，13条的同立体图、去立体图和Morgan radius2/2048bits/achiral Tanimoto≥0.8邻居均为0。与冻结主基准使用相同口径，0邻居不表示解决了全部可能的骨架等价关系；原研究仍明确沿用历史母体系列。
- 唯一目标重链参考对主库1,411个独特蛋白参考作同口径对齐，找到2个相关目标；另有238aa精确共享片段警示。因此**13条都不能称未见靶标或未见家族外测**。

原文明确实测靶标为Chugai供应的Trastuzumab单克隆人源IgG1，不是混合血清IgG。官方[KEGG D03257](https://www.kegg.jp/entry/D03257)给出449aa重链和214aa轻链；`target-reference-multichain.json`完整保存2H2L组成，没有人工拼接两条链。

面向当前只接收单条蛋白序列的作者模型，本目录只**提议**完整重链作为Fc侧结合的reference-view。它不是原测量的整个商业抗体、已认证的孤立Fc构建体或具体lot/glycoform。采用这个模型视图需要root建立新的补充清单；原75条接受清单仍保持原SHA。

入口文件：

- `postfreeze-supplement-candidate-manifest.json`：冻结候选数、实际独立等级、输入视图限制和16项文件SHA，状态为not adopted。
- `supplement-inputs13-not-adopted.jsonl`：无pKd输入，`synthetic_D_backbone`8条、`standard20_control`5条，与主协议分层字符串一致。
- `supplement-gold13-not-adopted.jsonl`：分离的原Kd、nM单位、pKd和原表定位，未供调参。
- `author-SI-0.pdf`、`SI-all-23-entity-annotations.json`：官方SI与23个实体的逐条转写。
- `runtime-independence-v1/`：全库分子、参考目标相似性、进程退出和资源限额收据。

本次两个独立性检查分别耗时89.44秒和32.20秒，均为单CPU、nice19、0GPU，进程已退出。root若接受，只能作为另一个回顾性、独立来源及声明图规则下化学冷的参考视图补充诊断；单一研究的13行不等于13个独立生物体系。
