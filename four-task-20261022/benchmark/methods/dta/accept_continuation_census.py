"""Combine independently checked scientific assets and real process receipts, without inference or fit."""
from pathlib import Path
import datetime as dt,hashlib,json,os,statistics
H=Path(__file__).resolve().parent;R=H.parents[1]
publisher_lock=(H/'accepted-census-publisher.lock').open('a+b')
publisher_lock.seek(0)
if os.name=='nt':
 import msvcrt
 if publisher_lock.read(1)==b'':publisher_lock.write(b'0');publisher_lock.flush()
 publisher_lock.seek(0);msvcrt.locking(publisher_lock.fileno(),msvcrt.LK_LOCK,1)
else:
 import fcntl
 fcntl.flock(publisher_lock.fileno(),fcntl.LOCK_EX)
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def atomic_json(path,value):
 tmp=path.with_name(path.name+'.tmp-'+str(os.getpid()));tmp.write_text(json.dumps(value,indent=2),encoding='utf-8');tmp.replace(path)
def local(path):
 p=str(path)
 for marker in ['/data/qlyu/projects/peptide-four-task-benchmark-20261022/','/mnt/d/work/科研工作台/research-tasks/peptide-four-task-benchmark-20261022/']:
  if p.startswith(marker):return R/p[len(marker):]
 return Path(path)
current=load(max(H.glob('common-formal-census-continuation-*.json')))
old=load(H/'common-formal-census-20261023T013530Z.json');accepted={tuple(x[k] for k in ['view','method','seed']):{'logical_key':[x['view'],x['method'],x['seed']],'source':'previous independently accepted59','prior_scientific_artifact_audit':'methods/dta/final-success-artifact-audit-20261023T0137Z.json'} for x in old['records']}
numeric={}
for p in H.glob('continuation-new-unit-audit-*.json'):
 a=load(p)
 if a['errors']:continue
 for x in a['units']:
  if x.get('two_candidate_weights_and_valpred_SHA') and x.get('test_and_selection_SHA'):numeric[tuple(x['logical_key'])]={'audit':str(p),'audit_sha256':sha(p),'test_n':x['test_n']}
process={};indices=[]
base=R/'resources/continuation-20261023'
for p in [base/'wsl25-process-receipts-v1/index.json',*base.glob('worksteal-process-receipts-*/index.json'),*H.glob('independent-wsl-process-*/index.json')]:
 if not p.exists():continue
 index=load(p);indices.append({'path':str(p),'sha256':sha(p)})
 for x in index['rows']:
  for role,f in x['files'].items():assert sha(p.parent/f['mirror_file'])==f['sha256'],(p,role)
  q=load(p.parent/x['files']['dispatch']['mirror_file']);v=load(p.parent/x['files']['validation']['mirror_file'])
  assert x['actual_exit_code']==0 and x['fresh_pgid_absent'] and x['remaining_owned_pids']==[]
  assert q['exit_code']==0 and q['status']=='succeeded' and q['remaining_owned_pids']==[]
  assert q['contract_sha256']==x['files']['contract']['sha256']
  assert v['valid_for_execution'] and not v['errors']
  cp=local(x['science_complete_path']);assert sha(cp)==x['science_complete_sha256']
  assert load(cp)['spec_sha256']==x['spec_sha256']
  process[tuple(x['logical_key'])]={'index':str(p),'index_sha256':sha(p),'actual_exit_receipt':str(p.parent/x['files']['dispatch']['mirror_file']),'actual_exit_receipt_sha256':x['files']['dispatch']['sha256'],'actual_exit_code':0,'fresh_no_live_processes':True,'local_complete_path':str(cp)}
