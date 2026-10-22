import subprocess,json,hashlib,time
from pathlib import Path
P=Path(__file__).resolve().parent
REMOTE='/data/qlyu/projects/peptide-binding-nc-benchmark-20261021/data-protocol'
PY='/data/qlyu/projects/peptide-binding-benchmark-20261020/common-prior-methods-20261021/.venv/bin/python'
receipts=[]
def run(args,name,timeout=45):
 t=time.time();r=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
 (P/(name+'.stdout.txt')).write_text(r.stdout,encoding='utf-8');(P/(name+'.stderr.txt')).write_text(r.stderr,encoding='utf-8')
 receipts.append({'name':name,'args':args,'exit_code':r.returncode,'seconds':time.time()-t});(P/'cpu-command-receipts.json').write_text(json.dumps(receipts,indent=2),encoding='utf-8')
 if r.returncode:raise RuntimeError(name+': '+r.stderr[-2000:])
 return r.stdout
def ssh(cmd,name,timeout=45):return run(['ssh.exe','-o','BatchMode=yes','-o','ConnectTimeout=15','node1',cmd],name,timeout)
ssh('mkdir -p '+REMOTE+' && test -w '+REMOTE+' && hostname && date -Is && df -h '+REMOTE,'staging-probe')
for name in ['remote_label_free_groups.py','label-free-grouping-input.jsonl','targets.fasta']:
 run(['scp.exe','-q',str(P/name),'node1:'+REMOTE+'/'+name],'upload-'+name)
ssh('cd '+REMOTE+' && CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 timeout 340s '+PY+' remote_label_free_groups.py','chemical-grouping',355)
for name in ['chemical-entity-mapping.jsonl','chemical-neighbor-edges.jsonl','chemical-runtime-receipt.json']:
 run(['scp.exe','-q','node1:'+REMOTE+'/'+name,str(P/name)],'download-'+name)
# MMseqs2 is prohibited by the current resource-card disposition. No invocation.
print('CPU grouping outputs downloaded; no training run.')
