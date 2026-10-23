"""Bounded administrative census/audit/readback loop. Never launches or retries any scientific work."""
from pathlib import Path
import argparse,datetime as dt,hashlib,json,os,subprocess,sys,tarfile,time
R=Path(__file__).resolve().parents[2];H=R/'methods/dta';REMOTE='/data/qlyu/projects/peptide-four-task-benchmark-20261022'
WP='/root/.venvs/peptide-omnipanel-v31-web311-20260723/bin/python';NP='/data/qlyu/projects/peptide-binding-benchmark-20261020/common-prior-methods-20261021/.venv/bin/python'
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now():return dt.datetime.now(dt.timezone.utc).isoformat()
def main():
 a=argparse.ArgumentParser();a.add_argument('--budget-seconds',type=int,default=1800);a.add_argument('--interval-seconds',type=int,default=120);args=a.parse_args();assert 60<=args.budget_seconds<=7200
 started=time.monotonic();stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ');dest=H/('administrative-watch-'+stamp);dest.mkdir();events=[]
 def write(name,data):
  p=dest/name;t=p.with_suffix('.tmp');t.write_text(json.dumps(data,indent=2),encoding='utf-8');t.replace(p)
 def run(argv,timeout=300):
  remaining=args.budget_seconds-(time.monotonic()-started)
  if remaining<1:raise TimeoutError('administrative watcher bounded time completed')
  q=subprocess.run(argv,cwd=R,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=min(timeout,remaining));events.append({'at':now(),'argv':argv,'exit_code':q.returncode,'stdout':q.stdout,'stderr':q.stderr});write('commands.json',events)
  if q.returncode:raise RuntimeError(f'administrative step failed with code {q.returncode}; no science affected')
  return q.stdout
 def remote(script):return run(['ssh.exe','-o','BatchMode=yes','-o','ConnectTimeout=15','node23','env','OMP_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1','MKL_NUM_THREADS=1','nice','-n','19',NP,REMOTE+'/methods/dta/'+script])
 def wsl(script,*extra):return run(['wsl.exe','-d','Ubuntu-22.04','--','env','CUDA_VISIBLE_DEVICES=','OMP_NUM_THREADS=1','OPENBLAS_NUM_THREADS=1','MKL_NUM_THREADS=1','nice','-n','19',WP,'/mnt/d/work/科研工作台/research-tasks/peptide-four-task-benchmark-20261022/methods/dta/'+script,*extra],timeout=600)
 write('started.json',{'at':now(),'pid':os.getpid(),'administrative_only':True,'fit_forward_or_scientific_dispatch':False,'budget_seconds':args.budget_seconds})
 while time.monotonic()-started<args.budget_seconds:
  try:
   run([sys.executable,str(H/'refresh_continuation_census.py')])
   current=max(H.glob('common-formal-census-continuation-*.json'));prior=max(H.glob('accepted-common-census-continuation-*.json'))
   if load(current)['complete_logical_units']>load(prior)['accepted_logical_units']:
    run(['scp.exe','-q',str(current),str(prior),str(H/'audit_incremental_continuation_units.py'),str(H/'mirror_completed_continuation_remote_v2.py'),'node23:'+REMOTE+'/methods/dta/'])
    wsl('audit_incremental_continuation_units.py')
    ra=json.loads(remote('audit_incremental_continuation_units.py').strip().splitlines()[-1]);run(['scp.exe','-q','node23:'+ra['path'],str(H)])
    rm=json.loads(remote('mirror_completed_continuation_remote_v2.py').strip().splitlines()[-1])
    if rm['records']:
     run(['scp.exe','-q','-r','node23:'+rm['directory'],str(H)],timeout=600)
     folder=H/Path(rm['directory']).name;j=load(folder/'index.json');archive=folder/'scientific-and-process-assets.tar.gz';assert sha(archive)==j['archive_sha256']
     with tarfile.open(archive) as t:
      assert all(not Path(m.name).is_absolute() and '..' not in Path(m.name).parts for m in t.getmembers());t.extractall(R,filter='data')
     assert all(sha(R/f['relative_path'])==f['sha256'] for f in j['files'])
     (folder/'local-readback-verified.json').write_text(json.dumps({'at':now(),'archive_sha256':j['archive_sha256'],'files':len(j['files']),'all_files_SHA':True,'local_scientific_and_actual_process_receipts':True},indent=2),encoding='utf-8')
    wsl('audit_wsl_terminal_receipts.py');run([sys.executable,str(H/'accept_continuation_census.py')])
   status=load(H/'accepted-census-current.json');write('progress.json',{'at':now(),'pid':os.getpid(),'status':status,'administrative_only':True});(H/'administrative-watch-current.json').write_text(json.dumps({'at':now(),'pid':os.getpid(),'directory':str(dest),'status':status},indent=2),encoding='utf-8')
   if status['accepted']==150:
    final_audits=[p for p in H.glob('final-all150-independent-audit-*.json') if load(p).get('accepted_census_sha256')==status['sha256'] and not load(p).get('errors')]
    if not final_audits:wsl('audit_final_150.py')
    wsl('score_effective_input_conditions.py','--native-report','/mnt/d/work/科研工作台/research-tasks/peptide-four-task-benchmark-20261022/methods/dta/effective-input-audit-cihebi-native-20261023T073053Z/complete.json','--manifest24-report','/mnt/d/work/科研工作台/research-tasks/peptide-four-task-benchmark-20261022/methods/dta/effective-input-audit-node23-manifest24-20261023T073109Z/complete.json')
    delivered=json.loads(run([sys.executable,str(H/'export_complete_dta_report.py')],timeout=600).strip().splitlines()[-1]);manifest=Path(delivered['path'])/'delivery-manifest.json';proof={'at':now(),'accepted':150,'candidate_fits':300,'path':delivered['path'],'delivery_manifest_path':str(manifest),'delivery_manifest_sha256':sha(manifest),'source_accepted_census_sha256':status['sha256'],'scientific_execution_in_this_watcher':False};write('final-delivery.json',proof);pointer=H/'final-delivery-current.json';temp=pointer.with_suffix('.tmp');temp.write_text(json.dumps(proof,indent=2),encoding='utf-8');temp.replace(pointer);break
  except Exception as e:write('last-error.json',{'at':now(),'error':repr(e),'scope':'administrative audit/readback only; no scientific model restarted or marked complete'})
  remaining=args.budget_seconds-(time.monotonic()-started)
  if remaining>0:time.sleep(min(args.interval_seconds,remaining))
 write('terminal.json',{'at':now(),'pid':os.getpid(),'administrative_only':True,'elapsed_seconds':time.monotonic()-started})
if __name__=='__main__':main()
