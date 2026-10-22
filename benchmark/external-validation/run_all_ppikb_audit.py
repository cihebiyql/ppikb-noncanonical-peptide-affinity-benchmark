from pathlib import Path,PurePosixPath
import base64,hashlib,json,shlex,subprocess,time
HERE=Path(__file__).resolve().parent;OUT=HERE/'full-PPIKB-audit-runtime'
REMOTE='/data/qlyu/projects/peptide-binding-benchmark-20261020/common-prior-methods-20261021/nc-external-fulldb-20261022-v1'
PYTHON='/data/qlyu/projects/peptide-binding-benchmark-20261020/common-prior-methods-20261021/.venv/bin/python'
receipts=[]
def run(args,name,timeout=45):
 s=time.time();r=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
 (OUT/(name+'.stdout.txt')).write_text(r.stdout,encoding='utf-8');(OUT/(name+'.stderr.txt')).write_text(r.stderr,encoding='utf-8');receipts.append({'name':name,'command':args,'exit_code':r.returncode,'seconds':time.time()-s});(OUT/'command-receipts.json').write_text(json.dumps(receipts,ensure_ascii=False,indent=2),encoding='utf-8');assert r.returncode==0,(name,r.returncode);return r.stdout
def ssh(code,name,timeout=45):
 return run(['ssh.exe','-o','BatchMode=yes','-o','ConnectTimeout=12','node1','printf %s '+base64.b64encode(code.encode()).decode()+' | base64 -d | bash'],name,timeout)
def main():
 OUT.mkdir(exist_ok=False)
 files=[HERE/'inputs/all-PPIKB-label-free-molecules.jsonl',HERE/'inputs/blind-inputs-with-certified-format-conversion.jsonl',HERE/'audit_all_ppikb_chemistry_cpu.py']
 contract={'scope':'75 existing external measured molecule formats versus all21845 PPIKB label-free molecular inputs','host':'node1','environment':PYTHON,'wall_seconds':190,'CPU_seconds':180,'CPU_threads':1,'nice':19,'RAM_GiB':2,'GPU':False,'source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files},'fresh_probe':str(HERE/'node1-probe.json'),'input_labels_present':False}
 (OUT/'task-contract.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2),encoding='utf-8')
 canary='import socket,rdkit;from rdkit import Chem;assert socket.gethostname()=="node1";assert Chem.MolFromSmiles("CCO") is not None;print(rdkit.__version__)'
 ssh('test -w '+shlex.quote(str(PurePosixPath(REMOTE).parent))+' && '+shlex.quote(PYTHON)+' -c '+shlex.quote(canary),'runtime-canary')
 ssh('mkdir '+shlex.quote(REMOTE),'isolated-directory')
 for p in files:run(['scp.exe','-q','-o','BatchMode=yes','-o','ConnectTimeout=12',str(p),'node1:'+REMOTE+'/'+p.name],'upload-'+p.name)
 ssh('cd '+shlex.quote(REMOTE)+' && CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 timeout 190s '+shlex.quote(PYTHON)+' audit_all_ppikb_chemistry_cpu.py','all-PPIKB-chemistry-audit',205)
 for n in ['external-versus-all-PPIKB-chemical-overlap.jsonl','full-PPIKB-chemical-runtime-receipt.json']:run(['scp.exe','-q','-o','BatchMode=yes','-o','ConnectTimeout=12','node1:'+REMOTE+'/'+n,str(OUT/n)],'download-'+n)
 result=json.loads((OUT/'full-PPIKB-chemical-runtime-receipt.json').read_text(encoding='utf-8'));assert result['input_sha256']==contract['source_hashes'][files[0].name] and result['external_sha256']==contract['source_hashes'][files[1].name]
 assert result['full_PPIKB_rows']==21845 and result['external_graphs_tested']==75
 state=ssh('if test -d /proc/'+str(result['process_id'])+'; then echo PROCESS_PRESENT; else echo PROCESS_EXITED; fi','terminal-state');assert 'PROCESS_EXITED' in state
 (OUT/'execution-receipt.json').write_text(json.dumps({'contract':contract,'result':result,'terminal_state':'exited','source_hashes_unchanged':all(hashlib.sha256(p.read_bytes()).hexdigest()==contract['source_hashes'][p.name] for p in files)},ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
