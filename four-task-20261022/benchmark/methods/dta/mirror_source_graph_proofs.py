import json,subprocess
from pathlib import Path
R=Path(r'D:\work\科研工作台\research-tasks\peptide-four-task-benchmark-20261022');remote='/data/qlyu/projects/peptide-four-task-benchmark-20261022'
for phase in ['node23-cpu-v1','node23-cpu-recovery-v2']:
 idx=json.loads((R/'methods/dta'/phase/'jobs.json').read_text())
 for j in idx['jobs']:
  if j['method_id']!='GraphDTA-GIN' or j['stage']!='formal' or j['view_id']!='ppikb_kd_source_cold_scope_v2':continue
  if (phase=='node23-cpu-v1' and j['seed']!=4) or (phase=='node23-cpu-recovery-v2' and j['seed'] not in range(5,10)):continue
  dst=R/Path(j['run_dir'].replace(remote+'/','')).parent;dst.mkdir(parents=True,exist_ok=True)
  subprocess.run(['scp.exe','-q','-r','node23:'+j['run_dir'],str(dst)],check=True)
  print('mirrored proof',j['seed'],flush=True)
