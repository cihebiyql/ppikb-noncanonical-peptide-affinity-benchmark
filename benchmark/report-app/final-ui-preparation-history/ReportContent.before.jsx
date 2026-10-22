import React from "react";
import { DataComponent, DataTable, EvidenceChart, Filters, ReportSection, RichNarrative,
  Section, useDataApp, useSectionFilters } from "../../data-app-public.jsx";
import "./report.css";

const panelNames={source_peptide_dependency_cold:"来源＋肽依赖冷",target_reference_homology_cold:"参考蛋白同源冷"};
const chemistryNames={synthetic_D_backbone:"非蛋白源／D型／骨架改变",PTM:"PTM残基修饰",synthetic_and_PTM:"两类同时出现",other_NC:"其他非标准残基",standard20_control:"标准20残基对照"};
const categoryShort={synthetic_D_backbone:"非蛋白源／D型／骨架",PTM:"PTM",synthetic_and_PTM:"两类混合",other_NC:"其他非标准"};
const stages={residue_class_start:"残基分类起点",Kd_endpoint:"保留Kd端点",exact_molar_point:"精确可换算点值",SMILES_and_standard20_reference_target_available:"具备分子与蛋白输入",legacy_primary_quarantine:"既有原文质量隔离",existing_entity_representation_conflict:"既有实体表示冲突",endpoint_internal_conflict:"端点字段冲突",concentration_internal_conflict:"浓度字段冲突",inherited_metadata_only_high_risk:"高风险仅元数据记录"};
const subtypeNames={d_stereoisomer:"D构型",n_substituted_or_peptoid:"N取代／peptoid",nonalpha_or_backbone_modified:"非α／骨架改变",nonproteinogenic_named:"明确命名的非蛋白源残基",nonproteinogenic_substituted_aminoacid:"取代型非蛋白源残基",reviewed_nonproteinogenic_residue:"经审阅确认的非蛋白源残基",ptm_phosphorylation:"磷酸化",ptm_methylation:"甲基化",ptm_acylation:"残基酰基化",ptm_sulfation:"硫酸化",ptm_hydroxylation:"羟基化",ptm_glycosylation:"糖基化",ptm_oxidation:"氧化",ptm_lipidation_sidechain:"侧链脂化",residue_sidechain_derivative:"侧链衍生残基",reviewed_residue_sidechain_modification:"经审阅的侧链修饰",terminal_residue_conversion:"末端残基本体转化",nonstandard_author_explicit_unspecified:"作者明确非标准、细类未明",natural_21_22:"天然额外残基注释（另记）"};
const col=(field,label,extra={})=>({field,label,...extra});
const numberCell=value=>value===null||value===undefined?"未分项":Number(value).toLocaleString("zh-CN");

