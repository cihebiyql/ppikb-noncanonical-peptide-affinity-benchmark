from pathlib import Path,PurePosixPath
import base64,hashlib,json,shlex,subprocess,time
HERE=Path(__file__).resolve().parent;OUT=HERE/'runtime-independence-v1'
REMOTE='/data/qlyu/projects/peptide-binding-benchmark-20261020/common-prior-methods-20261021/nc-external-igg-audit-20261022-v1'
PYTHON='/data/qlyu/projects/peptide-binding-benchmark-20261020/common-prior-methods-20261021/.venv/bin/python';receipts=[]
def run(args,name,timeout=45):
 start=time.time();r=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
 (OUT/(name+'.stdout.txt')).write_text(r.stdout,encoding='utf-8');(OUT/(name+'.stderr.txt')).write_text(r.stderr,encoding='utf-8');receipts.append({'name':name,'command':args,'exit':r.returncode,'seconds':time.time()-start});(OUT/'command-receipts.json').write_text(json.dumps(receipts,ensure_ascii=False,indent=2),encoding='utf-8');assert r.returncode==0,(name,r.returncode);return r.stdout
def ssh(code,name,timeout=45):return run(['ssh.exe','-o','BatchMode=yes','-o','ConnectTimeout=12','node1','printf %s '+base64.b64encode(code.encode()).decode()+' | base64 -d | bash'],name,timeout)
def main():
 OUT.mkdir(exist_ok=False)
 files=[(HERE/'all-PPIKB-label-free-molecules.jsonl','all-PPIKB-label-free-molecules.jsonl'),(HERE/'supplement-inputs13-not-adopted.jsonl','blind-inputs-with-certified-format-conversion.jsonl'),(HERE.parent/'audit_all_ppikb_chemistry_cpu.py','audit_all_ppikb_chemistry_cpu.py'),(HERE/'target-reference-and-main-inputs.json','target-reference-and-main-inputs.json'),(HERE/'audit_target_reference_cpu.py','audit_target_reference_cpu.py')]
 (OUT/'contract.json').write_text(json.dumps({'scope':'post-freeze existing measured IgG molecules and reference identity audit only; no training, scoring, affinity optimization or source repair','host':'node1','python':PYTHON,'CPU_threads':1,'chemical_wall_seconds':190,'chemical_CPU_seconds':180,'target_wall_seconds':130,'target_CPU_seconds':120,'nice':19,'RAM_GiB':2,'GPU':False,'fresh_probe':str(HERE/'node1-live-probe.json'),'input_hashes':{remote:hashlib.sha256(p.read_bytes()).hexdigest() for p,remote in files}},ensure_ascii=False,indent=2),encoding='utf-8')
 canary='import socket,rdkit,Bio;from rdkit import Chem;assert socket.gethostname()=="node1";assert Chem.MolFromSmiles("CCO") is not None;print(rdkit.__version__,Bio.__version__)'
 ssh('test -w '+shlex.quote(str(PurePosixPath(REMOTE).parent))+' && '+shlex.quote(PYTHON)+' -c '+shlex.quote(canary),'runtime-canary')
 ssh('mkdir '+shlex.quote(REMOTE),'new-directory')
 for p,remote in files:run(['scp.exe','-q','-o','BatchMode=yes','-o','ConnectTimeout=12',str(p),'node1:'+REMOTE+'/'+remote],'upload-'+remote)
 ssh('cd '+shlex.quote(REMOTE)+' && CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 timeout 190s '+shlex.quote(PYTHON)+' audit_all_ppikb_chemistry_cpu.py','all-PPIKB-molecular-audit',205)
 ssh('cd '+shlex.quote(REMOTE)+' && CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 timeout 130s '+shlex.quote(PYTHON)+' audit_target_reference_cpu.py','target-reference-audit',145)
 for n in ['external-versus-all-PPIKB-chemical-overlap.jsonl','full-PPIKB-chemical-runtime-receipt.json','supplement-target-reference-audit.json']:run(['scp.exe','-q','-o','BatchMode=yes','-o','ConnectTimeout=12','node1:'+REMOTE+'/'+n,str(OUT/n)],'download-'+n)
 chemical=json.loads((OUT/'full-PPIKB-chemical-runtime-receipt.json').read_text(encoding='utf-8'));target=json.loads((OUT/'supplement-target-reference-audit.json').read_text(encoding='utf-8'));assert chemical['full_PPIKB_rows']==21845 and chemical['external_graphs_tested']==13
 for pid in [chemical['process_id'],target['PID']]:assert 'EXITED' in ssh('if test -d /proc/'+str(pid)+'; then echo PRESENT; else echo EXITED; fi','process-state-'+str(pid))
 (OUT/'receipt.json').write_text(json.dumps({'chemical_audit':chemical,'target_related_main_refs':len(target['related_main_target_refs']),'target_shared_exact_domain_warnings':len(target['additional_shared_domain_warnings']),'processes_exited':True,'original_frozen75_not_modified':True,'model_results':False},ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(chemical,ensure_ascii=False))
if __name__=='__main__':main()
