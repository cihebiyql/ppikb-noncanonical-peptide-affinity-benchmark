"""Bounded CPU-only staging and receipts for representation conversion."""
from pathlib import Path, PurePosixPath
import base64, hashlib, json, shlex, subprocess, time

HERE=Path(__file__).resolve().parent
OUT=HERE/'chemistry-format-conversion-v3'
REMOTE='/data/qlyu/projects/peptide-binding-benchmark-20261020/common-prior-methods-20261021/nc-external-format-20261022-v3'
PYTHON='/data/qlyu/projects/peptide-binding-benchmark-20261020/common-prior-methods-20261021/.venv/bin/python'
receipts=[]

def run(args,name,timeout=45):
    started=time.time();r=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
    (OUT/(name+'.stdout.txt')).write_text(r.stdout,encoding='utf-8');(OUT/(name+'.stderr.txt')).write_text(r.stderr,encoding='utf-8')
    receipts.append({'name':name,'command':args,'exit_code':r.returncode,'elapsed_seconds':time.time()-started})
    (OUT/'command-receipts.json').write_text(json.dumps(receipts,ensure_ascii=False,indent=2),encoding='utf-8')
    assert r.returncode==0,(name,r.returncode)
    return r.stdout

def ssh(code,name,timeout=45):
    b64=base64.b64encode(code.encode()).decode()
    return run(['ssh.exe','-o','BatchMode=yes','-o','ConnectTimeout=12','node1','printf %s '+b64+' | base64 -d | bash'],name,timeout)

def main():
    OUT.mkdir(exist_ok=False)
    src=HERE/'inputs/blind-inputs.jsonl';converter=HERE/'convert_explicit_measured_entities.py'
    contract={'scope':'existing Kliche/SH2 measured chemical entity format conversion only, no biological design or optimization','host':'node1','GPU':False,'threads':1,'nice':19,'wall_seconds':75,'CPU_seconds':60,'RAM_GiB':2,'remote_directory':REMOTE,'python':PYTHON,'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'converter_sha256':hashlib.sha256(converter.read_bytes()).hexdigest(),'uncertain_chemistry_policy':'fail closed; source warnings preserved','protonation':'neutral phosphate convention, explicit COO- preserved'}
    (OUT/'task-contract.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2),encoding='utf-8')
    canary='import socket,rdkit,json;from rdkit import Chem;assert socket.gethostname()=="node1";assert Chem.MolFromSequence("AS") is not None;print(json.dumps({"hostname":socket.gethostname(),"rdkit":rdkit.__version__}))'
    ssh('test -w '+shlex.quote(str(PurePosixPath(REMOTE).parent))+' && '+shlex.quote(PYTHON)+' -c '+shlex.quote(canary),'runtime-canary')
    ssh('mkdir '+shlex.quote(REMOTE),'create-isolated-directory')
    for path in (src,converter):
        run(['scp.exe','-q','-o','BatchMode=yes','-o','ConnectTimeout=12',str(path),'node1:'+REMOTE+'/'+path.name],'upload-'+path.name)
    ssh('cd '+shlex.quote(REMOTE)+' && CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 timeout 75s '+shlex.quote(PYTHON)+' '+shlex.quote(converter.name),'convert',90)
    for name in ('Kliche-exact-annotation-format-converted.jsonl','conversion-summary.json'):
        run(['scp.exe','-q','-o','BatchMode=yes','-o','ConnectTimeout=12','node1:'+REMOTE+'/'+name,str(OUT/name)],'download-'+name)
    result=json.loads((OUT/'conversion-summary.json').read_text(encoding='utf-8'))
    assert result['input_sha256']==contract['source_sha256'] and result['input_unchanged']
    assert len(result['failed_rows'])+result['format_converted_rows']==75
    pid=result['process_id'];state=ssh('if test -d /proc/'+str(pid)+'; then echo PROCESS_STILL_PRESENT; else echo PROCESS_EXITED; fi','terminal-state')
    assert 'PROCESS_EXITED' in state
    (OUT/'execution-receipt.json').write_text(json.dumps({'contract':contract,'result':result,'terminal_state':'process_exited','fresh_probe':str(HERE/'node1-probe.json'),'task_readiness':'ready_for_bounded_tiny_one_cpu_nice19_format_only','local_input_unchanged':hashlib.sha256(src.read_bytes()).hexdigest()==contract['source_sha256']},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
