"""Administrative readback of completed remote scientific units and actual process receipts."""
from pathlib import Path
import datetime as dt, hashlib, json, tarfile
R=Path('/data/qlyu/projects/peptide-four-task-benchmark-20261022')
H=R/'methods/dta'
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
dest=H/('continuation-remote-mirror-'+stamp);dest.mkdir()
audit=load(H/'continuation-new-unit-audit-20261023T044647Z.json')
gpu=load(R/'resources/continuation-20261023/gpu-science-jobs.json')['jobs']
cpu=load(H/'continuation-cpu-v2/jobs.json')['inherited_jobs']
files=set();records=[]
for u in audit['units']:
 k=u['logical_key'];unit=Path(u['path']).parent
 files.update(p for p in unit.rglob('*') if p.is_file())
 j=next((j for j in gpu if j['logical_key']==k),None)
 if j:
  matches=list((R/'resources/continuation-20261023/dispatch').glob(j['job_id']+'--admit*/dispatch.json'))
  receipts=[p for p in matches if load(p).get('exit_code')==0 and load(p).get('status')=='succeeded']
  assert len(receipts)==1
  rp=receipts[0];q=load(rp);assert q['remaining_owned_pids']==[]
  issued=R/'resources/continuation-20261023/issued'/rp.parent.name
  files.update(p for p in issued.rglob('*') if p.is_file())
 else:
  j=next(j for j in cpu if [j['view_id'],j['method_id'],j['seed']]==k)
  rp=R/j['dispatch_relative_path']/'process-receipt.json';q=load(rp)
  assert q['exit_code']==0 and q['worker_pid_absent'] and q['residual_group_pids_before_cleanup']==[]
  assert q['termination_reason'] is None
 pgid=q['pgid'];live=[]
 for proc in Path('/proc').iterdir():
  if not proc.name.isdigit():continue
  try:
   st=(proc/'stat').read_text().split(')')[-1].split()
   if st[0]!='Z' and int(st[2])==pgid:live.append(int(proc.name))
  except (OSError,ValueError):pass
 assert not live
 files.update(p for p in rp.parent.rglob('*') if p.is_file())
 records.append({'logical_key':k,'complete_path':str(unit/'complete.json'),'complete_sha256':sha(unit/'complete.json'),'process_receipt':str(rp),'process_receipt_sha256':sha(rp),'actual_exit_code':q['exit_code'],'actual_pgid':pgid,'fresh_non_z_pgid_members':live})
manifest=[{'relative_path':str(p.relative_to(R)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(files)]
archive=dest/'scientific-and-process-assets.tar.gz'
with tarfile.open(archive,'w:gz') as t:
 for p in sorted(files):t.add(p,arcname=str(p.relative_to(R)))
report={'at':stamp,'records':records,'files':manifest,'archive':str(archive),'archive_bytes':archive.stat().st_size,'archive_sha256':sha(archive),'scope':'read-only archive, no model/forward/fit'}
(dest/'index.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'directory':str(dest),'archive_bytes':archive.stat().st_size,'archive_sha256':sha(archive),'files':len(files),'records':len(records)}))
