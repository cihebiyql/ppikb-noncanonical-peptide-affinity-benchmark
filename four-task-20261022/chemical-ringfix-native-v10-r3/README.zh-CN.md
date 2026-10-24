# 化学亲和力基准的新增证据 v10-r3

## 本版执行门与历史资格纠正

实际补充同源比对检出旧验证集与预留外测之间2条靶标关系，影响5条标准肽验证记录。原生v1和ringfix-v2内部成绩全部保留为历史结果；这些旧成绩不再承担严格外测独立选择的结论。旧v2完整encoder计划封存22/40已完成候选、18个未发放，TEST执行数为0；没有恢复旧driver或把部分训练算成十种子完成。

新全局v3为训练554/验证579/测试695，source0训练保持blocked。5条验证记录转外测依赖隔离，训练和测试ID、保留原始字段及label字符串不变。两条新边的输入、传播与角色划分通过422,963项独审。现用763个靶标的212,699跨角色对在固定30%identity/80%双覆盖和精确包含定义下由旧范围、长度上界及既有实际比对证据覆盖，残余正边为0；此范围不包含所有隔离靶标或未知底座预训练暴露。

[v3协议](data/v3-global/PROTOCOL.md) · [全局独审](audit/v3-global/FINAL-GO.actual.json) · [继承断言](data/v3-global/ROLE-INHERITANCE.actual.json) · [新共同输入实际状态](data/v3-model-cohort/ACTUAL-COUNTS.json) · [新cohort独审](audit/v3-model-cohort/COHORT-REVIEW.actual.json)。新模型实验结果尚未纳入本快照，新划分不会回填旧分数。Native候选覆盖原预计388/345/502、ringfix原预计497/495/656；实际完成状态以新共同输入实际表为准，未经实际独审的轨道保持pending。

以下三条结果表均是被保留的历史实验记录。新的同源资格修订与2018荧光标签疑点是两类独立问题，均完整披露。

本包追加三组分开记录的结果：原生分词器下的完整encoder微调、新ringfix-v2共同覆盖上的冻结表征预测头，以及六点条件外测。旧v9与原始结果保留。本包保存发布前验收快照；发布事实以仓库LATEST及发布收据为准。

## 三条结果轨道

|轨道|模型与候选|训练/验证/测试|完成情况|
|---|---|---|---|
|原生CLM2完整encoder普通微调|两变体×10种子，40候选、20选定TEST|388/346/502|51,910项最终独审通过|
|ringfix-v2冻结表征+普通预测头|3表示×5族×10种子，300候选、150选定模型|497/500/656|305,937项冻结审计与295,200项独立记录核查通过|
|条件外测|v1既有Morgan五族×10种子固定应用|6测量、2研究、1参考蛋白|50个固定模型全部保留，R²均为负|

Hybrid与MLM来自同一篇PeptideCLM-2论文。上述预测头是同任务重训练基准，完整encoder微调是普通回归适配；原八篇论文全部复现和四类任务总体目标仍在推进。v2完整encoder微调尚未纳入本快照。

## 原生502条测试：普通全参数微调

31,674,369个训练参数，冻结ESM320蛋白表示、普通MLP回归头，AdamW两学习率、最多30轮、早停5轮；验证集决定候选和轮次。同encoder同seed的两学习率共享初始化。

|表示|全参数MAE±样本SD|冻结ExtraTrees MAE±SD|
|---|---:|---:|
|Hybrid|1.5363±0.0173|1.5427±0.0123|
|MLM|1.5585±0.0212|1.5818±0.0224|

整体收益有限。NC14层全微调Hybrid MAE1.1292，冻结Hybrid+ET为0.9300；PTM34层全微调1.2295，冻结1.3033。mixed17仍约2.7。完整[逐种子](results/native-fullfine-v1/INDEPENDENT-per-seed-chemical-metrics.csv)、[化学层汇总](results/native-fullfine-v1/INDEPENDENT-ten-seed-chemical-summary.csv)与[最终独审](audit/native-fullfine-v1/FINAL-INDEPENDENT-AUDIT.actual.json)保留全部结果。最终审计重新读取20组微调小文件，150组旧预测头采用原已接受证据；大权重完整独立重哈希仅有前期两份抽样，其余按生产SHA及大小保全。

## 新共同656条测试：ringfix-v2

