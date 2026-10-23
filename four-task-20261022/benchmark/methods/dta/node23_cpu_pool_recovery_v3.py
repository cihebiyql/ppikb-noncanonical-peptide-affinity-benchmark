"""Five-slot non-preemptive CPU pool using independently bounded per-job supervisors."""
import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

ROOT=Path('/data/qlyu/projects/peptide-four-task-benchmark-20261022')
HERE=ROOT/'methods/dta/node23-cpu-recovery-v3'
PYTHON='/data/qlyu/projects/peptide-binding-benchmark-20261020/common-prior-methods-20261021/.venv/bin/python'
GIB=1024**3

def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024**2),b''):h.update(block)
    return h.hexdigest()
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.tmp-'+str(os.getpid()))
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');temp.replace(path)
def now():return dt.datetime.now(dt.timezone.utc).isoformat()
def cpu_stat():
    v=list(map(int,Path('/proc/stat').read_text().splitlines()[0].split()[1:]))
    return sum(v),v[3]
def available():
    return next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
def owned_rss():
    total=0
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():continue
        try:
            if path.stat().st_uid!=os.getuid():continue
            text=(path/'stat').read_text();f=text[text.rfind(')')+2:].split()
            total+=int(f[21])*os.sysconf('SC_PAGE_SIZE')
        except (OSError,ValueError):pass
    return total
def capacity():
    frames=[]
    for _ in range(3):
        a=cpu_stat();time.sleep(1);b=cpu_stat()
        frames.append({'idle_percent':100*(b[1]-a[1])/(b[0]-a[0]),'available_bytes':available(),'qlyu_RSS_bytes':owned_rss()})
    passed=all(x['idle_percent']>=40 and x['available_bytes']>=36*GIB and x['qlyu_RSS_bytes']+4*GIB<=80*GIB for x in frames)
    return {'at':now(),'frames':frames,'passed':passed,'max_DTA_workers':15,'reserve_GiB':32,'UID_RSS_cap_GiB':80}

def completed(job):
    receipt=Path(job['run_dir'])/'process-receipt.json'
    result=ROOT/job['output_root']/'complete.json'
    if not receipt.exists() or not result.exists():return False
    r=load(receipt);c=load(result)
    return r['exit_code']==0 and r.get('termination_reason') is None and not r.get('residual_group_pids_before_cleanup') and c['spec_sha256']==job['spec_sha256'] and sha(result.parent/'test-predictions.jsonl')==c['prediction_sha256']

def inherited_state(data):
    live=[];terminal=[]
    for job in data.get('inherited_running_cpu1',[]):
        folder=Path(job['run_dir']);launch=folder/'launch.json'
        if completed(job):
            terminal.append({'job_id':job['job_id'],'status':'complete'});continue
        if not launch.exists():
            terminal.append({'job_id':job['job_id'],'status':'no_launch_evidence'});continue
        info=load(launch);p=Path('/proc')/str(info['pid'])
        try:
            cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
            stat=(p/'stat').read_text();fields=stat[stat.rfind(')')+2:].split()
            matches=p.stat().st_uid==os.getuid() and fields[0]!='Z' and job['spec_path'] in cmd
        except OSError:matches=False
        if matches:live.append({'job_id':job['job_id'],'worker_pid':info['pid'],'cpu_affinity':info['cpu_affinity']})
        else:terminal.append({'job_id':job['job_id'],'status':'terminal_no_complete_kept_no_retry'})
    return live,terminal

def stop_registered_group(pgid):
    members=[]
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():continue
        try:
            text=(path/'stat').read_text();f=text[text.rfind(')')+2:].split()
            if int(f[2])==pgid:members.append((path.stat().st_uid,int(f[3])))
        except (OSError,ValueError):pass
    if any(uid!=os.getuid() or session!=pgid for uid,session in members):
        raise RuntimeError('Refuse to signal non-owned registered session')
    if members:
        try:os.killpg(pgid,signal.SIGTERM)
        except ProcessLookupError:pass

