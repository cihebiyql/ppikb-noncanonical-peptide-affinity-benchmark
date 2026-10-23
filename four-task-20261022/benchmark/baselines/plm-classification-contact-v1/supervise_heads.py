"""CPU2/3GiB finite admission queue and owned PGID control for matched manual controls."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import statistics
import subprocess
import time
import psutil

def sha(path):
    digest=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(1024**2),b''):digest.update(block)
    return digest.hexdigest()
def write(path,value):
    temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(value,indent=2),encoding='utf-8');temporary.replace(path)
def uid_rss():
    total=0
    for p in psutil.process_iter(['uids','memory_info']):
        try:
            if p.info['uids'].real==os.getuid():total+=p.info['memory_info'].rss
        except (psutil.Error,TypeError):pass
    return total
def now():return dt.datetime.now(dt.timezone.utc).isoformat()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--spec',required=True,type=Path);args=parser.parse_args()
    spec=json.loads(args.spec.read_text())
    assert socket.gethostname()=='node23'
    assert spec['cpu_affinity']==[25,26] and spec['reserved_sibling_cores']==[57,58]
    assert spec['max_rss_bytes']<=3*1024**3 and spec['cpu_threads']==2
    assert set(spec['cpu_affinity'])<=os.sched_getaffinity(0)
    output=Path(spec['output']);output.mkdir(parents=True,exist_ok=False)
    checks=[{'path':x['path'],'expected':x['sha256'],'actual':sha(x['path'])} for x in spec['input_hashes']]
    write(output/'input-hash-checks.json',checks)
    assert all(x['expected']==x['actual'] for x in checks)
    queue_started=time.monotonic();gate={'started_at':now(),'attempts':[],'admitted':False}
    while time.monotonic()-queue_started<spec['queue_timeout_seconds']:
        samples=[]
        for _ in range(3):
            idle=[100-value for value in psutil.cpu_percent(interval=1,percpu=True)]
            samples.append({'global_idle_percent':statistics.mean(idle),
                'reserved_core_idle_percent':{str(i):idle[i] for i in [25,26,57,58]}})
        attempt={'at':now(),'samples':samples,'mem_available_bytes':psutil.virtual_memory().available,'uid_rss_bytes':uid_rss()}
        admitted=all(s['global_idle_percent']>=40 and min(s['reserved_core_idle_percent'].values())>=60 for s in samples)
        admitted &= attempt['mem_available_bytes']>=36*1024**3
        admitted &= attempt['uid_rss_bytes']+spec['max_rss_bytes']<=80*1024**3
        attempt['passed']=bool(admitted);gate['attempts'].append(attempt);gate['admitted']=bool(admitted)
        write(output/'capacity-gate.json',gate)
        if admitted:break
        time.sleep(30)
    if not gate['admitted']:
        write(output/'admission-terminal.json',{'status':'queue_budget_expired','scientific_jobs_launched':0,'at':now()});return 3
    environment=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',NUMEXPR_NUM_THREADS='2',PYTHONDONTWRITEBYTECODE='1')
    def affinity():os.sched_setaffinity(0,set(spec['cpu_affinity']));os.nice(19)
    stdout=(output/'stdout.log').open('w');stderr=(output/'stderr.log').open('w')
    proc=subprocess.Popen(spec['command'],cwd=spec['cwd'],env=environment,stdout=stdout,stderr=stderr,start_new_session=True,preexec_fn=affinity)
    group=os.getpgid(proc.pid);owned=psutil.Process(proc.pid);started=time.monotonic()
    receipt={'pid':proc.pid,'pgid':group,'started_at':now(),'spec_sha256':sha(args.spec),'peak_rss_bytes':0,
             'termination_reason':None,'gpu':False,'cpu_affinity':[25,26],'reserved_sibling_cores':[57,58],
             'queue_elapsed_seconds':time.monotonic()-queue_started}
    write(output/'launch.json',receipt)
    while proc.poll() is None:
        try:rss=sum(p.memory_info().rss for p in [owned]+owned.children(recursive=True) if p.is_running())
        except psutil.Error:rss=0
        receipt['peak_rss_bytes']=max(receipt['peak_rss_bytes'],rss);reason=None
        if rss>spec['max_rss_bytes']:reason='owned-RSS-budget'
        if time.monotonic()-started>spec['timeout_seconds']:reason='owned-PGID-timeout'
        if psutil.virtual_memory().available<24*1024**3:reason='host-memory-reserve'
        if uid_rss()>80*1024**3:reason='shared-UID-RSS-budget'
        if reason:
            receipt['termination_reason']=reason;os.killpg(group,signal.SIGTERM)
            try:proc.wait(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(group,signal.SIGKILL)
            break
        time.sleep(3)
    code=proc.wait();stdout.close();stderr.close();survivors=[]
    for p in psutil.process_iter(['pid','status']):
        try:
            if os.getpgid(p.pid)==group and p.status()!=psutil.STATUS_ZOMBIE:survivors.append(p.pid)
        except (psutil.Error,ProcessLookupError,PermissionError):pass
    if survivors:os.killpg(group,signal.SIGKILL)
    receipt.update(completed_at=now(),elapsed_seconds=time.monotonic()-started,exit_code=code,
        worker_pid_absent=not psutil.pid_exists(proc.pid),surviving_group_pids=survivors)
    write(output/'process-receipt.json',receipt)
    return code if not receipt['termination_reason'] and not survivors else 3

if __name__=='__main__':raise SystemExit(main())
