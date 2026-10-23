import os,signal,json,time,datetime as dt
from pathlib import Path
R=Path('/data/qlyu/projects/peptide-four-task-benchmark-20261022');H=R/'methods/dta';receipt=[]
for pid,name in [(4062768,'node23_cpu_pool_recovery_v2.py'),(4070900,'node23_cpu_pool_recovery_v3.py')]:
 p=Path('/proc')/str(pid)
 if not p.exists():receipt.append({'pid':pid,'already_absent':True});continue
 cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode();assert p.stat().st_uid==os.getuid() and str(H/name) in cmd
 before=(p/'stat').read_text().split(')')[-1].split()[0];assert before=='T'
 os.kill(pid,signal.SIGKILL);time.sleep(.5)
 receipt.append({'pid':pid,'verified_uid':os.getuid(),'command':cmd,'old_state':before,'action':'SIGKILL only paused admission controller; no science process signaled','absent_after':not p.exists()})
p=H/'cache-reuse-v3/controller-cleanup.json';assert not p.exists();p.write_text(json.dumps({'at':dt.datetime.now(dt.timezone.utc).isoformat(),'scientific_snapshot':str(H/'runtime-snapshot-20261023T012911Z.json'),'scientific_active_count':0,'controllers':receipt},indent=2));print(json.dumps(receipt))
