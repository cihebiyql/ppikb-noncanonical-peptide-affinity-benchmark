"""Preserve immutable failed CPU continuation scientific/log assets; administrative only."""
from pathlib import Path
import datetime as dt,hashlib,json,tarfile
R=Path('/data/qlyu/projects/peptide-four-task-benchmark-20261022');H=R/'methods/dta'
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
files=set();rows=[]
for j in load(H/'continuation-cpu-v2/jobs.json')['inherited_jobs']:
 out=R/j['output_root'];folder=R/j['dispatch_relative_path'];rp=folder/'process-receipt.json'
 if not rp.exists():continue
 receipt=load(rp)
 if receipt.get('exit_code') in [0,None]:continue
 assert receipt['worker_pid_absent'] and receipt['residual_group_pids_before_cleanup']==[] and not (out/'complete.json').exists()
 pgid=receipt['pgid'];alive=[]
 for proc in Path('/proc').iterdir():
  if not proc.name.isdigit():continue
  try:
   st=(proc/'stat').read_text().split(')')[-1].split()
   if st[0]!='Z' and int(st[2])==pgid:alive.append(proc.name)
  except (OSError,ValueError):pass
 assert not alive
 files.update(p for root in [out,folder] for p in root.rglob('*') if p.is_file())
 rows.append({'logical_key':[j['view_id'],j['method_id'],j['seed']],'prior_output':str(out),'exit_code':receipt['exit_code'],'elapsed_seconds':receipt['elapsed_seconds'],'receipt_sha256':sha(rp),'fresh_owned_processes':alive,'reason':receipt['termination_reason']})
stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ');dest=H/('continuation-failure-preservation-'+stamp);dest.mkdir()
manifest=[{'relative_path':str(p.relative_to(R)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(files)]
archive=dest/'all-failed-scientific-and-logs.tar.gz'
with tarfile.open(archive,'w:gz',compresslevel=1) as t:
 for p in sorted(files):t.add(p,arcname=str(p.relative_to(R)))
assert all(sha(R/f['relative_path'])==f['sha256'] for f in manifest)
index={'at':stamp,'scope':'administrative preservation; original files untouched; no fit/forward','failed_attempts':rows,'file_count':len(manifest),'files':manifest,'archive_bytes':archive.stat().st_size,'archive_sha256':sha(archive)}
(dest/'index.json').write_text(json.dumps(index,indent=2));print(json.dumps({'directory':str(dest),'failed_attempts':len(rows),'files':len(manifest),'archive_bytes':archive.stat().st_size,'archive_sha256':sha(archive)}))
