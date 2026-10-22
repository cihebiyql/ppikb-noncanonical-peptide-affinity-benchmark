"""Stdlib-only CPU RF launch gates and isolated, bounded JSON writers."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import queue
import re
import socket
import sys
import threading
import time
import uuid

HERE=Path(__file__).resolve().parent
PROJECT=HERE.parents[1]
LAUNCH=PROJECT/'launch'
spec=importlib.util.spec_from_file_location('_rf_frozen_launch_primitives',LAUNCH/'common.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
read,sha,path,checked,utc,deadline,epoch,process_table,stop_owned_group=(getattr(base,n) for n in ('read','sha','path','checked','utc','deadline','epoch','process_table','stop_owned_group'))
GIB=1024**3
HOST='cihebi'
PYTHON='/root/.venvs/peptide-omnipanel-v31-web311-20260723/bin/python'
CPU_IDS=[4,5,6,7]
METHOD='RF-Morgan2-chiral-AAC-DP'
PANELS={'source_peptide_dependency_cold','target_reference_homology_cold'}
SOURCE_NAMES=('features.py','common.py','rf_runner.py','rf_score.py','feature-spec-v1.json','protocol-v1.json','installed-assets-v1.json','installed-binaries-v1.json')


def write(target,obj):
    """Unique temporary file and bounded replacement retries; never monkeypatch."""
    target=path(target);target.parent.mkdir(parents=True,exist_ok=True)
    temp=target.with_name(target.name+'.'+str(os.getpid())+'.'+str(threading.get_ident())+'.'+uuid.uuid4().hex+'.tmp')
    with temp.open('x',encoding='utf-8') as handle:
        handle.write(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False))
    delays=(.05,.1,.2,.4,.8,1.)
    for attempt in range(len(delays)+1):
        try:temp.replace(target);return
        except PermissionError:
            if attempt==len(delays):raise
            time.sleep(delays[attempt])


class ProgressWriter:
    """A dedicated writer: filesystem retries cannot block the RSS watchdog."""
    def __init__(self):
        self.error=None;self.queue=queue.Queue(maxsize=64)
        self.thread=threading.Thread(target=self._run,daemon=True,name='rf-progress-writer');self.thread.start()

    def _run(self):
        while True:
            item=self.queue.get()
            if item is None:return
            target,obj,done,result=item
            try:write(target,obj)
            except BaseException as error:self.error=repr(error);result['error']=self.error
            finally:done.set()
            if self.error:return

    def submit(self,target,obj,wait=False):
        if self.error:raise RuntimeError('Persistent artifact writer failure: '+self.error)
        done=threading.Event();result={}
        try:self.queue.put_nowait((target,obj,done,result))
        except queue.Full:
            self.error='bounded writer queue full';raise RuntimeError(self.error)
        if wait:
            if not done.wait(5):raise TimeoutError('Artifact writer completion timeout; watchdog remains independent')
            if result.get('error'):raise RuntimeError(result['error'])
        return done

    def close(self):
        try:self.queue.put_nowait(None)
        except queue.Full:pass
        self.thread.join(timeout=5)


def reference(ref):
    if not isinstance(ref,dict) or set(ref)!={'path','sha256'}:raise ValueError('Expected exact path/sha256 reference')
    return checked(ref['path'],ref['sha256'])


def same(a,b):return path(a).resolve()==path(b).resolve()


def runtime_gate(meta,unit=False):
    if os.name!='posix' or not Path('/proc').is_dir():raise RuntimeError('Linux private process controls required')
    if socket.gethostname()!=HOST or meta['expected_hostname']!=HOST:raise RuntimeError('Wrong actual host')
    if not same(sys.executable,PYTHON) or not same(meta['python'],PYTHON) or not same(sys.prefix,path(PYTHON).parent.parent):raise RuntimeError('Wrong actual interpreter/environment')
    expected=PROJECT/'resources/local-gpu-route/vendor-dependencies'
    if not same(meta['PYTHONPATH'],expected) or os.environ.get('PYTHONPATH')!=meta['PYTHONPATH']:raise RuntimeError('Wrong task-local dependency route')
    if os.environ.get('CUDA_VISIBLE_DEVICES')!='' or meta.get('CUDA_VISIBLE_DEVICES')!='':raise RuntimeError('CPU RF must have CUDA explicitly empty')
    if meta.get('allowed_cpu_ids')!=CPU_IDS or (not unit and not set(CPU_IDS)<=os.sched_getaffinity(0)):raise RuntimeError('Dedicated RF CPU4-7 slots unavailable')
    if unit:
        affinity=os.sched_getaffinity(0)
        if len(affinity)!=1 or not affinity<=set(CPU_IDS):raise RuntimeError('RF unit requires exactly one dedicated CPU4-7')
        if any(os.environ.get(k)!='1' for k in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS')):raise RuntimeError('RF thread budget must be one')


def private_pool_gate(binding_path):
    if os.getpid()!=os.getpgrp() or os.getsid(0)!=os.getpid():raise RuntimeError('RF unit must own private process group/session')
    parent=os.getppid();entry=process_table().get(parent)
    if os.environ.get('RF_POOL_OWNER_PID')!=str(parent) or not entry or entry['uid']!=os.getuid() or str(entry['start_ticks'])!=os.environ.get('RF_POOL_OWNER_START_TICKS'):raise RuntimeError('RF unit requires its actual issued parent pool')
    if not same(os.environ.get('RF_POOL_BINDING_PATH',''),binding_path) or os.environ.get('RF_POOL_BINDING_SHA256')!=sha(binding_path):raise RuntimeError('Pool binding SHA/path mismatch')
    if not re.fullmatch('[0-9a-f]{64}',os.environ.get('RF_POOL_INDEX_SHA256','')):raise RuntimeError('Missing pool index SHA')
    if str(HERE/'rf_pool.py').encode() not in (Path('/proc')/str(parent)/'cmdline').read_bytes().split(b'\0'):raise RuntimeError('Wrong actual parent pool command')


def cpu_probe():
    mem={}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key,value=line.split(':',1);mem[key]=int(value.strip().split()[0])*1024
    return {'at':utc(),'hostname':socket.gethostname(),'cpu_count':os.cpu_count(),'affinity':sorted(os.sched_getaffinity(0)),
            'load_average':list(os.getloadavg()),'available_memory_bytes':mem['MemAvailable'],
            'CUDA_VISIBLE_DEVICES':os.environ.get('CUDA_VISIBLE_DEVICES'),'processes_killed':0}


def full_timeout_fits(cutoff,now=None):return (time.time() if now is None else now)+1800<=cutoff


def preflight(binding_path,private=True,reserve=True):
    binding_path=path(binding_path);binding=read(binding_path)
    if binding.get('schema')!='rf-unit-binding-v1' or binding.get('issued') is not True:raise PermissionError('Root-issued RF binding required')
    if not re.fullmatch('[A-Za-z0-9_.-]+',binding['unit_id']):raise ValueError('Unsafe RF unit id')
    runtime_gate(binding,unit=private)
    if private:private_pool_gate(binding_path)
    cutoff=deadline(binding['deadline'])
    if int(binding['timeout_seconds'])!=1800:raise ValueError('RF unit timeout must be 1800 seconds')
    if reserve and not full_timeout_fits(cutoff):raise TimeoutError('Full RF timeout cannot fit original global window')
    checked(HERE/'rf_unit.py',binding['entrypoint_sha256']);checked(HERE/'rf_pool.py',binding['pool_sha256']);checked(__file__,binding['common_sha256'])
    auth=read(reference(binding['authorization']))
    if auth.get('root_real_RF_fit_authorized') is not True:raise PermissionError('Real RF fit authorization required')
    if auth['deadline_unix']!=cutoff or time.time()>=auth['deadline_unix']:raise TimeoutError('Authorization must retain exact original cutoff and remain live')
    if binding['spec']['sha256'] not in auth.get('allowed_spec_sha256',[]):raise PermissionError('This exact RF spec is not authorized')
    proof=read(reference(binding['live_cpu_proof']))
    if proof.get('hostname')!=HOST or not (proof.get('at') or proof.get('observed_at')):raise ValueError('Actual CPU proof must name real host/time')
    contract=read(reference(binding['central_contract']));validation=read(reference(binding['validation']))
    if contract.get('is_template') is not False or contract.get('contract_status')!='frozen' or contract['run_id']!=binding['unit_id']:raise PermissionError('Issued exact RF central contract required')
    bound=validation.get('contract_sha256') or validation.get('launch_binding',{}).get('contract_sha256')
    if validation.get('valid_for_execution') is not True or bound!=binding['central_contract']['sha256']:raise PermissionError('Positive exact-contract validation required')
    if 'central_validation_path' in validation:
        v=read(checked(validation['central_validation_path'],validation['central_validation_sha256']))
        if v.get('valid_for_execution') is not True:raise PermissionError('Central validator rejected RF execution')
    timing=contract['timing']
    if cutoff>epoch(timing['effective_deadline_at']) or timing.get('prior_window_expired') is True or timing.get('retry_resets_clock') is not False:raise ValueError('Original clock cannot be reset')
    argv=[binding['python'],str(HERE/'rf_unit.py'),'--binding',str(binding_path)]
    if contract['execution']['command']!=argv or int(contract['execution']['timeout_seconds'])!=1800:raise ValueError('Wrong exact RF contract command/timeout')
    resources=contract['resources']
    if resources['expected_hostname']!=HOST or resources.get('cpu_threads')!=1 or resources.get('memory_limit_bytes')!=2*GIB or resources.get('gpu_devices')!=[]:raise ValueError('Wrong CPU-only RF resource budget')
    if not same(contract['environment']['environment_path'],sys.prefix):raise ValueError('Contract actual environment mismatch')
    files=binding['code_files'];seen=set()
    for ref in files:
        p=path(ref['path']).resolve()
        if p.suffix!='.py' and p.name not in SOURCE_NAMES:raise ValueError('Code proof cannot read model/holdout/caches')
        if str(p) in seen:raise ValueError('Duplicate code proof')
        reference(ref);seen.add(str(p))
    required=[HERE/n for n in ('rf_common.py','rf_pool.py','rf_unit.py')]+[LAUNCH/'common.py']+[PROJECT/'auxiliary-rf-baseline'/n for n in SOURCE_NAMES]
    if not {str(p.resolve()) for p in required}<=seen:raise ValueError('Incomplete RF code/asset source proofs')
    source_sha={name:sha(PROJECT/'auxiliary-rf-baseline'/name) for name in SOURCE_NAMES}
    if auth['source_sha256']!=source_sha:raise ValueError('Authorized RF source changed')
    worker=reference(binding['worker'])
    if not same(worker,PROJECT/'auxiliary-rf-baseline/rf_runner.py'):raise ValueError('Wrong actual CPU RF worker')
    spec=read(reference(binding['spec']))
    coordinate=(spec['panel'],spec['regime'],spec['seed'])
    if spec['method_id']!=METHOD or coordinate[0] not in PANELS or coordinate[1] not in ('NC_only','standard_only') or coordinate[2] not in range(10):raise ValueError('Invalid RF experimental coordinate')
    meta=contract['benchmark_metadata']
    if meta['method_id']!='RF-Classic' or coordinate!=(meta['split_id'],meta['regime_id'],meta['seed']):raise ValueError('Contract/RF spec coordinate mismatch')
    allowed=PROJECT/'execution/prepared-panels-wsl-v3'/spec['panel']
    for name,file in [('train_rows','train.jsonl'),('validation_rows','validation.jsonl')]:
        if not same(spec[name],allowed/file):raise ValueError('RF labels restricted to own prepared train/validation only')
    for key in ('train_rows','validation_rows','train_ids','validation_ids','feature_manifest','installed_assets'):
        checked(spec[key],spec[key+'_sha256'])
    assets=read(path(spec['installed_assets']))
    profiles=assets['candidate_profiles']
    if {p['candidate_index'] for p in profiles}!={0,1}:raise ValueError('Exactly two fixed RF profiles required')
    for profile in profiles:
        parameters=profile['effective_parameters_seed0']
        if parameters['n_jobs']!=1 or parameters['n_estimators']!=200 or parameters['min_samples_leaf']!=({0:2,1:5}[profile['candidate_index']]):raise ValueError('Wrong one-thread fixed RF parameters')
    stage=contract['rf_execution_stage']
    for key in ('spec','authorization','live_cpu_proof','worker','code_files','receipt_root'):
        if stage[key]!=binding[key]:raise ValueError('Central RF stage '+key+' binding mismatch')
    if not path(binding['receipt_root']).resolve().is_relative_to(HERE.resolve()):raise ValueError('Unit receipts outside owned launcher')
    return {'binding':binding,'spec':spec,'contract':contract,'coordinate':coordinate,'cutoff':cutoff,'worker':worker,'binding_path':binding_path}


def validate_complete(folder,binding_sha):
    folder=path(folder);complete=read(checked(folder/'unit-complete.json',(folder/'unit-complete.sha256').read_text().strip()))
    if complete.get('status')!='complete' or complete['binding_sha256']!=binding_sha:raise ValueError('RF completion binding mismatch')
    for ref in complete['artifacts']:reference(ref)
    proof=read(checked(folder/'pool-exit-verification.json',(folder/'pool-exit-verification.sha256').read_text().strip()))
    if proof.get('exit_code')!=0 or proof.get('private_session_handles_absent') is not True or proof['binding_sha256']!=binding_sha:raise ValueError('Real RF pool exit verification absent')
    for name in ('stdout','stderr'):checked(proof[name+'_path'],proof[name+'_sha256'])
    return complete
