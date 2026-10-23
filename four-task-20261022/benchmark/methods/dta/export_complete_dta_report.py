"""Final export gate: all 150 independently accepted logical units, never a partial final report."""
from pathlib import Path,PureWindowsPath
import collections,csv,datetime as dt,hashlib,json,statistics
from stopping_rules import validate_stopping
H=Path(__file__).resolve().parent;R=H.parents[1]
METHODS=['GraphDTA-GIN','MGraphDTA','DGDTA-CL','DeepNC-GEN','GS-DTA']
VIEWS=['ppikb_kd_source_cold_scope_v2','ppikb_kd_target_cold_scope_v2','ppikb_effect_metadata_silver_source_cold']
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def local(raw):
 raw=str(raw)
 if len(raw)>2 and raw[1]==':':
  parts=PureWindowsPath(raw).parts;i=parts.index('peptide-four-task-benchmark-20261022');return R/Path(*parts[i+1:])
 if raw.startswith('/data/qlyu/projects/peptide-four-task-benchmark-20261022/') or raw.startswith('/mnt/d/work/科研工作台/research-tasks/peptide-four-task-benchmark-20261022/'):return R/raw.split('peptide-four-task-benchmark-20261022/',1)[1]
 return Path(raw)
def complete_gate(rows):
 keys=[tuple(x['logical_key']) for x in rows];expected={(v,m,s) for v in VIEWS for m in METHODS for s in range(10)}
 if len(keys)!=150 or len(set(keys))!=150 or set(keys)!=expected:raise ValueError('Final report requires every registered view/method/seed exactly once')