原生分词器对1238个唯一原SMILES中的317个产生UNK，主要涉及相邻环闭合标号12。v2透明修复此分词，保留%12优先级；原921个输入token IDs不变。实际1238个输入全部生成特征，官方权重、词表、原SMILES保持不变。该输入适配器是明确修改，并非原作者原生分词器。

三表示共同训练497/验证500/测试656；测试为572标准、26非天然/D/骨架、35PTM、18混合、5其他。source面板仍为0训练，blocked。不同共同覆盖版本的指标不可直接当作分词器改善量。

|同一ExtraTrees头|MAE±样本SD|Spearman|R²|
|---|---:|---:|---:|
|Hybrid|1.6150±0.0109|0.1759|−0.0642|
|MLM|1.6445±0.0116|0.0835|−0.0974|
|手性Morgan|1.6158±0.0104|0.1129|−0.0716|

Hybrid与Morgan同头误差几乎持平，全部总体模型R²为负。Morgan+HGB观察MAE1.6040；跨族测试排序属于描述统计，后续调参仍只使用验证集。十种子反映训练随机性，确定性模型SD可为0，未定义相关性保留NA。

[全五族逐种子](results/ringfix-v2/per-seed.csv) · [全部化学层均值/SD](results/ringfix-v2/ten-seed.csv) · [同头配对差值](results/ringfix-v2/paired-seed-MAE-differences.actual.csv) · [依赖组等权宏指标](results/ringfix-v2/group-macro-ten-seed.actual.csv) · [联合收据](audit/ringfix-v2/JOINT-AUDIT.actual.json)。21条化学注释冲突保留原评分，并提供固定预测排除后的635条敏感性。历史测试已经被查看，不称前瞻盲测。

## 六点条件外测：保留不利结果

来自两篇原始D-AA系列研究的ChEMBL完整SMILES，历史评分使用人MDM2官方参考序列；已有来源、isomeric/achiral分子身份交叉核查未发现与PPIKB重叠。严格独立gold数为0。六条测量不等于六个独立生物体系。

**新增资格勘误：2018年官方补充材料标明human MDM2 17–125，相关直接结合曲线属于Fl标记实体；原外测中该来源两条SMILES未包含荧光团，存在化学实体—标签错配疑点，两点隔离并暂停新增external6化学外测应用。** 旧六点manifest、历史固定模型结果保留以便追溯。未标记肽IC50不换算为Kd；精确原数值单元尚未取得，当前是身份错配疑点而非已认证更正Kd。另4条2017测量仅条件性保留。

官方[2018补充材料](https://ars.els-cdn.com/content/image/1-s2.0-S0960894X18300015-mmc1.pdf) S2§1.2/1.4给出构建体；S6§1.11/1.12分开直接FP Kd与竞争IC50/Ki；S11 Table S1区分Fl标记与未标记、末端酰胺；S12 Fig S4A为Fl-p53-TAD直接结合。荧光团是实验偶联，不能自动归入生物PTM。详见[聚合勘误与来源SHA](audit/conditional-external6/QUALIFICATION-ERRATUM.public.json)。此勘误针对外测资格，内部v2冻结结果保持其原数据与验证范围。

v1既有50个Morgan模型固定应用，未用这六点选参数。所有R²为负：ET MAE1.7853、R²−2.5502；HGB MAE1.2879、R²−0.8428；常数MAE1.5182、R²−1.6066。全部[逐种子](results/conditional-external6/RESULTS-per-seed.csv)和[均值/SD](results/conditional-external6/RESULTS-mean-sampleSD.csv)保留。原生CLM2覆盖0/6，保持not_run；新外测仅在v3新已选模型和conditional4资格绑定后推进，旧external6保持隔离/不恢复，本包没有合并这些数据回训练。

## 索引与复用

[Agent接手摘要](AGENTS-PUBLIC-SUMMARY.md)、[代码树恢复与测试](RESTORE-AND-TEST.md)、[自有适配器及微调代码](code/)、[官方获取与许可](SOURCE-AND-LICENSE-REFERENCES.md)、[来源字节映射](SOURCE-MAPPING.json)。原始序列、SMILES、逐行标签/预测、权重、私有SSH和第三方源码均不在此聚合包。record-ref是来源占位，恢复有权限输入时需按实际环境配置。科学CSV保持原字节，公开代码统一LF，原sourceSHA与公开SHA分别记录。ringfix配方按原字节公开，固定SHA与适配器严格匹配。公开code是紧凑披露布局；执行前须与v9自有依赖恢复到原project相对代码树，完整实验还需另取依赖、权重及有权限数据。
