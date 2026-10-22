"""Assemble reviewed aggregate results in the same authored report; no scorer/model IO."""
from pathlib import Path
import json,hashlib,datetime,urllib.parse,shutil
P=Path(__file__).resolve().parent;ROOT=P.parent;APP=P/'app'
load=lambda p:json.loads(p.read_text(encoding='utf-8'));sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
dpath=APP/'src/data.json';jsxpath=APP/'src/content/report/ReportContent.jsx';d=load(dpath);text=jsxpath.read_text(encoding='utf-8')
assert len(d['queries']['metrics']['rows'])==6880 and d['id']=='report:5569696c-9519-43ed-9a7a-073a11d14850'
summary=ROOT/'reporting/final-v1/summary.json';assert sha(summary)=='e5f5d346c5a5ed2de98cdccd8142cbf2e0c0299df02ca7250556cca27c2ba000';s=load(summary)
backup=P/'actual-results-ui-history';backup.mkdir(exist_ok=True)
for f,name in [(dpath,'data.after-import.before-display.json'),(jsxpath,'ReportContent.before-results.jsx')]:
 if not (backup/name).exists():(backup/name).write_bytes(f.read_bytes())
base_source=d['queries']['metrics']['source'];base_source['metricDefinitions'][0]['definition']='仅展示row_micro或matched_row_micro，n为观测记录数。mean/样本SD直接保留独立审阅聚合原值；seed_count为defined_seed_count，不是完成训练数。1092条均值未定义保留null。4600条macro及60条根批准仅不展示的RF混合clean诊断仍完整留档。'
base_source['files'] += [{'name':'final-v1/summary.json','sha256':sha(summary)},{'name':'root-final-summary-review-v1.json','sha256':'8f4c9879ce356ddce03451bb2b5bf2798c503828ebc7587efd6665a6900d188f'},{'name':'all240-joint-frozen.json','sha256':'5c506a6c9d1f140ef0556a2c35e46c0252a7710295017ce080a7830650443fcf'}]
cohort={'NC_core':'全部非标准肽（主任务）','all':'全部化学组','standard':'标准残基对照','standard20_control':'标准残基对照','synthetic_D_backbone':'非蛋白源／D型／骨架改变','PTM':'PTM残基修饰','synthetic_and_PTM':'两类同时出现','other_NC':'其他非标准残基','NC_core_exclude_discordant_sensitivity':'非标准肽排除注释冲突','standard_exclude_discordant_sensitivity':'标准肽排除注释冲突','exclude_discordant_sensitivity':'全体排除注释冲突','NC_matched':'共同靶标内非标准肽','standard_matched':'共同靶标内标准肽','external_primary67':'PTM主外测67','external_conditional_sensitivity8':'PTM条件敏感性8','external_reference_target_cold2':'PTM参考靶标冷2（属于67）','supplement_NC8':'IgG非标准补充8','supplement_standard5':'IgG标准补充5'}
for k,v in list(cohort.items()):
 if k in {'synthetic_D_backbone','PTM','synthetic_and_PTM','other_NC','standard20_control'}:cohort['exclude_discordant:'+k]=v+'：排除注释冲突'
datasets={'PPIKB-internal':'PPIKB内部测试','PTM-external75':'PTM外部75','IgG-supplement13':'IgG补充13'}
for r in d['queries']['metrics']['rows']:
 cat,ds,c,agg=[urllib.parse.unquote(x) for x in r['evaluation_set_id'].split('|')]
 assert c in cohort,c
 r['dataset_label']=datasets[ds];r['cohort_label']=('PTM全75诊断（含8条条件样本）' if ds=='PTM-external75' and c=='NC_core' else '补充非天然8诊断' if ds=='IgG-supplement13' and c=='NC_core' else cohort[c]);r['evaluation_label']=datasets[ds]+' · '+r['cohort_label']+(' · 共同靶标micro' if agg=='matched_row_micro' else '')
