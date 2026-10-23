"""Single owned CPU2 head-training group with live node23 capacity gates."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time
import psutil

def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(1024**2),b''):h.update(block)
    return h.hexdigest()

def write(path,obj):
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(obj,indent=2),encoding='utf-8');temporary.replace(path)

def uid_rss():
    total=0
    for p in psutil.process_iter(['uids','memory_info']):
        try:
            if p.info['uids'].real==os.getuid():total+=p.info['memory_info'].rss
        except (psutil.Error,TypeError):pass
    return total

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--spec',required=True,type=Path)
    args=parser.parse_args();spec=json.loads(args.spec.read_text())
    assert socket.gethostname()=='node23'
    assert spec['cpu_affinity']==[30,31] and spec['cpu_threads']==2
    assert set(spec['cpu_affinity'])<=os.sched_getaffinity(0)
    target=Path(spec['output']);target.mkdir(parents=True,exist_ok=False)
    checks=[{'path':x['path'],'expected':x['sha256'],'actual':sha(x['path'])} for x in spec['input_hashes']]
    write(target/'input-hash-checks.json',checks)
    assert all(x['expected']==x['actual'] for x in checks)
    idle=[100-psutil.cpu_percent(interval=1) for _ in range(3)]
    observed={'idle_samples':idle,'mem_available':psutil.virtual_memory().available,'uid_rss':uid_rss()}
    write(target/'capacity-gate.json',observed)
    assert min(idle)>=40 and observed['mem_available']>=36*1024**3
    assert observed['uid_rss']+spec['max_rss_bytes']<=80*1024**3
    env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',NUMEXPR_NUM_THREADS='2',PYTHONDONTWRITEBYTECODE='1')
    def affinity():
        os.sched_setaffinity(0,set(spec['cpu_affinity']));os.nice(15)
    stdout=(target/'stdout.log').open('w');stderr=(target/'stderr.log').open('w')
    proc=subprocess.Popen(spec['command'],cwd=spec['cwd'],env=env,stdout=stdout,stderr=stderr,start_new_session=True,preexec_fn=affinity)
    group=os.getpgid(proc.pid);owned=psutil.Process(proc.pid);start=time.monotonic()
    receipt={'pid':proc.pid,'pgid':group,'started_at':dt.datetime.now(dt.timezone.utc).isoformat(),
             'spec_sha256':sha(args.spec),'peak_rss_bytes':0,'termination_reason':None,'gpu':False,'cpu_affinity':[30,31]}
    write(target/'launch.json',receipt)
    while proc.poll() is None:
        try:rss=sum(p.memory_info().rss for p in [owned]+owned.children(recursive=True) if p.is_running())
        except psutil.Error:rss=0
        receipt['peak_rss_bytes']=max(receipt['peak_rss_bytes'],rss)
        reason=None
        if rss>spec['max_rss_bytes']:reason='owned-RSS-budget'
        if time.monotonic()-start>spec['timeout_seconds']:reason='owned-group-timeout'
        if psutil.virtual_memory().available<24*1024**3:reason='host-memory-reserve'
        if uid_rss()>80*1024**3:reason='UID-RSS-shared-budget'
        if reason:
            receipt['termination_reason']=reason;os.killpg(group,signal.SIGTERM)
            try:proc.wait(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(group,signal.SIGKILL)
            break
        time.sleep(3)
    code=proc.wait();stdout.close();stderr.close()
    survivors=[]
    for p in psutil.process_iter(['pid','status']):
        try:
            if os.getpgid(p.pid)==group and p.status()!=psutil.STATUS_ZOMBIE:survivors.append(p.pid)
        except (psutil.Error,ProcessLookupError,PermissionError):pass
    if survivors:os.killpg(group,signal.SIGKILL)
    receipt.update(completed_at=dt.datetime.now(dt.timezone.utc).isoformat(),elapsed_seconds=time.monotonic()-start,
                   exit_code=code,worker_pid_absent=not psutil.pid_exists(proc.pid),surviving_group_pids=survivors)
    write(target/'process-receipt.json',receipt)
    return code if not receipt['termination_reason'] and not survivors else 3

if __name__=='__main__':raise SystemExit(main())
