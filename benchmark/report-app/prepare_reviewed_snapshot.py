"""Use reviewed aggregate tables only. No labels, predictions or weights."""
import json,hashlib,datetime
from pathlib import Path
P=Path(__file__).resolve().parent;R=P.parent/'report-preparation'
data=json.loads((R/'method-data-evidence.json').read_text(encoding='utf-8'))
verification=json.loads((R/'verification.json').read_text(encoding='utf-8'));assert verification['all_checks_passed']
for name,meta in verification['files'].items():
 path=R/name
 if path.is_file():assert hashlib.sha256(path.read_bytes()).hexdigest()==meta['sha256'],name
zh={'synthetic_D_backbone':'非蛋白源／D型／骨架改变','PTM':'PTM残基修饰','synthetic_and_PTM':'两类同时出现','other_NC':'其他非标准残基','standard20_control':'标准20残基对照'}
queries={}
def add(qid,rows,file,components,definition,links=None):
 queries[qid]={'rows':rows,'source':{'label':'已核验本地聚合：'+file,'files':[{'name':file,'sha256':hashlib.sha256((R/file).read_bytes()).hexdigest()}],'metricDefinitions':[{'label':definition,'definition':definition,'componentIds':components,'sourceLineage':[{'files':[file]}]}],'evidenceFlow':[{'title':'冻结数据与记录级审计','detail':'依据共同冻结协议，只读取聚合表与公开方法资料。'},{'title':'聚合来源','detail':file+'；SHA256 '+hashlib.sha256((R/file).read_bytes()).hexdigest()},{'title':'分析粒度','detail':definition}],'links':links or []},'methods':[{'language':'text','code':'直接使用已独立核验的聚合行；各类别的互斥/重叠关系见定义。未读取训练标签、测试/外部金标、预测或检查点。'}]}
categories=[dict(r,label=zh[r['category']]) for r in data['chemical_categories']]
add('chemistry_counts',categories,'chemical-categories.csv',['chemistry-bars','cohort-table','data-brief'],'互斥残基注释类别的测量记录数；NC四类合计2099，标准对照7520；观测不等于独立分子。')
add('quality_flow',data['quality_filter_flow'],'quality-filter-flow.csv',['filter-flow','quality-brief'],'固定顺序筛选中每阶段前后记录量及该阶段移出量；原始删除数始终为0。')
add('split_counts',data['split_strata_counts'],'split-strata-counts.csv',['split-bars','sample-denominators','split-brief'],'固定训练/验证/测试分区内各互斥化学组的记录数；先共同划分，再按训练regime取NC或标准子集。')
add('sensitivity_counts',data['split_regime_counts'],'split-regime-counts.csv',['sample-denominators','discordance-table','discordance-brief'],'同一批测试预测排除结构—注释冲突的分母；只改变评价子集，不重新训练或选模型。')
add('prefix_counts',data['prefix_coverage'],'target-prefix-coverage.csv',['prefix-table','target-brief'],'作者蛋白前缀上限下会截断的参考序列/观测数；参考不等于实际实验构建体。')
modelrows=[]
for m in data['predecessor_models']:
 modelrows.append({k:m[k] for k in ['method','paper_title','year','first_online_date','doi','paper_url','repository','commit','protein_prefix_limit','atom_chirality_encoded','adapter_repairs_and_differences','original_task','current_task']})
add('methods',modelrows,'predecessor-models.csv',['model-table','method-brief'],'五篇不同公开架构在共同PPIKB数据上从头重训；年份、上游commit和披露修复如实保存。',[{'label':m['method']+'论文','url':m['paper_url']} for m in modelrows])
add('external_scope',data['external_scope'],'external-validation-scope.csv',['external-table','external-brief'],'原75为PTM外测（67主用+8条件敏感性）；补13为8非PTM+5标准，单独报告；来源冷、声明图冷和靶标冷分别列示。')
evidence=[{'evidence_id':r['evidence_id'],'claim':r['claim'],'source_name':Path(r['source_path']).name,'source_sha256':r['source_sha256'],'location':r['json_pointer_or_section']} for r in data['source_evidence']]
add('evidence',evidence,'source-evidence.csv',['evidence-table'],'28条已核验来源声明与SHA；只嵌入聚合证据，不嵌入机器私有路径或原始肽实体。')
add('subtypes',data['nc_subtypes_overlapping'],'nc-overlapping-subtypes.csv',['subtype-table'],'非标准子类注释flag可重叠，不能相加作为独立样本总数。')
add('raw_counts',data['raw_residue_class_counts'],'raw-residue-class-counts.csv',['raw-count-table'],'原PPIKB21845行残基类别审计；不确定/标签型记录保留原档案，未强行并入核心NC。')
panels={'source_peptide_dependency_cold':'来源＋肽依赖冷','target_reference_homology_cold':'参考蛋白同源冷'}
regimes={'NC_only':'只用非标准肽训练','standard_only':'只用标准肽训练'}
counts={(r['panel'],r['partition'],r['evaluation_stratum']):r['rows'] for r in data['split_strata_counts']}
sample=[]
for panel,plabel in panels.items():
 for regime,rlabel in regimes.items():
  for chem in zh:
   used=(chem=='standard20_control')==(regime=='standard_only')
   sensitivity=next(r['test_sensitivity_rows'] for r in data['split_regime_counts'] if r['panel']==panel and r['regime']=='standard_only') if chem=='standard20_control' else None
   sample.append({'panel_id':panel,'regime_id':regime,'chemistry_id':chem,'panel_label':plabel,'regime_label':rlabel,'chemistry_label':zh[chem],'train_n':counts[panel,'train',chem] if used else 0,'validation_n':counts[panel,'validation',chem] if used else 0,'test_n':counts[panel,'test',chem],'sensitivity_n':sensitivity,'training_used':used})