# Source-value-only pivot for the24 trainable means and2 simple constant references.
chosen=[r for r in s if r['dataset_id']=='PPIKB-internal' and r['cohort']=='NC_core' and r['aggregation']=='row_micro' and r['metric']=='MAE' and (r['category'] in {'five_prior_paper_NN','auxiliary_handcrafted_RF'} or (r['method_id']=='reference:train_median' and r['regime']=='standard_only'))]
assert len(chosen)==26
primary=[]
for r in chosen:
 r2=next(x for x in s if all(x[k]==r[k] for k in ['category','dataset_id','panel','method_id','regime','cohort','aggregation']) and x['metric']=='R2')
 primary.append({'panel_id':r['panel'],'panel_label':'来源＋肽依赖冷' if r['panel'].startswith('source') else '参考蛋白同源冷','method_id':r['method_id'],'regime_id':r['regime'],'regime_label':'非标准肽训练' if r['regime']=='NC_only' else '标准肽训练','MAE':r['mean'],'MAE_SD':r['sample_sd'],'R2':r2['mean'],'R2_SD':r2['sample_sd'],'n':next(iter(r['n_by_seed'].values())),'defined_seeds':r['defined_seed_count']})
assert all(r['MAE']>1.3178461694484538 for r in primary if r['panel_id'].startswith('source') and not r['method_id'].startswith('reference:'))
source={'label':'根审阅并独立重算的最终聚合：NC主任务','files':base_source['files'],'metricDefinitions':[{'label':'主NC均值与样本标准差','definition':'从唯一获准11540行summary的NC_core/row_micro直接取24可训练组合和两面板standard训练constantmedian；R²同坐标原值，无重新训练、无最小值显著性检验。','componentIds':['performance-brief','primary-performance'],'sourceLineage':[{'files':['final-v1/summary.json','root-final-summary-review-v1.json','all240-joint-frozen.json']}]}]}
d['queries']['primary_performance']={'rows':primary,'source':source}
receipt=load(ROOT/'reporting/final-v1/report-receipt.json');assert sha(ROOT/'reporting/final-v1/完整报告.md')==receipt['artifacts']['完整报告.md']
metadata=ROOT/'reporting/training-metadata-v1';mdmanifest=load(metadata/'FINAL-MANIFEST.json');mdhashes={Path(a['path']).name:a['sha256'] for a in mdmanifest['artifacts']}
logs=ROOT/'reporting/training-logs-v1';assert sha(logs/'verification.json')=='cb59429cb15c19526cbe632d3919ed6550c0b1de5f5440bf958feb23f78adb22';logv=load(logs/'verification.json');loghashes={Path(a['path']).name:a['sha256'] for a in logv['artifacts']}
docs=[]
for title,file,expected,purpose in [('完整指标报告',ROOT/'reporting/final-v1/完整报告.md',receipt['artifacts']['完整报告.md'],'内部／外部、micro／macro及10种子指标的完整叙述；原CSV和逐seed文件留在同目录。'),('超参数与训练元信息',metadata/'超参数与训练元信息.md',mdhashes['超参数与训练元信息.md'],'400NN＋80RF候选、240验证选择及两次技术中断；独立调参证据。'),('完整epoch预算诊断',logs/'预算诊断说明.md',loghashes['预算诊断说明.md'],'400份完整日志／40组：390候选按源码patience5在20轮前停止，10候选达到20轮。')]:
 assert sha(file)==expected
 docs.append({'title':title,'filename':file.name,'relative_path':file.relative_to(ROOT).as_posix(),'sha256':expected,'purpose':purpose,'markdown':file.read_bytes().decode('utf-8')})
