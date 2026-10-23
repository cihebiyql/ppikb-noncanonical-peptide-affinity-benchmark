"""Node23 continuation CPU admission; eight CPU2 fits, each independently bounded."""
import argparse,copy,datetime as dt,fcntl,hashlib,importlib.util,json,os,signal,socket,subprocess,sys,time
from pathlib import Path
R=Path('/data/qlyu/projects/peptide-four-task-benchmark-20261022');D=R/'methods/dta';H=D/'continuation-cpu-v2';PY='/data/qlyu/projects/peptide-binding-benchmark-20261020/common-prior-methods-20261021/.venv/bin/python';GIB=1024**3
s=importlib.util.spec_from_file_location('original_cpu_admission_helpers',D/'node23_cpu_pool_recovery_v3.py');p=importlib.util.module_from_spec(s);s.loader.exec_module(p)
sys.path.insert(0,str(R/'resources/continuation-20261023'))
import work_ownership_v2 as ownership
OWNER='node23-cpu'
def folder_of(j):return R/j['dispatch_relative_path']
def load(x):return p.load(x)
def sha(x):return p.sha(x)
def write(x,y):return p.write(x,y)
def now():return dt.datetime.now(dt.timezone.utc)
def live(pid,needle):
 q=Path('/proc')/str(pid)
 try:return q.stat().st_uid==os.getuid() and needle in (q/'cmdline').read_bytes().replace(b'\0',b' ').decode() and (q/'stat').read_text().split(')')[-1].split()[0]!='Z'
 except OSError:return False

def issue(j,folder):
 source=H/'previous-contracts'/Path(j['previous_contract_relative_path']).name;assert sha(source)==j['previous_contract_sha256'];c=copy.deepcopy(load(source));sp=R/j['spec_relative_path'];assert sha(sp)==j['spec_sha256'];spec=load(sp);stamp=now();opened=stamp.isoformat();deadline=(stamp+dt.timedelta(seconds=j['timeout_seconds']+300)).isoformat();jid=j['job_id']+'--resource-attempt1';argv=[PY,str(D/'train.py'),'--spec',str(sp),'--device','cpu'];probe=H/'probe-runtime.json'
 c.update(run_id=jid,created_at=opened,frozen_at=opened,contract_status='frozen',revision_reason='Direct user cancels total campaign cap; only missing CPU-owned fit, original scientific parameters unchanged, new independently bounded resource attempt.')
 c['execution_scope'].update(prior_run_ids=[load(source)['run_id']],relation_to_prior_run='Preserve original clock/expired and all earlier attempts; this is new common-data training under explicit continuation, not a restart of original paper full numerical reproduction.')
 c['timing'].update(prior_window_expired=True,retry_resets_clock=False,effective_deadline_at=deadline)
 c['campaign_continuation']={'schema':'paper-reproduction.campaign-continuation-contract.v1','campaign_id':'peptide-four-task-benchmark-20261022','mode':'campaign_total_cap_cancelled','authorization_path':str(R/'protocol/continuation-20261023/user-authorization.json'),'authorization_sha256':'26d34d9a771eed511245636598dee04df772179b84c74c0d38704d43a0d644fb','task_identity_path':str(R/'protocol/USER_REQUEST.txt'),'task_identity_sha256':'fcb526ed2732827a7e45e1e3f29c678847352f71d6039b1a81c758ae745dcb12','frozen_view_manifest_path':str(R/'protocol/continuation-20261023/frozen-view-manifest.json'),'frozen_view_manifest_sha256':'09be156624350725201177baccc34b83d7e41642e546c279f281708b917bb4a4','previous_contract_path':str(source),'previous_contract_sha256':sha(source),'job_window':{'opened_at':opened,'deadline_at':deadline}}
 replaced=0
 for a in c['assets']['code']:
  if a.get('path','').replace(str(R)+'/','')==j['base_spec_relative_path']:
   a.update(path=str(sp),sha256=sha(sp),archive_sha256=sha(sp));replaced+=1
 assert replaced==1
 for path,role in [(R/'resources/validate_reproduction_continuation.py','task-private explicit user continuation gate'),(R/'resources/cpu_supervise_node23.py','independent CPU PGID/RSS watchdog'),(R/'resources/continuation-20261023/work_ownership_v2.py','atomic logical-key ownership gate')]:c['assets']['code'].append({'role':role,'path':str(path),'archive_sha256':sha(path),'integrity':'complete'})
 c['environment'].update(environment_path=str(Path(PY).parent.parent),lockfile_path=str(probe),lockfile_sha256=sha(probe),shared_environment_modified=False)
 c['resources'].update(expected_hostname='node23',cpu_threads=2,data_loader_workers=0,memory_limit_bytes=4*GIB,gpu_devices=[],gpu_memory_budget_bytes=0,resource_probe_path=str(probe),resource_probe_at=load(probe)['at'],start_gate='Fresh3frames>=40%idle,available>=36GiB,UIDRSS+4GiB<=80GiB;max8 DTA CPU2 fits;reserve SWING0-7/32-39,never preempt',no_preemption=True)
 c['execution'].update(command=argv,working_directory=str(R),timeout_seconds=j['timeout_seconds'],stdout_path=str(folder/'stdout.log'),stderr_path=str(folder/'stderr.log'));c['execution']['process_control']={'platform':'linux','mechanism':'independent private PGID/RSS/wall watchdog, no campaign deadline reset','whole_tree_bounded':True};c['targets'][0].update(denominator=spec['paths']['test']['n'],comparison_endpoint='strict frozen held-out test; new common-data architecture transfer')
 cp=folder/'task-contract.json';write(cp,c);return cp,c,argv

