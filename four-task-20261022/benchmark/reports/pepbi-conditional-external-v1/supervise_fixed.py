"""Windows exact-runtime resource gate and bounded fixed-predict process supervision."""
import datetime as dt
import os
import subprocess
import sys
import time
import psutil
from common import HERE,RUN,sha,load,write

def now():return dt.datetime.now(dt.timezone.utc).isoformat()
def main():
    assert os.name=='nt'
    contract=load(HERE/'execution-contract.json');RUN.mkdir(parents=True,exist_ok=True)
    assert not (RUN/'launch.json').exists()
    for item in contract['input_hashes']:assert sha(item['path'])==item['sha256'],item['path']
    attempts=[];start=time.monotonic();cores=[]
    while time.monotonic()-start<contract['queue_timeout_seconds']:
        samples=[]
        for _ in range(3):
            busy=psutil.cpu_percent(interval=1,percpu=True)
            samples.append({'core_idle':[100-v for v in busy],'global_idle':100-sum(busy)/len(busy)})
        eligible=[i for i in range(len(samples[0]['core_idle'])) if min(s['core_idle'][i] for s in samples)>=60]
        eligible.sort(key=lambda i:min(s['core_idle'][i] for s in samples),reverse=True)
        available=psutil.virtual_memory().available
        passed=len(eligible)>=2 and min(s['global_idle'] for s in samples)>=40 and available>=contract['max_rss_bytes']+contract['os_reserve_bytes']
        attempts.append({'at':now(),'samples':samples,'available_bytes':available,'eligible_cores':eligible,'passed':passed})
        write(RUN/'capacity-gate.json',{'attempts':attempts,'admitted':passed})
        if passed:cores=eligible[:2];break
        time.sleep(10)
    if not cores:
        write(RUN/'admission-terminal.json',{'status':'finite_queue_budget_expired','new_model_predictions':0});return 3
    environment=dict(os.environ,PEPBI_CPU_AFFINITY=','.join(map(str,cores)),OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',NUMEXPR_NUM_THREADS='2',CUDA_VISIBLE_DEVICES='')
    out=(RUN/'stdout.log').open('w',encoding='utf-8');err=(RUN/'stderr.log').open('w',encoding='utf-8')
    proc=subprocess.Popen([sys.executable,'-B',str(HERE/'run_fixed.py')],cwd=HERE,env=environment,stdout=out,stderr=err,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP|psutil.IDLE_PRIORITY_CLASS)
    owned=psutil.Process(proc.pid);owned.cpu_affinity(cores);owned.nice(psutil.IDLE_PRIORITY_CLASS)
    receipt={'pid':proc.pid,'windows_process_group_leader_pid':proc.pid,'started_at':now(),'cpu_affinity':cores,
        'priority':'IDLE_PRIORITY_CLASS','posix_nice':None,'posix_nice_unavailable_on_windows':True,
        'contract_sha256':sha(HERE/'execution-contract.json'),'max_rss_bytes':contract['max_rss_bytes'],'peak_rss_bytes':0,
        'new_fit_count':0,'gpu':False,'termination_reason':None}
    write(RUN/'launch.json',receipt);started=time.monotonic()
    while proc.poll() is None:
        try:family=[owned]+owned.children(recursive=True);rss=sum(p.memory_info().rss for p in family if p.is_running())
        except psutil.Error:rss=0
        receipt['peak_rss_bytes']=max(receipt['peak_rss_bytes'],rss)
        reason=None
        if rss>contract['max_rss_bytes']:reason='owned-RSS-cap'
        if time.monotonic()-started>contract['timeout_seconds']:reason='owned-timeout'
        if psutil.virtual_memory().available<1024**3:reason='emergency-OS-memory-reserve'
        if reason:
            receipt['termination_reason']=reason
            for child in reversed(owned.children(recursive=True)):
                try:child.kill()
                except psutil.Error:pass
            proc.kill();break
        time.sleep(.25)
    exitcode=proc.wait();out.close();err.close()
    receipt.update(exit_code=exitcode,elapsed_seconds=time.monotonic()-started,completed_at=now(),worker_pid_absent=not psutil.pid_exists(proc.pid))
    write(RUN/'process-receipt.json',receipt)
    print(receipt);return 0 if exitcode==0 and not receipt['termination_reason'] else 2
if __name__=='__main__':raise SystemExit(main())
