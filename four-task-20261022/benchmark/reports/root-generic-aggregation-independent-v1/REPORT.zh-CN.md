# 通用基准汇总独立验收

修订后的通用基准汇总通过验收：1,050个正式选中训练条件、2,100次候选拟合、105个模型—视图组合，每组合实际种子0–9，合计1,350行指标汇总。数值与原已交付源表和逐种子表一致，固定外测、共同子集和原生论文方法没有充作通用模型训练。

## 分母与来源

|来源run|模型—视图组合|选中训练条件|候选拟合收据|汇总指标行|
|---|---:|---:|---:|---:|
|cpu-v2|10|100|200|120|
|cpu-additional-v1|10|100|200|120|
|cpu-contact-v1|5|50|100|60|
|cpu-effect-v1|10|100|200|140|
|cpu-contact64-v1|5|50|100|60|
|cpu-molecular-v1|15|150|300|190|
|her2-strict-local-baselines-v1|10|100|200|160|
|plm-simple-v1|15|150|300|190|
|plm-cohort-manual-controls-v1|15|150|300|190|
|plm-classification-contact-v1|10|100|200|120|

原CPU六个训练run合计550/1100；HER2严格局部100/200、冻结ESM亲和力/效应150/300、同输入手工对照150/300、冻结ESM分类/接触100/200。上述分母是训练条件与候选拟合次数；同数据不同划分、表示及随机种子共享观测，不能解释为新增生物样本。
105组合来自21个run—view条件与五类通用模型，包含15个不同view_id。1,350行同时包含验证/测试和部分未定义相关性等占位指标，不能当作1,350个模型。候选拟合数量以已验收收据核对；本次独立重算的是既有逐种子指标的均值、样本SD、有效种子数、种子数与n。

## 独立数值核对

- 对1,350行逐源核对10,800个身份/任务/来源字段和6,750个数值字段。
- 从原逐种子CSV独立重新聚合，再核对6,750个mean/SD/valid_seed_count/seed_count/n字段。
- 共24,300项原表核对，错误0；每个模型—视图—指标—划分实际覆盖种子0–9，n一致。
- 未读取GB模型/表示缓存，未运行fit、predict或PLM forward；GPU使用0。

## 发现、修订与增补验收

修订前汇总的1,350行中，1,190行endpoint为空；原160行非空端点没有冲突。原因是部分原mean-SD表本身没有endpoint列，原builder直接汇入。PPIKB pKd、PepAff混合端点及作者未校准DDG因此需要补充声明，不能仅凭task=affinity/effect比较量纲。
独立审计从原任务合同、HER2合同绑定manifest和冻结coverage生成15个view的端点映射；ESM五个派生视图另带父view和父manifest证据，未按指标数值猜端点。root随后仅补充端点声明及两列provenance。
增补复核确认：恰好填补1,190个原空端点；原160个端点保留；其余17,550个原字段单元逐字一致；新增仅endpoint_declaration_ref和endpoint_declaration_sha256。24份唯一合同、coverage或父manifest逐SHA通过，所有原指标及收据输入SHA保持不变。原发现审计保持原样，修订另行封存。

修订builder SHA：`2118f04000a1132b7eac01cad2083c7f1764c2a245aa31715b9cec45c0aa6d0c`。修订汇总CSV SHA：`60f29ff73f66845f580d4f13e0d9abc88717d30192b68c7765f6afadf7e1b447`。

## 非训练结果分层

|类型|既有应用数量|新增训练|通用训练表中|
|---|---:|---:|---|
|原CPU固定外测|250|0|未纳入|
|原CPU共同测试子集|100|0|未纳入|
|ProfAff HU条件固定外测|100|0|未纳入|
|PEPBI 27条候选条件外测|100|0|未纳入|

原CPU收据中fixed_external/common条目也使用selected_results字段；只有category=training六项进入550训练分母。HU100和PEPBI100均为应用既有权重，原生DTA、SWING、PepInter组件和UniAIR RDE的状态、指标独立登记，未混入该1,050训练条件表。PEPBI独特候选仍27条、已认证独立外测仍0条。
不同测试子集的固定预测也没有变成额外模型训练；表格汇总不使不同端点、训练覆盖或测试分母自动可比。

## 可复核入口

- original-snapshot/：修订前builder、汇总CSV和STATUS原件及SHA。
- original-snapshot-independent-audit.json：收据分母、逐源字段及逐种子重聚合核验。
- view-endpoint-map.json/.csv：15视图的端点/任务和合同、coverage、父view证据。
- repaired-snapshot/及endpoint-repair-supplement.json：root实际修订后的独立复核。
- root-builder-endpoint-repair.diff：修订前后builder差异，便于人工查看。
- DELIVERY-RECEIPT.json和local-audit-index.json：最终验收与本地审计产物SHA。

本验收针对该时间点的通用汇总完整性与分层，不改变原论文复现的完成状态，也不增加任何训练、外测或生物记录。
