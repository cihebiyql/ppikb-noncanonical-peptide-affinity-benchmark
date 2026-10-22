"""Ordinary Windows Python read fd against a synthetic WSL atomic writer."""
from pathlib import Path
import subprocess,sys,json,os,hashlib,datetime
p=Path(__file__).resolve().parent
target=p/'windows_python_plain_open.synthetic.json'
target.write_text('{"synthetic_only":true,"before":true}',encoding='utf-8')
wslroot='/mnt/d/work/科研工作台/research-tasks/peptide-binding-nc-benchmark-20261021/control/recovery-diagnosis-v1'
command=['wsl.exe','-d','Ubuntu-22.04','-u','root','--','/root/.venvs/peptide-omnipanel-v31-web311-20260723/bin/python',wslroot+'/atomic_replace_probe.py','--target',wslroot+'/'+target.name,'--receipt',wslroot+'/windows_python_plain_open.receipt.json','--scenario','ordinary_Windows_Python_Path_open_r']
with target.open('r',encoding='utf-8') as reader:
 before=reader.read();reader.seek(0)
 result=subprocess.run(command,capture_output=True,timeout=20)
 after_fd=reader.read()
(p/'windows_python_plain_open.stdout.json').write_bytes(result.stdout)
(p/'windows_python_plain_open.stderr.txt').write_bytes(result.stderr)
receipt={'scenario':'ordinary_windows_python_reader','python':sys.executable,'python_version':sys.version.split()[0],'platform':sys.platform,'windows_pid':os.getpid(),'at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'actual_command':command,'child_exit':result.returncode,'reader_implementation':'Path.open(mode=r, encoding=utf-8), default sharing, held continuously during owned WSL writer','custom_share_flags_used':False,'read_fd_still_sees_original_content':after_fd==before,'target_sha256_after':hashlib.sha256(target.read_bytes()).hexdigest(),'synthetic_only':True,'models_started':0}
(p/'windows_python_plain_open.command-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
probe=json.loads((p/'windows_python_plain_open.receipt.json').read_text())
print(json.dumps({'scenario':receipt['scenario'],'python_version':receipt['python_version'],'child_exit':result.returncode,'ok':probe['ok'],'error_class':probe['error_class'],'errno':probe['errno'],'error_path':probe['error_path'],'error_path2':probe['error_path2'],'custom_share_flags_used':False},ensure_ascii=False,indent=2))
