"""Live Node23 CPU/runtime evidence; never constructs a model."""
import datetime as dt
import json
import os
from pathlib import Path
import socket
import subprocess
import time

def stat():
    values=list(map(int,Path('/proc/stat').read_text().splitlines()[0].split()[1:]))
    return sum(values),values[3],values[4]

assert socket.gethostname()=='node23'
samples=[]
for _ in range(3):
    a=stat();time.sleep(1);b=stat();total=b[0]-a[0]
    samples.append({'idle_percent':100*(b[1]-a[1])/total,'iowait_percent':100*(b[2]-a[2])/total})
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
python='/data/qlyu/projects/peptide-binding-benchmark-20261020/common-prior-methods-20261021/.venv/bin/python'
code="import json,sys,torch,torch_geometric,numpy,scipy,sklearn;from rdkit import rdBase;print(json.dumps({'executable':sys.executable,'prefix':sys.prefix,'python':sys.version,'torch':torch.__version__,'PyG':torch_geometric.__version__,'RDKit':rdBase.rdkitVersion,'numpy':numpy.__version__,'scipy':scipy.__version__,'sklearn':sklearn.__version__,'cuda_available':torch.cuda.is_available()}))"
runtime=subprocess.run([python,'-c',code],env=env,capture_output=True,text=True,timeout=90)
mem={key:int(value.strip().split()[0])*1024 for line in Path('/proc/meminfo').read_text().splitlines()
     for key,value in [line.split(':',1)]}
result={'schema':'fourtask.dta-node23-live.v1','at':dt.datetime.now(dt.timezone.utc).isoformat(),
        'hostname':socket.gethostname(),'uid':os.getuid(),'samples':samples,'load':os.getloadavg(),
        'memory_available_bytes':mem['MemAvailable'],'cpu_count':os.cpu_count(),
        'runtime':{'exit_code':runtime.returncode,'stdout':runtime.stdout,'stderr':runtime.stderr},
        'all_idle_ge40':all(s['idle_percent']>=40 for s in samples),
        'reserve32GiB_plus_max5jobs4GiB_available':mem['MemAvailable']>=(32+20)*1024**3,
        'environment_modified':False,'GPU_used':False}
root=Path('/data/qlyu/projects/peptide-four-task-benchmark-20261022/methods/dta/node23-cpu-v1')
root.mkdir(parents=True,exist_ok=True)
(root/'probe-runtime.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
