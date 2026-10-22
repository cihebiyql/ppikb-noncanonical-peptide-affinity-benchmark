"""Bounded max16 CPU cache workers; only owned PGIDs may be terminated."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import json
import os
import signal
import subprocess
import threading
import time

HERE=Path(__file__).resolve().parent
LOCK=threading.Lock()
LIVE={}
def write(path,value):
    tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2));tmp.replace(path)
def rss(pid):
    try:
        for line in Path(f'/proc/{pid}/status').read_text().splitlines():
            if line.startswith('VmRSS:'):return int(line.split()[1])*1024
    except (FileNotFoundError,ProcessLookupError):pass
    return 0
def terminate(process):
    if process.poll() is None:
        os.killpg(process.pid,signal.SIGTERM)
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
def one(job,slot):
    contract=json.loads((HERE/job['contract_relative']).read_text())
    logroot=HERE/'logs';logroot.mkdir(exist_ok=True)
    out=logroot/(job['cell_id']+'.stdout.log');err=logroot/(job['cell_id']+'.stderr.log')
    affinity=sorted(os.sched_getaffinity(0))
    core=affinity[slot%len(affinity)]
    env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1')
    argv=['nice','-n','15','taskset','-c',str(core),contract['python'],str(HERE/'cache_worker.py'),str(HERE/job['contract_relative'])]
    started=time.time();peak=0;reason=None
    with out.open('w') as stdout,err.open('w') as stderr:
        process=subprocess.Popen(argv,cwd=HERE,env=env,stdout=stdout,stderr=stderr,start_new_session=True)
        with LOCK:
            LIVE[process.pid]=0
            write(HERE/'live-workers.json',dict(started_unix=time.time(),workers=LIVE))
        write(HERE/'receipts'/(job['cell_id']+'.started.json'),dict(pid=process.pid,pgid=process.pid,
            argv=argv,started_unix=started,contract=job['contract_relative'],cpu_affinity=core))
        while process.poll() is None:
            current=rss(process.pid);peak=max(peak,current)
            with LOCK:
                LIVE[process.pid]=current
                pooled=sum(LIVE.values())
            if current>contract['rss_bytes']:reason='rss_exceeded'
            elif time.time()-started>contract['timeout_seconds']:reason='timeout'
            elif pooled>64*1024**3:reason='pool_rss_exceeded'
            if reason:terminate(process);break
            time.sleep(1)
        returncode=process.wait()
    with LOCK:
        LIVE.pop(process.pid,None)
        write(HERE/'live-workers.json',dict(updated_unix=time.time(),workers=LIVE))
    result=dict(cell_id=job['cell_id'],pid=process.pid,pgid=process.pid,returncode=returncode,
        peak_rss_bytes=peak,seconds=time.time()-started,stop_reason=reason,stdout=str(out),stderr=str(err),
        status='completed' if returncode==0 and reason is None else 'failed')
    write(HERE/'receipts'/(job['cell_id']+'.process.json'),result)
    return result
def main():
    assert os.uname().nodename=='node23'
    (HERE/'receipts').mkdir(exist_ok=True)
    jobs=json.loads((HERE/'stage-manifest.json').read_text())['jobs']
    assert len(jobs)==20
    write(HERE/'pool-started.json',dict(pid=os.getpid(),host=os.uname().nodename,started_unix=time.time(),max_parallel=16,
        stage='CPU feature encoding only',models_fit=0))
    results=[]
    with ThreadPoolExecutor(max_workers=16) as pool:
        futures=[pool.submit(one,job,index) for index,job in enumerate(jobs)]
        for future in as_completed(futures):
            results.append(future.result())
            write(HERE/'pool-progress.json',dict(completed=len(results),total=20,results=results))
    write(HERE/'pool-complete.json',dict(status='complete',results=results,models_fit=0))
    print(json.dumps(results))
if __name__=='__main__':main()