add('sample_denominators',sample,'split-strata-counts.csv',['sample-denominators'],'每个面板/训练regime/互斥化学组的真实训练、验证和测试分母；训练0表示该regime设计上不使用该组。NC细分冲突排除分母未知而保留null。')
queries['sample_denominators']['source']['files'].append({'name':'split-regime-counts.csv','sha256':hashlib.sha256((R/'split-regime-counts.csv').read_bytes()).hexdigest()})
queries['sample_denominators']['source']['metricDefinitions'][0]['sourceLineage']=[{'files':['split-strata-counts.csv','split-regime-counts.csv']}]
queries['phase_snapshot']={'rows':[{'label':'NC神经网络选择完成','count':100,'denominator':100},{'label':'全部神经网络选择完成','count':104,'denominator':200},{'label':'RF选择完成','count':40,'denominator':40},{'label':'真实测试评测已执行','count':0,'denominator':None}],'source':{'label':'协调者本轮直接任务状态快照','metricDefinitions':[{'label':'训练与选择状态','definition':'仅为本轮指令提供的非实时状态；日期2026-10-22，精确时刻未提供。不是性能、成功率或独立测试结果。','componentIds':['phase-snapshot']}],'evidenceFlow':[{'title':'协调者同线程指令','detail':'NC100训练/选择已完成，standard100中，104total；RF40选择完成；真实测试0。未读取任何训练标签或评测产物。'}]}}
queries['rf_reference']={'rows':[{'method':'随机森林 RF','role':'传统机器学习参考，另计','selected_units':40,'configuration_status':'具体特征与搜索配置等待root核验表补齐','neural_paper_count_contribution':0}],'source':{'label':'协调者本轮直接任务说明','metricDefinitions':[{'label':'随机森林参考','definition':'40个训练/选择单元完成；不算第六篇神经网络论文，也不从训练完成推断测试性能。','componentIds':['rf-reference']}],'evidenceFlow':[{'title':'同线程任务范围','detail':'RF40训练选优全完成。性能与具体模型配置尚未向本应用提供。'}]}}
rfroot=P.parent/'auxiliary-rf-baseline'
rffreeze=json.loads((rfroot/'SOURCE-FREEZE-v1.json').read_text(encoding='utf-8'))
rfmetadata={}
for filename in ['feature-spec-v1.json','protocol-v1.json','installed-assets-v1.json']:
 blob=(rfroot/filename).read_bytes();assert hashlib.sha256(blob).hexdigest()==rffreeze['source_sha256'][filename]
 rfmetadata[filename]=json.loads(blob)
