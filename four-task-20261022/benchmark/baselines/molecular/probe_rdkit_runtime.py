"""Bounded read-only runtime and capacity probe for an existing RDKit CPU route."""
import json
import os
import pathlib
import socket
import subprocess
import time
from datetime import datetime, timezone

if socket.gethostname() != "node23":
    raise RuntimeError("expected node23")
python_paths = [
    "/data/qlyu/projects/peptide-binding-benchmark-20261020/common-prior-methods-20261021/swing/.venv/bin/python",
    "/data/qlyu/anaconda3/envs/cuda12.1/bin/python",
    "/data/qlyu/anaconda3/envs/boltz/bin/python",
    "/data/qlyu/anaconda3/bin/python",
]
code = """import importlib,json,sys
r={'python':sys.version,'executable':sys.executable}
for name in ['rdkit','numpy','pandas','scipy','sklearn','joblib','threadpoolctl']:
 try:
  m=importlib.import_module(name);r[name]={'version':getattr(m,'__version__',None)}
 except Exception as e:r[name]={'error':type(e).__name__+': '+str(e)}
if 'error' not in r['rdkit']:
 from rdkit import Chem
 from rdkit.Chem import rdFingerprintGenerator
 g=rdFingerprintGenerator.GetMorganGenerator(radius=2,fpSize=2048,includeChirality=True)
 a=g.GetFingerprint(Chem.MolFromSmiles('N[C@@H](C)C(=O)O')).ToBitString()
 b=g.GetFingerprint(Chem.MolFromSmiles('N[C@H](C)C(=O)O')).ToBitString()
 r['chiral_canary_distinct']=a!=b
print(json.dumps(r))
"""
env = dict(os.environ, CUDA_VISIBLE_DEVICES="", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", PYTHONDONTWRITEBYTECODE="1")
results = []
for python in python_paths:
    if not pathlib.Path(python).exists():
        results.append({"python": python, "exists": False})
        continue
    try:
        process = subprocess.run([python,"-I","-B","-c",code], capture_output=True,text=True,timeout=30,env=env)
        results.append({"python":python,"exists":True,"exit_code":process.returncode,"stdout":process.stdout,"stderr":process.stderr})
    except subprocess.TimeoutExpired:
        results.append({"python":python,"exists":True,"timeout_seconds":30})
samples = []
for _ in range(2):
    a = [int(v) for v in pathlib.Path('/proc/stat').read_text().splitlines()[0].split()[1:]]
    time.sleep(1)
    b = [int(v) for v in pathlib.Path('/proc/stat').read_text().splitlines()[0].split()[1:]]
    samples.append(100*((b[3]+b[4])-(a[3]+a[4]))/(sum(b)-sum(a)))
root = pathlib.Path('/data/qlyu/projects/peptide-four-task-benchmark-20261022')
print(json.dumps({"schema":"fourtask.rdkit-existing-runtime-probe.v1","at":datetime.now(timezone.utc).isoformat(),
                  "hostname":socket.gethostname(),"uid":os.getuid(),"load":os.getloadavg(),"cpu_count":os.cpu_count(),
                  "idle_percent_samples":samples,"meminfo":pathlib.Path('/proc/meminfo').read_text(),
                  "psi":{name:pathlib.Path('/proc/pressure',name).read_text() for name in ['cpu','memory','io']},
                  "root_resolved":str(root.resolve()),"root_writable":os.access(root,os.W_OK),"runtime_candidates":results,
                  "new_packages_installed":False,"gpu_used":False},indent=2))
