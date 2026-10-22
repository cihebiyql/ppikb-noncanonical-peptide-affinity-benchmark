import argparse,hashlib,importlib.util,json,os,platform,signal,subprocess,sys,time
from pathlib import Path
P=Path(__file__).resolve().parent;project=P.parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,v):Path(p).write_text(json.dumps(v,indent=2))
def main():
 a=argparse.ArgumentParser();a.add_argument('--mode',choices=['cpu','gpu'],required=True);mode=a.parse_args().mode
 assert platform.node()=='cihebi'
 watchdog=project/'resources/local-gpu-route/run_gpu_canaries.py'
 spec=importlib.util.spec_from_file_location('existing_gpu_watchdog',watchdog);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 dest=P/('canary-'+mode+'-v1');dest.mkdir(exist_ok=False)
 os.sched_setaffinity(0,set(sorted(os.sched_getaffinity(0))[:2]))
 rows=[json.loads(l) for l in (P/'train-only-32.jsonl').read_text().splitlines()]
 contract={'mode':mode,'method_id':'GS-DTA','host':'cihebi','GPU_UUID':m.GPU,'cpu_threads':2,'memory_gib':4,'owned_GPU_budget_gib':4,'GPU_allocator_cap_gib':3,'timeout_seconds':180,
  'source_files_sha256':{n:sha(P/n) for n in ['adapter.py','author_model.py','author_features.py','canary.py']},
  'train_sample_sha256':sha(P/'train-only-32.jsonl'),'allowed_train_ids':[r['record_id'] for r in rows],
  'receipt_path':str(dest/'result.json'),'entrypoint':str(P/'canary.py'),'python':sys.executable,'no_full_training':True,
  'PYTHONPATH':str(project/'resources/local-gpu-route/vendor-dependencies'),'architecture':'author full unchanged defaults',
  'watchdog':'process tree RSS4GiB and global observed GPU delta4GiB; RSS0.1s GPU1s polls; timeout180s; owned child process-group only'}
 cp=dest/'contract.json';write(cp,contract)
 probes=[];baseline=0
 if mode=='gpu':
  for _ in range(3):
   q=m.gpu_state();probes.append(q)
   if q['compute']:write(dest/'launch-block.json',{'reason':'external_compute_present','probes':probes});raise RuntimeError('GPU compute busy')
   time.sleep(2)
  baseline=probes[-1]['used_MiB']
 env=dict(os.environ,PYTHONPATH=contract['PYTHONPATH'],CUDA_VISIBLE_DEVICES=m.GPU if mode=='gpu' else '',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',NUMEXPR_NUM_THREADS='2')
 start=time.monotonic();rss=gpu=0;reason=None;monitor=[];last_gpu=0
 with (dest/'stdout.log').open('w') as out,(dest/'stderr.log').open('w') as err:
  child=subprocess.Popen([sys.executable,str(P/'canary.py'),'--contract',str(cp)],env=env,stdout=out,stderr=err,start_new_session=True)
  while child.poll() is None:
   rss=max(rss,m.tree_rss(child.pid));elapsed=time.monotonic()-start
   if mode=='gpu' and elapsed-last_gpu>=1:
    q=m.gpu_state();monitor.append(q);gpu=max(gpu,max(0,q['used_MiB']-baseline)*1024**2);last_gpu=elapsed
   if rss>4*1024**3:reason='RSS_above4GiB'
   elif gpu>4*1024**3:reason='GPU_delta_above4GiB'
   elif elapsed>180:reason='timeout180s'
   if reason:os.killpg(child.pid,signal.SIGKILL);break
   time.sleep(.1)
  code=child.wait()
 after=m.gpu_state() if mode=='gpu' else None
 receipt={'status':'passed' if code==0 and not reason else 'failed','mode':mode,'exit_code':code,'stop_reason':reason,'wall_seconds':time.monotonic()-start,
  'peak_process_tree_RSS_bytes':rss,'peak_observed_GPU_delta_bytes':gpu,'prelaunch_three_probes':probes,'GPU_monitor':monitor,'post_exit_GPU_probe':after,
  'process_exited':not Path('/proc/'+str(child.pid)).exists(),'contract_sha256':sha(cp),'outputs':{}}
 for f in [dest/'stdout.log',dest/'stderr.log',dest/'result.json']:
  if f.exists():receipt['outputs'][f.name]={'bytes':f.stat().st_size,'sha256':sha(f)}
 write(dest/'watchdog-receipt.json',receipt);print(json.dumps(receipt));return 0 if receipt['status']=='passed' else 1
if __name__=='__main__':raise SystemExit(main())
