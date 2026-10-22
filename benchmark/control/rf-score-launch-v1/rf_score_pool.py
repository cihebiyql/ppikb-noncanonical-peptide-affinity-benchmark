"""Four CPU-only owned RF post-joint three-dataset scoring workers."""
import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
from rfs_common import HERE,PROJECT,CPU_IDS,GIB,PANELS,ProgressWriter,runtime_gate,preflight,validate_complete,full_timeout_fits,cpu_probe,reference,read,path,sha,checked,utc,deadline,process_table,stop_owned_group,write,score_outputs


def private_state(pgid,table=None):
    table=process_table() if table is None else table
    members={pid:r for pid,r in table.items() if r['pgid']==pgid and r['session']==pgid and r['uid']==os.getuid()}
    return {'pgid':pgid,'pids':sorted(members),'rss_bytes':sum(r['rss'] for r in members.values())}


def cleanup(pgid,process):
    stop_owned_group(pgid,grace=.1)
    try:process.wait(timeout=5)
    except subprocess.TimeoutExpired:stop_owned_group(pgid,grace=0);process.wait(timeout=5)
    if private_state(pgid)['pids']:raise RuntimeError('RF private process session still populated')


def budget_decision(cutoff,states,stats,pool_rss,interrupted=False,writer_error=None,wall=None,mono=None):
    wall=time.time() if wall is None else wall;mono=time.monotonic() if mono is None else mono
    if wall>=cutoff:return 'original_global_deadline'
    if interrupted:return 'pool_interrupted'
    if writer_error:return 'persistent_writer_error:'+writer_error
    if pool_rss>8*GIB:return 'owned_RF_pool_RSS_above_8GiB'
    if any(s['rss_bytes']>2*GIB for s in stats.values()):return 'owned_RF_worker_RSS_above_2GiB'
    if any(mono>=s['unit_monotonic_deadline'] for s in states.values()):return 'original_RF_unit_1800sec_deadline'
    return None


def verify_index(index_path,expected_sha):
    index=read(checked(index_path,expected_sha))
    if index.get('schema')!='rf-score-unit-index-v1' or index.get('issued') is not True:raise PermissionError('Root-issued actual RF index required')
    runtime_gate(index)
    checked(__file__,index['supervisor_sha256']);checked(HERE/'rf_score_unit.py',index['unit_sha256']);checked(HERE/'rfs_common.py',index['common_sha256'])
    cutoff=deadline(index['deadline'])
    if index.get('max_concurrent')!=4 or index.get('timeout_seconds')!=1800:raise ValueError('RF plan requires four CPU1 workers / 1800sec units')
    if not path(index['output_root']).resolve().is_relative_to(HERE.resolve()):raise ValueError('RF launch artifacts outside owned directory')
    units=index['units']
    if len(units)!=40 or len({u['unit_id'] for u in units})!=40:raise ValueError('Exactly 40 unique RF units required')
    contexts={}
    for unit in units:
        p=reference(unit['binding']);ctx=preflight(p,private=False,reserve=False)
        if ctx['binding']['unit_id']!=unit['unit_id'] or ctx['binding']['deadline']!=index['deadline']:raise ValueError('RF index/binding identity mismatch')
        contexts[unit['unit_id']]=ctx
    if {c['coordinate'] for c in contexts.values()}!={(p,r,s) for p in PANELS for r in ('NC_only','standard_only') for s in range(10)}:raise ValueError('Incomplete RF2panel/2regime/10seed grid')
    roots=[str(path(c['binding']['receipt_root']).resolve()) for c in contexts.values()]
    if len(set(roots))!=40:raise ValueError('RF score units share receipt roots')
    outputs=[str(p.resolve()) for c in contexts.values() for p in score_outputs(c)]
    if len(outputs)!=120 or len(set(outputs))!=120:raise ValueError('RF score outputs must be120 distinct paths')
    return index,contexts,cutoff


