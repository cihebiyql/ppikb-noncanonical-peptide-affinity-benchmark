"""One existing institutional fetch attempt, no install/config/login changes."""
import datetime,hashlib,json,pathlib,subprocess,time
R=pathlib.Path(__file__).resolve().parent/'instsci-final-fallback';R.mkdir(exist_ok=True)
EXE=pathlib.Path('C:/Users/ciheb/.local/bin/instsci.exe')
cmd=[str(EXE),'fetch','10.1093/bib/bbac468','--output',str(R/'pdfs'),'--format','json']
start=time.time();rec={'scope':'last bounded existing institutional access channel only','command':cmd,'doi':'10.1093/bib/bbac468','utc_start':datetime.datetime.now(datetime.timezone.utc).isoformat(),'timeout_seconds':90,'no_installs':True,'no_global_network_config_changes':True,'no_login_or_account_creation':True,'parent_authorization':'new common PPIKB NC benchmark materials acquisition; no original viral case-study execution'}
with (R/'stdout.log').open('wb') as stdout,(R/'stderr.log').open('wb') as stderr:
 p=subprocess.Popen(cmd,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
 rec['pid']=p.pid
 try:p.wait(timeout=90);rec['timeout']=False
 except subprocess.TimeoutExpired:
  rec['timeout']=True
  kill=subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True,timeout=15)
  rec['own_process_tree_kill_exitcode']=kill.returncode;p.wait(timeout=10)
 rec['exit_code']=p.returncode;rec['process_exited']=p.poll() is not None
rec['elapsed_seconds']=time.time()-start
rec['utc_end']=datetime.datetime.now(datetime.timezone.utc).isoformat()
rec['outputs']=[]
for f in R.rglob('*'):
 if f.is_file() and f.name!='receipt.json':
  b=f.read_bytes();o={'path':str(f),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
  if f.suffix.lower()=='.pdf':o['pdf_magic']=b.startswith(b'%PDF-')
  rec['outputs'].append(o)
(R/'receipt.json').write_text(json.dumps(rec,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'exit_code':rec['exit_code'],'elapsed_seconds':rec['elapsed_seconds'],'timeout':rec['timeout'],'process_exited':rec['process_exited'],'pdfs':[x for x in rec['outputs'] if x['path'].lower().endswith('.pdf')],'receipt':str(R/'receipt.json')},ensure_ascii=False))
