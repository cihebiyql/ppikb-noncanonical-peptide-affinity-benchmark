import hashlib
import json
import subprocess
import time
from pathlib import Path
P=Path(__file__).resolve().parent
source=P.parents[1]/'data-protocol/model-observations.jsonl'
rows=(json.loads(l) for l in source.open(encoding='utf-8'))
row=max(rows,key=lambda r:len(r.get('canonical_isomeric_smiles') or r['peptide_smiles']))
(P/'long-smoke-input.json').write_text(json.dumps(row),encoding='utf-8')
remote='/data/qlyu/projects/peptide-binding-nc-benchmark-20261021/methods/mrbdta/smoke-long-v1'
py='/data/qlyu/projects/peptide-binding-benchmark-20261020/common-prior-methods-20261021/.venv/bin/python'
names=['adapter.py','author_model.py','vocabularies.json','long_smoke.py','long-smoke-input.json']
contract={'host':'node23','remote':remote,'python':py,'file_sha256':{n:hashlib.sha256((P/n).read_bytes()).hexdigest() for n in names},
 'model_view_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'selection':'largest full isomeric SMILES length; no label-based selection',
 'cpu_threads':1,'address_space_bytes':6*1024**3,'timeout_seconds':180,'CUDA_VISIBLE_DEVICES':'','scope':'one authentic longest molecule native forward/backward; no optimizer, GPU, full training or installation'}
(P/'long-smoke-contract.json').write_text(json.dumps(contract,indent=2),encoding='utf-8')
receipts=[]
def run(args,name,timeout=45):
 t=time.time();r=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
 (P/(name+'.stdout.txt')).write_text(r.stdout,encoding='utf-8');(P/(name+'.stderr.txt')).write_text(r.stderr,encoding='utf-8')
 receipts.append({'name':name,'argv':args,'exit_code':r.returncode,'wall_seconds':time.time()-t})
 (P/'long-smoke-command-receipts.json').write_text(json.dumps(receipts,indent=2),encoding='utf-8')
 if r.returncode:raise RuntimeError(name+': '+r.stderr[-2000:])
 return r.stdout
ssh=['ssh.exe','-o','BatchMode=yes','-o','ConnectTimeout=15','node23']
run(ssh+['test ! -e '+remote+' && mkdir -p '+remote+' && test -w '+remote+' && hostname && date -Is && uptime && free -m && df -h '+remote],'long-remote-preflight')
for n in names+['long-smoke-contract.json']:run(['scp.exe','-q',str(P/n),'node23:'+remote+'/'+n],'long-upload-'+n)
cmd='cd '+remote+' && ulimit -v 6291456 && CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 timeout 180s '+py+' -c '+"'import os,runpy; os.sched_setaffinity(0,{min(os.sched_getaffinity(0))}); runpy.run_path(\"long_smoke.py\",run_name=\"__main__\")'"
out=run(ssh+[cmd],'long-bounded-smoke',195)
run(['scp.exe','-q','node23:'+remote+'/long-smoke-receipt.json',str(P/'long-smoke-receipt.json')],'long-download-receipt')
print(out)
