"""Independent, read-only Linux process-receipt audit of local WSL scientific completions."""
from pathlib import Path
from pathlib import PureWindowsPath
import datetime as dt,hashlib,json,shutil
R=Path(__file__).resolve().parents[2];H=R/'methods/dta';B=R/'resources/continuation-20261023'
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def local(raw):
 s=str(raw)
 if s.startswith('/mnt/d/work/科研工作台/research-tasks/peptide-four-task-benchmark-20261022/'):return R/s.split('peptide-four-task-benchmark-20261022/',1)[1]
 if len(s)>2 and s[1]==':':
  a=PureWindowsPath(s).parts;i=a.index('peptide-four-task-benchmark-20261022');return R/Path(*a[i+1:])
 return Path(s)
current=load(max(H.glob('common-formal-census-continuation-*.json')))
old={tuple(x[k] for k in ['view','method','seed']) for x in load(H/'common-formal-census-20261023T013530Z.json')['records']}
issued=[]
for p in (B/'issued').glob('*/issued.json'):
 j=load(p)
 if j.get('assigned_route')=='wsl-native' and str(j.get('spec_path','')).startswith('/mnt/d/'):
  issued.append((p,j))
stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ');dest=H/('independent-wsl-process-'+stamp);dest.mkdir();rows=[]
for x in current['records']:
 key=tuple(x[k] for k in ['view','method','seed'])
 if key in old:continue
 cp=local(x['path'])
 if not cp.exists():continue
 c=load(cp)
 matches=[(p,j) for p,j in issued if tuple(j['logical_key'])==key and j['spec_sha256']==c['spec_sha256']]
 successful=[]
 for p,j in matches:
  dp=B/'dispatch'/p.parent.name/'dispatch.json'
  if dp.exists() and load(dp).get('exit_code')==0 and load(dp).get('status')=='succeeded':successful.append((p,j,dp))
 if not successful:continue
 assert len(successful)==1,(key,'multiple successful resource receipts')
 ip,j,dp=successful[0];q=load(dp);assert q['remaining_owned_pids']==[]
 pgid=q['pgid'];live=[]
 for proc in Path('/proc').iterdir():
  if not proc.name.isdigit():continue
  try:
   s=(proc/'stat').read_text().split(')')[-1].split()
   if s[0]!='Z' and int(s[2])==pgid:live.append(int(proc.name))
  except (OSError,ValueError):pass
 assert not live,(key,live)
 contract=local(j['contract_path']);validation=dp.parent/'validation.stdout.json';v=load(validation)
 assert sha(ip)==q['job_sha256'] and sha(contract)==q['contract_sha256']==j['contract_sha256']
 assert v['valid_for_execution'] and not v['errors']
 files={}
 for role,p in [('issued',ip),('contract',contract),('dispatch',dp),('validation',validation)]:
  name=f'{len(rows):02d}.{role}.json';shutil.copyfile(p,dest/name);files[role]={'original_path':str(p),'mirror_file':name,'sha256':sha(p)}
 for role in ['stdout','stderr']:assert sha(local(q[role]))==q[role+'_sha256']
 rows.append({'logical_key':list(key),'science_job_id':j['science_job_id'],'spec_sha256':c['spec_sha256'],'science_complete_path':str(cp),'science_complete_sha256':sha(cp),'actual_exit_code':q['exit_code'],'actual_pgid':pgid,'fresh_pgid_absent':True,'remaining_owned_pids':[],'files':files,'stdout_stderr_SHA_verified':True})
index={'at':stamp,'host':'cihebi','logical_units':len(rows),'rows':rows,'scope':'independent current WSL PGID+stdout/stderr+contract/validator/issued/actual exit audit, no fit/forward'}
(dest/'index.json').write_text(json.dumps(index,indent=2));print(json.dumps({'directory':str(dest),'units':len(rows)}))
