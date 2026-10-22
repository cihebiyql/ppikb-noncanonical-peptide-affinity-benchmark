"""Root-authorized <=600s continuation only when original train is atomic."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import time
import cache_pool

HERE=Path(__file__).resolve().parent
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    original=json.loads((HERE/'pool-complete.json').read_text())
    folder=HERE/'validation-cache-completion-v2';folder.mkdir(exist_ok=False)
    results=[]
    for old in original['results']:
        if old['status']!='failed':continue
        cell=old['cell_id']
        contract=json.loads((HERE/'contracts'/(cell+'.json')).read_text())
        derived=json.loads(Path(contract['spec_path']).read_text())
        key=derived['split_id']+'-'+derived['regime']+'-'+derived['method_id']
        train=Path(derived['cache_root'])/(key+'-train.pkl')
        val=Path(derived['cache_root'])/(key+'-validation-'+derived['validation_scope']+'.pkl')
        eligible=old['stop_reason']=='timeout' and train.is_file() and train.with_suffix('.input-audit.jsonl').is_file() and not val.exists()
        if not eligible:
            results.append(dict(cell_id=cell,status='not_retried',reason='No atomic train+audit / validation already present / non-timeout; report to root',
                                atomic_train_present=train.is_file(),validation_present=val.is_file()))
            continue
        contract.update(stage='validation-cache-completion-v2',timeout_seconds=600,
            original_process_receipt=str(HERE/'receipts'/(cell+'.process.json')),
            original_process_receipt_sha256=sha(HERE/'receipts'/(cell+'.process.json')),
            global_deadline='same root 01:45Z deadline; not reset',paperclock_reset=False)
        contract_path=folder/(cell+'.contract.json')
        cache_pool.write(contract_path,contract)
        env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
        argv=['nice','-n','15','taskset','-c',str(sorted(os.sched_getaffinity(0))[0]),contract['python'],
              str(HERE/'validation_cache_worker_v2.py'),str(contract_path)]
        started=time.time();peak=0;reason=None
        with (folder/(cell+'.stdout.log')).open('w') as out,(folder/(cell+'.stderr.log')).open('w') as err:
            process=subprocess.Popen(argv,cwd=HERE,env=env,stdout=out,stderr=err,start_new_session=True)
            cache_pool.write(folder/(cell+'.started.json'),dict(pid=process.pid,pgid=process.pid,argv=argv,started_unix=started))
            while process.poll() is None:
                current=cache_pool.rss(process.pid);peak=max(peak,current)
                if current>4*1024**3:reason='rss_exceeded'
                elif time.time()-started>600:reason='timeout'
                if reason:cache_pool.terminate(process);break
                time.sleep(1)
            code=process.wait()
        result=dict(cell_id=cell,status='completed' if code==0 and reason is None else 'failed',returncode=code,
            pid=process.pid,pgid=process.pid,seconds=time.time()-started,peak_rss_bytes=peak,stop_reason=reason,
            original_failed_pid=old['pid'],global_deadline_preserved=True)
        cache_pool.write(folder/(cell+'.process.json'),result)
        results.append(result)
    cache_pool.write(folder/'completion-index.json',dict(results=results,models_fit=0))
    print(json.dumps(results))
if __name__=='__main__':main()