d['queries']['report_documents']={'rows':docs,'source':{'label':'三份已绑定的独立报告原文','files':[{'name':r['relative_path'],'sha256':r['sha256']} for r in docs],'metricDefinitions':[{'label':'完整报告下载','definition':'下载内容是SHA绑定的Markdown原文；指标报告的可选训练元信息未绑定，不能理解为训练未核验。后两份独立证据补齐实际调优和完整epoch诊断。','componentIds':['report-downloads'],'sourceLineage':[{'files':[r['relative_path'] for r in docs]}]}]}}
fig=ROOT/'reporting/figures-v1/actual-v1/figures/png/fig_01_nc_mae.png';assert sha(fig)=='cea4b75cc4bcbfb40f521e6b6c923a10bdf1799913c859a84d30437a608a9e9a'
assets=APP/'src/content/assets';assets.mkdir(exist_ok=True);shutil.copyfile(fig,assets/'fig_01_nc_mae.png')
source['files'].append({'name':'fig_01_nc_mae.png','sha256':sha(fig)});source['metricDefinitions'][0]['componentIds'].append('primary-figure')
text=text.replace('import "./report.css";','import "./report.css";\nimport primaryFigure from "../assets/fig_01_nc_mae.png";')
text=text.replace('{id:"chemistry",label:', '{id:"dataset",label:"测试数据来源",field:"dataset_label",defaultValue:"PPIKB内部测试",queryIds:["metrics"]},\n  {id:"metric",label:"评价指标",field:"metric_id",defaultValue:"MAE",queryIds:["metrics"]},\n  {id:"chemistry",label:')
text=text.replace('col("evaluation_set_id","测试集")','col("evaluation_label","测试范围")')
text=text.replace('未来成绩','成绩').replace('未来表结构支持：','成绩表包含：')
text=text.replace('40个选择单元和80个候选完成属于训练状态，测试性能仍等待统一评测。','40个选择单元和80个候选均已完成；独立复算的测试指标现已进入上方成绩表。')
old='**训练已完成，评测仍在准备。** 本次指令时真实评测0，成绩表保持为空，待统一评分、独立复算及审阅后更新。这是静态快照，不是实时状态或性能结论。'
new='**训练与统一测试评分均已完成。** NN200个评分单元对应600份三数据集评分，RF40对应120份；NN600与RF120经独立复算，指标差异数均为0。另保留三个确定性参考及完整macro扩展。成绩现已导入；本节记录流程状态，不代替各测试范围的分母。'
assert old in text;text=text.replace(old,new).replace('title="训练完成，评测待更新 · 静态快照"','title="训练、统一评分与独立复算均已完成"')
d['queries']['phase_snapshot']['rows']=[r for r in d['queries']['phase_snapshot']['rows'] if r['label']!='本次状态快照时真实评测已执行']+[{'label':'完成的NN评分单元','count':200,'denominator':200},{'label':'完成的RF评分单元','count':40,'denominator':40},{'label':'独立复算NN600／RF120指标差异','count':0,'denominator':None}]
d['queries']['phase_snapshot']['source']['files'] += [{'name':'root-final-summary-review-v1.json','sha256':'8f4c9879ce356ddce03451bb2b5bf2798c503828ebc7587efd6665a6900d188f'}]
d['queries']['phase_snapshot']['source']['metricDefinitions'][0]['definition']='训练200NN选择/400有效候选及40RF选择/80候选完成；200NN与40RF评分单元完成。NN600/RF120独立复算0差异；两技术中断另保留，不增科学cell。旧训练完成时尚未评分的历史由旧源快照留存，当前由根最终审阅覆盖。'
d['queries']['phase_snapshot']['source']['evidenceFlow'].append({'title':'最终根审阅','detail':'根明确授权实际summary；NN600/RF120独立重算0差异，三个确定性参考和v6完整保留。'})
intro='''  <EvidenceText id="performance-brief" queryId="primary_performance" rows={rows("primary_performance")} value={"## 基准已完成，但泛化能力仍有限\\n\\n五个前人神经网络和另计的随机森林均完成共同数据、两个冷面板、两个训练方案及10种子的比较。来源＋肽依赖冷的NC测试有303条，**12个可训练组合的MAE都高于标准训练集常数中位数参考1.3178**。\\n\\n参考蛋白同源冷的NC测试有332条。可训练组合中，DeepNC-GEN只用NC训练的平均MAE最低，为**1.2978 ± 0.0554**；R²为**0.0638 ± 0.0551**。这是此次比较中显示的最小均值，不能据此宣称显著优势。±是10次训练的样本标准差，不是生物重复的置信区间。\\n\\n标准训练集更大，靶标和来源分布也不同。这些对照不能因果证明加入NC数据是否有用。分层、标准对照、冲突排除、外部67／8／2及另补8／5分别查看；2条参考靶标冷外测属于67，不能再相加。"}/>
  <DataComponent id="primary-performance" queryId="primary_performance" title="NC主任务：24个可训练组合与两个常数参考" kind="table" sourceRows={rows("primary_performance")} displayRows={rows("primary_performance")}>
   <DataTable rows={rows("primary_performance")} compactNumbers={false} label="NC主任务十种子聚合" columns={[col("panel_label","冷面板"),col("method_id","方法"),col("regime_label","训练队列"),col("MAE","MAE均值"),col("MAE_SD","MAE样本SD"),col("R2","R²均值"),col("R2_SD","R²样本SD"),col("n","NC测试记录"),col("defined_seeds","可定义种子数")]}/>
  </DataComponent>
  <ReportSection id="primary-figure" queryId="primary_performance" title="两个冷面板上的实际NC误差" sourceRows={rows("primary_performance")}>
   <img src={primaryFigure} alt="六个可训练模型在两个冷面板、两个训练队列上的NC测试MAE均值与十种子样本标准差" style={{width:"100%",height:"auto"}}/>
   <RichNarrative id="primary-figure:caption" value="左图NC测试303条，右图332条。实心为NC训练，斜线为标准训练；误差线是10训练种子的样本SD。图中未绘常数参考，需结合上表判断。" label="编辑主图说明"/>
   <a href={primaryFigure} download="fig_01_nc_mae.png">下载原始PNG</a>
  </ReportSection>
'''
needle='  <EvidenceText id="data-brief"';assert needle in text;text=text.replace(needle,intro+'\n'+needle,1)
downloads='''  <DataComponent id="report-downloads" queryId="report_documents" title="完整指标、实际调优和预算诊断报告" kind="table" sourceRows={rows("report_documents")} displayRows={rows("report_documents")}>
   <RichNarrative id="report-downloads:explain" value="三个报告分别保存：完整指标叙述、验证集调优证据，以及完整epoch预算诊断。指标报告中的可选训练元信息段未接入；实际调优已由第二份报告核验，390次patience5／10次达20轮来自第三份完整日志诊断，不能把原可选段的pending理解为训练未验。完整CSV和每种子指标仍保留在项目reporting/final-v1/，应用不替代原始交付。" label="编辑报告入口说明"/>
   <DataTable rows={rows("report_documents")} searchable={false} label="SHA绑定的独立报告" columns={[col("title","报告",{renderCell:(v,r)=><a href={"data:text/markdown;charset=utf-8,"+encodeURIComponent(r.markdown)} download={r.filename}>{v} · 下载Markdown</a>}),col("purpose","阅读用途"),col("relative_path","项目内位置"),col("sha256","SHA256",{renderCell:v=><abbr title={v}>{v.slice(0,12)}</abbr>})]}/>
  </DataComponent>
'''
needle='  <EvidenceText id="evidence-brief"';assert needle in text;text=text.replace(needle,downloads+'\n'+needle,1)
text=text.replace('这次优先研究含非标准残基的肽与蛋白的结合亲和力。先弄清测量是什么、哪些数据进入训练，以及测试真正隔离了什么。','含非标准残基肽的亲和力基准：先看实际结果，再核对数据、测试范围和代码来源。五个前人架构共同重训，另计随机森林与三个确定性参考。')
d['researchMetadata']['performanceRows']=6880;d['researchMetadata']['originalSummaryRows']=11540;d['researchMetadata']['macroRowsPreservedOutsideApp']=4600;d['researchMetadata']['rootExplicitAppDisplayExclusions']=60
d['researchMetadata']['coordinatorStatusSnapshot'].update(actualNNScoreUnitsComplete=200,actualRFScoreUnitsComplete=40,NNindependentMetricDifferences=0,RFindependentMetricDifferences=0,performanceSummaryReviewed=True)
d['researchMetadata']['reportingStatus']='reviewed performance with standalone training metadata and epoch diagnosis'
d['status']='reviewed_aggregate_data_methods_and_performance';d['buildStatus']='complete';d['generatedAt']=datetime.datetime.now(datetime.timezone.utc).isoformat()
dump(dpath,d);jsxpath.write_text(text,encoding='utf-8')
print(json.dumps({'metrics':6880,'primary_rows':26,'report_documents':3,'query_count':len(d['queries']),'buildStatus':'complete','same_app_id':d['id']},ensure_ascii=False))
