"""Compile frozen metadata only. Never opens gold, predictions or checkpoints."""
from pathlib import Path
import json,csv,hashlib,datetime
from collections import Counter
P=Path(__file__).resolve().parent;ROOT=P.parent;F=ROOT/'data-protocol/frozen-v1'
OPEN=[]
def guard(p):
 p=Path(p);low=str(p).lower().replace('\\','/')
 if any(x in low for x in ['/gold/','posttraining-gold','/labels.jsonl','sealed-test-label','prediction','/best.pt','formal-runs-gpu-v4','encoded-cache-v3']):raise ValueError('Forbidden report input '+str(p))
 return p
def content(p):
 p=guard(p);raw=p.read_bytes();OPEN.append({'path':str(p),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'access':'frozen_metadata_or_label_free_input'})
 return raw.decode('utf-8-sig')
def read(p):return json.loads(content(p))
def lines(p):return [json.loads(x) for x in content(p).splitlines() if x.strip()]
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def csvout(name,rs):
 keys=list(dict.fromkeys(k for r in rs for k in r))
 with (P/name).open('w',encoding='utf-8-sig',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=keys);writer.writeheader()
  for r in rs:writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()})
def mdtable(rs,columns):
 def cell(v):return '未知' if v is None else str(v).replace('|','／').replace('\n','；')
 return '| '+' | '.join(label for _,label in columns)+' |\n| '+' | '.join('---' for _ in columns)+' |\n'+'\n'.join('| '+' | '.join(cell(r.get(k,'')) for k,_ in columns)+' |' for r in rs)