function EvidenceText({id,queryId,rows,value,extra}){
 const heading=value.match(/^#{1,3}\s+(.+)$/m)?.[1]??"数据与方法说明";
 return <ReportSection id={id} title={heading} queryId={queryId} sourceRows={rows} showHeading={false}>
  <RichNarrative id={`${id}:body`} value={value} label="编辑说明" />{extra}
 </ReportSection>;
}

function ComparisonScope(){
 const { snapshot }=useDataApp();
 const scope=useSectionFilters([
  {id:"panel",label:"测试怎样留出",field:"panel_label",defaultValue:"来源＋肽依赖冷",queryIds:["sample_denominators","metrics"]},
  {id:"regime",label:"模型用什么训练",field:"regime_label",defaultValue:"只用非标准肽训练",queryIds:["sample_denominators","metrics"]},
  {id:"chemistry",label:"查看哪类肽",field:"chemistry_label",defaultValue:"all",queryIds:["sample_denominators","metrics"]},
 ],{}, {id:"affinity-evaluation-scope",label:"评价分组"});
 const samples=scope.componentProps("sample_denominators",["panel_label","regime_label","chemistry_label"]);
 const metrics=scope.componentProps("metrics",["method_id","panel_label","regime_label","chemistry_label","evaluation_set_id","metric_id"]);
 return <Section id="evaluation-scope-heading" title="选一个评价范围，看清训练和测试分母" filters={<Filters {...scope.filterProps} />}>
  <RichNarrative id="scope:explain" value={"筛选只影响本节的样本分母和未来成绩。**训练、验证按训练方案取子集；测试保留共同池，再分化学类别报告。** 表中训练数为0，表示该方案设计上未使用这一组。"} label="编辑评价范围说明" />
  <DataComponent id="sample-denominators" title="当前选择下的真实样本数" queryId="sample_denominators" kind="table" {...samples}>
   {samples.displayRows.length ? <DataTable rows={samples.displayRows} searchable={false} compactNumbers={false} label="分组训练、验证、测试记录数" columns={[
    col("panel_label","划分"),col("regime_label","训练方案"),col("chemistry_label","化学组"),col("train_n","训练"),col("validation_n","验证"),col("test_n","测试"),
   ]}/> : <RichNarrative id="sample-denominators:empty" value="当前汇总切片没有单独的分母聚合行。后续成绩表中的n以审阅结果为准；这里保留未知，不填0。" label="编辑分母空态"/>}
  </DataComponent>
  <DataComponent id="metrics-table" title="亲和力成绩" queryId="metrics" kind="table" {...metrics}>
   {metrics.displayRows.length ? <DataTable rows={metrics.displayRows} compactNumbers={false} label="独立复算的评价指标" columns={[
    col("method_id","方法"),col("evaluation_set_id","测试集"),col("panel_label","划分"),col("regime_label","训练方案"),col("chemistry_label","化学组"),col("metric_id","指标"),col("mean","均值"),col("sd","样本标准差"),col("n","样本数"),col("seed_count","实际种子数"),
   ]}/> : <div className="research-empty" role="status">
    <RichNarrative id="metrics:empty" value={"### 统一评测后更新\n\n这里还没有经独立复算、审阅后的真实成绩。训练完成不等于测试完成；缺失成绩保留为空。\n\n未来表结构支持：方法、划分、训练方案、化学类别、测试集、指标、均值、标准差、样本数和种子数。"} label="编辑成绩空态" />
   </div>}
  </DataComponent>
  <RichNarrative id="metrics:interpretation" value={"**10个随机种子是同一份固定数据上的10次训练，不是10份独立数据。** 计划报告MAE、RMSE、Pearson、Spearman和R²，并保留每个种子的结果；常数或样本不足时，按指标定义保留未定义值。"} label="编辑随机种子说明" />
 </Section>;
}

export function ReportContent(){
 const {snapshot,reviewedRows,visible,appTitle,canEdit,mode,setAppTitle}=useDataApp();
 const rows=q=>reviewedRows(q);
 const categories=rows("chemistry_counts");
 const nc=categories.filter(r=>r.category!=="standard20_control");
 const chartRows=nc.map(r=>({...r,shortLabel:categoryShort[r.category]}));
 const methods=rows("methods");
 const sources=rows("evidence");
 const sensitivity=rows("sensitivity_counts").map(r=>({...r,panel_label:panelNames[r.panel],regime_label:r.regime==="NC_only"?"非标准肽测试子集":"标准肽测试子集",excluded:r.test-r.test_sensitivity_rows}));
 const flow=rows("quality_flow").filter(r=>r.stage!=="exact_molar_point"&&r.stage!=="endpoint_internal_conflict").map(r=>({...r,cohort_label:r.cohort==="NC"?"非标准肽":"标准肽",stage_label:stages[r.stage]}));
 const external=rows("external_scope").map(r=>({...r,dataset_label:r.dataset.includes("SH2")?"SH2/ProBound":r.dataset.includes("Kliche")?"Kliche 2023":r.dataset.includes("ProfAff")?"ProfAff（资产候选）":"IgG-Fc 2025（另列补集）",graph_cold:r.declared_graph_cold===null?"未知":r.declared_graph_cold}));
 return <article className="report-content research-report" aria-label="肽蛋白亲和力数据与方法报告">
  <header className="report-hero">
   <h1 data-data-app-title contentEditable={canEdit&&mode==="edit"} suppressContentEditableWarning onBlur={canEdit&&mode==="edit"?e=>setAppTitle(e.currentTarget.textContent.trim()||appTitle):undefined}>{appTitle}</h1>
   <RichNarrative id="research:deck" value={"这次优先研究含非标准残基的肽与蛋白的结合亲和力。先弄清测量是什么、哪些数据进入训练，以及测试真正隔离了什么。"} className="report-deck" label="编辑导语"/>
  </header>

  <EvidenceText id="data-brief" queryId="chemistry_counts" rows={categories} value={"## 这次数据里，什么是主队列，什么是对照？\n\n主队列是 **2,099条非标准残基肽的Kd观测**，标准残基对照有 **7,520条**。总共9,619条测量，对应5,140种分子图；其中非标准队列对应990种分子图。**一条观测不等于一个独立分子。**\n\n当前研究的是亲和力回归：输入肽的完整分子表示和蛋白参考序列，输出pKd。是否结合、结合位点和对接姿态是另外的任务，这一轮没有用人为负例或结构分数替代它们。"}/>
  <ReportSection id="affinity-definition" title="pKd的含义" queryId="chemistry_counts" sourceRows={categories} showHeading={false}>
   <RichNarrative id="affinity-definition:body" value={"### pKd可以怎样理解？\n\nKd是解离常数，描述结合平衡，数值越小通常表示结合越强。为了便于建模，把以摩尔为单位的Kd取负对数，得到 **pKd = −log₁₀(Kd / M)**。pKd不是统计检验的p值。\n\n本轮只用Kd。Ki是抑制常数，IC50是依赖实验条件的半数抑制浓度，它们继续保存在原数据库，各用各的端点。"} label="编辑亲和力解释"/>
  </ReportSection>
  <EvidenceChart id="chemistry-bars" queryId="chemistry_counts" title="2,099条非标准残基观测分成四个互斥组" spec={{type:"horizontalBar",x:"label",y:"rows",valueDecimals:0,stackable:false}} rows={chartRows} sourceRows={nc} height={300}/>
  <DataComponent id="cohort-table" queryId="chemistry_counts" title="四类NC和标准对照的完整数量" kind="table" sourceRows={categories} displayRows={categories}>
   <DataTable rows={categories} searchable={false} compactNumbers={false} label="互斥化学类别记录数" columns={[col("label","类别"),col("rows","测量记录数")]}/>
  </DataComponent>
  <EvidenceText id="chemistry-definition" queryId="chemistry_counts" rows={categories} value={"**非蛋白源／D型／骨架改变**包括标准20种残基之外、D构型或骨架发生变化的已注释残基。**PTM**指磷酸化、甲基化等残基层面修饰；同时具有两轴标记的记录单列为混合组。\n\n末端封端、环化、连接体和实验标签另记。标准残基对照也可能有这些化学处理，所以“标准残基”不等于“完全无修饰”。其他非标准组中包括2条天然额外残基注释，不能把全部NC都称为人工残基。"}/>
  <details className="research-details">
   <summary>进一步查看：残基细类标记，可以重叠</summary>
   <DataComponent id="subtype-table" queryId="subtypes" title="同一条肽可以同时具有多个残基标记，数量不能加总" kind="table" sourceRows={rows("subtypes")} displayRows={rows("subtypes").map(r=>({...r,subtype_label:subtypeNames[r.subtype]??r.subtype}))}>
    <DataTable rows={rows("subtypes").map(r=>({...r,subtype_label:subtypeNames[r.subtype]??r.subtype}))} label="非标准残基重叠标记" compactNumbers={false} columns={[col("subtype_label","残基标记"),col("rows","含该标记的观测")]} />
   </DataComponent>
  </details>

  <EvidenceText id="quality-brief" queryId="quality_flow" rows={rows("quality_flow")} value={"## 清洗改变的是建模视图，原始记录全部保留\n\n原PPIKB的21,845行没有删除。当前只取Kd端点、具备分子与蛋白输入、并通过既有质量flag的记录。非标准Kd从2,120到2,099，主要移出3条输入不足、13条浓度字段冲突、5条高风险仅元数据记录。\n\n移出当前任务的Ki、IC50或身份未解记录仍有各自用途；缺值和未测组合不会被改成“不结合”。43条NC记录还有附加注释未解，继续显式保留。"}/>
  <DataComponent id="filter-flow" queryId="quality_flow" title="每一步保留多少记录" kind="table" sourceRows={rows("quality_flow")} displayRows={flow}>
   <DataTable rows={flow} compactNumbers={false} label="固定顺序质量筛选" columns={[col("cohort_label","队列"),col("stage_label","筛选步骤"),col("excluded_this_stage","本步移出"),col("retained","剩余")]} />
  </DataComponent>
  <details className="research-details">
   <summary>原始21,845行的残基类别去向</summary>
   <DataComponent id="raw-count-table" queryId="raw_counts" title="未进入当前主队列的记录仍保留原档案" kind="table" sourceRows={rows("raw_counts")} displayRows={rows("raw_counts")}>
    <DataTable rows={rows("raw_counts")} searchable={false} label="原始数据库残基审计" compactNumbers={false} columns={[col("residue_class","类别",{renderCell:v=>({noncanonical_explicit:"明确非标准残基",standard20_supported:"标准20残基支持",noncanonical_assay_tag_residue:"仅残基连接实验标签",unresolved:"身份未解"}[v]??v)}),col("rows","记录数")]} />
   </DataComponent>
  </details>

  <EvidenceText id="split-brief" queryId="split_counts" rows={rows("split_counts")} value={"## 两种测试，分别回答两种泛化问题\n\n**来源＋肽依赖冷**：同一研究、同一分子或声明规则下相近的肽放在同一边，考察模型能否迁移到新的来源／肽背景；相近蛋白仍可在两边出现。\n\n**参考蛋白同源冷**：参考序列按声明的相似度与包含关系分组，并合并相同模型前缀，考察新参考靶标上的预测；研究来源和相近肽仍可在两边出现。\n\n先共同划分，再分别用非标准或标准肽训练。两个面板各自隔离一个方向，不能统称双冷；双冷图最大组件占93.02%，本轮只作诊断。"}/>
  <ComparisonScope/>

  <EvidenceText id="discordance-brief" queryId="sensitivity_counts" rows={rows("sensitivity_counts")} value={"## 608条图—注释冲突，怎样处理？\n\n60种相同含立体分子图，既出现NC注释也出现标准注释，涉及357条NC和251条标准记录。当前无法决定哪一侧注释正确，因此都保留并标记。\n\n先保存同一批测试预测，再另报排除冲突行的敏感性结果；训练与验证仍含标记记录。这是对测试汇总分母的检查，不是重新清洗后重训。"}/>
  <DataComponent id="discordance-table" queryId="sensitivity_counts" title="同一批预测，冲突排除前后的测试分母" kind="table" sourceRows={rows("sensitivity_counts")} displayRows={sensitivity}>
   <DataTable rows={sensitivity} searchable={false} compactNumbers={false} label="注释冲突敏感性样本数" columns={[col("panel_label","面板"),col("regime_label","子集"),col("test","原测试"),col("excluded","标记移出"),col("test_sensitivity_rows","敏感性测试")]}/>
  </DataComponent>

  <EvidenceText id="target-brief" queryId="prefix_counts" rows={rows("prefix_counts")} value={"## 输入的是蛋白参考序列，长度限制也会影响模型\n\n当前实际实验构建体序列认证数为0，模型使用数据库参考序列。MGraphDTA保留作者前1,200个残基，其余四个架构保留前1,000个残基。肽分子没有原子截断。\n\n五个图模型都不编码原子手性，D/L同拓扑分子可能得到相同有效输入。分组时合并去立体图有助于控制泄漏，但不会给模型增加手性辨识能力。"}/>
  <DataComponent id="prefix-table" queryId="prefix_counts" title="有多少观测会受到蛋白前缀截断" kind="table" sourceRows={rows("prefix_counts")} displayRows={rows("prefix_counts").map(r=>({...r,cohort_label:r.cohort==="NC"?"非标准肽":"标准对照"}))}>
   <DataTable rows={rows("prefix_counts").map(r=>({...r,cohort_label:r.cohort==="NC"?"非标准肽":"标准对照"}))} searchable={false} compactNumbers={false} label="蛋白前缀覆盖" columns={[col("protein_prefix_limit","前缀上限aa"),col("cohort_label","队列"),col("records","观测总数"),col("truncated_records","会截断的观测"),col("truncated_reference_sequences","会截断的参考序列")]}/>
  </DataComponent>

  <EvidenceText id="method-brief" queryId="methods" rows={methods} value={"## 五个经典／近期公开架构，在同一数据上从头训练\n\nGraphDTA、MGraphDTA、DGDTA、DeepNC和GS-DTA来自五篇不同论文，原任务是小分子—蛋白亲和力预测。这一轮保留作者架构及披露修复，迁移到共同PPIKB数据；不是重复原论文数据和主表分母。\n\n当前满足五个前人架构比较。严格回溯近三年，五名单只有GS-DTA 2025在窗口内；它们不能称为五篇近三年肽专属方法。"}/>
  <DataComponent id="model-table" queryId="methods" title="五篇论文、作者代码与必要修复" kind="table" sourceRows={methods} displayRows={methods}>
   <DataTable rows={methods} searchable={false} label="五个公开架构" columns={[col("method","方法"),col("year","论文年"),col("protein_prefix_limit","蛋白前缀"),col("doi","论文",{renderCell:(v,r)=><a href={r.paper_url} target="_blank" rel="noreferrer">{v}</a>}),col("adapter_repairs_and_differences","适配与修复")]} />
  </DataComponent>
  <ReportSection id="model-provenance" title="代码版本" queryId="methods" sourceRows={methods} showHeading={false}>
   <RichNarrative id="model-provenance:body" value={"### 代码身份可以追溯\n\n作者选定源码、commit、SHA和修复diff均保留。DGDTA修复了维度与LSTM布局错误，按“修正版作者实现”解释；其余方法也保留作者可执行行为和披露差异。"} label="编辑方法版本说明" />
   <ul className="research-code-links" data-reviewed-rows>{methods.map(m=><li key={m.method}><a href={`${m.repository}/tree/${m.commit}`} target="_blank" rel="noreferrer">{m.method} · {m.commit.slice(0,12)}</a></li>)}</ul>
  </ReportSection>
  <DataComponent id="rf-reference" queryId="rf_reference" title="另计一个传统参考：随机森林" kind="table" sourceRows={rows("rf_reference")} displayRows={rows("rf_reference")}>
   <DataTable rows={rows("rf_reference")} searchable={false} label="随机森林冻结配置" compactNumbers={false} columns={[col("method","方法"),col("feature_dimension","特征维度"),col("n_estimators","树数"),col("min_leaf_candidates","叶最少样本候选"),col("selected_units","完成单元"),col("candidate_fits","完成候选fit")]} />
  </DataComponent>
  <ReportSection id="rf-method-brief" title="随机森林如何表示肽和蛋白" queryId="rf_reference" sourceRows={rows("rf_reference")} showHeading={false}>
   <RichNarrative id="rf-method-brief:body" value={"RF把完整肽分子转成**2,048位Morgan指纹**（半径2，保留已给出的手性与键型）；把蛋白前1,000个残基转成20个单残基比例、400个相邻二残基比例和1个有效长度，共**2,469维固定特征**。未指派的构型保持未指派，不做可学习预处理。\n\n使用200棵树、sqrt特征抽样，比较叶最少样本数2或5，依据同训练方案的验证MAE选择；单线程、种子0–9。40个选择单元和80个候选完成属于训练状态，测试性能仍等待统一评测。"} label="编辑RF方法说明"/>
  </ReportSection>
  <ReportSection id="training-plan" title="共同训练和选择预算" queryId="training_plan" sourceRows={rows("training_plan")} showHeading={false}>
   <RichNarrative id="training-budget:body" value={"五个神经网络设计为5方法 × 2面板 × 2训练方案 × 10种子，共200个选择单元、400个候选fit。每单元只比较预声明的两个学习率，最多20轮、patience 5，依据验证MAE选优。标准队列比NC更大，差异还受到训练样本量和靶标分布影响。随机森林参考另计，不算第六篇神经网络论文。"} label="编辑共同训练预算"/>
  </ReportSection>

  <EvidenceText id="external-brief" queryId="external_scope" rows={rows("external_scope")} value={"## 外部验证有两份，要分开读\n\n**原75条全部是PTM**：SH2/ProBound 45条、Kliche 30条；其中67条主用，8条构建体／位点条件存在歧义，仅作敏感性。75条都通过来源和声明分子图规则下的全PPIKB审查，但只有2条同时满足参考靶标冷。\n\n**另13条独立补充诊断**含8条非蛋白源／D型／骨架改变和5条标准对照，单独报告。它们来自一项研究，使用449aa重链的Fc侧参考视图，均与主库参考靶标有关联；不是13个独立体系或家族冷验证。\n\n这些都是回顾性外测。来源冷、声明图表示冷、靶标冷和实际构建体认证是不同层次，结果必须保留这些边界。"}/>
  <DataComponent id="external-table" queryId="external_scope" title="外部数据接受范围与当前输入状态" kind="table" sourceRows={rows("external_scope")} displayRows={external}>
   <DataTable rows={external} searchable={false} compactNumbers={false} label="外部验证独立性范围" columns={[col("dataset_label","资源"),col("records","记录"),col("primary","原主用"),col("sensitivity","原敏感性"),col("separate_supplement","另列补诊断"),col("source_cold","来源冷"),col("graph_cold","声明图冷"),col("target_reference_cold","参考靶标冷")]} />
  </DataComponent>

  <DataComponent id="phase-snapshot" queryId="phase_snapshot" title="协调者准备状态快照 · 非实时" kind="table" sourceRows={rows("phase_snapshot")} displayRows={rows("phase_snapshot")}>
   <RichNarrative id="phase-snapshot:note" value={"本轮指令提供的2026-10-22状态：NC神经网络100个选择完成，标准100个仍在推进；当时总计104个完成，RF40完成选择，真实测试0。这里只作静态背景，不随训练实时变化，也不代表成绩。"} label="编辑状态快照说明"/>
  </DataComponent>

  <EvidenceText id="evidence-brief" queryId="evidence" rows={sources} value={"## 需要核对来源时，从这28条证据进入\n\n每个图表和表格都保留真实聚合行、定义、来源文件与SHA，可使用共享的查看来源功能。应用仅嵌入已审阅聚合与公开方法资料，没有原始金标、逐样本预测或模型权重。更详细的中文方法说明与CSV由主报告另行交付。"}/>
  <DataComponent id="evidence-table" queryId="evidence" title="来源与定义索引" kind="table" sourceRows={sources} displayRows={sources}>
   <DataTable rows={sources} label="28条已核验证据" columns={[col("evidence_id","ID"),col("claim","支持内容"),col("source_name","来源文件"),col("source_sha256","SHA256",{renderCell:v=><abbr title={v}>{v.slice(0,12)}</abbr>})]} />
  </DataComponent>
 </article>;
}