def start(j,slot,probe,token):
 folder=folder_of(j);folder.mkdir(parents=True,exist_ok=False)
 write(folder/'ownership-claim.json',{'token':token,'logical_key':[j['view_id'],j['method_id'],j['seed']],'ledger_path':str(ownership.LEDGER)})
 for n in ['stdout.log','stderr.log']:(folder/n).touch()
 cp,c,argv=issue(j,folder);validation=subprocess.run([PY,str(R/'resources/validate_reproduction_continuation.py'),'--contract',str(cp),'--check-files'],capture_output=True,text=True,timeout=120);(folder/'validation.stdout.json').write_text(validation.stdout);(folder/'validation.stderr.log').write_text(validation.stderr);gate=json.loads(validation.stdout)
 if validation.returncode or not gate.get('valid_for_execution'):write(folder/'gate-rejected.json',{'model_launched':False,'gate':gate});return False
 hashes=[{'path':str(cp),'sha256':sha(cp)},{'path':str(R/j['spec_relative_path']),'sha256':j['spec_sha256']}]
 for cat,key in [('datasets','manifest_sha256'),('code','archive_sha256')]:hashes.extend({'path':a['path'],'sha256':a[key]} for a in c['assets'][cat] if a.get('path') and a.get(key))
 supervisor=folder/'supervisor-spec.json';write(supervisor,{'output':str(folder),'input_hashes':hashes,'contract_validation':gate,'command':argv,'cwd':str(R),'cpu_threads':2,'cpu_offset':slot,'memory_limit_bytes':4*GIB,'timeout_seconds':j['timeout_seconds'],'deadline_at':c['timing']['effective_deadline_at'],'gpu':None,'environment':{'CUDA_VISIBLE_DEVICES':'','PYTHONHASHSEED':str(j['seed'])}});write(folder/'capacity-gate.json',probe)
 env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',NUMEXPR_NUM_THREADS='2');out=(folder/'controller.stdout.log').open('w');err=(folder/'controller.stderr.log').open('w');q=subprocess.Popen([PY,str(R/'resources/cpu_supervise_node23.py'),'--spec',str(supervisor)],cwd=R,env=env,stdout=out,stderr=err,start_new_session=True,preexec_fn=lambda:os.nice(15));out.close();err.close();write(folder/'pool-launch.json',{'at':now().isoformat(),'supervisor_pid':q.pid,'job_id':j['job_id'],'cpu_affinity':[slot,slot+1],'contract_sha256':sha(cp),'spec_sha256':j['spec_sha256'],'supervisor_spec_sha256':sha(supervisor)});print(json.dumps({'started':j['job_id'],'supervisor_pid':q.pid,'cpu_affinity':[slot,slot+1]}),flush=True);return True

