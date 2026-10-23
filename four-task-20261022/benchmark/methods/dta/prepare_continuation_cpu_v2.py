import json,copy,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[2];OLD=R/'methods/dta/continuation-cpu-v1';NEW=R/'methods/dta/continuation-cpu-v2'
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);assert not p.exists();p.write_text(json.dumps(x,indent=2),encoding='utf-8')
base=load(OLD/'jobs.json');paused=load(OLD/'admission-paused-for-resource-v2.json')['states'];jobs=[];inherited=[];NEW.mkdir(exist_ok=True);(NEW/'probe-runtime.json').write_bytes((OLD/'probe-runtime.json').read_bytes())
for j in base['jobs']:
 if paused[j['job_id']]!='pending':
  old=copy.deepcopy(j);old['dispatch_relative_path']='methods/dta/continuation-cpu-v1/dispatch/'+j['job_id'];old['inherited_live_or_terminal']=True;inherited.append(old);continue
 oldpath=R/j['spec_relative_path'];s=load(oldpath);old=copy.deepcopy(s);hours=({'DGDTA-CL':6,'GS-DTA':6,'DeepNC-GEN':4,'GraphDTA-GIN':4} if s['task']=='effect' else {'DGDTA-CL':8,'GS-DTA':8,'DeepNC-GEN':6,'GraphDTA-GIN':4})[s['method_id']];jid=j['job_id'].replace('continuation-v1','continuation-v2');s.update(job_id=jid,run_root=s['run_root'].replace('dta_continuation_cpu_v1/','dta_continuation_cpu_v2/'),timeout_seconds=hours*3600,resource_revision='Unstarted job resource-only revision: observed per-epoch latency times max40 total epochs plus margin; no campaign cap, independently bounded '+str(hours)+'h',previous_prepared_cpu_spec_sha256=sha(oldpath));p=NEW/'specs'/(jid+'.json');write(p,s)
 allowed={'job_id','run_root','timeout_seconds','resource_revision','previous_prepared_cpu_spec_sha256'};assert all(old.get(k)==s.get(k) for k in set(old)|set(s) if k not in allowed)
 jj=copy.deepcopy(j);jj.update(job_id=jid,spec_relative_path=p.relative_to(R).as_posix(),spec_sha256=sha(p),output_root=s['run_root'],timeout_seconds=hours*3600,previous_unstarted_spec_sha256=sha(oldpath),dispatch_relative_path='methods/dta/continuation-cpu-v2/dispatch/'+jid);jobs.append(jj)
 source=OLD/'previous-contracts'/Path(j['previous_contract_relative_path']).name;dest=NEW/'previous-contracts'/source.name;dest.parent.mkdir(exist_ok=True);dest.write_bytes(source.read_bytes());assert sha(dest)==j['previous_contract_sha256']
assert len(jobs)==36 and len(inherited)==8
base.update(schema='fourtask.cpu-continuation.v2',jobs=jobs,inherited_jobs=inherited,resource_revision='Prepared-unstarted resource-only revision; previous eight scientific fits remain at their original bounds',max_observed_epoch_seconds={'DGDTA-CL':1287.9432966709137/2,'DeepNC-GEN':1584.3290603160858/4,'GS-DTA':1583.540870666504/3},budget_basis='max20epochs per LR x2LR=40, observed latency and task-size effects; native early stop retained; totals are finite job bounds, not campaign caps');write(NEW/'jobs.json',base);print(json.dumps({'new_jobs':36,'inherited':8,'index_sha256':sha(NEW/'jobs.json'),'timeout_hours':sorted(set(j['timeout_seconds']/3600 for j in jobs))}))
