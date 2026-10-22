"""Update only reviewed report UI/asset metadata; never load performance data."""
from pathlib import Path
import datetime,json,hashlib,copy
P=Path(__file__).resolve().parent; ROOT=P.parent; APP=P/'app'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p): return json.loads(p.read_text(encoding='utf-8'))
def write(p,v): p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
dpath=APP/'src/data.json'; jpath=APP/'src/content/report/ReportContent.jsx'
d=load(dpath); old=copy.deepcopy(d); text=jpath.read_text(encoding='utf-8')
assert d['id']=='report:5569696c-9519-43ed-9a7a-073a11d14850' and d['queries']['metrics']['rows']==[]
assets=ROOT/'resources/upstream-full-v1'; delivery=load(assets/'DELIVERY-MANIFEST.json')
assert sha(assets/'DELIVERY-MANIFEST.json')=='92b7a9e77caadb084fa35380d31b43b20710e38093b444484b2f396eddffb425'
for name in ['manifest.json','asset-integrity-verification.json']:
 assert sha(assets/name)==delivery['files_sha256'][name]
m=load(assets/'manifest.json'); verification=load(assets/'asset-integrity-verification.json')
assert delivery['total_source_files']==129 and delivery['total_archives']==5
rows=[]
for r in m['repositories']:
 v=next(v for v in verification['repositories'] if v['method_id']==r['method_id'])
 author=next(a for a in d['queries']['methods']['rows'] if a['method']==r['method_id'])
 assert r['commit']==author['commit'] and r['repository_url']==author['repository']
 assert r['file_count']==v['git_blob_sha1_match_count'] and v['exact_git_blob_path_set_match']
 rows.append({k:r[k] for k in ['method_id','commit','official_archive_url','file_count','archive_bytes','archive_sha256','evaluation_split_script_candidate_count','license_status']})
