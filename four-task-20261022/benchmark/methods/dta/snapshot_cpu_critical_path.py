"""Read-only actual live CPU candidate progress; conditional epoch-budget scenarios, never an ETA guarantee."""
from pathlib import Path
import datetime as dt,hashlib,json,os,statistics,time
R=Path('/data/qlyu/projects/peptide-four-task-benchmark-20261022');H=R/'methods/dta'
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def epoch_bounds(n,stale,max_epochs=20,patience=5):
 upper=max(0,max_epochs-n)
 return (min(upper,patience+1 if n==0 else max(0,patience-stale)),upper)
def readlogs(p):
 rows=[]
 if not p.exists():return rows
 for line in p.read_text().splitlines():
  try:rows.append(json.loads(line))
  except json.JSONDecodeError:pass
 return rows
def main():
 jobs=load(H/'continuation-cpu-v2/jobs.json');ledger=load(R/'resources/continuation-20261023/work-ownership.json');rows=[]
 comparison=load(H/'criticalpath-GPU-comparison-input.json') if (H/'criticalpath-GPU-comparison-input.json').exists() else {'records':[]}
 for j in jobs['jobs']+jobs['inherited_jobs']:
  key=[j['view_id'],j['method_id'],j['seed']];e=ledger['entries'][json.dumps(key,separators=(',',':'))]
  if e['owner']!='node23-cpu' or e['state']!='active':continue
  out=R/j['output_root'];sp=out/'started.json'
  if not sp.exists():continue
  start=load(sp);pid=start['pid'];proc=Path('/proc')/str(pid)
  try:
   st=(proc/'stat').read_text().split(')')[-1].split();cmd=(proc/'cmdline').read_bytes().replace(b'\0',b' ').decode()
   actual_live=st[0]!='Z' and proc.stat().st_uid==os.getuid() and str(R/j['spec_relative_path']) in cmd and int(st[2])==start['pgid']
  except OSError:actual_live=False
  if not actual_live:continue
  assert sha(R/j['spec_relative_path'])==j['spec_sha256']==start['spec_sha256'];spec=load(R/j['spec_relative_path']);elapsed=time.time()-start['started_unix'];candidates=[];total_lower=total_upper=0;current=None;previous_elapsed=0
  for ci in range(2):
   folder=out/('candidate-'+str(ci));logs=readlogs(folder/'epochs.jsonl');done=(folder/'complete.json').exists();n=len(logs)
   best=min((x['validation']['MAE'] for x in logs),default=None);improved=[i for i,x in enumerate(logs) if x['improved']];stale=n-1-improved[-1] if improved else 0
   rates=[b['elapsed_seconds']-a['elapsed_seconds'] for a,b in zip(logs,logs[1:]) if b['elapsed_seconds']>a['elapsed_seconds']]
   rate_scope='completed inter-epoch differences; first epoch excluded'
   if not rates and logs and ci==1 and logs[0]['elapsed_seconds']>previous_elapsed:rates=[logs[0]['elapsed_seconds']-previous_elapsed];rate_scope='first epoch of next candidate minus prior candidate final epoch; includes new-candidate setup'
   if not rates and logs:rates=[logs[0]['elapsed_seconds']];rate_scope='only first epoch observed; includes encoding/setup overhead'
   recent=rates[-5:];lower,upper=(0,0) if done else epoch_bounds(n,stale,spec['max_epochs'],spec['patience']);total_lower+=lower;total_upper+=upper
   record={'candidate':ci,'learning_rate':spec['candidates'][ci]['learning_rate'],'completed_epochs':n,'last_epoch':logs[-1]['epoch'] if logs else None,'best_validation_MAE':best,'stale_epochs':stale,'candidate_complete':done,'remaining_epoch_bounds_if_future_nonimprovement_vs_all20':[lower,upper],'completed_epoch_seconds_recent5':recent,'epoch_timing_scope':rate_scope,'last_elapsed_seconds':logs[-1]['elapsed_seconds'] if logs else None}
   candidates.append(record)
   if current is None and not done:current=record
   if logs:previous_elapsed=logs[-1]['elapsed_seconds']
  rate=current['completed_epoch_seconds_recent5'] if current else []
  in_progress=max(0,elapsed-current['last_elapsed_seconds']) if current and current['last_elapsed_seconds'] is not None else None
  scenario=None
  if rate:
   deduction=min(in_progress or 0,statistics.median(rate));scenario={'lower_seconds':max(0,total_lower*min(rate)-deduction),'upper_seconds':max(0,total_upper*max(rate)-deduction),'median_epoch_seconds':statistics.median(rate),'scope':'conditional throughput scenarios, not a confidence interval or promised ETA; excludes final selection/test IO, assumes future rate stays in observed range'}
  gpu=[x for x in comparison['records'] if x['view']==j['view_id'] and x['method']==j['method_id']]
  gpu_times=[x['elapsed_seconds'] for x in gpu];gpu_summary={'n_full_two_candidate_fits':len(gpu),'median_seconds':statistics.median(gpu_times) if gpu_times else None,'min_seconds':min(gpu_times) if gpu_times else None,'max_seconds':max(gpu_times) if gpu_times else None,'scope':'empirical completed GPU fits of same view/method, varying seeds/earlystop/runtime/cache overhead'}
  rows.append({'logical_key':key,'job_id':j['job_id'],'pid':pid,'pgid':start['pgid'],'actual_live_verified':True,'actual_elapsed_seconds':elapsed,'declared_job_timeout_seconds':spec['timeout_seconds'],'nominal_resource_remaining_seconds':max(0,spec['timeout_seconds']-elapsed),'phase':'candidate-'+str(current['candidate']) if current else 'selection_or_test_scoring','in_progress_seconds_since_last_completed_epoch':in_progress,'candidates':candidates,'remaining_training_epoch_bounds':[total_lower,total_upper],'remaining_time_scenarios':scenario,'completed_GPU_comparison':gpu_summary,'candidate_progress_source':str(out),'resource_migration_action':'none; evidence-only. Any later stop/retrain requires explicit new administrative phase, actual old-PGID absence, preserved partial and atomic ownership gate; GPU retraining starts from scratch.'})
 stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ');dest=H/('cpu-critical-path-'+stamp+'.json');report={'at':stamp,'live_count':len(rows),'rows':rows,'ledger_snapshot_revision':ledger['revision'],'scope':'read-only actual process and epoch evidence; no signal, migration or scientific launch'};dest.write_text(json.dumps(report,indent=2));p=H/'cpu-critical-path-current.json';temp=p.with_suffix('.tmp');temp.write_text(json.dumps({'at':stamp,'path':str(dest),'sha256':sha(dest),'live_count':len(rows)},indent=2));temp.replace(p);print(json.dumps({'path':str(dest),'live_count':len(rows),'summaries':[{'key':x['logical_key'],'phase':x['phase'],'epochs':[c['completed_epochs'] for c in x['candidates']],'stale':[c['stale_epochs'] for c in x['candidates']],'remaining_training_epochs':x['remaining_training_epoch_bounds'],'remaining_time_scenarios':x['remaining_time_scenarios'],'GPU':x['completed_GPU_comparison']} for x in rows]}))
if __name__=='__main__':main()