def main():
 P.mkdir(exist_ok=True)
 manifest=read(F/'manifest.json');protocol=read(F/'protocol.json');leak=read(F/'independent-leakage-verification.json');gran=read(F/'granularity-audit.json');feas=read(F/'split-feasibility-report.json')
 verification=read(ROOT/'data-protocol/frozen-v1-verification.json');models=read(ROOT/'model-audit/model-routes.json')['models'];registered=read(ROOT/'control/registered-paper-map.json');gs=read(ROOT/'model-audit/replacement-gs-dta/candidate-audit.json');revision=read(ROOT/'administration/protocol-revision-v3.json')
 assert next(r['sha256'] for r in OPEN if Path(r['path'])==F/'manifest.json')==verification['manifest_sha256']
 ext=read(ROOT/'external-validation/acceptance-manifest.json');supp=read(ROOT/'external-validation/scoring-supplement13-v1/root-accepted-manifest.json');suppcandidate=read(ROOT/'external-validation/IgG-Fc-supplementary-audit-v1/postfreeze-supplement-candidate-manifest.json');exttarget=read(F/'external-target-overlap-summary.json')
 extaliases=read(ROOT/'external-validation/training-blacklist.json')['external_original_study_aliases'];igglead=read(ROOT/'external-validation/new-resource-leads/IgG-Fc-2025-lead-summary.json')
 primarydates=read(ROOT/'model-audit/papers/primary-method-verification-sidecar-v3.json')
 input_manifest=read(F/'input-manifest.json');inputs=lines(F/'inputs.jsonl')
 auditpath=next(Path(k) for k in input_manifest['source_files'] if k.endswith('all-21845-status.jsonl'))
 audittext=content(auditpath);assert hashlib.sha256(audittext.encode('utf-8')).hexdigest()==input_manifest['source_files'][str(auditpath)]
 audits=[json.loads(x) for x in audittext.splitlines() if x];byid={r['record_id']:r for r in audits}
 rawclasses=[{'residue_class':k,'rows':v} for k,v in sorted(Counter(r['residue_class'] for r in audits).items())]
 rawendpoints=[{'endpoint':k,'rows':v,'definition':'frozen parsed endpoint field; not unreviewed original structured-column count'} for k,v in sorted(Counter(r['endpoint'] for r in audits).items())]
 category_zh={'synthetic_D_backbone':'非蛋白源／D型／骨架改变（无PTM主标记）','PTM':'PTM（无前述非天然主标记）','synthetic_and_PTM':'非天然主轴与PTM混合','other_NC':'其他已注释非标准残基','standard20_control':'标准20残基对照'}
 categories=[{'category':k,'category_zh':category_zh[k],'rows':v,'kind':'mutually_exclusive'} for k,v in protocol['chemistry_strata_mutually_exclusive'].items()]
 selected=[byid[r['record_id']] for r in inputs];nc=[r for r in selected if r['NC_core']]
 subtypes=[{'subtype':k,'rows':v,'kind':'overlapping_annotation_flag_not_additive'} for k,v in sorted(Counter(s for r in nc for s in r['noncanonical_subtypes']).items())]
 axis=[]
 for name,rs in [('NC',nc),('standard20_control',[r for r in selected if not r['NC_core']])]:
  for flag in ['terminal_n_nonfree','terminal_c_nonfree','terminal_n_unknown','terminal_c_unknown','cyclic_topology','assay_tag_present','linker_present']:
   axis.append({'cohort':name,'independent_axis':flag,'rows':sum(bool(r[flag]) for r in rs),'additive':False})
  axis.append({'cohort':name,'independent_axis':'additional_annotation_unresolved','rows':sum(bool(r['annotation_unresolved_components']) for r in rs),'additive':False})
 stages=[('Kd_endpoint',lambda r:r['endpoint']=='Kd'),('exact_molar_point',lambda r:r['exact_molar_point']),('SMILES_and_standard20_reference_target_available',lambda r:r['peptide_smiles_present'] and r['reference_target_sequence_standard20_available']),('legacy_primary_quarantine',lambda r:not r['existing_primary_quarantine']),('existing_entity_representation_conflict',lambda r:not r['existing_entity_representation_conflict']),('endpoint_internal_conflict',lambda r:not r['source_endpoint_conflict']),('concentration_internal_conflict',lambda r:not r['source_concentration_conflict']),('inherited_metadata_only_high_risk',lambda r:'explicit_high_risk_source_metadata_only' not in r['quality_flags'])]
 flow=[]
 for cohort,cls in [('NC','noncanonical_explicit'),('standard20_control','standard20_supported')]:
  current=[r for r in audits if r['residue_class']==cls];flow.append({'cohort':cohort,'stage':'residue_class_start','before':len(current),'excluded_this_stage':0,'retained':len(current),'original_deleted':0})
  for stage,test in stages:
   nxt=[r for r in current if test(r)];flow.append({'cohort':cohort,'stage':stage,'before':len(current),'excluded_this_stage':len(current)-len(nxt),'retained':len(nxt),'original_deleted':0});current=nxt
  assert len(current)==(2099 if cohort=='NC' else 7520)
 splitrows=[];stratified=[]
 for panel,regimes in verification['regime_split_counts'].items():
  stats=feas['panels'][panel]
  for regime,count in regimes.items():splitrows.append({'panel':panel,'regime':regime,**count,'test_sensitivity_excluded':count['test']-count['test_sensitivity_rows']})
  for partition,strata in stats['strata_by_split'].items():
   for stratum,n in strata.items():stratified.append({'panel':panel,'partition':partition,'evaluation_stratum':stratum,'rows':n})
 prefix=[]
 for cap in [1000,1200]:
  for group,rs in [('NC',[r for r in inputs if r['NC_core']]),('standard20_control',[r for r in inputs if not r['NC_core']])]:
   seqs={r['target_sequence'] for r in rs};prefix.append({'protein_prefix_limit':cap,'cohort':group,'records':len(rs),'truncated_records':sum(len(r['target_sequence'])>cap for r in rs),'unique_reference_sequences':len(seqs),'truncated_reference_sequences':sum(len(s)>cap for s in seqs),'minimum_reference_length':min(map(len,seqs)),'maximum_reference_length':max(map(len,seqs))})
 fixes={'GraphDTA-GIN':'作者GIN模型逐字节保留；纯函数AST提取去除导入即读数据副作用；保持源码global_add_pool并披露论文文字max pool差异；统一validation选优替换作者test选优循环。','MGraphDTA':'保留22节点/6边特征与单图minmax；forward克隆Data以避免data.x污染复用缓存；核心GraphConv未使用边属性。','DGDTA-CL':'删除GCNConv不支持的dropout参数；拼接入口256→1688；LSTM设置batch_first=True，修复跨样本依赖；使用修正版作者实现，原源码及diff保留。','DeepNC-GEN':'super(GEN_Conv,self)未定义名称修为super(GEN,self)；现PyG对softmax_sg语义已兼容，无额外聚合替换；保留源码global_add_pool。','GS-DTA':'作者模型逐字节保留；AST提取五个纯编码函数；固定路径载入真正GS类，避开大小写目录和原training_validation.py误导入其他模型问题。'}
 methodrows=[]
 for method in ['GraphDTA-GIN','MGraphDTA','DGDTA-CL','DeepNC-GEN','GS-DTA']:
  if method=='GS-DTA':m={'paper':gs['paper']['title'],'year':2025,'doi':gs['paper']['doi'],'repo':'zhuziguang/GS-DTA','source_commit':gs['code']['commit'],'cap':1000}
  else:m=next(r for r in models if r['name']==method)
  folder={'GraphDTA-GIN':'graphdta-deepnc','DeepNC-GEN':'graphdta-deepnc','MGraphDTA':'mgraph-dgdta','DGDTA-CL':'mgraph-dgdta','GS-DTA':'gs-dta'}[method]
  text=content(ROOT/'methods'/folder/'README.md')
  date='2025-02-04' if method=='GS-DTA' else next(r for r in primarydates['models'] if r['method']==method)['publication_dates']['first_online']
  license_value=m.get('license');license_value=license_value.get('spdx_id','unknown') if isinstance(license_value,dict) else license_value or 'unknown'
  methodrows.append({'method':method,'paper_title':m['paper'],'year':m['year'],'first_online_date':date,'doi':m['doi'],'paper_url':'https://doi.org/'+m['doi'],'repository':'https://github.com/'+m['repo'],'commit':m['source_commit'],'source_code_license':license_value,'protein_prefix_limit':m['cap'],'atom_cap':'none','atom_chirality_encoded':False,'pretrained_or_author_checkpoint_used':False,'original_task':'compound-protein affinity regression','current_task':'same frozen PPIKB Kd benchmark retrained from scratch','adapter_repairs_and_differences':fixes[method],'evidence_readme':str(ROOT/'methods'/folder/'README.md'),'registered_task_id':registered[method]['task_id'],'paper_pdf_sha256_declared':registered[method]['pdf_sha256'],'snapshot_coverage':'selected frozen source; not asserted full Git checkout'})
 for f in [ROOT/'methods/graphdta-deepnc/vendor-manifest.json',ROOT/'methods/mgraph-dgdta/source-freeze-manifest.json',ROOT/'methods/gs-dta/source-manifest.json']:read(f)
 # Read only one issued fit specification per method; it contains no holdout gold.
 tuning={};tuning_sources=[]
 for file in sorted((ROOT/'control/gpu-fit-specs-v4').glob('*.json')):
  if not file.name.endswith('__seed00.json') or file.name.split('__')[0] in tuning:continue
  candidate=read(file)
  if 'method_id' in candidate and candidate['method_id'] not in tuning:
   tuning[candidate['method_id']]={key:candidate.get(key) for key in ['batch_size','gradient_accumulation','max_epochs','patience','cpu_threads','device','y_standardize','candidates']};tuning_sources.append(file)
 # Filename spelling is implementation metadata; use one small spec if the first pattern is absent.
 if not tuning:
  for file in sorted((ROOT/'control/gpu-fit-specs-v4').glob('*.json')):
   candidate=read(file)
   if 'method_id' in candidate and candidate['method_id'] not in tuning:tuning[candidate['method_id']]={key:candidate.get(key) for key in ['batch_size','gradient_accumulation','max_epochs','patience','cpu_threads','device','y_standardize','candidates']}
   if len(tuning)==5:break
 externalrows=[{'dataset':'SH2/ProBound','study_doi':extaliases['SH2_ProBound']['doi'],'records':45,'chemistry':'pY/PTM','primary':45,'sensitivity':0,'separate_supplement':0,'source_cold':45,'declared_graph_cold':45,'target_reference_cold':0,'target_scope':'protein reference','training_use':False}, {'dataset':'Kliche2023','study_doi':extaliases['Kliche2023_phosphomimetic']['doi'],'records':30,'chemistry':'pS/pT PTM','primary':22,'sensitivity':8,'separate_supplement':0,'source_cold':30,'declared_graph_cold':30,'target_reference_cold':2,'target_scope':'reference/domain;8 conditioned boundary/site views','training_use':False},{'dataset':'ProfAff2022 assets-only','study_doi':extaliases['ProfAff2022']['doi'],'records':52,'chemistry':'PTM','primary':0,'sensitivity':0,'separate_supplement':0,'source_cold':52,'declared_graph_cold':None,'target_reference_cold':38,'target_scope':'domain/reference, full fusion unresolved; graph independence unknown without complete SMILES','training_use':False},{'dataset':'IgG-Fc2025 separate supplement','study_doi':igglead['study_id'],'records':13,'chemistry':'8 synthetic_D_backbone +5 standard','primary':0,'sensitivity':0,'separate_supplement':13,'source_cold':13,'declared_graph_cold':13,'target_reference_cold':0,'target_scope':'449aa heavy-chain Fc-side reference; full2H2L provenance retained','training_use':False}]
 content(ROOT/'execution/runner.py')
 evidence=[]
 def ev(key,claim,source,pointer,kind='source_metadata'):
  p=Path(source);entry=next(r for r in OPEN if Path(r['path'])==p)
  evidence.append({'evidence_id':key,'claim':claim,'source_path':str(p),'source_sha256':entry['sha256'],'json_pointer_or_section':pointer,'evidence_type':kind,'gold_or_model_outputs_opened':False})
 ev('E01','冻结9619行NC2099+标准7520，固定seed与两面板',F/'manifest.json','/rows;/NC;/standard;/seed_list;/primary_panels')
 ev('E02','互斥类别、输入范围、分组规则与注释冲突策略',F/'protocol.json','/chemistry_strata_mutually_exclusive;/source_peptide_panel;/target_panel;/class_graph_discordance')
 ev('E03','逐级筛选和残基子类，由冻结继承的无亲和力数值审计表重算',auditpath,'all-21845-status; SHA bound by frozen input-manifest','derived_metadata_counts')
 ev('E04','两面板NC/std计数与同预测敏感性分母',ROOT/'data-protocol/frozen-v1-verification.json','/regime_split_counts')
 ev('E05','零泄漏声明与允许跨轴关系',F/'independent-leakage-verification.json','/panel_audits')
 ev('E06','93.02%双冷巨型组件及实际分区',F/'split-feasibility-report.json','/panels')
 ev('E07','观测/实体/靶标/实体靶标对粒度',F/'granularity-audit.json','/all;/NC;/standard20_control')
 ev('E08','靶标前缀截断计数与独立化学flags；未打开任何金标',F/'inputs.jsonl','label-free target_sequence + chemistry flags','derived_label_free_counts')
 ev('E09','五篇论文正式身份与PDF字节哈希',ROOT/'control/registered-paper-map.json','all five method entries')
 ev('E10','替换MRBDTA为GS及20epochs/pat5/两LR的训练前修订',ROOT/'administration/protocol-revision-v3.json','/replacement_method;/current_max_epochs;/basis')
 ev('E11','GS论文/仓库commit和原生模型身份',ROOT/'model-audit/replacement-gs-dta/candidate-audit.json','/paper;/code;/method')
 for i,m in enumerate(methodrows,12):ev('E'+str(i),m['method']+'输入与执行修复',Path(m['evidence_readme']),'Frozen source and disclosed changes / 必要修复 / 接入接口')
 ev('E17','原75外测的接受分母、回顾性和独立性边界',ROOT/'external-validation/acceptance-manifest.json','/counts;/graph_rule;/target_rule;/gold_policy')
 ev('E18','13补集接受依据和449aa参考视图',ROOT/'external-validation/scoring-supplement13-v1/root-accepted-manifest.json','/root_direct_task_decision;/counts;/target_input_scope;/evaluation_policy')
 ev('E19','13补集源23实体至13接受点的筛选',ROOT/'external-validation/IgG-Fc-supplementary-audit-v1/postfreeze-supplement-candidate-manifest.json','/counts;/chemistry_quality;/excluded_chemical_axes')
 ev('E20','四个保留方法的首次在线日期；该旧sidecar的MRBDTA名单已被revision-v3替换',ROOT/'model-audit/papers/primary-method-verification-sidecar-v3.json','/models/*/publication_dates')
 ev('E21','外部三来源DOI、来源/实体训练黑名单0',ROOT/'external-validation/training-blacklist.json','/external_original_study_aliases;/source_blacklist_record_ids;/conservative_related_entity_blacklist_record_ids')
 ev('E22','13补集原始研究DOI和来源URL；旧就绪状态由后续接受清单覆盖',ROOT/'external-validation/new-resource-leads/IgG-Fc-2025-lead-summary.json','/study_id;/official_source_url')
 ev('E23','共同Adam/MSE实现与候选LR常量；只读代码，不执行任何评分',ROOT/'execution/runner.py','HYPERPARAMETERS; train_candidate; torch.optim.Adam; mse_loss')
 for i,file in enumerate(tuning_sources,24):ev('E'+str(i),'正式'+file.name.split('__')[0]+'参数规格（只读train/validation路径元数据）',file,'/batch_size;/gradient_accumulation;/max_epochs;/patience;/candidates')
 for name,data in [('raw-residue-class-counts.csv',rawclasses),('raw-endpoint-counts.csv',rawendpoints),('chemical-categories.csv',categories),('nc-overlapping-subtypes.csv',subtypes),('independent-chemical-axes.csv',axis),('quality-filter-flow.csv',flow),('split-regime-counts.csv',splitrows),('split-strata-counts.csv',stratified),('target-prefix-coverage.csv',prefix),('predecessor-models.csv',methodrows),('external-validation-scope.csv',externalrows),('source-evidence.csv',evidence)]:csvout(name,data)
 assembled={'frozen_dataset_manifest_sha256':manifest and next(r['sha256'] for r in OPEN if Path(r['path'])==F/'manifest.json'),'raw_residue_class_counts':rawclasses,'raw_parsed_endpoint_counts':rawendpoints,'chemical_categories':categories,'nc_subtypes_overlapping':subtypes,'independent_chemical_axes':axis,'quality_filter_flow':flow,'split_regime_counts':splitrows,'split_strata_counts':stratified,'prefix_coverage':prefix,'granularity':gran,'predecessor_models':methodrows,'training_specs_metadata':tuning,'external_scope':externalrows,'source_evidence':evidence,'performance_results_included':False,'test_or_external_gold_opened':False,'predictions_or_checkpoints_opened':False}
 dump(P/'method-data-evidence.json',assembled)
 stage_zh={'residue_class_start':'残基注释分类起点','Kd_endpoint':'只取Kd端点','exact_molar_point':'只取精确可换算点值','SMILES_and_standard20_reference_target_available':'具备SMILES与合格蛋白参考输入','legacy_primary_quarantine':'应用既有原文质量隔离','existing_entity_representation_conflict':'移出既有实体表示冲突','endpoint_internal_conflict':'移出端点字段冲突','concentration_internal_conflict':'移出浓度字段冲突','inherited_metadata_only_high_risk':'移出继承的高风险仅元数据记录'}
 flowdisplay=[{**r,'cohort':'非标准残基' if r['cohort']=='NC' else '标准残基对照','stage':stage_zh[r['stage']]} for r in flow]
 panel_zh={'source_peptide_dependency_cold':'来源＋肽依赖冷','target_reference_homology_cold':'参考蛋白同源冷'}
 splitdisplay=[{**r,'panel':panel_zh[r['panel']],'regime':'仅NC训练' if r['regime']=='NC_only' else '仅标准训练'} for r in splitrows]
 methoddisplay=[{**r,'doi':f"[{r['doi']}]({r['paper_url']})",'repository':f"[官方代码]({r['repository']})",'commit':f"[{r['commit'][:12]}]({r['repository']}/tree/{r['commit']})"} for r in methodrows]
 evidencedisplay=[{**r,'source_path':f"[{Path(r['source_path']).name}]({Path(r['source_path']).as_posix()})"} for r in evidence]
 report=f'''# PPIKB非标准肽—蛋白亲和力基准：方法与数据说明

本轮以PPIKB的**2,099条非标准残基肽Kd观测**为主队列，以**7,520条标准20残基肽Kd观测**为对照，在共同冻结的数据划分上从头重训五篇已发表方法。非蛋白源／D型／骨架改变、PTM、混合类和其他非标准残基分开评价。PepLand及其衍生数据已经排除。【E01–E03】

这是一份方法和证据说明。模型比较统一放在全部200个选择冻结之后，本文不使用任何真实测试／外部金标、预测或检查点，也不提供性能结论。冻结入口为`data-protocol/frozen-v1/manifest.json`，SHA256 `{assembled['frozen_dataset_manifest_sha256']}`。

## 1. 数据表示与当前任务

当前任务是给定肽的完整分子SMILES和蛋白参考序列，预测实验Kd的负对数：`pKd = -log10(Kd / M)`。Kd与Ki、IC50保持不同端点；后两类仍留在原数据库，本轮不混入Kd监督。二元“是否结合”、对接姿态和残基接触位点属于其他任务，本轮Kd主表不通过人为负例或结构评分替代它们。【E01–E03】

9,619行的统计单位是**测量记录**。它们对应5,140种含立体信息的标准化分子图、1,411条靶标参考序列和6,054个分子图—靶标参考组合。非标准2,099行对应990种分子图、415条靶标参考序列、1,212个分子图—靶标组合；标准7,520行对应4,210种图、1,226条参考序列、4,919个组合。不同来源、实验条件或重复测量沿用各自记录，分组处理其依赖关系。【E07】

### 残基类别

{mdtable(categories,[('category_zh','互斥评价类别'),('rows','记录数')])}

非天然主类由六个预声明的非蛋白源／D／骨架子类flag定义，PTM由`ptm_*`flag定义；同时具有两轴证据的观测进入混合类。子类flag可重叠，详见`nc-overlapping-subtypes.csv`。其中显式D型注释73行、非α／骨架改变175行、N取代／peptoid69行；PTM注释包含磷酸化627行、甲基化422行等，不能把这些重叠数量直接相加。

“其他非标准”106行保持独立：其中存在未能归入上述主轴的已注释残基身份，且整个NC队列含2条天然额外残基`natural_21_22`注释。因此“NC2099”准确表示标准20残基集合之外或明确残基修饰的操作性队列，不能全称为人工非天然残基。43条NC观测还有附加化学注释未解，原文与分子表示保持原样。【E02–E03】

末端封端、环化、连接体、实验标签是独立化学轴。仅末端乙酰化或酰胺化不自动进入NC主类；普通标准氨基酸替换仍是标准残基。当前NC队列有723行N端非free注释、794行C端非free注释、381行环化、258行实验标签、71行连接体；这些数量允许重叠。标准对照也保留封端与拓扑信息，**标准残基对照不等于无修饰肽对照**。【E02–E03】

## 2. 质量筛选与原始数据保留

原始PPIKB的21,845行继续完整保留。筛选是在派生视图上标记资格，未删除原始文件，未重写数值、单位、序列或化学实体。全部物种按同一规则进入候选，未额外限制人源。【E01–E03】

原始残基审计分为NC明确4,642行、标准20残基支持15,754行、仅残基连接实验标签100行、身份未解1,349行。后两类1,449行保留在原始档案，未并入本轮核心NC／标准对照。其余缩减主要来自端点不同，所有Ki、IC50及其他端点仍可在各自任务中使用；它们没有被当作坏数据删除。【E03】

按冻结解析表的`endpoint`字段统计，Kd共10,517行，其中NC2,120、标准7,903、其他残基类别494；该口径与未经复核的原结构化端点列计数区分，内部冲突flag继续保存。完整端点清单见`raw-endpoint-counts.csv`。【E03】

下表按固定顺序展示筛选，每阶段剔除量互斥；机器冲突flag表示已有字段一致性风险，尚未授权的原文单位调查未重启。

{mdtable(flowdisplay,[('cohort','队列'),('stage','阶段'),('before','阶段前'),('excluded_this_stage','本阶段移出'),('retained','保留')])}

NC从2,120条Kd到2,099条技术候选，具体是3条缺少合格分子／蛋白输入、13条继承的浓度字段冲突、5条继承的metadata-only高风险记录。标准Kd从7,903到7,520：159条输入不足、2条既有原文质量隔离、5条已有实体表示冲突、155条浓度字段冲突、62条metadata-only高风险记录。该流程保留所有原始测量，并不把缺值、删失记录或未测组合改成“不结合”。【E03】

端点名统一以后，不同实验来源的测量方法、温度、缓冲条件和蛋白构建体仍可能不同。当前缺失项按未知保留，技术候选资格不代替逐篇实验条件认证。

## 3. 两个严格划分面板

所有NC与标准观测**先一起建图、划分，再按训练regime取子集**。分组输入没有数值亲和力；固定划分种子为`nc-protocol-20261021-v1`，训练种子0–9不改变测试分区。下列NC和标准测试数是共同测试池中的评分子集；正式每个模型可对同一完整测试池产生一次预测，再汇总各子集。【E01–E06】

{mdtable(splitdisplay,[('panel','面板'),('regime','训练子集'),('train','训练'),('validation','验证'),('test','同类测试子集'),('test_sensitivity_rows','冲突排除后同类测试')])}

**来源＋肽依赖冷面板**将来源study id及规范化DOI／PMID／题名别名、同含立体分子图、去立体分子图、相同原始母体／已给parent series、长度至少5的同长度单替换邻居，以及Morgan radius2／2048bit／无立体指纹Tanimoto≥0.8邻居连接成传递组件。组件整体划分。最大组件7,540行，占78.39%，故实际7540／1040／1039，保留图完整性而采用实际比例。来源别名、同图、去立体图及声明化学邻居跨分区均为0；205条精确参考序列、549条声明靶标相似边允许跨分区。【E05–E06】

**蛋白参考序列同源冷面板**使用冻结Bio.Align1.85的BLOSUM62局部最优对齐，gap open=-10、extend=-0.5，固定取首个最优解；身份率为完全匹配残基数／非gap成对列数≥0.30，两方覆盖率均为成对列数／各自完整参考长度≥0.80。另加入较短端≥40aa的精确序列包含关系，以及相同1000aa模型前缀关系。全部主—主和外—主序列对被逐对比较或由必要的长度／成分上界排除；没有可能漏检的kmer近邻预筛。含外部参考共1,433条序列、1,025,797对、1,172条阳性边。实际6733／1443／1443。精确参考、1000aa前缀和声明同源边跨分区均为0；432个来源别名、223种分子图和4,730条化学邻居边允许跨分区。【E05】

两个面板分别测量新来源／肽背景和新参考靶标条件下的泛化。它们不同时隔离全部关系；声明的参考序列阈值也不等同于普适蛋白家族注释。双冷图最大组件8,948行，占93.02%，只保留可行性诊断，不作本轮主表。【E02、E05–E06】

## 4. 608条结构—注释冲突与敏感性分析

60种**相同含立体分子图**同时有NC和标准残基注释，涉及357条NC及251条标准记录，共608行。当前证据不能决定哪一侧注释正确，主名册保持9,619行，并以`residue_class_graph_discordance`标记。因此当前主结果的准确名称是**按残基注释分层的亲和力基准**。同图依赖已进入划分关系。【E02、E07】

所有测试预测先完整保存，再从同一批预测排除冲突flag计算敏感性结果，无需重新拟合或重新选择模型。来源冷NC测试303→274（排29），标准736→724（排12）；参考同源冷NC332→261（排71），标准1111→1067（排44）。608是全池冲突行数，不应从每个测试分母再减608。【E04】

这个敏感性分析只改变测试汇总分母，训练与验证仍保留已标记观测；它衡量结果对测试身份冲突的敏感性，不能解释为已在完全化学一致训练集上重训。

## 5. 参考蛋白与模型有效输入

本轮蛋白输入是数据库参考序列。**实际实验蛋白构建体序列认证数为0**；完整参考序列、域边界和构建体是不同层次。模型保留各自作者输入：MGraphDTA采用前1200aa，其余四方法采用前1000aa，均按原作者padding。分区额外合并1000aa相同前缀，避免模型有效蛋白输入重合带来的目标泄漏。【E02、E08、E12–E16】

{mdtable(prefix,[('protein_prefix_limit','作者前缀上限'),('cohort','队列'),('records','观测'),('truncated_records','会截断的观测'),('unique_reference_sequences','独特参考序列'),('truncated_reference_sequences','会截断的参考序列'),('minimum_reference_length','最短aa'),('maximum_reference_length','最长aa')])}

肽分子保持完整SMILES和全部原子，未用标准残基替代非标准残基，未设置原子截断。五个现有图模型均没有原子手性特征；四个78维特征模型还省略键级／键立体，MGraphDTA虽构造边属性，核心GraphConv也未使用它们。因此D/L等同拓扑立体异构体可能具有相同有效输入。分子图去立体依赖能约束泄漏，不能给模型增加手性辨识能力。还需保留每个方法的实际输入hash和拒绝原因，区分原分子身份与模型可见信息。【E12–E16】

## 6. 五篇前人方法和适配定位

五篇正式身份以`control/registered-paper-map.json`及训练前revision-v3为准。旧`model-routes.json`仍保留被替换的MRBDTA历史；其早期“selected_count=5”不能代替当前五名单。GS-DTA的替换依据是权威原文和执行资产可用性，发生在正式训练前，未使用模型测试／验证表现。【E09–E11】

{mdtable(methoddisplay,[('method','方法'),('year','卷期／论文年'),('first_online_date','首次在线'),('doi','DOI'),('repository','官方仓库'),('commit','冻结commit（全值见CSV）'),('protein_prefix_limit','蛋白前缀')])}

五方法原任务都是小分子—蛋白亲和力预测。本轮使用其作者架构和预处理，在同一PPIKB肽—蛋白数据上从头训练，未使用作者预训练／监督检查点；论文原始数据、训练循环和主表分母与本轮不同，复现定位为**前人方法在新共同数据上的可追溯重训比较**。本轮五个方法不计为五篇肽专属方法，也不计为原论文主表数值的重复实验。【E09–E16】

{mdtable(methodrows,[('method','方法'),('adapter_repairs_and_differences','保留行为及适配修复')])}

DGDTA的维度和LSTM布局修复会改变原错误执行语义，必须标为修正版作者实现。GraphDTA论文文字与冻结代码pooling不一致、DeepNC论文batch描述不一致等原始差异保持披露，未为统一外观而重写架构。完整上游快照、commit、源SHA及diff可追溯；当前执行所需的选定源码快照不自动等于完整Git checkout。【E12–E16】

`DGDTA-CL`是本轮选定DGDTA作者类的冻结方法ID，计为DGDTA这一篇论文；它没有增加一个新论文身份或新的训练目标。

该五篇覆盖2020首次在线／2021卷期至2025年。以2026-10-22严格回溯三年，窗口起点为2023-10-22，当前五名单只有GS-DTA2025在窗口内；DGDTA首次在线2023-09-30，已在窗口外。GraphDTA首次在线2020-10-24，也早于严格五年窗口起点2021-10-22。当前范围满足五个已发表前人架构的共同数据比较，近三年与近五年肽专属文献的穷尽覆盖是另外一项仍需核对的历史目标。【E09–E11、E20】

## 7. 统一训练、调参与评分约定

设计共5方法×2面板×2训练regime×10种子=**200个模型选择unit**，每unit搜索两个LR，共**400个候选fit**。NC_only只用对应训练／验证分区的NC行；standard_only只用标准行；本轮不做pooled。所有方法当前冻结batch32、梯度累积1、Adam、直接pKd MSE、LR 0.001／0.0003、weight decay0，最多20epochs、patience5。按验证MAE选择epoch与LR，平分时取较小候选序号。训练前30epoch CPU方案及替换记录保留为历史版本。【E10、E23–E28】

标准训练观测多于NC训练观测，标准模型与NC模型的差异同时受训练数据量、靶标分布和化学分布影响。两队列共有230条靶标参考序列，未来可补充共享靶标的汇总分析；当前总体差异不能直接解释成“非标准残基导致模型更难”。

全部选择冻结后统一读取测试／外部金标，保存每方法／面板／regime／seed逐记录预测和全部失败。MAE、RMSE、Pearson、Spearman、R²按同一测试池和明确化学子集输出；10种子汇总均值及样本标准差。样本不足、任一输入恒定时的相关，以及真值恒定时的R²，按各指标定义输出未定义；预测恒定而真值非常数时，R²仍可定义。10个训练种子衡量训练随机性，不能替代独立生物体系重复。评分代码另由root冻结，本文没有运行评分。

这是预声明的有限LR搜索和20epoch预算，是否充分收敛由后续训练／验证记录判断。共同训练保留FP32、不启用AMP和TF32；CUDA确定性采用`warn_only=True`，相关内核警告保留，不能把十种子记录解释为CUDA位级确定。【E23】

## 8. 独立外部验证的接受范围

{mdtable(externalrows,[('dataset','资源'),('study_doi','来源DOI'),('records','观测'),('chemistry','类别'),('primary','原主外测'),('sensitivity','原敏感性'),('separate_supplement','独立补诊断'),('source_cold','来源冷'),('declared_graph_cold','声明分子图冷'),('target_reference_cold','参考靶标冷')])}

**原75条外测**由SH2/ProBound45条pY和Kliche30条pS/pT组成，全部是PTM；其中67条为主用参考视图，8条Kliche构建体／位点条件存在歧义，仅作敏感性。原测量实体经明确残基、位置、封端及构型转写为SMILES，并检查原子／化学身份约束；对PPIKB全21,845行、11,256种原SMILES分子图，精确含立体图、去立体图和声明Morgan≥0.8重合均为0，来源DOI／PMID／题名重合为0。75中仅2条Kliche同时满足声明的参考靶标冷，SH2的45条都与主池同参考靶标。ProfAff的52条来源独立，但真实连接体SMILES与全融合构建体未齐，仍为资产候选，38条参考冷也不改变当前无法推理的状态。【E17】

**13条独立补充诊断**来自一项2025研究，经root以来源和实体证据接受，独立于原75保存。原23个新作者实体中有19条点值Kd。对全部23实体按来源端点／身份规则排9条，余14条尝试实体转写，其中1条作者分子式冲突隔离，最终接受8条非蛋白源／D／骨架及5条标准对照。来源和全PPIKB声明分子图审查均通过。13条全部与主池参考靶标有关联，输入为449aa重链的Fc侧参考视图；完整2H2L重／轻链证据另存，实际商业抗体lot、糖型和整实验构建体均未认证。原研究承继既有母体骨架，声明图阈值冷也不等于普适母体家族独立。【E18–E19】

原75接受SHA为`85973838adc28c0b6b9134a28a90312162a158eafd20f8b2bf14e68e13d36c4d`；13的root接受清单单独记录，未增加训练或调参数据，也未合并进75。它们都是回顾性外测：公开原标签此前在来源整理阶段已被研究者看到，模型选择不使用这些标签；文件分离是数据流程约束，共享账户下不称OS权限隔离。75和13应分别报告，13中的8／5从同一预测划分；单篇研究的13个案例不能当13个独立体系。【E17–E19】

声明分子图审查保留电荷和立体表示，未统一质子化、互变异构或盐身份；外部磷酸基的中性表示是已披露的格式约定。这些规则支持可复核的图表示独立性，而物理化学实体等价范围仍受表示约定限制。【E17、E21–E22】

## 9. 解释结果时必须保持的口径

1. NC2099是注释分层的技术候选，不是2,099个独立、化学身份逐篇认证的分子；608行图—注释冲突与43条NC附加未知组分继续显式保留。
2. “标准残基”与“无修饰”不同，末端、拓扑和标签仍可能影响测量；当前两个训练regime的样本量和靶标分布也不同。
3. 来源＋肽冷和参考同源冷各自有允许跨分区的轴；主表不能统称双冷或普适家族外推。
4. 输入为参考蛋白及作者前缀，不是经认证的实际构建体或结合位点；预测值解释应保留此范围。
5. 五模型都具有手性盲区；DGDTA是披露必要语义修复后的实现。新共同数据重训与原论文分母的完整复现分别记账。
6. 原75只覆盖PTM；补13提供8条非PTM但来自同一来源／靶标，广泛跨家族与非天然化学泛化仍需更多独立体系。
7. 全测试池`all`指标、NC主子集、标准子集、608冲突排除敏感性是不同分母。正式评分必须清楚标注scope，不能以`all`代替NC主结果。
8. 400候选fit／200选择是计划覆盖量，实际完成、失败、截止与缺失由root运行清单另行归档。本说明没有据此推断性能或完成率。

## 10. 文件与证据入口

机器可读总表：`method-data-evidence.json`；逐条证据表：`source-evidence.csv`。配套CSV分别保存化学类别、重叠子类、独立化学轴、质量流失、划分／敏感性、前缀覆盖、五模型与外测范围。`report-read-audit.json`记录本报告实际读取的元数据及SHA；任何金标、预测、检查点均未打开。

{mdtable(evidencedisplay,[('evidence_id','证据ID'),('claim','支持内容'),('source_path','本地来源'),('json_pointer_or_section','位置')])}
'''
 (P/'方法与数据说明.md').write_text(report,encoding='utf-8')
 dump(P/'report-read-audit.json',{'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'opened_sources':OPEN,'gold_opened':False,'predictions_opened':False,'checkpoints_opened':False,'source_data_edits':0,'training_or_scoring_calls':0})
 assert sum(r['rows'] for r in categories)==9619 and len(methodrows)==5 and sum(r['NC_core'] for r in inputs)==2099
 print(json.dumps({'report':str(P/'方法与数据说明.md'),'methods':len(methodrows),'metadata_files_opened':len(OPEN),'performance_results':False,'gold_opened':False},ensure_ascii=False))
if __name__=='__main__':main()
