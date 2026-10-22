"""One owned GPU worker for root-authorized 200 x three post-barrier scores."""
import argparse
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
import time

from score_common import HERE, HOST, GIB, GPU_UUID, runtime_gate, preflight, score_outputs, validate_complete, reference, read, path, checked, sha, write, utc, deadline, process_table
from pool_supervisor import gpu_probe, ownership_gate
from common import stop_owned_group


def session_state(pgid, table=None):
    table = process_table() if table is None else table
    members = {pid:r for pid,r in table.items() if r['pgid']==pgid and r['session']==pgid and r['uid']==os.getuid()}
    return {'pids':sorted(members), 'rss_bytes':sum(r['rss'] for r in members.values()), 'pgid':pgid}


def full_timeout_fits(cutoff, timeout=1200, now=None):
    return (time.time() if now is None else now) + timeout <= cutoff


def watchdog_decision(global_cutoff, state, snapshot, interrupted=False, wall_now=None, mono_now=None):
    wall_now=time.time() if wall_now is None else wall_now
    mono_now=time.monotonic() if mono_now is None else mono_now
    if wall_now>=global_cutoff:return 'original_global_deadline'
    if interrupted:return 'pool_interrupted'
    if state and snapshot['rss_bytes']>4*GIB:return 'owned_worker_RSS_above_4GiB'
    if state and mono_now>=state['monotonic_deadline']:return 'unit_original_1200sec_deadline'
    return None


def cleanup_private(pgid, process):
    stop_owned_group(pgid, grace=.1)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        stop_owned_group(pgid, grace=0)
        process.wait(timeout=5)
    if session_state(pgid)['pids']:
        raise RuntimeError('Private session still has live handles after cleanup')


def verify_index(index_path, expected_sha):
    index = read(checked(index_path, expected_sha))
    if index.get('schema')!='score-unit-index-v1' or index.get('issued') is not True:
        raise PermissionError('Root-issued scoring index required')
    runtime_gate(index)
    checked(__file__, index['supervisor_sha256'])
    checked(HERE/'score_unit.py', index['unit_sha256'])
    checked(HERE/'score_common.py', index['common_sha256'])
    cutoff = deadline(index['deadline'])
    if not path(index['output_root']).resolve().is_relative_to(HERE.resolve()):
        raise ValueError('Pool output must stay in owned scoring-launch directory')
    if int(index.get('max_concurrent',0))!=1 or int(index.get('timeout_seconds',0))!=1200:
        raise ValueError('One GPU worker / 1200 second unit policy required')
    if len(index.get('units',[]))!=200 or len({u['unit_id'] for u in index['units']})!=200:
        raise ValueError('Exactly 200 distinct issued scoring units required')
    contexts = {}
    for unit in index['units']:
        binding_path = reference(unit['binding'])
        context = preflight(binding_path, require_private_session=False, reserve_full_timeout=False)
        if context['binding']['unit_id']!=unit['unit_id'] or context['binding']['deadline']!=index['deadline']:
            raise ValueError('Index/binding identity or deadline mismatch')
        contexts[unit['unit_id']]=context
    identities={ctx['identity'] for ctx in contexts.values()}
    methods={x[0] for x in identities};panels={x[1] for x in identities}
    expected={(m,p,r,s) for m in methods for p in panels for r in ('NC_only','standard_only') for s in range(10)}
    if len(methods)!=5 or len(panels)!=2 or len(identities)!=200 or identities!=expected:
        raise ValueError('Incomplete five-method/two-panel/two-regime/ten-seed grid')
    receipt_roots=[str(path(ctx['binding']['receipt_root']).resolve()) for ctx in contexts.values()]
    if len(set(receipt_roots))!=200:
        raise ValueError('Scoring receipt roots must be unique')
    output_dirs=[str(p.resolve()) for ctx in contexts.values() for p in score_outputs(ctx)]
    if len(set(output_dirs))!=600:
        raise ValueError('Scoring output directories must be 600 distinct paths')
    return index, contexts, cutoff


