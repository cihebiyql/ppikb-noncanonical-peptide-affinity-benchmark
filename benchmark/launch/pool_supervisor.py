"""Fail-closed local WSL GPU pool. Only issued indices may launch formal units."""
import argparse,csv,io,json,os,signal,socket,subprocess,sys,time,math,threading,re
from pathlib import Path
from common import read,sha,path,checked,write,utc,deadline,process_table,children,stop_owned_group,GPU_UUID
from run_unit import validate_complete
GIB=1024**3

def gpu_probe():
 def query(fields,compute=False):
  arg='--query-compute-apps=' if compute else '--query-gpu='
  r=subprocess.run(['nvidia-smi','-i',GPU_UUID,arg+fields,'--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=8)
  if r.returncode:raise RuntimeError('GPU query unavailable: '+r.stderr.strip())
  return list(csv.reader(io.StringIO(r.stdout)))
 result=query('uuid,memory.used,utilization.gpu')
 if len(result)!=1 or result[0][0].strip()!=GPU_UUID:raise RuntimeError('Physical GPU identity uncertain')
 gpu={'uuid':result[0][0].strip(),'memory_used_bytes':int(result[0][1].strip())*1024**2,'utilization_percent':int(result[0][2].strip()),'compute':[],'sample_at':utc(),'WSL_visibility_limitation':'NVIDIA WSL process list can omit or use unmappable Windows PIDs. An unknown reported compute PID blocks new launch; absence only establishes no externally reported compute process, not perfect cross-OS visibility.'}
 for row in query('gpu_uuid,pid,used_gpu_memory,process_name',True):
  if not row or not ''.join(row).strip():continue
  if len(row)<4:raise RuntimeError('Incomplete compute-PID query')
  if row[0].strip()!=GPU_UUID:continue
  try:pid=int(row[1].strip())
  except ValueError:raise RuntimeError('Unmappable compute PID: '+str(row))
  try:memory=int(row[2].strip())*1024**2
  except ValueError:memory=None
  gpu['compute'].append({'pid':pid,'used_gpu_memory_bytes':memory,'name':','.join(row[3:]).strip()})
 return gpu

def ownership_gate(sample,owned_pids):
 unknown=[p for p in sample['compute'] if p['pid'] not in owned_pids]
 return not unknown,unknown

def rss_snapshot(active,table):
 per={};owned=set()
 for unit,state in active.items():
  pgid=state['pgid'];members={pid for pid,r in table.items() if r['pgid']==pgid and r['session']==pgid and r['uid']==os.getuid()}
  # Private session membership is stronger than parent PID after orphan reparenting.
  owned|=members;per[unit]={'pids':sorted(members),'rss_bytes':sum(table[pid]['rss'] for pid in members),'pgid':pgid}
 return per,owned

def unit_args(unit,index):
 binding_keys={'unit_binding','unit_binding_sha256','bound_entrypoint','bound_entrypoint_sha256'}
 if binding_keys&set(unit):
  if not binding_keys<=set(unit):raise ValueError('Partial bound unit entrypoint')
  entry=checked(unit['bound_entrypoint'],unit['bound_entrypoint_sha256']);binding=checked(unit['unit_binding'],unit['unit_binding_sha256'])
  return [index['python'],str(entry),'--binding',str(binding)]
 return [index['python'],str(Path(__file__).with_name('run_unit.py'))]+[value for key in ['spec','spec_sha256','contract','contract_sha256','validation','validation_sha256'] for value in ['--'+key.replace('_','-'),str(unit[key])]]+['--deadline',index['deadline']]

def cache_gate(unit,required,verified=None,spec=None):
 proofs=unit.get('feature_cache_proofs',[])
 if required and not proofs:return False,'missing_signed_cache_proofs'
 if required and spec is not None:
  key=str(spec['split_id'])+'-'+spec['regime']+'-'+spec['method_id'];cache=path(spec['cache_root'])
  expected={str((cache/(key+'-train.pkl')).resolve()),str((cache/(key+'-validation-'+spec['validation_scope']+'.pkl')).resolve())}
  if not expected<={str(path(p['path']).resolve()) for p in proofs}:return False,'signed_cache_paths_do_not_cover_actual_runner_paths'
 for item in proofs:
  try:
   p=path(item['path']);stat=p.stat();key=(str(p),item['sha256']);signature=(stat.st_size,stat.st_mtime_ns,stat.st_ino)
   if verified is None or verified.get(key)!=signature:
    checked(p,item['sha256'])
    if verified is not None:verified[key]=signature
  except (FileNotFoundError,ValueError) as error:return False,repr(error)
 return True,None

def run(index_path,index_hash):
 checked(index_path,index_hash);index=read(path(index_path))
 if index.get('schema')!='nc-unit-index-v1' or index.get('issued') is not True:raise ValueError('Only root-issued unit index accepted')
 if os.name!='posix' or not Path('/proc').exists():raise RuntimeError('Linux WSL process controls required')
 if socket.gethostname()!=index['expected_hostname'] or socket.gethostname()!='cihebi':raise RuntimeError('Wrong execution host')
 if index['gpu_uuid']!=GPU_UUID or os.environ.get('CUDA_VISIBLE_DEVICES')!=GPU_UUID:raise RuntimeError('GPU UUID mismatch')
 if Path(sys.executable).resolve()!=path(index['python']).resolve():raise RuntimeError('Wrong actual interpreter')
 if Path(sys.prefix).resolve()!=path(index['python']).parent.parent.resolve():raise RuntimeError('Wrong virtual environment prefix')
 if os.environ.get('PYTHONPATH')!=index['PYTHONPATH']:raise RuntimeError('Actual dependency route changed')
 checked(__file__,index['supervisor_sha256']);checked(Path(__file__).with_name('run_unit.py'),index['wrapper_sha256']);checked(Path(__file__).with_name('common.py'),index['common_sha256'])
 cutoff=deadline(index['deadline']);root=path(index['output_root']);root.mkdir(parents=True,exist_ok=True)
 attempt=root/'attempts'/(str(time.time_ns())+'-'+str(os.getpid()));attempt.mkdir(parents=True,exist_ok=False)
 if index.get('feature_cache_required') is not True:raise ValueError('Formal workers require prewarmed signed caches')
 maximum=int(index.get('max_concurrent',2))
 if not 1<=maximum<=3:raise ValueError('Only 1-3 owned workers permitted')
 # Budget reservations guarantee 3-GiB workers never reserve >8 GiB jointly.
 config={'worker_RSS_limit':4*GIB,'pool_RSS_limit':12*GIB,'pool_owned_GPU_limit':8*GIB,'worker_GPU_limit':3*GIB,'worker_CPU_threads':2,'max_concurrent':maximum}
 units=index['units'];ids=[u['unit_id'] for u in units]
 if not all(re.fullmatch('[A-Za-z0-9_.-]+',x) for x in ids):raise ValueError('Unsafe unit id for receipt path')
 if len(ids)!=len(set(ids)):raise ValueError('Duplicate unit id')
 specs={u['unit_id']:read(checked(u['spec'],u['spec_sha256'])) for u in units}
 contracts={};receiptdirs=[];rundirs=[]
 for unit in units:
  for key in ['contract','validation']:checked(unit[key],unit[key+'_sha256'])
  contract=read(path(unit['contract']));contracts[unit['unit_id']]=contract
  if contract['run_id']!=unit['unit_id']:raise ValueError('Index unit id differs from actual contract')
  timeout=int(contract['execution']['timeout_seconds'])
  if not 0<timeout<=7200:raise ValueError('Invalid per-unit timeout')
  proof=specs[unit['unit_id']].get('launch_proof') or contract['execution']['launch_proof'];receiptdirs.append(str(path(proof['receipt_root']).resolve()));rundirs.append(str(path(specs[unit['unit_id']]['run_root']).resolve()))
 if len(set(receiptdirs))!=len(units) or len(set(rundirs))!=len(units):raise ValueError('Units must not share receipt/output directories')
 # Initial resource evidence is always refreshed, even on resume.
 samples=[]
 for i in range(3):
  sample=gpu_probe();samples.append(sample)
  if sample['compute']:raise RuntimeError('External/unknown compute PID present before pool start')
  if sample['utilization_percent']>int(index.get('startup_max_utilization_percent',20)):raise RuntimeError('Startup utilization above declared graphics baseline gate')
  if i<2:time.sleep(1)
 baseline=min(s['memory_used_bytes'] for s in samples)
 if 'graphics_baseline_memory_bytes' in index:baseline=min(baseline,int(index['graphics_baseline_memory_bytes']))
 write(attempt/'startup-gpu-samples.json',{'samples':samples,'conservative_graphics_baseline_bytes':baseline,'requested_reference_graphics_baseline_bytes':index.get('graphics_baseline_memory_bytes'),'limits':config,'index_sha256':index_hash,'deadline':index['deadline'],'sample_scope':'no externally reported compute PID; WSL visibility limitation retained'})
 active={};pending=[];completed=[];failed=[];interrupted=False
 for unit in units:
  spec=specs[unit['unit_id']];proof=spec.get('launch_proof') or read(path(unit['contract']))['execution']['launch_proof'];receiptroot=path(proof['receipt_root'])
  if (receiptroot/'unit-complete.json').exists():
   validate_complete(receiptroot,unit['spec_sha256'],unit['contract_sha256'],unit['validation_sha256']);completed.append(unit['unit_id'])
  elif receiptroot.exists():failed.append({'unit_id':unit['unit_id'],'reason':'preserved_failed_or_incomplete_no_retry'})
  else:pending.append(unit)
 def request_stop(signum,frame):
  nonlocal interrupted;interrupted=True
 signal.signal(signal.SIGTERM,request_stop);signal.signal(signal.SIGINT,request_stop)
 reason=None;last_sample=None;trip={'reason':None};heartbeat_state={'status':'running','pending':len(pending),'active':[]};heartbeat_lock=threading.Lock();watchdog_stop=threading.Event();verified_caches={}
 def watchdog():
  last=0
  try:
   while not watchdog_stop.is_set():
    snapshot=dict(active);table=process_table();current,current_owned=rss_snapshot(snapshot,table);total=sum(table[p]['rss'] for p in (current_owned|children(os.getpid(),table)) if p in table)
    for state in snapshot.values():
     if time.monotonic()-state['launch_monotonic']>=state['timeout_seconds'] and not state.get('timeout_fired'):
      state['timeout_fired']=True;state['watchdog_reason']='per_unit_original_timeout';stop_owned_group(state['pgid'],grace=0)
    why=('original_deadline' if time.time()>=cutoff else 'signal' if interrupted else 'owned_RSS_budget_exceeded' if total>config['pool_RSS_limit'] or any(r['rss_bytes']>config['worker_RSS_limit'] for r in current.values()) else None)
    if why:
     trip['reason']=why
     for state in snapshot.values():stop_owned_group(state['pgid'],grace=0)
    if time.monotonic()-last>=1:
     with heartbeat_lock:record=dict(heartbeat_state)
     record.update(at=utc(),watchdog_reason=trip['reason'],watchdog_RSS=current,watchdog_pool_RSS_bytes=total,deadline=index['deadline'],index_sha256=index_hash)
     write(root/'progress.json',record);last=time.monotonic()
    watchdog_stop.wait(.2)
  except BaseException as error:
   trip['reason']='watchdog_failed:'+repr(error)
   for state in dict(active).values():
    try:stop_owned_group(state['pgid'],grace=0)
    except Exception:pass
 watch=threading.Thread(target=watchdog,daemon=True);watch.start()
 try:
  while pending or active:
   if trip['reason'] or interrupted or time.time()>=cutoff:reason=trip['reason'] or ('signal' if interrupted else 'original_deadline');break
   table=process_table();per,owned=rss_snapshot(active,table)
   for uid,state in list(active.items()):
    code=state['process'].poll()
    if code is not None:
     # Reap or stop any children left in the private unit session.
     stop_owned_group(state['pgid'],grace=.2);state['stdout'].close();state['stderr'].close()
     unit=state['unit'];spec=specs[uid];proof=spec.get('launch_proof') or read(path(unit['contract']))['execution']['launch_proof'];receiptroot=path(proof['receipt_root'])
     good=False
     if code==0:
      try:validate_complete(receiptroot,unit['spec_sha256'],unit['contract_sha256'],unit['validation_sha256']);good=True
      except Exception as error:failure=repr(error)
     else:failure=state.get('watchdog_reason') or 'wrapper_exit_'+str(code)
     write(root/(uid+'.terminal.json'),{'unit_id':uid,'exit_code':code,'status':'complete' if good else 'failed','reason':None if good else failure,'pgid':state['pgid'],'finished_at':utc(),'stdout_sha256':sha(state['stdout_path']),'stderr_sha256':sha(state['stderr_path'])})
     if good:completed.append(uid)
     else:failed.append({'unit_id':uid,'reason':failure})
     del active[uid]
   table=process_table();per,owned=rss_snapshot(active,table)
   supervisor_rss=table.get(os.getpid(),{}).get('rss',0);poolrss=sum(table[p]['rss'] for p in (owned|children(os.getpid(),table)) if p in table)
   over=[uid for uid,v in per.items() if v['rss_bytes']>config['worker_RSS_limit']]
   if over or poolrss>config['pool_RSS_limit']:reason='owned_RSS_budget_exceeded';break
   try:
    last_sample=gpu_probe();gate,unknown=ownership_gate(last_sample,owned)
   except Exception as exc:gate=False;unknown=[{'probe_error':repr(exc)}];last_sample=None
   owned_delta=max(0,last_sample['memory_used_bytes']-baseline) if last_sample else None
   if owned_delta is not None and owned_delta>config['pool_owned_GPU_limit']:reason='conservative_owned_GPU_delta_budget_exceeded';break
   if last_sample:
    per_gpu={uid:sum(p['used_gpu_memory_bytes'] or 0 for p in last_sample['compute'] if p['pid'] in status['pids']) for uid,status in per.items()}
    if any(v>config['worker_GPU_limit'] for v in per_gpu.values()):reason='owned_worker_GPU_reported_budget_exceeded';break
   launch_allowed=gate and bool(pending) and len(active)<maximum and not trip['reason'] and time.time()<cutoff
   cache_blocks={}
   if launch_allowed:
    # Ready caches may overtake blocked ones, with no scientific-label access.
    ready=[];blocked=[]
    for candidate in pending:
     okay,why=cache_gate(candidate,index.get('feature_cache_required',False),verified_caches,specs[candidate['unit_id']])
     if okay:ready.append(candidate)
     else:blocked.append(candidate);cache_blocks[candidate['unit_id']]=why
    pending=ready+blocked;launch_allowed=bool(ready)
   if launch_allowed:
    unit=pending[0];spec=specs[unit['unit_id']];required=int(spec.get('gpu_allocator_budget_bytes',0))
    reserved=sum(int(specs[uid].get('gpu_allocator_budget_bytes',0)) for uid in active)
    # Whole-pool reservation bounds remain meaningful when WSL hides per-PID memory.
    if not 0<required<=config['worker_GPU_limit']:raise ValueError('Missing/bad GPU reservation')
    if reserved+required<=config['pool_owned_GPU_limit'] and (len(active)+1)*config['worker_RSS_limit']+supervisor_rss<=config['pool_RSS_limit'] and not trip['reason'] and time.time()<cutoff:
     pending.pop(0);uid=unit['unit_id'];outpath=root/(uid+'.stdout.log');errpath=root/(uid+'.stderr.log')
     if outpath.exists() or errpath.exists():raise FileExistsError('Prior pool logs retained; no silent relaunch '+uid)
     stdout=outpath.open('xb');stderr=errpath.open('xb');env=os.environ.copy()
     env.update(OMP_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',MKL_NUM_THREADS='2',NUMEXPR_NUM_THREADS='2',CUDA_VISIBLE_DEVICES=GPU_UUID,PYTHONPATH=index['PYTHONPATH'],NC_POOL_OWNER_PID=str(os.getpid()))
     cpus=sorted(os.sched_getaffinity(0));slot=next(x for x in range(maximum) if x not in {s['slot'] for s in active.values()});affinity=cpus[slot*2:slot*2+2]
     if len(affinity)!=2:raise RuntimeError('Insufficient CPU affinity for 2 threads per worker')
     def child_setup():os.sched_setaffinity(0,set(affinity));os.nice(10)
     process=subprocess.Popen(unit_args(unit,index),stdout=stdout,stderr=stderr,env=env,start_new_session=True,preexec_fn=child_setup)
     active[uid]={'unit':unit,'process':process,'pgid':process.pid,'slot':slot,'stdout':stdout,'stderr':stderr,'stdout_path':outpath,'stderr_path':errpath,'launch_monotonic':time.monotonic(),'timeout_seconds':int(contracts[uid]['execution']['timeout_seconds'])}
     write(root/(uid+'.started.json'),{'argv':unit_args(unit,index),'pid':process.pid,'pgid':process.pid,'session_id':process.pid,'CPU_affinity':affinity,'started_at':utc(),'index_sha256':index_hash,'global_deadline':index['deadline'],'per_unit_timeout_seconds':active[uid]['timeout_seconds'],'unit_effective_deadline_epoch':min(cutoff,time.time()+active[uid]['timeout_seconds'])})
   with heartbeat_lock:heartbeat_state={'status':'running','deadline':index['deadline'],'pending':len(pending),'active':list(active),'complete_count':len(completed),'failed_count':len(failed),'completed_units':list(completed),'failed_units':list(failed),'RSS':per,'pool_RSS_bytes':poolrss,'GPU':last_sample,'conservative_owned_GPU_delta_bytes':owned_delta,'new_launch_gate':gate,'unknown_external_compute':unknown,'cache_blocks':cache_blocks,'limits':config,'reserved_GPU_bytes':sum(int(specs[uid].get('gpu_allocator_budget_bytes',0)) for uid in active),'test_scoring_started':False}
   time.sleep(1)
 except BaseException as exc:
  reason='supervisor_error:'+repr(exc);raise
 finally:
  reason=reason or trip['reason']
  watchdog_stop.set();watch.join(timeout=3)
  cleanup_errors=[]
  for uid,state in active.items():
   try:stop_owned_group(state['pgid'])
   except Exception as error:cleanup_errors.append({'unit_id':uid,'signal_error':repr(error)})
   try:state['process'].wait(timeout=10)
   except Exception as error:cleanup_errors.append({'unit_id':uid,'wait_error':repr(error)})
   state['stdout'].close();state['stderr'].close()
   write(root/(uid+'.interrupted.json'),{'unit_id':uid,'reason':reason or 'pool_finally','pgid':state['pgid'],'stopped_at':utc(),'retry_clock_reset':False,'stderr_sha256':sha(state['stderr_path']),'stdout_sha256':sha(state['stdout_path'])})
  if cleanup_errors:reason=reason or 'cleanup_incomplete'
  write(root/'progress.json',{'status':'stopped' if reason else 'complete','at':utc(),'reason':reason,'pending':len(pending),'active':[],'cleanup_errors':cleanup_errors,'complete_count':len(completed),'failed_count':len(failed),'completed_units':completed,'failed_units':failed,'deadline':index['deadline'],'index_sha256':index_hash,'test_scoring_started':False})
  write(attempt/'terminal.json',read(root/'progress.json'))
 return 0 if not reason and not failed else 2
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--index',required=True);parser.add_argument('--index-sha256',required=True);args=parser.parse_args()
 try:code=run(args.index,args.index_sha256)
 except BaseException as error:
  write(Path(__file__).parent/'rejections'/('pool-'+str(time.time_ns())+'-'+str(os.getpid())+'.json'),{'status':'rejected_or_failed','at':utc(),'args':vars(args),'error':repr(error),'PID':os.getpid(),'score_started':False});raise
 sys.exit(code)
if __name__=='__main__':main()