def start(job,slot,probe):
    folder=Path(job['run_dir'])
    if folder.exists():raise FileExistsError('Preserve existing failed/incomplete phase: '+str(folder))
    folder.mkdir(parents=True)
    for n in ['stdout.log','stderr.log']:(folder/n).touch()
    cp=Path(job['contract_path'])
    if sha(cp)!=job['contract_sha256'] or sha(job['spec_path'])!=job['spec_sha256']:raise ValueError('Frozen bytes changed')
    contract=load(cp)
    validation=subprocess.run([PYTHON,str(ROOT/'resources/validate_reproduction.py'),'--contract',str(cp),'--check-files'],capture_output=True,text=True,timeout=120)
    (folder/'validation.stdout.json').write_text(validation.stdout,encoding='utf-8');(folder/'validation.stderr.log').write_text(validation.stderr,encoding='utf-8')
    gate=json.loads(validation.stdout)
    if validation.returncode or gate.get('valid_for_execution') is not True:
        write(folder/'pool-rejected.json',{'status':'standard_validator_rejected','gate':gate,'model_launched':False})
        return None
    import shlex
    if shlex.split(contract['execution']['command'])!=job['argv'] or contract['resources']['gpu_devices']:
        raise ValueError('Actual command/CPU contract mismatch')
    hashes=[{'path':str(cp),'sha256':job['contract_sha256']},{'path':job['spec_path'],'sha256':job['spec_sha256']}]
    for cat,key in [('datasets','manifest_sha256'),('code','archive_sha256')]:
        hashes.extend({'path':a['path'],'sha256':a[key]} for a in contract['assets'][cat] if a.get('path') and a.get(key))
    spec={'output':str(folder),'input_hashes':hashes,'contract_validation':gate,'command':job['argv'],
          'cwd':str(ROOT),'cpu_threads':2,'cpu_offset':slot,'memory_limit_bytes':4*GIB,
          'timeout_seconds':job['timeout_seconds'],'deadline_at':contract['timing']['effective_deadline_at'],
          'gpu':None,'environment':{'CUDA_VISIBLE_DEVICES':'','PYTHONHASHSEED':str(job['seed'])}}
    supervision=folder/'supervisor-spec.json';write(supervision,spec);write(folder/'capacity-gate.json',probe)
    out=(folder/'controller.stdout.log').open('w');err=(folder/'controller.stderr.log').open('w')
    env=dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2',NUMEXPR_NUM_THREADS='2')
    argv=[PYTHON,str(ROOT/'resources/cpu_supervise_node23.py'),'--spec',str(supervision)]
    p=subprocess.Popen(argv,cwd=ROOT,env=env,stdout=out,stderr=err,start_new_session=True,preexec_fn=lambda:os.nice(15))
    write(folder/'pool-launch.json',{'at':now(),'supervisor_pid':p.pid,'supervisor_pgid':os.getpgid(p.pid),
        'job_id':job['job_id'],'contract_sha256':job['contract_sha256'],'supervisor_spec_sha256':sha(supervision),
        'cpu_affinity':[slot,slot+1],'nice':15,'GPU_used':False})
    return {'process':p,'job':job,'slot':slot,'out':out,'err':err,'started_monotonic':time.monotonic()}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--phase',choices=['smoke','first-formal','formal'],required=True)
    parser.add_argument('--max-concurrent',type=int,default=15)
    args=parser.parse_args()
    if socket.gethostname()!='node23' or not 1<=args.max_concurrent<=15:raise ValueError('Wrong resource/parallelism')
    lock=(HERE/'pool.lock').open('a');fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    data=load(HERE/'jobs.json');deadline=dt.datetime.fromisoformat(data['global_deadline']).timestamp()
    jobs=data['jobs']
    if args.phase=='smoke':jobs=[j for j in jobs if j['stage']=='smoke']
    elif args.phase=='first-formal':jobs=[j for j in jobs if j['stage']=='formal' and j['method_id']=='GraphDTA-GIN' and j['view_id']=='ppikb_kd_source_cold_scope_v2' and j['seed']==4]
    else:jobs=[j for j in jobs if j['stage']=='formal']
    selected=[];outcomes=[]
    for j in jobs:
        if j['stage']=='formal' and not any(s['stage']=='smoke' and s['method_id']==j['method_id'] and completed(s) for s in data.get('prerequisite_smokes',data['jobs'])):
            outcomes.append({'job_id':j['job_id'],'status':'own_method_smoke_not_complete_no_launch'})
        elif completed(j):outcomes.append({'job_id':j['job_id'],'status':'verified_current_route_complete_skipped'})
        elif Path(j['run_dir']).exists():outcomes.append({'job_id':j['job_id'],'status':'preserved_existing_incomplete_no_retry'})
        else:selected.append(j)
    active=[];stop=False
    def terminate(signum,frame):
        nonlocal stop
        stop=True
        for item in active:
            launch=Path(item['job']['run_dir'])/'launch.json'
            if launch.exists():
                pgid=load(launch)['pgid']
                stop_registered_group(pgid)
    signal.signal(signal.SIGTERM,terminate);signal.signal(signal.SIGINT,terminate)
    while selected or active:
        inherited_live,inherited_terminal=inherited_state(data)
        for item in active[:]:
            if item['process'].poll() is None:continue
            item['out'].close();item['err'].close()
            ok=completed(item['job'])
            outcome={'job_id':item['job']['job_id'],'status':'complete' if ok else 'failed_or_partial',
                     'supervisor_exit_code':item['process'].returncode,'elapsed_seconds':time.monotonic()-item['started_monotonic']}
            outcomes.append(outcome);print(json.dumps(outcome),flush=True);active.remove(item)
        if time.time()>=deadline:stop=True
        if stop and not active:break
        if selected and not stop and len(active)+len(inherited_live)<args.max_concurrent:
            # A long-budget job becoming ineligible must not prevent later
            # shorter-budget jobs from using the remaining authorized window.
            while selected and time.time()+selected[0]['timeout_seconds']+120>=deadline:
                j=selected.pop(0)
                outcomes.append({'job_id':j['job_id'],'status':'deadline_start_gate_no_launch'})
            if selected:
                probe=capacity()
                write(HERE/(args.phase+'-last-capacity.json'),probe)
                if probe['passed']:
                    occupied={core for row in inherited_live for core in row['cpu_affinity']}
                    occupied.update(core for row in active for core in (row['slot'],row['slot']+1))
                    slot=next(core for core in range(11,63) if core not in occupied and core+1 not in occupied)
                    job=selected.pop(0)
                    try:item=start(job,slot,probe)
                    except Exception as exc:
                        outcomes.append({'job_id':job['job_id'],'status':'prelaunch_failed','error':repr(exc)})
                    else:
                        if item:active.append(item)
                        else:outcomes.append({'job_id':job['job_id'],'status':'standard_gate_rejected'})
                else:time.sleep(10)
        write(HERE/(args.phase+'-progress.json'),{'at':now(),'controller_pid':os.getpid(),'phase':args.phase,
              'active':[{'job_id':x['job']['job_id'],'supervisor_pid':x['process'].pid,'cpu_affinity':[x['slot'],x['slot']+1]} for x in active],
              'inherited_live_cpu1':inherited_live,'inherited_terminal_cpu1':inherited_terminal,
              'pending':len(selected),'outcomes':outcomes,'max_concurrent':args.max_concurrent,'GPU_used':False})
        if active:time.sleep(1)
    write(HERE/(args.phase+'-result.json'),{'at':now(),'outcomes':outcomes,'unlaunched':[j['job_id'] for j in selected],
          'all_expected_complete':len(outcomes)==len(jobs) and all(x['status'] in ['complete','verified_current_route_complete_skipped'] for x in outcomes)})

if __name__=='__main__':main()
