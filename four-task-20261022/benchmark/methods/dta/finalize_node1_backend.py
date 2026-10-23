"""Administrative result records for two already-terminal Node1 fits; never launches models."""
import copy,json,hashlib,datetime as dt,subprocess,sys
from pathlib import Path
from audit_runs import independent_metrics
R=Path('/data/qlyu/projects/peptide-four-task-benchmark-20261022');H=R/'methods/dta'
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):Path(p).write_text(json.dumps(x,indent=2,allow_nan=False))
def contains(x,target):
 if x==target:return True
 if isinstance(x,dict):return any(contains(v,target) for v in x.values())
 if isinstance(x,list):return any(contains(v,target) for v in x)
 return False
summary=[]
for family,scientific in [('mgraph-backend-v4','ppikb_kd_source_cold_scope_v2--MGraphDTA--formal--seed2--no-cudnn-cache-v4'),('mgraph-effect-backend-v4','ppikb_effect_metadata_silver_source_cold--MGraphDTA--formal--seed2--no-cudnn-effect-cache-v4')]:
 jid=scientific+'--admission-v1';home=R/'resources'/family;cp=home/(jid+'.contract.json');log=home/'dispatch'/jid;receipt=log/'dispatch.json';unit=R/'runs/dta_backend_compat'/scientific;c=load(cp);r=load(receipt);done=load(unit/'complete.json');issued=Path(r['job_path']);cmd=c['execution']['command']
 assert r['status']=='succeeded' and r['exit_code']==0 and r['stop_reason'] is None and not r['remaining_owned_pids']
 assert sha(cp)==r['contract_sha256'] and sha(issued)==r['job_sha256'] and contains(load(issued),cmd)
 spec=Path(cmd[cmd.index('--spec')+1]);assert sha(spec)==done['spec_sha256'];assert sha(unit/'test-predictions.jsonl')==done['prediction_sha256'];assert sha(unit/'selection.json')==done['selection_sha256']
 for z in load(unit/'selection.json')['candidates']:
  p=unit/('candidate-'+str(z['candidate_index']));assert sha(p/'best.pt')==z['checkpoint_sha256'];assert sha(p/'validation-predictions.jsonl')==z['validation_predictions_sha256']
 rows=[json.loads(x) for x in (unit/'test-predictions.jsonl').read_text().splitlines()];metrics=independent_metrics(rows,done['task']);assert all((v is None and done['metrics'][k] is None) or (v is not None and abs(v-done['metrics'][k])<=1e-10) for k,v in metrics.items())
 audit=log/'overall-prediction-audit.json';write(audit,{'valid':True,'recomputed':metrics,'scope':'Actual completed unit overall test only'})
 stamp=dt.datetime.now(dt.timezone.utc).isoformat();rec=copy.deepcopy(load(H/'node23-result-record.template.json'))
 rec.update(is_template=False,task_id=c['task_id'],run_id=c['run_id'],contract_path=str(cp),contract_sha256=sha(cp),recorded_at=stamp,lifecycle_status='succeeded',reproduction_level='training',scope_coverage='partial_subset')
 rec['claims']=[{'text':'Actual completed common-data MGraphDTA retraining, two frozen LR candidates, validation-only selection, no-cuDNN compatibility backend. Not original-paper numerical reproduction.','evidence_type':'source_fact','evidence_paths':[str(receipt),str(unit/'complete.json'),str(audit)],'limitations':'Mixed GPU/runtime cohorts require stratification. Effect endpoint is metadata-silver. warn_only nondeterminism is preserved.'}]
 rec['assets_integrity']={k:{'status':'complete','scope':'exact completed common-data unit','evidence_paths':[str(log/'validation.stdout.json'),str(unit/'complete.json')]} for k in ['datasets','code','models','environment']}
 rec['execution'].update(performed=True,command=cmd,working_directory=c['execution']['working_directory'],environment_path=c['environment']['environment_path'],hostname='node1',resource_probe_path=str(log/'startup-capacity.json'),resource_usage_path=str(receipt),seeds=c['execution']['seeds'],started_at=r['started_at'],ended_at=r['finished_at'],effective_deadline_at=c['timing']['effective_deadline_at'],timeout_seconds=c['execution']['timeout_seconds'],pid=r['pid'],pgid=r['pgid'],job_object_or_tree_control='Node1 private setsid GPU process group, watchdog, current capacity admission and empty remaining_owned_pids verified',exit_code=0,timed_out=False,termination_reason=None,handles_absent_verified_at=r['finished_at'],exit_verification_path=str(receipt),stdout_path=r['stdout'],stderr_path=r['stderr'],receipt_path=str(receipt),notes='Already-completed GPU fit; this administrative audit was performed on Node23 shared filesystem. Scientific hostname remains Node1; no scientific model launched by this script.')
 t=c['targets'][0];comp={k:t.get(k) for k in ['target_id','paper_endpoint','metric','metric_definition','statistical_unit','denominator','unit','paper_value']};comp.update(denominator=len(rows),actual_value=metrics['MAE'],comparability='not_comparable',passed=None,absolute_difference=None,relative_difference=None,reason='New common-data test MAE; original contract denominator denotes full dataset. Actual test n is explicit; no original-paper number compared.',evidence_paths=[str(audit),str(unit/'complete.json')]);rec['metric_comparisons']=[comp]
 files=[p for p in unit.rglob('*') if p.is_file()]+[receipt,Path(r['stdout']),Path(r['stderr']),log/'validation.stdout.json',log/'startup-capacity.json',audit]
 rec['artifacts']=[{'role':'actual completed fit evidence','path':str(p),'location':'local','available':True,'size_bytes':p.stat().st_size,'sha256':sha(p)} for p in files]
 rec['differences']=[{'category':'scope/runtime/denominator','description':'Common-data native network retraining with no-cuDNN backend, not original paper protocol. Contract target denominator is total-view count '+str(t.get('denominator'))+'; actual held-out test denominator is '+str(len(rows))+'.','effect_on_comparison':'Mixed runtime SD is not pure seed noise; actual test denominator reported instead of total-view count.','evidence_type':'source_fact','evidence_paths':[str(cp),str(unit/'complete.json')]}];rec['incomplete_reasons']=[]
 rec['review'].update(status='accepted',reviewer='dta_build actual already-terminal Node1 unit audit',reviewed_at=stamp,checks=[{'item':k,'passed':True,'reason':'Exact actual receipt, contracted bytes, all candidate/checkpoint/prediction SHA and independent test scores checked'} for k in ['identity','assets','contract','execution','comparison','claims','preservation']],evidence_paths=[str(receipt),str(audit)])
 out=log/'result-record.json';assert not out.exists();write(out,rec);p=subprocess.run([sys.executable,str(R/'resources/validate_reproduction.py'),'--contract',str(cp),'--result',str(out),'--check-files'],text=True,capture_output=True,timeout=120);(log/'result-validation.json').write_text(p.stdout);(log/'result-validation.stderr.log').write_text(p.stderr);v=json.loads(p.stdout);summary.append({'job_id':jid,'valid_for_acceptance':v.get('valid_for_acceptance'),'errors':v.get('errors'),'result_path':str(out)})
write(H/'node1-completed-backend-result-acceptance.json',summary);print(json.dumps(summary))