for p in H.glob('continuation-remote-mirror-*/index.json'):
 index=load(p)
 if not (p.parent/'local-readback-verified.json').exists():continue
 for f in index['files']:assert sha(R/f['relative_path'])==f['sha256']
 for x in index['records']:
  q=load(local(x['process_receipt']));assert sha(local(x['process_receipt']))==x['process_receipt_sha256']
  assert x['actual_exit_code']==0 and x['fresh_non_z_pgid_members']==[] and q['exit_code']==0
  folder=local(x['process_receipt']).parent;gate=load(folder/'validation.stdout.json')
  assert gate['valid_for_execution'] and not gate['errors']
  if 'contract_sha256' in q:
   assert sha(base/'issued'/folder.name/'contract.json')==q['contract_sha256']
  else:
   assert sha(folder/'task-contract.json')==load(folder/'pool-launch.json')['contract_sha256']
  process[tuple(x['logical_key'])]={'index':str(p),'index_sha256':sha(p),'actual_exit_receipt':str(local(x['process_receipt'])),'actual_exit_receipt_sha256':x['process_receipt_sha256'],'actual_exit_code':0,'fresh_no_live_processes':True,'local_complete_path':str(local(x['complete_path']))}
observed={(x['view'],x['method'],x['seed']):x for x in current['records']}
for key,n in numeric.items():
 if key in process and key in observed:accepted[key]={'logical_key':list(key),'source':'continuation independent numeric, candidate assets and actual terminal receipt audit',**n,**process[key]}
groups=[]
for g in current['groups']:
 seeds=sorted(k[2] for k in accepted if k[:2]==(g['view'],g['method']))
 groups.append({'view':g['view'],'method':g['method'],'accepted_seeds':seeds,'n':len(seeds),'denominator':10,'missing_seeds':sorted(set(range(10))-set(seeds))})
stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ');out=H/('accepted-common-census-continuation-'+stamp+'.json')
result={'at':stamp,'observed_scientific_complete':len(observed),'accepted_logical_units':len(accepted),'expected_logical_units':150,'unaccepted_observed':[list(k) for k in observed if k not in accepted],'groups':groups,'records':list(accepted.values()),'process_indices':indices,'scope':'Common-data author architecture retraining, mixed runtime/backend strata; acceptance requires independent metrics, both candidates and selected prediction integrity, actual exit0 and owned process absence. Prior59 retain their original linked audits.'}
out.write_text(json.dumps(result,indent=2),encoding='utf-8')
atomic_json(H/'accepted-census-current.json',{'at':stamp,'path':str(out),'sha256':sha(out),'accepted':len(accepted),'observed':len(observed),'expected':150,'unaccepted_observed':result['unaccepted_observed']})
details_stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');details_path=H/('accepted-details-'+details_stamp+'.json');detail_records=[]
for key,proof in accepted.items():
 assert key in observed,('accepted key absent from current observed census',key)
 row=dict(observed[key]);row['acceptance_record']=proof;row['runtime']=row.get('runtime');detail_records.append(row)
detail_groups=[]
for group in groups:
 rows=[x for x in detail_records if (x['view'],x['method'])==(group['view'],group['method'])]
 metrics={}
 for metric in ['MAE','RMSE','R2']:
  values=[x['metrics'][metric] for x in rows if x['metrics'].get(metric) is not None]
  if values:metrics[metric]={'mean':statistics.mean(values),'sd':statistics.stdev(values) if len(values)>1 else None}
 detail_groups.append({'view':group['view'],'method':group['method'],'seeds':group['accepted_seeds'],'missing_seeds':group['missing_seeds'],'ten_seed_complete':group['n']==10,'metrics_available_seeds_only':metrics,'sd_caveat':'Runtime/backends mixed; not pure random-seed variation'})
details={'schema':'fourtask.accepted-complete-detail-census.v1','at':details_stamp,'complete_logical_units':len(detail_records),'accepted_logical_units':len(detail_records),'expected_logical_units':150,'observed_logical_units':len(observed),'count_basis':'strict independently accepted keys only','source_accepted_census':str(out),'source_accepted_census_sha256':sha(out),'source_censuses':current['source_censuses'],'duplicate_conflicts':current['duplicate_conflicts'],'groups':detail_groups,'records':detail_records,'scope':result['scope']}
with details_path.open('x',encoding='utf-8') as f:json.dump(details,f,indent=2)
atomic_json(H/'accepted-details-current.json',{'schema':'fourtask.accepted-details-pointer.v1','at':details_stamp,'path':str(details_path),'sha256':sha(details_path),'accepted':len(detail_records),'observed':len(observed),'expected':150})
print(json.dumps({'path':str(out),'observed':len(observed),'accepted':len(accepted),'unaccepted_observed':result['unaccepted_observed']}))
