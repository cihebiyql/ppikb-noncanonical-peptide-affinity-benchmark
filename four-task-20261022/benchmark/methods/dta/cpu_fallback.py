"""Independent bounded CPU fallback, with standard contracts and no GPU visibility."""
from __future__ import annotations
import argparse
import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shlex
import signal
import socket
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
HOME = HERE/'cpu-fallback-v1'
PYTHON = '/root/.venvs/peptide-omnipanel-v31-web311-20260723/bin/python'
OVERLAY = '/mnt/d/work/科研工作台/research-tasks/peptide-binding-nc-benchmark-20261021/resources/local-gpu-route/vendor-dependencies'
START = dt.datetime(2026, 10, 22, 15, 31, 20, tzinfo=dt.timezone.utc)
DEADLINE = START + dt.timedelta(hours=10)
CAP = 6*1024**3

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            h.update(block)
    return h.hexdigest()

def write(path, value, immutable=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2)
    if immutable and path.exists() and path.read_text(encoding='utf-8') != text:
        raise FileExistsError(path)
    path.write_text(text, encoding='utf-8')

def windows_to_wsl(value):
    text = str(value)
    if len(text) > 2 and text[1:3] in (':\\', ':/'):
        return '/mnt/' + text[0].lower() + '/' + text[3:].replace('\\', '/')
    return text

def wsl(path):
    return windows_to_wsl(path.resolve())

