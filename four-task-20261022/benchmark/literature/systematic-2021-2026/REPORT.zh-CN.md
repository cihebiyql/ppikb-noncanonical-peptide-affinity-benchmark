# 肽—蛋白相互作用近五年前作：检索目录与公开资源核查

检索窗口：2021-10-23—2026-10-23；近三年从2023-10-23起。生成时间：2026-10-23T06:23:03.177979+00:00。

本轮整理80项方法、数据库与结构研究条目；其中51项归入直接肽—蛋白预测及其基准相关类别，43项处于近三年窗口。这些数量包含明确标为预印本、植物任务或仅元数据核实的条目，不能当成51个已经可完整复现的模型。原八方法执行范围保持不变，本轮没有训练、调参或模型前向。

## 主要结论

1. 用户对旧基准的质疑成立：GraphDTA、MGraphDTA、DGDTA、DeepNC、GS-DTA属于DTA迁移对照。直接肽—蛋白相关方法近三年已有PepInter、PepBAN、UMPPI、SaMCL、HGT-PepPI、VITAL、PepLM-GNN、PepPAP和多种位点预测器。模型选择应按实际任务分栏。
2. 定量预测必须核端点。VITAL的BSU来自ASM计算，是与结合强度有关的代理量，当前公开代码不支持直接把它写成pKd回归器。Peptriever是检索/排序。PepPAP明确做定量亲和力，但作者公开链接当前404。DeepPpIScore评价亲和力评分，原训练不使用亲和力标签。
3. NC能力最值得继续核查的是PepBAN论文的原子图分支；公开默认ESM读取路径与该分支的完整交付尚未对齐。SaMCL、HGT-PepPI、UMPPI和VITAL已查到的默认输入以标准序列/语言模型特征为主；X或未知字符回退不代表编码了非天然残基。SH2/ProBound的磷酸酪氨酸是明确PTM情境，不能扩大到任意NC化学空间。
4. 新下载来源不能自动成为独立外测。HGT-PepPI测试文件与当前PepInter存在数百个完全相同序列对；PepXPro显式合并PPIKB/PEPBI/PDBbind；PEPBI329行只有147个独特序列对，存在温度/晶体copy等依赖。
5. VITAL公开索引有4个正例ID跨训练/测试重复。当前接触64个PDB中37个出现在其训练正例PDB集合；这是PDB级暴露证据，尚非逐链污染定论。完整索引、四个重复ID和来源SHA均已保存。

## 检索、筛选与范围

OpenAlex三条主字段查询分别取得654/654、1280/1280、255/255条，亲和力67/67、突变19/19条；另有命名种子查询、PubMed与引文补检。PubMed458个ID全部有账：457篇Article及1篇无关BookArticle。CAMP、PepCNN、PepNN、PepBCL、PepCA、SWING等前向引文按记录的索引命中量取全；531个去重后向OpenAlex引文ID中取得172条窗口内记录。
原始查询共形成7167条记录出现次数，按DOI优先、否则OpenAlexID/PMID去重得到4147条。80项进入人工证据目录，103项作为综述背景；3789项经确定性元数据规则排除于本轮直接任务焦点，175项保留待详细审查。排除规则与人工核实深度均逐行标明，元数据规则筛选不等于通读全文。
原始宽查询部分返回401，失败响应保留；随后合法公共小分页/字段查询已取全相应命中。未创建API账户，也未绕过权限、付费或验证码。检索轮次新增记录和新增目录DOI见search-round-additions.json。**本轮未证明最后一轮新增相关方法为零，不宣称全球文献穷尽。** 多索引覆盖、词法差异、索引延迟和仍待详细审查记录限制了“全部”表述；这里交付的是可复查的有界系统目录。

## 原八项身份与任务定位

|方法|定位|时间边界与说明|
|---|---|---|
|GraphDTA|DTA控制|2020在线/2021印刷，均早于本窗口；保留已授权对照|
|MGraphDTA、DeepNC|DTA控制|2022，非直接PepPI原作|
|DGDTA|DTA控制|2023-09，早于近三年起点；DGDTA-CL只是内部别名，原文使用MSE，没有缺失的contrastive预训练要求|
|GS-DTA|DTA控制|2025，仍是DTA架构迁移|
|PepInter|直接PepPI|原生分类/混合亲和力；冻结表征加回归头不是整篇完整微调复现|
|SWING|广义相互作用，含PepPI|分类和扰动任务；不能把本文或本轮适配的排序/分类统一改称pKd|
|UniAIR|免疫识别一般PPI效应|HER2实际为Fab—蛋白任务，RDE专家与完整四专家MoFPE分层验收|

## 近三年直接方法目录

