from pathlib import Path,PurePosixPath
import base64,hashlib,json,shlex,subprocess,time
HERE=Path(__file__).resolve().parent;OUT=HERE/'runtime-conversion-v1'
REMOTE='/data/qlyu/projects/peptide-binding-benchmark-20261020/common-prior-methods-20261021/nc-external-igg-supplement-20261022-v1'
PYTHON='/data/qlyu/projects/peptide-binding-benchmark-20261020/common-prior-methods-20261021/.venv/bin/python';receipts=[]
def run(args,name,timeout=45):
 start=time.time();r=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
 (OUT/(name+'.stdout.txt')).write_text(r.stdout,encoding='utf-8');(OUT/(name+'.stderr.txt')).write_text(r.stderr,encoding='utf-8');receipts.append({'name':name,'command':args,'exit':r.returncode,'seconds':time.time()-start});(OUT/'command-receipts.json').write_text(json.dumps(receipts,ensure_ascii=False,indent=2),encoding='utf-8');assert r.returncode==0,(name,r.returncode);return r.stdout
def ssh(code,name,timeout=45):return run(['ssh.exe','-o','BatchMode=yes','-o','ConnectTimeout=12','node1','printf %s '+base64.b64encode(code.encode()).decode()+' | base64 -d | bash'],name,timeout)
def main():
 OUT.mkdir(exist_ok=False);files=[HERE/'explicit-label-free-inputs.jsonl',HERE/'convert_author_entities_cpu.py']
 (OUT/'contract.json').write_text(json.dumps({'scope':'post-freeze fixed existing author-observed chemistry format only, no model inference, design or optimization','host':'node1','python':PYTHON,'CPU_threads':1,'CPU_seconds':60,'wall_seconds':75,'nice':19,'RAM_GiB':2,'GPU':False,'input_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}},ensure_ascii=False,indent=2),encoding='utf-8')
 canary='import socket,rdkit;from rdkit import Chem;assert socket.gethostname()=="node1";assert Chem.MolFromSequence("AS") is not None;print(rdkit.__version__)'
 ssh('test -w '+shlex.quote(str(PurePosixPath(REMOTE).parent))+' && '+shlex.quote(PYTHON)+' -c '+shlex.quote(canary),'runtime-canary')
 ssh('mkdir '+shlex.quote(REMOTE),'new-directory')
 for p in files:run(['scp.exe','-q','-o','BatchMode=yes','-o','ConnectTimeout=12',str(p),'node1:'+REMOTE+'/'+p.name],'upload-'+p.name)
 ssh('cd '+shlex.quote(REMOTE)+' && CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 timeout 75s '+shlex.quote(PYTHON)+' convert_author_entities_cpu.py','bounded-conversion',90)
 for n in ['author-entity-formats.jsonl','author-entity-conversion-summary.json']:run(['scp.exe','-q','-o','BatchMode=yes','-o','ConnectTimeout=12','node1:'+REMOTE+'/'+n,str(OUT/n)],'download-'+n)
 result=json.loads((OUT/'author-entity-conversion-summary.json').read_text(encoding='utf-8'));assert result['input_sha256']==hashlib.sha256(files[0].read_bytes()).hexdigest();state=ssh('if test -d /proc/'+str(result['PID'])+'; then echo PRESENT; else echo EXITED; fi','process-state');assert 'EXITED' in state
 (OUT/'receipt.json').write_text(json.dumps({'result':result,'process_exited':True,'original_frozen_external_not_modified':True},ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
