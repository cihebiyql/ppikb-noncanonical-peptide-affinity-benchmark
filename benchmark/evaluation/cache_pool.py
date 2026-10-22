"""At most seven CPU X encoders, leaving one CPU slot for allowed parity tests."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import json
import os
import signal
import subprocess
import time
import common
HERE=Path(__file__).resolve().parent
PYTHON='/data/qlyu/projects/peptide-binding-benchmark-20261020/common-prior-methods-20261021/.venv/bin/python'
def rss(pid):
    try:
        for line in Path(f'/proc/{pid}/status').read_text().splitlines():
            if line.startswith('VmRSS:'):return int(line.split()[1])*1024
    except FileNotFoundError:pass
    return 0
def one(index,job,manifest):
    folder=HERE/'producer-evidence';folder.mkdir(exist_ok=True)
    name=job['dataset_id']+'__'+job['method_id'];started=time.time();peak=0;reason=None
    contract=dict(stage='root-authorized-label-free-X-only',job_index=index,method_id=job['method_id'],dataset_id=job['dataset_id'],
        input_sha256=job['input_sha256'],adapter_tree_sha256=job['adapter_tree_sha256'],placeholder_pKd=0.0,
        cpu_threads=1,nice=15,rss_watch_bytes=4*1024**3,timeout_seconds=1800,gpu_count=0,
        global_deadline='same root 01:45Z, no paperclock reset',manifest_sha256=common.sha(HERE/'authorized-manifest-v2.json'))
    common.write_json(folder/(name+'.contract.json'),contract)
    argv=['nice','-n','15','taskset','-c',str(sorted(os.sched_getaffinity(0))[index%len(os.sched_getaffinity(0))]),PYTHON,str(HERE/'feature_cache.py'),
        '--manifest',str(HERE/'authorized-manifest-v2.json'),'--authorization',str(HERE/'cache-authorization-v2.json'),
        '--job-index',str(index),'--input',str(HERE/'stage/inputs'/(job['dataset_id']+'.jsonl')),
        '--methods-root',manifest['node_methods_root'],'--runner',manifest['node_runner'],'--output',str(HERE/'feature-caches-v2')]
    env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    with (folder/(name+'.stdout.log')).open('w') as out,(folder/(name+'.stderr.log')).open('w') as err:
        process=subprocess.Popen(argv,cwd=HERE,env=env,stdout=out,stderr=err,start_new_session=True)
        common.write_json(folder/(name+'.started.json'),dict(pid=process.pid,pgid=process.pid,argv=argv,started_unix=started))
        while process.poll() is None:
            current=rss(process.pid);peak=max(peak,current)
            if current>4*1024**3:reason='rss_exceeded'
            elif time.time()-started>1800:reason='timeout'
            if reason:
                os.killpg(process.pid,signal.SIGTERM)
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
                break
            time.sleep(1)
        code=process.wait()
    result=dict(status='complete' if code==0 and reason is None else 'failed',returncode=code,pid=process.pid,pgid=process.pid,
        job_index=index,dataset_id=job['dataset_id'],method_id=job['method_id'],seconds=time.time()-started,
        peak_sampled_rss_bytes=peak,stop_reason=reason,models_constructed=0,forwards=0,gold_reads=0)
    common.write_json(folder/(name+'.process.json'),result)
    return result
def main():
    assert os.uname().nodename=='node23'
    manifest=common.read_json(HERE/'authorized-manifest-v2.json')
    common.write_json(HERE/'pool-started.json',dict(pid=os.getpid(),max_parallel=7,parity_cpu_reserved=1,
        models_constructed=0,forwards=0,gold_or_checkpoint_reads=0))
    results=[]
    with ThreadPoolExecutor(max_workers=7) as pool:
        futures=[pool.submit(one,i,job,manifest) for i,job in enumerate(manifest['jobs'])]
        for future in as_completed(futures):
            results.append(future.result());common.write_json(HERE/'pool-progress.json',dict(completed=len(results),results=results))
    common.write_json(HERE/'pool-complete.json',dict(results=results,model_forwards=0,gold_reads=0))
    print(json.dumps(results))
if __name__=='__main__':main()