def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def prepare():
    template = load(ROOT.parents[1]/'复现/规范/task-contract.template.json')
    runtime = HOME/'runtime-probe.json'
    probe = load(runtime)
    if probe['hostname'] != 'cihebi' or probe['torch_cuda_available'] or probe['CUDA_VISIBLE_DEVICES'] != '':
        raise ValueError('CPU-only live runtime not verified')
    registry = load(ROOT/'protocol/method_registry.json')['methods']
    sources = load(HERE/'source-manifest.json')
    original_jobs = [job for job in load(HERE/'jobs.json')['jobs']
                     if job['stage'] == 'smoke' and job['view_id'] == 'ppikb_kd_source_cold_scope_v2']
    issued = []
    for original in original_jobs:
        model = next(m for m in registry if m['id'] == original['method_id'] or
                     (m['id'] == 'DGDTA' and original['method_id'] == 'DGDTA-CL'))
        job_id = original['job_id'] + '--cpu-fallback-v1'
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        spec = copy.deepcopy(load(ROOT/original['spec']))
        spec.update(job_id=job_id, run_root=spec['run_root'].replace('runs/dta/', 'runs/dta_cpu/'),
                    cpu_threads=1, gpu_allocator_budget_bytes=0, timeout_seconds=900,
                    execution_device='cpu', fallback_reason='Other current-user tasks occupy three GPUs; new independent CPU run')
        specpath = HOME/'specs'/(job_id+'.json')
        write(specpath, spec, immutable=True)
        argv = [PYTHON, wsl(HERE/'train.py'), '--spec', wsl(specpath), '--device', 'cpu']
        logdir = HOME/'dispatch'/job_id
        pdf = ROOT/'resources/papers'/(original['method_id']+'.pdf')
        if not pdf.is_file():
            raise FileNotFoundError(pdf)
        contract = copy.deepcopy(template)
        contract.update(is_template=False, task_id='fourtask-common-'+model['id'], run_id=job_id,
                        contract_status='frozen', created_at=now, frozen_at=now)
        contract['identity'].update(title=model['id']+' CPU common-data smoke', doi=model['doi'],
            publication_status='published', pdf={'path': wsl(pdf), 'sha256': sha(pdf),
                'version': 'retained identified source', 'source_url': 'https://doi.org/'+model['doi']})
        contract['execution_scope'].update(objective='New independent CPU fallback end-to-end smoke on 64 train/32 validation/32 test records; two LR candidates; validation-only choice; no full-paper claim',
            authorization_reference=wsl(ROOT/'protocol/USER_REQUEST.txt'),
            relation_to_prior_run='New common-data objective. Original GPU specs, outputs and historical clocks unchanged. CPU fallback authorized by current parent task.',
            prior_run_ids=[original['job_id']], safety_assessment='allowed', scope_coverage='partial_subset',
            intended_level='smoke', excluded_claims=['full original-paper reproduction','ten-seed formal training complete'],
            restriction_check={'prior_platform_restriction': False,
                'reason': 'Same assessed benign common-data view; no excluded workflow resumed.',
                'evidence_paths': [wsl(ROOT/'protocol/USER_REQUEST.txt')]})
        contract['timing'].update(first_substantive_started_at=START.isoformat(),
            earliest_associated_preparation_at=START.isoformat(), wall_clock_cap_hours=10,
            original_deadline_at=DEADLINE.isoformat(), effective_deadline_at=DEADLINE.isoformat(),
            prior_window_expired=False, retry_resets_clock=False)
        datasets = []
        for role, item in spec['paths'].items():
            path = ROOT/item['path']
            if sha(path) != item['sha256']:
                raise ValueError('Frozen split changed')
            datasets.append({'name': role, 'path': wsl(path), 'sha256': sha(path),
                'manifest_sha256': sha(path), 'sample_count': item['n'], 'integrity': 'complete',
                'statistical_unit': 'frozen original observation',
                'notes': 'Smoke subset from unchanged original partition; no resplitting'})
        code = [{'role':'new common-data runner','path':wsl(HERE/'train.py'),'sha256':sha(HERE/'train.py'),
                 'archive_sha256':sha(HERE/'train.py'),'integrity':'complete','source_url':model['source']},
                {'role':'frozen CPU configuration','path':wsl(specpath),'sha256':sha(specpath),
                 'archive_sha256':sha(specpath),'integrity':'complete'},
                {'role':'CPU process-tree watchdog','path':wsl(Path(__file__)), 'sha256':sha(Path(__file__)),
                 'archive_sha256':sha(Path(__file__)),'integrity':'complete'}]
        for item in sources['files']:
            path = HERE/item['path']
            code.append({'role':'frozen audited author module','path':wsl(path),'sha256':item['sha256'],
                         'archive_sha256':item['sha256'],'integrity':'complete'})
        contract['assets'] = {'datasets':datasets,'code':code,
            'models':[{'integrity':'not_applicable','notes':'Random initialization; no pretrained supervised weights'}]}
        contract['targets'] = [{'target_id':job_id,'required':True,'paper_endpoint':'pKd',
            'comparison_endpoint':'new common-data subset smoke', 'metric':'MAE',
            'metric_definition':'Mean absolute error on frozen test predictions after validation-only checkpoint/LR choice',
            'statistical_unit':'measurement','denominator':32,'unit':'pKd','paper_value':None,
            'checkpoint_selection':'minimum validation MAE; two LR candidates retained','repetitions':1,
            'tolerance':{'kind':'not_comparable','reason':'New smoke subset; not original paper denominator'}}]
        contract['environment'].update(isolation='Existing private WSL environment plus existing task-local audited dependencies; no installation',
            environment_path=probe['sys_prefix'], lockfile_path=wsl(runtime), lockfile_sha256=sha(runtime),
            runtime_versions={k:probe[k] for k in ('python','numpy','torch','torch_geometric','rdkit')},
            shared_environment_modified=False)
        contract['resources'].update(expected_hostname='cihebi',cpu_threads=1,data_loader_workers=0,
            memory_limit_bytes=CAP,gpu_devices=[],gpu_memory_budget_bytes=0,
            resource_probe_path=wsl(runtime),resource_probe_at=probe['observed_at'],
            start_gate='Standard contract validation; CUDA hidden; private process-group timeout900s; aggregate RSS6GiB',
            budget_basis='Parent explicitly authorized CPU fallback while other tasks occupy all three GPUs', no_preemption=True)
        contract['execution'].update(command=shlex.join(argv),working_directory=wsl(ROOT),
            seed_policy='seed0 component smoke; formal seeds0-9 remain distinct pending jobs',seeds=[0],timeout_seconds=900,
            process_control={'platform':'linux','mechanism':'private setsid process group; wall/RSS watchdog', 'whole_tree_bounded':True},
            stdout_path=wsl(logdir/'stdout.log'),stderr_path=wsl(logdir/'stderr.log'))
        contractpath = HOME/'contracts'/(job_id+'.json')
        write(contractpath,contract,immutable=True)
        issued.append({'job_id':job_id,'method_id':original['method_id'], 'spec_path':wsl(specpath),
            'spec_sha256':sha(specpath),'contract_path':wsl(contractpath),'contract_sha256':sha(contractpath),
            'argv':argv,'run_root':spec['run_root'],'log_dir':wsl(logdir),'timeout_seconds':900})
    write(HOME/'jobs.json',{'schema':'fourtask.dta-cpu-fallback.v1','jobs':issued},immutable=True)
    print(json.dumps({'prepared':len(issued),'jobs_sha256':sha(HOME/'jobs.json')}))

def snapshot_group(pgid):
    rows = []
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():
            continue
        try:
            stat = (path/'stat').read_text()
            f = stat[stat.rfind(')')+2:].split()
            if int(f[2]) == pgid:
                rows.append({'pid':int(path.name),'uid':path.stat().st_uid,'session':int(f[3]),
                             'rss':int(f[21])*os.sysconf('SC_PAGE_SIZE')})
        except (OSError,ValueError):
            pass
    return rows