def run(index_path,index_sha):
    index,contexts,cutoff=verify_index(index_path,index_sha)
    root=path(index['output_root']);root.mkdir(parents=True,exist_ok=True)
    attempt=root/'attempts'/(str(time.time_ns())+'-'+str(os.getpid()));attempt.mkdir(parents=True,exist_ok=False)
    writer=ProgressWriter();pending=[];complete=[];failed=[];active={};lock=threading.Lock();heart={'status':'running'}
    interrupted=threading.Event();stop=threading.Event();trip={'reason':None};reason=None
    for unit in index['units']:
        ctx=contexts[unit['unit_id']];receipt=path(ctx['binding']['receipt_root'])
        if (receipt/'unit-complete.json').exists():validate_complete(receipt,unit['binding']['sha256']);complete.append(unit['unit_id'])
        elif receipt.exists() or any(p.exists() for p in score_outputs(ctx)) or (root/(unit['unit_id']+'.stdout.log')).exists() or (root/(unit['unit_id']+'.stderr.log')).exists():failed.append({'unit_id':unit['unit_id'],'reason':'preserved_failed_or_incomplete_no_retry'})
        else:pending.append(unit)
    initial=cpu_probe()
    if initial['available_memory_bytes']<8*GIB:writer.close();raise RuntimeError('Fresh CPU proof has less than8GiB available; no launch')
    writer.submit(attempt/'startup-CPU-proof.json',{'actual':initial,'index_sha256':index_sha,'CPU_slots':CPU_IDS,'global_deadline':index['deadline']},wait=True)
    def request_stop(signum,frame):interrupted.set()
    signal.signal(signal.SIGTERM,request_stop);signal.signal(signal.SIGINT,request_stop)
    def watchdog():
        last=0
        try:
            while not stop.wait(.2):
                states=dict(active);table=process_table();stats={uid:private_state(s['pgid'],table) for uid,s in states.items()}
                pool_rss=table.get(os.getpid(),{}).get('rss',0)+sum(v['rss_bytes'] for v in stats.values())
                why=budget_decision(cutoff,states,stats,pool_rss,interrupted.is_set(),writer.error)
                if why:
                    trip['reason']=why
                    for s in states.values():stop_owned_group(s['pgid'],grace=0)
                if time.monotonic()-last>=1:
                    with lock:record=dict(heart)
                    record.update(at=utc(),watchdog_reason=trip['reason'],worker_RSS=stats,pool_RSS_bytes=pool_rss,
                                  deadline=index['deadline'],index_sha256=index_sha,RF_score_stage=True)
                    writer.submit(root/'progress.json',record,wait=False);last=time.monotonic()
        except BaseException as error:
            trip['reason']='watchdog_failed:'+repr(error)
            for s in dict(active).values():
                try:stop_owned_group(s['pgid'],grace=0)
                except Exception:pass
    watch=threading.Thread(target=watchdog,daemon=True,name='rf-resource-watchdog');watch.start()
    try:
        while pending or active:
            if trip['reason'] or interrupted.is_set() or time.time()>=cutoff:
                reason=trip['reason'] or ('pool_interrupted' if interrupted.is_set() else 'original_global_deadline');break
            for uid,state in list(active.items()):
                code=state['process'].poll()
                if code is None:continue
                cleanup(state['pgid'],state['process']);state['stdout'].close();state['stderr'].close()
                receipts=path(contexts[uid]['binding']['receipt_root']);receipts.mkdir(parents=True,exist_ok=True)
                proof={'unit_id':uid,'binding_sha256':state['unit']['binding']['sha256'],'pool_pid':os.getpid(),
                       'pid':state['process'].pid,'pgid':state['pgid'],'exit_code':code,'private_session_handles_absent':not private_state(state['pgid'])['pids'],
                       'handles_absent_verified_at':utc(),'stdout_path':str(state['stdout_path']),'stdout_sha256':sha(state['stdout_path']),
                       'stderr_path':str(state['stderr_path']),'stderr_sha256':sha(state['stderr_path']),'index_sha256':index_sha}
                proofpath=receipts/'pool-exit-verification.json'
                if proofpath.exists():raise FileExistsError('Preserve prior RF exit proof')
                writer.submit(proofpath,proof,wait=True);(receipts/'pool-exit-verification.sha256').write_text(sha(proofpath)+'\n')
                good=False
                if code==0:
                    try:validate_complete(receipts,state['unit']['binding']['sha256']);good=True
                    except Exception as error:failure=repr(error)
                else:failure='RF_unit_exit_'+str(code)
                writer.submit(attempt/(uid+'.terminal.json'),{'unit_id':uid,'status':'complete' if good else 'failed','exit_code':code,'reason':None if good else failure,'exit_verification_sha256':sha(proofpath),'ended_at':utc()},wait=True)
                if good:complete.append(uid)
                else:failed.append({'unit_id':uid,'reason':failure})
                del active[uid]
            current=cpu_probe();launch_gate=current['available_memory_bytes']>=2*GIB and current['load_average'][0]<=float(index.get('launch_max_load_1min',12.))
            if pending and len(active)<4 and launch_gate:
                if not full_timeout_fits(cutoff):reason='insufficient_original_window_for_full_1800sec_unit';break
                unit=pending.pop(0);uid=unit['unit_id'];ctx=contexts[uid]
                preflight(ctx['binding_path'],private=False)
                slot=next(cpu for cpu in CPU_IDS if cpu not in {s['cpu'] for s in active.values()})
                stdout_path=root/(uid+'.stdout.log');stderr_path=root/(uid+'.stderr.log')
                stdout=stdout_path.open('xb');stderr=stderr_path.open('xb');parent=process_table()[os.getpid()]
                env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',
                         PYTHONDONTWRITEBYTECODE='1',RF_SCORE_POOL_OWNER_PID=str(os.getpid()),RF_SCORE_POOL_OWNER_START_TICKS=str(parent['start_ticks']),RF_SCORE_POOL_INDEX_SHA256=index_sha,
                         RF_SCORE_POOL_BINDING_PATH=str(ctx['binding_path']),RF_SCORE_POOL_BINDING_SHA256=unit['binding']['sha256'])
                def setup():os.sched_setaffinity(0,{slot});os.setpriority(os.PRIO_PROCESS,0,10)
                argv=[index['python'],str(HERE/'rf_score_unit.py'),'--binding',str(ctx['binding_path'])]
                child=subprocess.Popen(argv,stdout=stdout,stderr=stderr,env=env,start_new_session=True,preexec_fn=setup)
                active[uid]={'unit':unit,'process':child,'pgid':child.pid,'cpu':slot,'stdout':stdout,'stderr':stderr,
                             'stdout_path':stdout_path,'stderr_path':stderr_path,'unit_monotonic_deadline':time.monotonic()+1800}
                writer.submit(attempt/(uid+'.started.json'),{'argv':argv,'pid':child.pid,'pgid':child.pid,'private_session':child.pid,'CPU_affinity':[slot],'nice':10,
                              'actual_CPU_proof':current,'started_at':utc(),'binding_sha256':unit['binding']['sha256'],'index_sha256':index_sha,'global_deadline':index['deadline'],'timeout_seconds':1800},wait=True)
            with lock:heart={'status':'running','pending':len(pending),'active':list(active),'complete_count':len(complete),'failed_count':len(failed),
                             'completed_units':list(complete),'failed_units':list(failed),'CPU':current,'new_launch_gate':launch_gate,
                             'RF_only_limits':{'workers':4,'CPU_threads_each':1,'RSS_each_bytes':2*GIB,'pool_RSS_bytes':8*GIB,'CUDA_VISIBLE_DEVICES':''}}
            time.sleep(.2)
    except BaseException as error:reason='supervisor_error:'+repr(error);raise
    finally:
        errors=[]
        # Resource watchdog remains alive during cleanup and writer retries.
        for uid,state in list(active.items()):
            try:cleanup(state['pgid'],state['process'])
            except Exception as error:errors.append({'unit_id':uid,'error':repr(error)})
            state['stdout'].close();state['stderr'].close()
            try:writer.submit(attempt/(uid+'.interrupted.json'),{'unit_id':uid,'reason':reason or trip['reason'],'pid':state['process'].pid,'pgid':state['pgid'],
                              'exit_code':state['process'].returncode,'private_session_handles_absent':not private_state(state['pgid'])['pids'],
                              'stdout_sha256':sha(state['stdout_path']),'stderr_sha256':sha(state['stderr_path']),'ended_at':utc(),'retry_clock_reset':False},wait=True)
            except Exception as error:errors.append({'unit_id':uid,'artifact_error':repr(error)})
            del active[uid]
        stop.set();watch.join(timeout=3)
        final={'status':'stopped' if reason or trip['reason'] or errors or writer.error else 'complete','reason':reason or trip['reason'] or writer.error,
               'at':utc(),'pending':len(pending),'active':[],'complete_count':len(complete),'failed_count':len(failed),
               'completed_units':complete,'failed_units':failed,'cleanup_errors':errors,'deadline':index['deadline'],'index_sha256':index_sha,
               'RF_score_stage':True,'no_retry':True,'writer_error':writer.error}
        try:writer.submit(root/'progress.json',final,wait=True);writer.submit(attempt/'terminal.json',final,wait=True)
        finally:writer.close()
    return 0 if not reason and not trip['reason'] and not failed and not pending and not errors and not writer.error else 2


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--index',required=True);parser.add_argument('--index-sha256',required=True);args=parser.parse_args()
    try:code=run(args.index,args.index_sha256)
    except BaseException as error:
        try:write(HERE/'rejections'/('pool-'+str(time.time_ns())+'-'+str(os.getpid())+'.json'),{'status':'rejected_or_failed','at':utc(),'error':repr(error),'index_path':args.index,'pid':os.getpid(),'RF_score_stage':True})
        except Exception:pass
        raise
    raise SystemExit(code)


if __name__=='__main__':main()