assert sum(r['file_count'] for r in rows)==129
files=[{'name':f'upstream-full-v1/{n}','sha256':sha(assets/n)} for n in ['DELIVERY-MANIFEST.json','manifest.json','asset-integrity-verification.json']]
d['queries']['upstream_assets']={'rows':rows,'source':{'label':'五个官方确切commit完整文件归档：129文件','files':files,'metricDefinitions':[{'label':'完整仓库文件快照','definition':'固定commit的完整官方文件归档；文件路径集与Git blob SHA1逐一核验，不含完整Git历史，也未额外下载外链数据。评价脚本数量是候选文件清点，不是已复现任务数。','componentIds':['upstream-assets-brief','upstream-assets-table'],'sourceLineage':[{'files':[f['name'] for f in files]}]}],'evidenceFlow':[{'title':'冻结完整归档元数据','detail':'5个官方确切commit ZIP，129文件，26892727压缩字节；CRC、解压文件SHA256与官方Git blob SHA1一致。仅读取manifest/验证元数据，不执行作者代码。'}],'links':[{'label':r['method_id']+' 官方commit ZIP','url':r['official_archive_url']} for r in rows]}}
closed=ROOT/'launch/pool-runs-v6-cuda-recovery02/progress.json'
closed_progress=load(closed)
# Read the closed producer metadata only; don't follow any referenced model/prediction/label paths.
write(P/'final-ui-training-state-source.json',{'schema':'root-verified-training-status-snapshot-v1','as_of_date':'2026-10-22','exact_snapshot_time_provided':False,'root_instruction_verified':True,'NN_selections_complete':200,'NN_valid_candidate_fits_complete':400,'RF_selections_complete':40,'RF_candidate_fits_complete':80,'technical_interrupted_attempts_retained':2,'actual_scientific_scores_at_instruction':0,'native_training_pool_exit_code':0,'native_exit_observer':'root actual wait; not independently inferred by UI author','closed_progress_source':'pool-runs-v6-cuda-recovery02/progress.json','closed_progress_sha256':sha(closed),'read_scope':'closed training-state metadata only; no weights/gold/predictions/metrics','full_report_status':'actively updating; performance audit pending'})
statusfile=P/'final-ui-training-state-source.json'
d['queries']['phase_snapshot']['rows']=[{'label':label,'count':count,'denominator':den} for label,count,den in [('NC神经网络选择完成',100,100),('标准神经网络选择完成',100,100),('全部神经网络选择完成',200,200),('有效神经网络候选fit完成',400,400),('RF选择完成',40,40),('RF候选fit完成',80,80),('已保存的技术中断attempt',2,None),('本次状态快照时真实评测已执行',0,None)]]
d['queries']['phase_snapshot']['source']={'label':'协调者核验训练完成的同线程快照；非实时','files':[{'name':statusfile.name,'sha256':sha(statusfile)},{'name':'pool-runs-v6-cuda-recovery02/progress.json','sha256':sha(closed)}],'metricDefinitions':[{'label':'训练完成与评价分开记录','definition':'协调者已核200个NN选择、400有效NN候选fit及RF40选择/80候选完成，恢复pool native exit0；两个历史技术中断保留，不计为新增种子或科学cell。指令时真实评价0，后续状态不自动刷新。','componentIds':['phase-snapshot'],'sourceLineage':[{'files':[statusfile.name,'pool-runs-v6-cuda-recovery02/progress.json']}]}],'evidenceFlow':[{'title':'协调者同线程最终UI准备指令','detail':'只同步已核验的闭合训练状态，不把训练完成当成性能。精确指令时刻未提供，真实评测仍等待独立复算和审阅。'}]}
d['researchMetadata']['coordinatorStatusSnapshot']={'label':'协调者已核验训练完成快照，非实时','asOfDate':'2026-10-22','exactTimestampKnown':False,'NCNeuralSelectionsComplete':100,'standardNeuralSelectionsComplete':100,'standardNeuralSelectionsInProgress':False,'totalNeuralSelectionsComplete':200,'validNeuralCandidateFitsComplete':400,'randomForestSelectionsComplete':40,'randomForestCandidateFitsComplete':80,'technicalInterruptedAttemptsRetained':2,'actualTestEvaluationsAtSnapshot':0}
d['buildStatus']='updating'; d['generatedAt']=datetime.datetime.now(datetime.timezone.utc).isoformat()
text=text.replace('col("seed_count","实际种子数")','col("seed_count","可定义种子数")')
text=text.replace('样本数和种子数。','样本数和可定义种子数。')
text=text.replace('**10个随机种子是同一份固定数据上的10次训练，不是10份独立数据。** 计划报告MAE、RMSE、Pearson、Spearman和R²，并保留每个种子的结果；常数或样本不足时，按指标定义保留未定义值。','**10个随机种子是同一份固定数据上的10次训练，不是10份独立数据。** 保留每个种子的MAE、RMSE、Pearson、Spearman和R²。表中“可定义种子数”只计算该指标有定义的次数：即使10次训练全部完成，若相关系数因真值或预测为常量而无法定义，这一列也可能是0；不表示训练缺失。均值和样本标准差只汇总有定义值。\\n\\n应用成绩表仅展示按观测记录汇总的micro结果及匹配子集micro结果，样本数n是测量记录数。按母体、来源或靶标分组的macro结果保留在完整Markdown／CSV报告中，不能把分组数量填成这里的样本数。')
oldphase='本轮指令提供的2026-10-22状态：NC神经网络100个选择完成，标准100个仍在推进；当时总计104个完成，RF40完成选择，真实测试0。这里只作静态背景，不随训练实时变化，也不代表成绩。'
newphase='协调者已核验的2026-10-22状态：五个神经网络在两个面板、两个训练方案和10个种子下的200个选择、400个有效候选fit全部完成；RF另有40个选择、80个候选完成。两个历史技术中断的记录保留，不算新增种子。\\n\\n**训练已完成，评测仍在准备。** 本次指令时真实评测0，成绩表保持为空，待统一评分、独立复算及审阅后更新。这是静态快照，不是实时状态或性能结论。'
assert oldphase in text; text=text.replace(oldphase,newphase).replace('title="协调者准备状态快照 · 非实时"','title="训练完成，评测待更新 · 静态快照"')
needle='  <DataComponent id="rf-reference"'
newblock='''  <EvidenceText id="upstream-assets-brief" queryId="upstream_assets" rows={rows("upstream_assets")} value={"### 五个官方仓库的完整文件也已归档\\n\\n固定上述commit下载了5个官方ZIP，共129个文件、26,892,727压缩字节。归档位于项目的`resources/upstream-full-v1/`；各仓库的清单同时记录评价／划分代码候选。所有文件已核对CRC、解压SHA256及官方Git blob SHA1，95个早期选定源码文件也逐字节一致。\\n\\n下表可打开官方同版本ZIP，并查看归档SHA。这里的完整指该commit的文件快照，不含完整Git历史或另行下载的外链数据；训练所用适配源码仍以原冻结版本为准。"}/>
  <DataComponent id="upstream-assets-table" queryId="upstream_assets" title="五个完整仓库资产入口" kind="table" sourceRows={rows("upstream_assets")} displayRows={rows("upstream_assets")}>
   <DataTable rows={rows("upstream_assets")} searchable={false} compactNumbers={false} label="完整作者仓库归档" columns={[col("method_id","方法"),col("official_archive_url","固定版本",{renderCell:(v,r)=><a href={v} target="_blank" rel="noreferrer">官方ZIP · {r.commit.slice(0,12)}</a>}),col("file_count","文件数"),col("evaluation_split_script_candidate_count","评价／划分候选文件"),col("archive_sha256","归档SHA256",{renderCell:v=><abbr title={v}>{v.slice(0,12)}</abbr>})]}/>
  </DataComponent>
'''
assert needle in text and 'id="upstream-assets-table"' not in text
text=text.replace(needle,newblock+needle,1)
assert '104个完成' not in text and '实际种子数' not in text
for key in old['queries']:
 if key!='phase_snapshot': assert old['queries'][key]==d['queries'][key],key
backup=P/'final-ui-preparation-history'; backup.mkdir(exist_ok=True)
for source,name in [(dpath,'data.before.json'),(jpath,'ReportContent.before.jsx')]:
 dest=backup/name
 if not dest.exists(): dest.write_bytes(source.read_bytes())
write(dpath,d);jpath.write_text(text,encoding='utf-8')
write(P/'final-ui-preparation.json',{'stage':'final_ui_preparation_before_reviewed_metrics','build_status':'updating','app_id':d['id'],'performance_rows':0,'upstream_files':129,'upstream_delivery_sha256':sha(assets/'DELIVERY-MANIFEST.json'),'training_state_source_sha256':sha(statusfile),'unchanged_existing_scientific_queries':[k for k in old['queries'] if k!='phase_snapshot'],'metric_mapper_importer_schema_changed':False,'browser_control':False,'real_gold_predictions_weights_metrics_read':False})
print('UI updated; 16 queries, performance rows 0; scientific query values unchanged.')
