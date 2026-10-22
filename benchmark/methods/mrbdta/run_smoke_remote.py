"""Freeze then execute the explicitly bounded MRBDTA CPU smoke contract."""
import hashlib
import json
import subprocess
import time
from pathlib import Path
P=Path(__file__).resolve().parent
remote='/data/qlyu/projects/peptide-binding-nc-benchmark-20261021/methods/mrbdta/smoke-v1'
python='/data/qlyu/projects/peptide-binding-benchmark-20261020/common-prior-methods-20261021/.venv/bin/python'
names=['adapter.py','author_model.py','vocabularies.json','smoke.py','smoke-inputs.jsonl']
files={n:hashlib.sha256((P/n).read_bytes()).hexdigest() for n in names}
contract={'host':'node23','remote':remote,'python':python,'files_sha256':files,'cpu_threads':1,'address_space_bytes':6*1024**3,'timeout_seconds':180,'CUDA_VISIBLE_DEVICES':'','scope':'two real small inputs forward/backward batch1,2; eval order and singleton invariance; no optimizer updates/full training/GPU/installation'}
(P/'smoke-contract.json').write_text(json.dumps(contract,indent=2),encoding='utf-8')
receipts=[]
def run(args,name,timeout=45):
 start=time.time();r=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
 (P/(name+'.stdout.txt')).write_text(r.stdout,encoding='utf-8');(P/(name+'.stderr.txt')).write_text(r.stderr,encoding='utf-8')
 receipts.append({'name':name,'argv':args,'exit_code':r.returncode,'seconds':time.time()-start})
 (P/'smoke-command-receipts.json').write_text(json.dumps(receipts,indent=2),encoding='utf-8')
 if r.returncode:raise RuntimeError(name+' failed: '+r.stderr[-1500:])
 return r.stdout
ssh=['ssh.exe','-o','BatchMode=yes','-o','ConnectTimeout=15','node23']
run(ssh+['test ! -e '+remote+' && mkdir -p '+remote+' && test -w '+remote+' && hostname && date -Is && df -h '+remote], 'remote-preflight')
for n in names+['smoke-contract.json']:
 run(['scp.exe','-q',str(P/n),'node23:'+remote+'/'+n],'upload-'+n)
# Address-space limit is enforced by shell, threads and CUDA visibility explicit.
cmd='cd '+remote+' && ulimit -v 6291456 && CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 timeout 180s '+python+' -c '+"'import os,runpy; os.sched_setaffinity(0,{min(os.sched_getaffinity(0))}); runpy.run_path(\"smoke.py\",run_name=\"__main__\")'"
out=run(ssh+[cmd],'bounded-smoke',195)
run(['scp.exe','-q','node23:'+remote+'/smoke-receipt.json',str(P/'smoke-receipt.json')],'download-receipt')
print(out)