rffeat=rfmetadata['feature-spec-v1.json'];rfplan=rfmetadata['protocol-v1.json']
queries['rf_reference']['rows']=[{'method':'随机森林 RF','method_id':rfplan['method_id'],'role':'传统机器学习参考，另计','feature_dimension':rffeat['feature_dimension'],'n_estimators':rfplan['fixed_parameters']['n_estimators'],'min_leaf_candidates':' / '.join(str(r['min_samples_leaf']) for r in rfplan['candidate_profiles']),'n_jobs':rfplan['fixed_parameters']['n_jobs'],'protein_prefix_limit':1000,'selected_units':40,'candidate_fits':80,'configuration_status':'冻结特征与参数已核验','neural_paper_count_contribution':0}]
queries['rf_reference']['source']={'label':'RF冻结特征/协议/已安装库元数据＋协调者执行状态','files':[{'name':filename,'sha256':hashlib.sha256((rfroot/filename).read_bytes()).hexdigest()} for filename in ['SOURCE-FREEZE-v1.json','feature-spec-v1.json','protocol-v1.json','installed-assets-v1.json']],'metricDefinitions':[{'label':'RF固定特征与候选','definition':'2469维=2048位半径2/含已给手性与键型的Morgan指纹+蛋白前1000残基AAC20+DP400+有效长度1。200棵树、max_features=sqrt，叶最少样本数2/5两候选，n_jobs1、训练种子0–9。','componentIds':['rf-reference','rf-method-brief']},{'label':'RF训练完成快照','definition':'协调者新指令确认40单元/80候选均完成退出，选择已冻结；底层SOURCE-FREEZE状态是拟合前准备历史，不改写该文件。本应用没有打开任何RF模型、selection或指标。','componentIds':['rf-reference','rf-method-brief']}],'evidenceFlow':[{'title':'冻结元信息','detail':'仅读取SOURCE-FREEZE、feature-spec、protocol、installed-assets四个JSON，并核验后三者SHA。未读真实矩阵、模型、selection、标签或性能指标。'},{'title':'特征构成','detail':'2048+20+400+1=2469维；使用实际给出的立体信息，不推断未指派构型；不做可学习预处理。'},{'title':'候选选择','detail':'validation MAE，只取同regime验证；平局取leaf2。40单元/80候选完成由root同线程指令提供，非本应用重新核算。'}]}
add('training_plan',[{'methods':5,'panels':2,'regimes':2,'seeds':10,'candidate_learning_rates':2,'selected_units_planned':200,'candidate_fits_planned':400,'maximum_epochs':20,'patience':5,'batch_size':32}],'method-data-evidence.json',['training-plan'],'预声明设计规模：五神经网络、两个冷面板、两个训练方案、十训练种子，构成200个模型选择单元、400候选fit；是计划，不是性能或完成率。')
bindings={'chemistry_counts':['chemistry-bars','cohort-table','data-brief','affinity-definition','chemistry-definition'],'quality_flow':['filter-flow','quality-brief'],'split_counts':['split-brief'],'sensitivity_counts':['discordance-table','discordance-brief'],'prefix_counts':['prefix-table','target-brief'],'methods':['model-table','method-brief','model-provenance'],'external_scope':['external-table','external-brief'],'evidence':['evidence-table','evidence-brief']}
for q,ids in bindings.items():queries[q]['source']['metricDefinitions'][0]['componentIds']=ids
for q in ['chemistry_counts','split_counts','sensitivity_counts','training_plan']:
 queries[q]['source']['files'].append({'name':'方法与数据说明.md','sha256':hashlib.sha256((R/'方法与数据说明.md').read_bytes()).hexdigest()})
queries['chemistry_counts']['source']['metricDefinitions'].append({'label':'pKd','definition':'pKd=-log10(Kd/M)，是对以摩尔为单位的Kd取负对数，不是统计检验p值。当前任务只纳入Kd点值。','componentIds':['affinity-definition'],'formula':'-log10(Kd/M)','sourceLineage':[{'files':['方法与数据说明.md']}]})
queries['metrics']={'rows':[],'source':{'label':'统一评测结果尚未导入','metricDefinitions':[{'label':'未来成绩表','definition':'仅在root提供独立复算和审阅后的汇总CSV/JSON时导入。当前没有性能数值，缺失不按0处理。','componentIds':['metrics-table']}],'evidenceFlow':[{'title':'当前状态','detail':'成绩行为空。模型选择冻结后统一评测，之后由root提供独立核算CSV。'}]},'methods':[{'language':'text','code':'schema: method_id,panel_id,regime_id,chemistry_id,evaluation_set_id,metric_id,mean,sd,n,seed_count. 只接受已审阅汇总。'}]}
snapshot={'title':'先看清数据，再比较肽—蛋白亲和力模型','surface':'report','status':'reviewed_aggregate_data_methods_only','buildStatus':'creating','generatedAt':datetime.datetime.now(datetime.timezone.utc).isoformat(),'report':{'asOf':'2026-10-22'},'filters':[],'queries':queries,'researchMetadata':{'reviewedEvidenceSha256':hashlib.sha256((R/'method-data-evidence.json').read_bytes()).hexdigest(),'datasetManifestSha256':data['frozen_dataset_manifest_sha256'],'sourceEvidenceCount':28,'performanceRows':0,'metricsSchema':queries['metrics']['methods'][0]['code'],'cohortCounts':{'NC':2099,'standard':7520,'measurements':9619,'canonicalIsomericGraphs':5140,'NCGraphs':990},'coordinatorStatusSnapshot':{'label':'协调者本轮指令快照，非实时','asOfDate':'2026-10-22','exactTimestampKnown':False,'NCNeuralSelectionsComplete':100,'standardNeuralSelectionsInProgress':True,'totalNeuralSelectionsComplete':104,'randomForestSelectionsComplete':40,'actualTestEvaluations':0}}}
appdata=P/'app/src/data.json'
if appdata.exists():snapshot['id']=json.loads(appdata.read_text(encoding='utf-8'))['id']
(P/'reviewed-snapshot.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding='utf-8')
if appdata.exists():appdata.write_text(json.dumps(snapshot,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'queries':len(queries),'performance_rows':0,'snapshot':str(P/'reviewed-snapshot.json')},ensure_ascii=False))
