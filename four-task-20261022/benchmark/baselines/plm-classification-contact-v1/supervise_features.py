"""One freshly admitted CPU2 frozen-feature PGID at a time, with finite resource waiting."""
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
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1024**2),b''):h.update(b)
    return h.hexdigest()
def write(path,value):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,indent=2),encoding='utf-8');temp.replace(path)
def now():return dt.datetime.now(dt.timezone.utc).isoformat()
def uid_rss():
    total=0
    for p in psutil.process_iter(['uids','memory_info']):
        try:
            if p.info['uids'].real==os.getuid():total+=p.info['memory_info'].rss
        except (psutil.Error,TypeError):pass
    return total
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--canary',action='store_true');parser.add_argument('--chunk',type=int)
    args=parser.parse_args();plan=json.loads(args.plan.read_text())
    assert socket.gethostname()=='node23' and plan['cpu_affinity']==[25,26] and plan['reserved_siblings']==[57,58]
    assert plan['rss_limit_bytes']<=3*1024**3 and set(plan['cpu_affinity'])<=os.sched_getaffinity(0)
    suffix='canary' if args.canary else f'chunk-{args.chunk:03d}'
    previous=list((Path(plan['output_root'])/'resource-supervision').glob(suffix+'*'))
    if previous:suffix=suffix+f'-admission-{len(previous):02d}'
    output=Path(plan['output_root'])/'resource-supervision'/suffix
    output.mkdir(parents=True,exist_ok=False)
    hashes=[{'path':r['path'],'expected':r['sha256'],'actual':sha(r['path'])} for r in plan['input_hashes']]
    write(output/'input-hash-checks.json',hashes);assert all(r['expected']==r['actual'] for r in hashes)
    started_queue=time.monotonic();gate={'attempts':[],'admitted':False}
    while time.monotonic()-started_queue<plan['queue_timeout_seconds']:
        frames=[]
        for _ in range(3):
            idle=[100-v for v in psutil.cpu_percent(interval=1,percpu=True)]
            frames.append({'overall_idle':statistics.mean(idle),'reserved_idle':{str(i):idle[i] for i in [25,26,57,58]}})
        sample={'at':now(),'frames':frames,'available_memory':psutil.virtual_memory().available,'uid_rss':uid_rss()}
        admitted=all(f['overall_idle']>=40 and min(f['reserved_idle'].values())>=60 for f in frames)
        admitted &= sample['available_memory']>=36*1024**3 and sample['uid_rss']+plan['rss_limit_bytes']<=80*1024**3
        sample['passed']=bool(admitted);gate['attempts'].append(sample);gate['admitted']=bool(admitted);write(output/'capacity-gate.json',gate)
        if admitted:break
        time.sleep(30)
    if not gate['admitted']:
        write(output/'admission-terminal.json',{'status':'finite_queue_expired','scientific_workers_started':0,'at':now()});return 3
    command=[plan['feature_python'],'-B',plan['extractor'],'--contract',plan['feature_contract']]
    command+=['--canary'] if args.canary else ['--chunk',str(args.chunk)]
    env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',NUMEXPR_NUM_THREADS='2',PYTHONDONTWRITEBYTECODE='1')
    def configure():os.sched_setaffinity(0,{25,26});os.nice(19)
    stdout=(output/'stdout.log').open('w');stderr=(output/'stderr.log').open('w')
    proc=subprocess.Popen(command,cwd=plan['cwd'],env=env,stdout=stdout,stderr=stderr,start_new_session=True,preexec_fn=configure)
    group=os.getpgid(proc.pid);owned=psutil.Process(proc.pid);start=time.monotonic()
    receipt={'pid':proc.pid,'pgid':group,'started_at':now(),'plan_sha256':sha(args.plan),'peak_rss_bytes':0,
        'termination_reason':None,'cpu_affinity':[25,26],'nice':19,'gpu':False,'phase':suffix}
    write(output/'launch.json',receipt)
    limit=plan['canary_timeout_seconds'] if args.canary else plan['chunk_timeout_seconds']
    while proc.poll() is None:
        try:rss=sum(p.memory_info().rss for p in [owned]+owned.children(recursive=True) if p.is_running())
        except psutil.Error:rss=0
        receipt['peak_rss_bytes']=max(receipt['peak_rss_bytes'],rss);reason=None
        if rss>plan['rss_limit_bytes']:reason='owned-RSS-limit'
        if time.monotonic()-start>limit:reason='owned-PGID-timeout'
        if psutil.virtual_memory().available<24*1024**3:reason='host-memory-reserve'
        if uid_rss()>80*1024**3:reason='shared-UID-RSS-limit'
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
    receipt.update(completed_at=now(),elapsed_seconds=time.monotonic()-start,exit_code=code,
        worker_pid_absent=not psutil.pid_exists(proc.pid),surviving_group_pids=survivors)
    write(output/'process-receipt.json',receipt)
    return code if not receipt['termination_reason'] and not survivors else 3
if __name__=='__main__':raise SystemExit(main())
