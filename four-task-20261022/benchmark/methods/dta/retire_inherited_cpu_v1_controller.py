"""Retire only the proved stopped obsolete administrative controller after all eight inherited workers terminated."""
from pathlib import Path
import datetime as dt,json,os,signal,time
R=Path('/data/qlyu/projects/peptide-four-task-benchmark-20261022');H=R/'methods/dta';pid=161221
def load(p):return json.loads(Path(p).read_text())
def processes():
 rows=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:
   fields=(p/'stat').read_text().split(')')[-1].split();rows.append({'pid':int(p.name),'state':fields[0],'ppid':int(fields[1]),'pgid':int(fields[2]),'uid':p.stat().st_uid})
  except (OSError,ValueError):pass
 return rows
old=Path('/proc')/str(pid);stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ');out=H/('retired-inherited-v1-controller-'+stamp+'.json')
if not old.exists():out.write_text(json.dumps({'at':stamp,'pid':pid,'action':'none','reason':'already absent','scientific_processes_signalled':[]}));raise SystemExit(0)
cmd=(old/'cmdline').read_bytes().replace(b'\0',b' ').decode();assert old.stat().st_uid==os.getuid() and str(H/'continuation_cpu_pool_v1.py') in cmd and 'continuation_cpu_pool_v2' not in cmd
before=processes();actual=next(x for x in before if x['pid']==pid);assert actual['state'] in ['T','t']
jobs=load(H/'continuation-cpu-v2/jobs.json')['inherited_jobs'];proof=[]
for j in jobs:
 rp=R/j['dispatch_relative_path']/'process-receipt.json';r=load(rp);assert r['exit_code'] is not None and r['worker_pid_absent'] and r['residual_group_pids_before_cleanup']==[]
 assert not [x for x in before if x['pgid']==r['pgid'] and x['state']!='Z'];proof.append({'job_id':j['job_id'],'receipt_path':str(rp),'terminal_exit_code':r['exit_code'],'pgid':r['pgid']})
assert not [x for x in before if x['ppid']==pid and x['state']!='Z']
os.kill(pid,signal.SIGKILL)
time.sleep(.2)
after=processes();assert not [x for x in after if x['pid']==pid and x['state']!='Z']
out.write_text(json.dumps({'at':stamp,'pid':pid,'before':actual,'command':cmd,'single_administrative_PID_signal':'SIGKILL after stopped-controller and full worker terminal verification; no SIGCONT','eight_inherited_worker_proofs':proof,'after_non_z_old_controller':[],'scientific_processes_signalled':[],'current_v2_controller_untouched':260075,'old_logs_preserved':True},indent=2));print(json.dumps({'path':str(out),'retired_administrative_pid':pid,'scientific_processes_signalled':[]}))