def stop_group(pgid):
    rows = snapshot_group(pgid)
    if any(row['uid'] != os.getuid() or row['session'] != pgid for row in rows):
        raise RuntimeError('Refuse to signal non-owned session')
    try:
        os.killpg(pgid,signal.SIGTERM)
    except ProcessLookupError:
        return
    time.sleep(.5)
    if snapshot_group(pgid):
        try:
            os.killpg(pgid,signal.SIGKILL)
        except ProcessLookupError:
            pass

def execute(job):
    if socket.gethostname() != 'cihebi' or os.environ.get('CUDA_VISIBLE_DEVICES') != '':
        raise RuntimeError('Only verified CPU-hidden WSL route allowed')
    contractpath = Path(job['contract_path'])
    if sha(contractpath) != job['contract_sha256']:
        raise ValueError('Contract hash mismatch')
    contract = load(contractpath)
    if shlex.split(contract['execution']['command']) != job['argv'] or contract['resources']['gpu_devices']:
        raise ValueError('CPU contract argv/device mismatch')
    folder = Path(job['log_dir'])
    folder.mkdir(parents=True,exist_ok=False)
    for name in ('stdout.log','stderr.log'):
        (folder/name).touch()
    validator = ROOT.parents[1]/'复现/规范/validate_reproduction.py'
    validation = subprocess.run([sys.executable,str(validator),'--contract',str(contractpath),'--check-files'],
                                text=True,capture_output=True,timeout=90)
    (folder/'validation.stdout.json').write_text(validation.stdout,encoding='utf-8')
    (folder/'validation.stderr.log').write_text(validation.stderr,encoding='utf-8')
    gate = json.loads(validation.stdout)
    if validation.returncode or gate.get('valid_for_execution') is not True:
        write(folder/'execution-receipt.json',{'status':'rejected_by_standard_validator','gate':gate,'model_launched':False})
        return {'job_id':job['job_id'],'status':'rejected_by_standard_validator'}
    env = dict(os.environ,CUDA_VISIBLE_DEVICES='',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',
               OPENBLAS_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',PYTHONHASHSEED='0',PYTHONPATH=OVERLAY)
    started = time.time()
    with (folder/'stdout.log').open('a') as out,(folder/'stderr.log').open('a') as err:
        proc = subprocess.Popen(job['argv'],cwd=ROOT,env=env,stdout=out,stderr=err,
                                start_new_session=True,preexec_fn=lambda:os.nice(10))
        pgid = os.getpgid(proc.pid)
        write(folder/'started.json',{'job_id':job['job_id'],'pid':proc.pid,'pgid':pgid,
              'contract_sha256':job['contract_sha256'],'started_unix':started,'CUDA_VISIBLE_DEVICES':''})
        peak, reason = 0, None
        while proc.poll() is None:
            current = snapshot_group(pgid)
            rss = sum(row['rss'] for row in current)
            peak = max(peak,rss)
            if rss > CAP:
                reason = 'aggregate_process_group_RSS_limit'
            if time.time()-started >=900 or time.time() >= DEADLINE.timestamp():
                reason = 'original_timeout_or_campaign_deadline'
            if reason:
                stop_group(pgid)
                break
            time.sleep(.25)
        proc.wait(timeout=10)
    if snapshot_group(pgid):
        stop_group(pgid)
    remaining = snapshot_group(pgid)
    result = {'job_id':job['job_id'],'status':'succeeded' if proc.returncode == 0 and not reason else 'failed',
        'exit_code':proc.returncode,'reason':reason,'pid':proc.pid,'pgid':pgid,
        'elapsed_seconds':time.time()-started,'peak_group_RSS_bytes':peak,'remaining_group_members':remaining,
        'contract_sha256':job['contract_sha256'],'model_launched':True,'gpu_devices':[],
        'stdout_sha256':sha(folder/'stdout.log'),'stderr_sha256':sha(folder/'stderr.log')}
    write(folder/'execution-receipt.json',result)
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--run',action='store_true')
    parser.add_argument('--method')
    args = parser.parse_args()
    if args.prepare:
        prepare()
    if args.run:
        results = []
        jobs = load(HOME/'jobs.json')['jobs']
        for job in jobs:
            if args.method and job['method_id'] != args.method:
                continue
            result = execute(job)
            results.append(result)
            print(json.dumps(result,ensure_ascii=False),flush=True)
        write(HOME/('batch-results'+('-'+args.method if args.method else '')+'.json'),results)

if __name__ == '__main__':
    main()