def run(index_path, index_sha):
    index, contexts, cutoff = verify_index(index_path,index_sha)
    root=path(index['output_root']);root.mkdir(parents=True,exist_ok=True)
    attempt=root/'attempts'/(str(time.time_ns())+'-'+str(os.getpid()));attempt.mkdir(parents=True,exist_ok=False)
    completed=[];failed=[];pending=[]
    for unit in index['units']:
        context=contexts[unit['unit_id']];receiptroot=path(context['binding']['receipt_root'])
        if (receiptroot/'unit-complete.json').exists():
            validate_complete(receiptroot,unit['binding']['sha256']);completed.append(unit['unit_id'])
        elif receiptroot.exists():
            failed.append({'unit_id':unit['unit_id'],'reason':'preserved_failed_or_incomplete_no_retry'})
        elif (root/(unit['unit_id']+'.stdout.log')).exists() or (root/(unit['unit_id']+'.stderr.log')).exists():
            failed.append({'unit_id':unit['unit_id'],'reason':'preserved_prior_logs_no_retry'})
        else:
            pending.append(unit)
    samples=[]
    for i in range(3):
        sample=gpu_probe();samples.append(sample)
        okay,_=ownership_gate(sample,set())
        if not okay:raise RuntimeError('Unknown/external compute PID at scoring startup')
        if sample['utilization_percent']>int(index.get('startup_max_utilization_percent',20)):
            raise RuntimeError('Scoring startup utilization above low-utilization gate')
        if sample['memory_used_bytes']>10*GIB:
            raise RuntimeError('Desktop baseline leaves insufficient conservative GPU headroom')
        if i<2:time.sleep(1)
    baseline=min(s['memory_used_bytes'] for s in samples)
    write(attempt/'startup-gpu-probes.json',{'samples':samples,'baseline_bytes':baseline,'index_sha256':index_sha,'deadline':index['deadline']})
    active={'state':None};interrupted=threading.Event();stop=threading.Event();trip={'reason':None};heartbeat={'status':'running'};lock=threading.Lock()
    reason=None;last_gpu=None;unknown=[];probe_error=None
    def signal_stop(signum,frame):interrupted.set()
    signal.signal(signal.SIGTERM,signal_stop);signal.signal(signal.SIGINT,signal_stop)
    def watchdog():
        last=0
        try:
            while not stop.wait(.2):
                state=active['state'];snapshot=session_state(state['pgid']) if state else None
                why=watchdog_decision(cutoff,state,snapshot,interrupted.is_set())
                if why:
                    trip['reason']=why
                    if state:stop_owned_group(state['pgid'],grace=0)
                if time.monotonic()-last>=1:
                    with lock:record=dict(heartbeat)
                    record.update(at=utc(),watchdog_reason=trip['reason'],owned_private_session=snapshot,
                                  original_global_deadline=index['deadline'],index_sha256=index_sha)
                    write(root/'progress.json',record);last=time.monotonic()
        except BaseException as error:
            trip['reason']='watchdog_failed:'+repr(error)
            state=active['state']
            if state:
                try:stop_owned_group(state['pgid'],grace=0)
                except Exception:pass
    watch=threading.Thread(target=watchdog,daemon=True);watch.start()
    try:
        while pending or active['state']:
            if trip['reason'] or interrupted.is_set() or time.time()>=cutoff:
                reason=trip['reason'] or ('pool_interrupted' if interrupted.is_set() else 'original_global_deadline');break
            state=active['state']
            if state and state['process'].poll() is not None:
                uid=state['unit']['unit_id'];code=state['process'].returncode
                cleanup_private(state['pgid'],state['process'])
                state['stdout'].close();state['stderr'].close()
                receiptroot=path(contexts[uid]['binding']['receipt_root']);receiptroot.mkdir(parents=True,exist_ok=True)
                exit_proof={'unit_id':uid,'binding_sha256':state['unit']['binding']['sha256'],'pool_pid':os.getpid(),
                            'pid':state['process'].pid,'pgid':state['pgid'],'exit_code':code,
                            'private_session_handles_absent':not session_state(state['pgid'])['pids'],
                            'handles_absent_verified_at':utc(),'stdout_path':str(state['stdout_path']),
                            'stdout_sha256':sha(state['stdout_path']),'stderr_path':str(state['stderr_path']),
                            'stderr_sha256':sha(state['stderr_path']),'index_sha256':index_sha}
                exit_path=receiptroot/'pool-exit-verification.json'
                if exit_path.exists():raise FileExistsError('Preserve prior actual exit verification')
                write(exit_path,exit_proof);(receiptroot/'pool-exit-verification.sha256').write_text(sha(exit_path)+'\n')
                good=False
                if code==0:
                    try:validate_complete(receiptroot,state['unit']['binding']['sha256']);good=True
                    except Exception as error:failure=repr(error)
                else:failure=state.get('watchdog_reason') or 'unit_exit_'+str(code)
                write(attempt/(uid+'.terminal.json'),{'unit_id':uid,'exit_code':code,'status':'complete' if good else 'failed','reason':None if good else failure,'finished_at':utc(),'exit_verification_path':str(exit_path),'exit_verification_sha256':sha(exit_path)})
                if good:completed.append(uid)
                else:failed.append({'unit_id':uid,'reason':failure})
                active['state']=None;state=None
            owned=set(session_state(state['pgid'])['pids']) if state else set()
            try:
                last_gpu=gpu_probe();okay,unknown=ownership_gate(last_gpu,owned);probe_error=None
            except Exception as error:
                okay=False;unknown=[];probe_error=repr(error);last_gpu=None
            # Unknown compute owners/probe errors only block NEW launches. Never
            # signal outsiders or attribute their GPU memory to this worker.
            if state and last_gpu:
                reported=sum(p['used_gpu_memory_bytes'] or 0 for p in last_gpu['compute'] if p['pid'] in owned)
                if reported>3*GIB:
                    reason='owned_worker_reported_GPU_above_3GiB';break
            if not state and pending and okay and last_gpu and last_gpu['utilization_percent']<=int(index.get('launch_max_utilization_percent',20)):
                if not full_timeout_fits(cutoff):
                    reason='insufficient_original_window_for_full_1200sec_unit';break
                unit=pending.pop(0);uid=unit['unit_id'];context=contexts[uid]
                # Recheck ALL gates immediately before launch, without model/gold imports.
                preflight(context['binding_path'],require_private_session=False)
                stdout_path=root/(uid+'.stdout.log');stderr_path=root/(uid+'.stderr.log')
                stdout=stdout_path.open('xb');stderr=stderr_path.open('xb')
                parent=process_table()[os.getpid()]
                env=dict(os.environ,OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',NUMEXPR_NUM_THREADS='2',
                         PYTHONDONTWRITEBYTECODE='1',NC_SCORE_POOL_OWNER_PID=str(os.getpid()),
                         NC_SCORE_POOL_OWNER_START_TICKS=str(parent['start_ticks']),NC_SCORE_POOL_INDEX_SHA256=index_sha,
                         NC_SCORE_POOL_BINDING_PATH=str(context['binding_path']),NC_SCORE_POOL_BINDING_SHA256=unit['binding']['sha256'],
                         NC_SCORE_UNIT_STDOUT_PATH=str(stdout_path),NC_SCORE_UNIT_STDERR_PATH=str(stderr_path))
                cpus=sorted(os.sched_getaffinity(0))[:2]
                if len(cpus)!=2:raise RuntimeError('Two CPU cores required')
                def child_setup():os.sched_setaffinity(0,set(cpus));os.nice(10)
                argv=[index['python'],str(HERE/'score_unit.py'),'--binding',str(context['binding_path'])]
                child=subprocess.Popen(argv,stdout=stdout,stderr=stderr,env=env,start_new_session=True,preexec_fn=child_setup)
                active['state']={'unit':unit,'process':child,'pgid':child.pid,'stdout':stdout,'stderr':stderr,
                                 'stdout_path':stdout_path,'stderr_path':stderr_path,'monotonic_deadline':time.monotonic()+1200}
                write(attempt/(uid+'.started.json'),{'argv':argv,'pid':child.pid,'pgid':child.pid,'private_session_id':child.pid,
                      'CPU_affinity':cpus,'started_at':utc(),'global_deadline':index['deadline'],'timeout_seconds':1200,
                      'binding_sha256':unit['binding']['sha256'],'index_sha256':index_sha})
            with lock:
                heartbeat={'status':'running','pending':len(pending),'active':active['state']['unit']['unit_id'] if active['state'] else None,
                           'completed_units':list(completed),'failed_units':list(failed),'complete_count':len(completed),
                           'failed_count':len(failed),'GPU':last_gpu,'new_launch_gate':okay,'unknown_compute_processes':unknown,
                           'probe_error':probe_error,'worker_limit':1,'worker_RSS_limit_bytes':4*GIB,'allocator_budget_bytes':3*GIB}
            time.sleep(1)
    except BaseException as error:
        reason='supervisor_error:'+repr(error);raise
    finally:
        stop.set();watch.join(timeout=3)
        state=active['state']
        cleanup_errors=[]
        if state:
            try:cleanup_private(state['pgid'],state['process'])
            except Exception as error:cleanup_errors.append(repr(error))
            state['stdout'].close();state['stderr'].close()
            write(attempt/(state['unit']['unit_id']+'.interrupted.json'),{'unit_id':state['unit']['unit_id'],'reason':reason or trip['reason'],
                  'pid':state['process'].pid,'pgid':state['pgid'],'exit_code':state['process'].returncode,
                  'private_session_handles_absent':not session_state(state['pgid'])['pids'],
                  'stdout_sha256':sha(state['stdout_path']),'stderr_sha256':sha(state['stderr_path']),
                  'finished_at':utc(),'original_deadline':index['deadline'],'retry_clock_reset':False})
        final={'status':'stopped' if reason or trip['reason'] else 'complete','reason':reason or trip['reason'],
               'at':utc(),'pending':len(pending),'active':None,'completed_units':completed,'failed_units':failed,
               'complete_count':len(completed),'failed_count':len(failed),'cleanup_errors':cleanup_errors,
               'deadline':index['deadline'],'index_sha256':index_sha,'no_retry':True}
        write(root/'progress.json',final);write(attempt/'terminal.json',final)
    return 0 if not reason and not trip['reason'] and not failed and not pending else 2


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--index',required=True);parser.add_argument('--index-sha256',required=True)
    args=parser.parse_args()
    try:code=run(args.index,args.index_sha256)
    except BaseException as error:
        write(HERE/'rejections'/('pool-'+str(time.time_ns())+'-'+str(os.getpid())+'.json'),{'status':'rejected_or_failed','at':utc(),'error':repr(error),'index_path':args.index,'pid':os.getpid()});raise
    raise SystemExit(code)


if __name__=='__main__':main()
