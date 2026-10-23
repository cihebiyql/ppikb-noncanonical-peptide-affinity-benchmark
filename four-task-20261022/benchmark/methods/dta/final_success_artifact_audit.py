import json,hashlib,datetime as dt
from pathlib import Path
H=Path(__file__).resolve().parent;R=H.parents[1];src=H/'common-formal-census-20261023T013530Z.json';data=json.loads(src.read_text());cpu={};route={}
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
for phase in ['node23-cpu-v1','node23-cpu-recovery-v2']:
 for j in load(H/phase/'jobs.json')['jobs']:
  if j['stage']=='formal':cpu[(j['view_id'],j['method_id'],j['seed'])]=j
for name in ['routed-gpu-audit-local.json','routed-gpu-audit-node1.json']:
 for row in load(R/'resources'/name)['rows']:
  if row.get('complete_verified'):route[tuple(row['logical_key'])]=dict(row,audit_file=name)
records=[]
for r in data['records']:
 key=(r['view'],r['method'],r['seed']);p=Path(r['path']).parent;c=load(p/'complete.json');s=load(p/'selection.json');checks={'test_prediction':sha(p/'test-predictions.jsonl')==c['prediction_sha256'],'selection':sha(p/'selection.json')==c['selection_sha256']};assetpaths=[p/'complete.json',p/'selection.json',p/'test-predictions.jsonl',p/'test-metrics.json',p/'runtime.json',p/'started.json']
 for q in s['candidates']:
  d=p/('candidate-'+str(q['candidate_index']));ci=str(q['candidate_index']);checks['candidate'+ci+'_weight']=sha(d/'best.pt')==q['checkpoint_sha256'];checks['candidate'+ci+'_validation_prediction']=sha(d/'validation-predictions.jsonl')==q['validation_predictions_sha256'];checks['candidate'+ci+'_complete']=(d/'complete.json').exists();checks['candidate'+ci+'_epochs']=(d/'epochs.jsonl').exists();assetpaths.extend(x for x in d.iterdir() if x.is_file())
 if key in route:
  rr=route[key];checks['actual_resource_route_complete']=rr['complete_verified'] and rr['spec_sha256']==c['spec_sha256'];evidence={'kind':'GPU actual resource owner exit/source/selection audit','path':str(R/'resources'/rr['audit_file']),'job_id':rr['job_id']}
 else:
  j=cpu[key];log=R/Path(j['run_dir'].replace('/data/qlyu/projects/peptide-four-task-benchmark-20261022/',''));receipt=load(log/'process-receipt.json');val=load(log/'result-validation.json');checks['actual_CPU_terminal']=receipt['exit_code']==0 and receipt['termination_reason'] is None and receipt['worker_pid_absent'] and not receipt['residual_group_pids_before_cleanup'];checks['CPU_standard_acceptance']=val['valid_for_acceptance'];checks['CPU_spec_binding']=j['spec_sha256']==c['spec_sha256'];evidence={'kind':'CPU actual terminal and standard result acceptance','path':str(log/'process-receipt.json')}
 records.append({'view':key[0],'method':key[1],'seed':key[2],'checks':checks,'all_passed':all(checks.values()),'evidence':evidence,'local_artifacts':[{'path':str(a),'bytes':a.stat().st_size,'sha256':sha(a)} for a in assetpaths]})
assert len(records)==59 and all(r['all_passed'] for r in records)
out=H/'final-success-artifact-audit-20261023T0137Z.json';out.write_text(json.dumps({'at':dt.datetime.now(dt.timezone.utc).isoformat(),'source_census':str(src),'records':records,'all_59_present_and_sha_valid':True,'logical_units':59,'all_candidate_checkpoints':sum(sum(k.endswith('_weight') for k in r['checks']) for r in records)},indent=2));print(json.dumps({'path':str(out),'units':len(records),'candidate_checkpoints':sum(sum(k.endswith('_weight') for k in r['checks']) for r in records),'all_passed':True}))