def state(j):
 folder=folder_of(j);out=R/j['output_root'];complete=out/'complete.json';receipt=folder/'process-receipt.json'
 if complete.exists() and receipt.exists():
  c=load(complete);r=load(receipt)
  if r['exit_code']==0 and r['termination_reason'] is None and c['spec_sha256']==j['spec_sha256'] and sha(out/'test-predictions.jsonl')==c['prediction_sha256']:return 'complete'
 if not folder.exists():return 'pending'
 for f,key,needle in [('launch.json','pid',str(R/j['spec_relative_path'])),('pool-launch.json','supervisor_pid',str(folder/'supervisor-spec.json'))]:
  if (folder/f).exists() and live(load(folder/f)[key],needle):return 'active'
 return 'failed_or_partial_preserved'

def global_state(j,ledger):
 e=ledger['entries'][ownership.key([j['view_id'],j['method_id'],j['seed']])]
 if e['owner']!=OWNER:
  return 'complete_elsewhere' if e['state']=='complete' else 'failed_elsewhere' if e['state']=='failed' else 'transferred_awaiting_owner'
 native=state(j)
 if native in {'complete','failed_or_partial_preserved'} and e['state'] in {'claimed','active'}:
  folder=folder_of(j);rp=folder/'process-receipt.json'
  if not rp.exists():rp=folder/'gate-rejected.json'
  if rp.exists():ownership.mark([j['view_id'],j['method_id'],j['seed']],OWNER,e['claim_token'],'complete' if native=='complete' else 'failed',{'hostname':'node23','no_live_processes_verified':True,'receipt_path':str(rp),'receipt_sha256':sha(rp),'output_root':j['output_root']})
 if native=='pending' and e['state']!='pending':return 'protected_claim_without_local_launch'
 return native

def main():
 if socket.gethostname()!='node23':raise ValueError('Node23 only')
 lock=(H/'pool.lock').open('a');fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB);index=load(H/'jobs.json');jobs=index['jobs']+index['inherited_jobs'];stop=False
 def halt(*args):
  nonlocal stop
  stop=True
 signal.signal(signal.SIGTERM,halt);signal.signal(signal.SIGINT,halt)
 while True:
  ledger=ownership.snapshot();states={j['job_id']:global_state(j,ledger) for j in jobs};active=[j for j in jobs if states[j['job_id']]=='active'];pending=[j for j in jobs if states[j['job_id']]=='pending'];write(H/'progress.json',{'at':now().isoformat(),'controller_pid':os.getpid(),'states':states,'counts':{x:list(states.values()).count(x) for x in set(states.values())},'campaign_total_cap_cancelled':True,'no_automatic_failed_retries':True})
  awaiting=any(x=='transferred_awaiting_owner' for x in states.values())
  if not active and (stop or not pending) and (stop or not awaiting):break
  if pending and not stop and len(active)<8:
   probe=p.capacity();write(H/'latest-capacity.json',probe)
   if probe['passed']:
    used=set()
    for j in active:
     f=folder_of(j)/'pool-launch.json'
     if f.exists():used.update(load(f)['cpu_affinity'])
    slot=next((i for i in [8,10,12,14,16,18,20,22] if i not in used and i+1 not in used),None)
    if slot is not None:
     try:
      j=pending[0];claimed=ownership.claim([j['view_id'],j['method_id'],j['seed']],OWNER,j['job_id'],j['spec_sha256'])
      if claimed['ok']:
       token=claimed['token']
       if not start(j,slot,probe,token):
        rp=folder_of(j)/'gate-rejected.json';ownership.mark([j['view_id'],j['method_id'],j['seed']],OWNER,token,'failed',{'no_live_processes_verified':True,'receipt_path':str(rp),'receipt_sha256':sha(rp)});stop=True
       else:
        launch=load(folder_of(j)/'pool-launch.json');ownership.mark([j['view_id'],j['method_id'],j['seed']],OWNER,token,'active',{'supervisor_pid':launch['supervisor_pid'],'hostname':'node23','contract_sha256':launch['contract_sha256']})
     except Exception as exc:write(H/('start-error-'+pending[0]['job_id']+'.json'),{'at':now().isoformat(),'error':repr(exc)});print(repr(exc),flush=True);stop=True
   else:time.sleep(10)
  time.sleep(2)
 write(H/'terminal-controller.json',{'at':now().isoformat(),'states':states,'scientific_progress_incomplete':any(x not in {'complete','complete_elsewhere'} for x in states.values())})
if __name__=='__main__':main()