def stats(values):return {'mean':statistics.mean(values),'sd':statistics.stdev(values),'n_seeds':len(values)}
def csvwrite(path,rows):
 fields=list(dict.fromkeys(k for row in rows for k in row))
 with path.open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def main():
 pointer=load(H/'accepted-census-current.json');accepted=load(local(pointer['path']));assert sha(local(pointer['path']))==pointer['sha256'];complete_gate(accepted['records']);assert not accepted['unaccepted_observed']
 audits=list(H.glob('final-all150-independent-audit-*.json'))
 if not audits:raise ValueError('Final report also requires the fresh independent all150 label/metric/asset audit')
 final_audit=load(max(audits));assert final_audit['unit_count']==150 and final_audit['candidate_count']==300 and not final_audit['errors'] and final_audit['accepted_census_sha256']==pointer['sha256']
 detail_pointer=load(H/'accepted-details-current.json');conditional_pointer=load(H/'conditional-input-scores-current.json');conditional_path=local(conditional_pointer['path']);assert sha(conditional_path)==conditional_pointer['sha256'];conditional=load(conditional_path)
 assert conditional['accepted_units']==conditional['scored_units']==150 and not conditional['missing'] and conditional['source_accepted_details_sha256']==detail_pointer['sha256']
 input_proofs=[]
 for evidence in conditional['input_proofs']:
  p=local(evidence['path']);assert sha(p)==evidence['sha256'];r=load(p);assert r['runtime']['auditor_source_sha256']=='5c77fdbe679f1213e04d38109db40d45b6a0d9f32408f7078290997a32b25916';input_proofs.append({'path':str(p),'sha256':sha(p),'runtime':r['runtime'],'results':r['results']})
 cross_path=H/'cross-runtime-effective-input-comparison-20261023T074046Z.json';cross=load(cross_path)
 assert {cross['left_report_sha256'],cross['right_report_sha256']}=={p['sha256'] for p in input_proofs}
 assert cross['total_compared_overlap_rows_across_method_views']==cross['equal_consumed_input_fingerprint_rows']==71954
 for x in final_audit['units']:
  u=local(x['unit_path']);assert sha(u/'test-metrics.json')==x['test_metrics_sha256'] and sha(u/'complete.json')==x['complete_sha256']
 census=load(max(H.glob('common-formal-census-continuation-*.json')));assert not census['duplicate_conflicts'];units={(x['view'],x['method'],x['seed']):x for x in census['records']};assert len(units)==150
 raw=[];provenance=[];expected_n={};runtime=[]
 for v in VIEWS:
  for method in METHODS:
   for seed in range(10):
    entry=units[v,method,seed];unit=local(entry['path']).parent;c=load(unit/'complete.json');selection=load(unit/'selection.json');m=load(unit/'test-metrics.json');env=load(unit/'runtime.json');start=load(unit/'started.json')
    assert sha(unit/'selection.json')==c['selection_sha256'] and sha(unit/'test-predictions.jsonl')==c['prediction_sha256']
    assert len(selection['candidates'])==2 and {x['hyperparameters']['learning_rate'] for x in selection['candidates']}=={.001,.0003}
    assert selection['winner']==min(selection['candidates'],key=lambda x:(x['best_validation_score'],x['candidate_index']))['candidate_index'] and not selection['test_used_for_selection']
    epochs=[];stopping=[]
    for cand in selection['candidates']:
     folder=unit/('candidate-'+str(cand['candidate_index']));assert sha(folder/'best.pt')==cand['checkpoint_sha256'];assert sha(folder/'validation-predictions.jsonl')==cand['validation_predictions_sha256']
     logs=[json.loads(x) for x in (folder/'epochs.jsonl').read_text().splitlines() if x.strip()];assert 1<=len(logs)<=20;assert all(x['train_n']==c['sample_counts']['train'] for x in logs);epochs.append(len(logs))
     stopping.append(validate_stopping(logs,cand['best_epoch'],c['sample_counts']['train']))
    cohort=start['hostname']+' | '+env['torch']+' | numpy '+env.get('numpy','unknown')+' | '+('CPU' if start['device']=='cpu' else 'CUDA')
    for level,buckets in [('overall',{'all':m['all']}),('chemical_stratum',m['strata'])]:
     for name,scores in buckets.items():
      nk=(v,level,name);expected_n.setdefault(nk,scores['n']);assert expected_n[nk]==scores['n']
      for metric,value in scores.items():
       if metric!='n':raw.append({'view':v,'method':method,'seed':seed,'level':level,'stratum':name,'metric':metric,'value':value,'test_n':scores['n'],'runtime_cohort':cohort})
    runtime.append({'view':v,'method':method,'seed':seed,'runtime_cohort':cohort,'python_path':env['python_path'],'numpy':env.get('numpy'),'epochs_candidate0':epochs[0],'epochs_candidate1':epochs[1],'elapsed_seconds':c['elapsed_seconds'],'selected_candidate':selection['winner'],**{f'candidate{ci}_{k}':value for ci,record in enumerate(stopping) for k,value in record.items()}})
    provenance.append({'logical_key':[v,method,seed],'unit_path':str(unit),'source_spec_sha256':c['spec_sha256'],'selection_sha256':c['selection_sha256'],'test_predictions_sha256':c['prediction_sha256'],'candidate_checkpoints':[x['checkpoint_sha256'] for x in selection['candidates']]})
 buckets=collections.defaultdict(list)
 for x in raw:
  if x['value'] is not None:buckets[x['view'],x['method'],x['level'],x['stratum'],x['metric']].append(x)
 aggregate=[];cohorts=[]
 for (v,m,l,s,metric),values in buckets.items():
  aggregate.append({'view':v,'method':m,'level':l,'stratum':s,'metric':metric,'test_n':values[0]['test_n'],**stats([x['value'] for x in values]),'sd_scope':'mixed environments/backends and seeds'})
  by=collections.defaultdict(list)
  for x in values:by[x['runtime_cohort']].append(x)
  for cohort,rows in by.items():cohorts.append({'view':v,'method':m,'level':l,'stratum':s,'metric':metric,'runtime_cohort':cohort,'seeds':','.join(str(x['seed']) for x in rows),'mean':statistics.mean(x['value'] for x in rows),'sd':statistics.stdev(x['value'] for x in rows) if len(rows)>1 else None,'n_seeds':len(rows)})
 dest=H/('complete150-report-'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ'));dest.mkdir()
 for name,rows in [('all-seed-metrics.csv',raw),('ten-seed-summary.csv',aggregate),('runtime-stratified-summary.csv',cohorts),('actual-training-runtime.csv',runtime)]:csvwrite(dest/name,rows)
 (dest/'run-provenance.json').write_text(json.dumps(provenance,indent=2),encoding='utf-8')
 (dest/'effective-input-audit-provenance.json').write_text(json.dumps({'input_proofs':input_proofs,'cross_runtime_overlap_proof':{'path':str(cross_path),'sha256':sha(cross_path),'compared_method_view_row_entries':71954,'equal_consumed_input_fingerprints':71954,'scope':'actual overlapping cached inputs only; repeated biological observations, no model or gradient equivalence claim'},'conditional_scores_path':str(conditional_path),'conditional_scores_sha256':sha(conditional_path),'conditional_scored_units':150,'scope':'diagnostic input subsets, original fitted models/test splits and primary metrics unchanged'},indent=2),encoding='utf-8')
 lines=['# 五种作者架构共同数据亲和力基准：完整150单元','',f'15个模型×视图组合均取得10个种子，合计150个独立验收正式单元和300个验证候选。验收索引：{pointer["path"]}。','', '采用来源留出pKd、靶标留出pKd和来源留出metadata-silver ΔpKd三个视图；训练/验证/测试分别为7125/977/1014、6355/1378/1383、1988/172/129。每个种子比较学习率0.001/0.0003，Adam、batch16、最多20 epoch、patience5，按验证MAE选择后评价测试集。', '', '| 视图 | 方法 | MAE均值±SD | RMSE均值±SD | R²均值±SD |','|---|---|---:|---:|---:|']
 def text(v,m,metric):
  x=next(x for x in aggregate if (x['view'],x['method'],x['level'],x['metric'])==(v,m,'overall',metric));return f'{x["mean"]:.5f} ± {x["sd"]:.5f}'
 for v in VIEWS:
  for m in METHODS:lines.append('| '+v+' | '+m+' | '+' | '.join(text(v,m,k) for k in ['MAE','RMSE','R2'])+' |')
 lines += ['','输入有效信息审计使用原缓存中实际参与forward的x、edge_index和蛋白token，逐dtype、shape和bytes哈希；MGraph储存但未读取的edge_attr另存容器哈希。原测试集不重划，另列排除已见有效输入、蛋白截断和同输入原始类别注释不一致后的诊断评分。完整结果见effective-input-audit-provenance.json所链接的150单元条件评分。该审计处理有序张量精确等价；图同构下等价可能更多。']
 lines+=['','完整逐种子结果、标准肽/非天然残基/PTM等化学类别结果和运行环境分层分别保存在all-seed-metrics.csv、ten-seed-summary.csv和runtime-stratified-summary.csv。实际每候选epoch数和耗时列于actual-training-runtime.csv。', '', '这些方法以作者DTA架构处理肽完整分子图和蛋白序列；改动任务使用同一势函数f(mut)-f(wt)和差值MSE。DGDTA-CL是历史索引别名，DGDTA原训练本身使用MSE。五方法在本轮承担绝对亲和力及改动效应；二分类和接触位点的原生适用性由整体任务矩阵单列。', '', '解释范围：metadata-silver配对尚未逐篇认证实验条件；五种图特征均省略手性，DGDTA还省略显式键级；蛋白前缀上限为MGraph1200 aa、其他1000 aa。整体基准中的独立Morgan化学对照显式includeChirality=True，已有D/L差异及磷酸化canary，可用于检查输入中已标注的立体信息；参见baselines/molecular/molecular_features.py和molecular-delivery-audit.json。WSL Torch2.12/RDKit26、Node1 Torch2.6/RDKit24/no-cuDNN和Node23 CPU环境共同构成结果，汇总SD同时包含种子和环境差异。已验证的19项预处理tensor等价只限同一RDKit24环境，跨RDKit版本的特征逐bit等价没有作为假设。', '', '所有旧失败、超时和中断保留独立输出；统计按(view,method,seed)取唯一已验收结果。外部验证在独立报告中呈现。']
 lines+=['','跨环境补充实证：两个已冻结缓存报告的实际重叠部分共有71954个方法×视图×记录条目，其forward消费张量哈希逐项相同。该数量重复使用生物学记录，不表示独立实验数；无缓存的运行组合仍单独列缺口，结论不延伸至参数、梯度或后端的逐位一致。证据路径与SHA已写入effective-input-audit-provenance.json。']
 capped=sum(x[f'candidate{ci}_epoch_bound_without_patience'] for x in runtime for ci in range(2))
 lines+=['',f'训练停止规则核验：300个候选中，{capped}个达到20轮上限时尚未耗尽patience5，其余候选已触发早停。每个候选的最佳验证轮次、停止时连续未改进轮数和停止原因均在actual-training-runtime.csv。达到预算上限不等于已经收敛；该统计描述本轮固定预算，不更改既有训练或成绩。']
 (dest/'完整结果报告.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 manifest=[{'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)} for p in dest.iterdir() if p.is_file()];(dest/'delivery-manifest.json').write_text(json.dumps({'accepted':150,'candidate_fits':300,'source_accepted_census_sha256':pointer['sha256'],'files':manifest},indent=2),encoding='utf-8');print(json.dumps({'path':str(dest),'accepted':150,'candidate_fits':300}))
if __name__=='__main__':main()