A=绝对亲和力；E=改动效应；B=是否相互作用；S=接触/位点。proxy、ranking、case、not_confirmed按字面限制；有attention不等于有接触金标准。日期优先Crossref在线日期，否则显示带来源的索引/印刷日期；年/月精度不补造日。完整条目与所有来源字段在curated-catalog.csv/json。

|方法|记录日期|A|E|B|S|化学输入/证据|
|---|---|---|---|---|---|---|
|[PepInter](https://doi.org/10.1038/s42004-026-02168-3)|2026-08-20|native_mixed_endpoint|adaptation_only|native|not_native_gold|sequence_blind_to_chemistry|
|[VITAL](https://doi.org/10.1038/s42256-026-01291-z)|2026-08-19|proxy_BSU|not_native|native|ASM_interface|canonical_sequence_only_demonstrated|
|[GeoPep](https://doi.org/10.1021/acs.jcim.6c00187)|2026-06-29|no|no|no|protein_side|canonical_protein_ESM3_geometry|
|[ConGA_PepPI](https://doi.org/10.48550/arxiv.2604.18467)|2026-04-20|not_confirmed|no|prediction_component|not_confirmed|input_schema_unknown|
|[SaMCL](https://doi.org/10.1093/bib/bbag178)|2026-04-19|no|no|native|both_sides|canonical_sequence_structure_tokens|
|[PepLM-GNN](https://doi.org/10.1371/journal.pcbi.1014084)|2026-03-24|no|no|native|no_native_head|canonical_sequence_ProtT5_graph|
|[CliPepPI](https://doi.org/10.64898/2026.03.18.712595)|2026-03-20|specificity_score_schema_pending|no|domain_specificity|not_confirmed|input_schema_unknown|
|[HGT-PepPI](https://doi.org/10.1021/acs.jcim.5c03139)|2026-03-17|no|case_scan_only|native|no_native_supervised_head|canonical_sequence_X_ambiguous|
|[DLSPPI](https://doi.org/10.1109/ncc68160.2026.11479113)|2026-02-26|not_confirmed|no|native|not_confirmed|backbone_structure_GMM_features|
|[MAGAN_PP](https://doi.org/10.1109/iementech202669403.2026.11434268)|2026-02-06|not_confirmed|not_confirmed|reported_binary|not_confirmed|3D_graph_and_annotation_text|
|[MGAPep](https://doi.org/10.1109/jbhi.2026.3690953)|2026|not_confirmed|no|not_confirmed|protein_side|multimodal_geometry_input_schema_unknown|
|[PocketStruct](https://doi.org/10.1109/tcbbio.2025.3648459)|2025-12-25|not_confirmed|no|native|not_confirmed|protein_pocket_structure_and_sequence|
|[PepGFD](https://doi.org/10.1109/bibm66473.2025.11356557)|2025-12-15|no|no|no|protein_side|protein_PLM_structure_domain|
|[PepENS](https://doi.org/10.1093/nargab/lqaf137)|2025-10-22|no|no|no|protein_side|canonical_protein_features|
|[SH2_ProBound](https://doi.org/10.1002/pro.70317)|2025-10-14|relative_free_energy_calibrated_subset|conditional_variant_effect|domain_specificity|no|explicit_phosphotyrosine_PTM_fixed_context|
|[LM_multiscale_site](https://doi.org/10.1016/j.patcog.2025.112487)|2025-09-24|not_confirmed|no|not_confirmed|title_only_site|input_schema_unknown|
|[PepBAN](https://doi.org/10.1021/acs.jcim.5c01713)|2025-08-25|no|no|native|attention_interpretation_only|paper_NC_cyclic_atom_graph_public_default_ESM_ID|
|[SWING](https://doi.org/10.1038/s41592-025-02723-1)|2025-07-28|adaptation_only|perturbation_task_context_dependent|native|not_native_gold|sequence_blind_to_chemistry|
|[MultiRepPI](https://doi.org/10.1186/s12870-025-06878-z)|2025-07-19|no|no|native_plant|not_confirmed|canonical_plant_multimodal|
|[Generative_sampling_ensemble_site](https://doi.org/10.1016/j.asoc.2025.113603)|2025-07-15|not_confirmed|no|not_confirmed|title_only_site|input_schema_unknown|
|[Physics_effect_benchmark](https://doi.org/10.1002/jcc.70160)|2025-06-26|experimental_1to1000nM|single_residue_specificity|no|no|canonical_peptide_structure|
|[IIDL-PepPI](https://doi.org/10.1109/tnnls.2025.3540291)|2025-03-18|case_analysis_not_calibrated|no|native|reported_sites|canonical_sequence_PLM|
|[UMPPI](https://doi.org/10.1021/acs.jcim.4c02365)|2025-03-13|no|no|native|both_sides|canonical_sequence_plus_dense_features|
|[CPPIF](https://doi.org/10.1109/jbhi.2025.3539313)|2025-02-06|no|no|native|both_sides|canonical_sequence_features|
|[MMPepPro](https://doi.org/10.1109/jbhi.2025.3607370)|2025|not_confirmed|no|native|not_confirmed|canonical_multimodal|
|[DPPBP](https://doi.org/10.65286/icic.v21i2.56686)|2025|no|no|no|protein_side|canonical_protein_sequence|
|[PepGPL](https://doi.org/10.1145/3698587.3701348)|2024-12-16|no|no|native|both_sides|canonical_sequence_graph|
|[PepPCR](https://doi.org/10.1109/bibm62325.2024.10821766)|2024-12-03|no|no|no|protein_side|canonical_protein_ProtT5|
|[TPepPro](https://doi.org/10.1093/bioinformatics/btae708)|2024-11-25|no|no|native|not_confirmed|canonical_sequence_structural_features|
|[PLM_affinity_ranking](https://doi.org/10.1101/2024.11.14.623613)|2024-11-15|IC50_ranking_not_Kd|no|ranking_only|no|canonical_sequence_PLM|
|[PepCA](https://doi.org/10.1016/j.isci.2024.110850)|2024-08-30|no|no|no|protein_side_pair_conditioned|canonical_sequence_ESM|
|[E2EPep](https://doi.org/10.1016/j.ab.2024.115637)|2024-08-08|no|no|no|protein_side|canonical_protein_PLM|
|[PepPAP](https://doi.org/10.1016/j.ijbiomac.2024.133811)|2024-07-10|native_endpoint_audit_needed|no_native_delta|secondary_binary|not_confirmed|canonical_sequence_features|
|[Survivin_composition](https://doi.org/10.1088/2632-2153/ad5784)|2024-06-28|not_confirmed|no|native_single_target|no|sequence_composition|
|[PepPFN](https://doi.org/10.1109/cai59869.2024.00195)|2024-06-25|no|no|no|protein_side|canonical_protein_PLM|
|[GAPS](https://doi.org/10.1093/bib/bbae297)|2024-06-20|no|no|no|protein_side|protein_structure_cyclic_tests_not_generic_NC_support|
|[DP-site](https://doi.org/10.1016/j.ymeth.2024.06.001)|2024-06-12|no|no|no|protein_side|canonical_protein_features|
|[DeepPepPI](https://doi.org/10.1016/j.eswa.2024.124168)|2024-05-14|no|no|native_plant|not_confirmed|canonical_plant_sequence|
|[ITN](https://doi.org/10.1016/j.xcrp.2024.101980)|2024-05-10|no|no|native_specificity|residue_level_representation|template_structures_canonical|
|[Peptriever](https://doi.org/10.1093/bioinformatics/btae303)|2024-05-06|retrieval_score_not_pKd|no|retrieval_binary|no|canonical_sequence|
|[ProtTrans_MW_CNN](https://doi.org/10.1016/j.jmgm.2024.108777)|2024-04-17|no|no|no|protein_side|canonical_protein_PLM|
|[PepGB_diPepGB](https://doi.org/10.48550/arxiv.2401.14665)|2024-01-26|relative_strength_not_pKd|directed_relative_ranking|native|no_native_gold|canonical_sequence_graph|
|[PepCNN](https://doi.org/10.1038/s41598-023-47624-5)|2023-11-28|no|no|no|protein_side|canonical_protein_features|

近五年早期还包括PepNN、PepBCL、GraphPPepIS/SeqPPepIS、usPpIA、PPI-Affinity、BioGPS-LDA、SPPPred和AlphaFold特异性微调等。CAMP发表于2021-09-15，作为窗口外基础工作保留。GraphPep、扩散对接、PepPCBench等放入结构/评分类别；它们的pose质量不能替代实验亲和力。

## 四来源可以比较什么

|当前来源|已冻结任务证据|与新方法比较时的条件|
|---|---|---|
|PPIKB|9116pKd；2289元数据silver配对；64实验复合物8625观测残基标签|分类缺独立阴性；NC/PTM须保持真实化学身份；5Å接触定义须与原模型6Å等标签重构或单独报告|
|UniAIR/HER2|419作者DDG与同批Kd；严格local293/63/63|Fab227aa，不是短肽；authorDDG单位/符号未认证；同来源辅助pKd不是独立验证|
|PepAffDB/PepInter|3620混合pAffinity；17054分类原记录|Kd/Ki/IC50不合称pKd；阴性部分由作者构造；没有当前冻结的配对效应/接触标签|
|ProfAff/PDZ|162directFP；默认16806HU情境/16772输入；42PTM配对|HU和FP分轨；42配对共享162测量；删失42432与未测5067不能当阴性；已用来源不再称blind外测|

逐方法×来源的原生/条件适配/不支持任务见four-source-method-routing.csv；它描述任务可接受性，未把新模型登记为已复现。数据数量引用现有独立验收快照，副本及SHA见current-four-source-task-matrix.provenance.json。

## 公开资源实物与外测候选

|资源|本轮实际获取/清点|外测判断|
|---|---|---|
|VITAL|固定commit静态代码、9701结构索引、17806/1600划分；核心权重为LFS指针，未下载|无原始Kd列；4正例ID跨split；须链/同源/来源审计后重划分|
|SaMCL|固定commit33个轻量文件；例表含双方sequence、com_seq、site label、interaction|结构token与标准序列；完整原始标签/结构资源尚未下载审计，不能报外测有效量|
|HGT-PepPI|作者zip8.82MB SHA冻结；训练17244，Test1440=2880，Test167=510，Test251=498实际pair记录|文件名不是样本数；当前PepInter完全相同pair分别4838/673/35/22，不独立|
|PepBAN|固定commit默认代码与BioGRID/STRING/CAMP/HSM/cyclic小表；cyclic有SMILES/labels|可继续审NC二元任务；真实NC/端帽/PTM及目标身份、原始证据仍需逐条核|
|UMPPI|固定commit7个代码/README文件；完整数据指向作者Drive|待下原始多任务标签再审计；不能从README报告数推称已可用|
|PEPBI|官方Dryad SHA匹配工作簿329行/32group/181complex名/147序列对；329正Kd；4蛋白长度冲突|潜在标准肽ITC对照，非NC核心；原文条件、构建体、人源与重复仍需确认|
|PepXPro|固定commit37文件；70sample含22PPIKB、1PEPBI，47未标ext_source|合并数据，不作为新增独立外测；可用其来源追溯代码，不把聚合再计新证据|
|DeepPpIScore|固定commit17文件；445表均标Kd，438肽序列，缺靶序列列；源NC/cyclic两标志均445个1|PDBbind衍生，ACE/侧链环不能直接解释为NC核心/环肽；补构建体、化学身份和原测量查重后再定|
|PepPAP|出版社给作者URL，但当前GitHub API404，有失败收据|不能称仓库/数据成功下载；保留亲和力方法候选，等待公开资产恢复或合法补充|

本轮外测候选优先级：先查PEPBI的人源、同条件独立ITC系列与SH2/ProBound直接亲和力验证子集；NC方向优先核PepBAN cyclic原化学实体及其目标标签。HGT与VITAL适合任务对照或经过重划分的共同数据评价，不能默认独立。没有新增候选在本轮被自动合并进训练集或执行外测。
PepLand及其表征路线不采纳。2026affinity-shift预印本确实评测PepLand，但其数据由PPIKB及2025modified-peptide研究汇集；是否数据本身为PepLand衍生仍待谱系审计，不能凭使用该编码器就反向捏造数据来源。

## 复查入口

- protocol.json、queries/、raw/、request-log.jsonl：范围、查询式、命中量、失败与原响应。
- curated-catalog.csv/json、curated-registry.psv、curated-metadata/、seeds/：80条目录、原始任务判断、出版日期/来源。
- screening-decisions.csv/json、pending-detailed-review.json：4147条逐记录筛选和待审清单。
- static-code-evidence-anchors.json、repositories/*stage-manifest*.json：实际源码行、固定commit和逐文件SHA。
- dataset-schema-and-overlap-audit.json、datasets/：实际行数、端点、重复、当前来源交集与官方摘要SHA核验。
- VALIDATION.json、DELIVERY-MANIFEST.json：自动一致性检查和最终实物清单。


## 用户已有参考清单补差

已全文对照用户原txt：62条可见文献/资源表格行涵盖56个名称键，加正文DeepPepPI/TPepPro两项，共58个可见名称键。原自报34资源目录对应xlsx未随附件提供，不能认证其完整字段。具体原文SHA、逐行对照、窗外分栏及错误链接纠正见provided-reference-reconciliation.zh-CN.md和provided-reference-checklist.csv。

额外核实23项Crossref身份元数据及3项后续精确身份，包含Case2024、APPRAISE、SIMBA、ASHI、ProBound、RDE、DDAffinity、CATH-ddG、Graphinity等，不把用户已有线索写成首次发现。ASHI v2小原始表已官方MD5/SHA核验，12153编码行/4051独特肽，DMS3040独特肽/10source分组/9bait；原始表主要计数和z-score，没有预聚合SIMBA-score/Kd列，不注册新监督视图或独立外测。

PepBAN cyclic经字面.pdb后缀ID对齐后，740/186行目标训练/测试全部解析；test有1个序列对与当前PepAff重合，化学等价和人源范围尚未核。HGT作者zip包含一份未加载的9,222,786字节model.pth，未单独解出；本轮所有模型前向为0。
