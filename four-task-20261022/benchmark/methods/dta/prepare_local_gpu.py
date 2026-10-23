"""Freeze a new local-CUDA revision; never launch a job or mutate Node1 contracts."""
import argparse
import copy
import datetime as dt
import json
from pathlib import Path
import shlex
from cpu_fallback import ROOT, HERE, HOME, PYTHON, OVERLAY, START, DEADLINE, load, sha, write, wsl

LOCAL = HERE/'local-gpu-v1'

def prepare(uuid):
    runtime=ROOT/'resources/local-dta-runtime-probe.json'
    resource=ROOT/'resources/probe-local-wsl-fallback.json'
    # These retained probes prove identity/runtime. The GPU dispatcher MUST
    # independently resample current local GPU and cross-host count at launch.
    probe=load(resource)
    historical_time=probe['generated_at']
    cpu_jobs={job['method_id']:job for job in load(HOME/'jobs.json')['jobs']}
    jobs=[]
    old_index=load(HERE/'jobs.json')
    for original in old_index['jobs']:
        base=load(ROOT/original['spec'])
        job_id=original['job_id']+'--local-gpu-v1'
        spec=copy.deepcopy(base)
        spec.update(job_id=job_id,run_root=base['run_root'].replace('runs/dta/','runs/dta_local_gpu/'),
            execution_device='cuda:0',resource_revision='local5080-Torch2.12.1-CUDA13-after-Node1-full-runtime-failures',
            prior_node1_spec_sha256=original['spec_sha256'])
        sp=LOCAL/'specs'/(job_id+'.json')
        write(sp,spec,immutable=True)
        argv=[PYTHON,wsl(HERE/'train.py'),'--spec',wsl(sp),'--device','cuda:0']
        # Reuse only contract metadata from the already validated CPU contract;
        # replace the scope, exact data, argv, environment, device and outputs.
        cp0=cpu_jobs[original['method_id']]['contract_path']
        cp0=Path(cp0.replace('/mnt/d/','D:/')) if not str(HERE).startswith('/') else Path(cp0)
        contract=copy.deepcopy(load(cp0))
        now=dt.datetime.now(dt.timezone.utc).isoformat()
        logdir=LOCAL/'dispatch'/job_id
        contract.update(run_id=job_id,created_at=now,frozen_at=now,previous_contract_sha256=None,
            resource_revision='New local CUDA host/environment; Node1 originals remain immutable')
        contract['identity']['title']=original['method_id']+' local-CUDA common-data '+original['stage']
        contract['execution_scope'].update(objective='New local5080 common-data '+original['stage']+'; exact original scope_v2 partition, seed, batch and two LR candidates retained.',
            relation_to_prior_run='Resource/host/runtime revision after Node1 CUDA full-run failures. Original failed outputs/specs/clocks remain preserved. No paper-full reproduction claim.',
            prior_run_ids=[original['job_id']],intended_level='smoke' if original['stage']=='smoke' else 'training',
            excluded_claims=['full original-paper reproduction','CUDA bitwise reproducibility','formal ten-seed completion before receipts exist'])
        if original['task']=='effect':
            contract['execution_scope']['objective']+=' Effect view is metadata-silver and potential-difference loss adaptation, not strict same-condition gold.'
        contract['assets']['datasets']=[]
        for name,item in spec['paths'].items():
            path=ROOT/item['path']
            if sha(path)!=item['sha256']:
                raise ValueError('Frozen prepared input changed')
            contract['assets']['datasets'].append({'name':name,'path':wsl(path),'sha256':sha(path),
                'manifest_sha256':sha(path),'sample_count':item['n'],'integrity':'complete',
                'statistical_unit':'source observation' if original['task']!='effect' else 'metadata-silver effect pair'})
        contract['assets']['code']=[x for x in contract['assets']['code'] if x['role'] not in
                                    ('frozen CPU configuration','CPU process-tree watchdog')]
        contract['assets']['code'].append({'role':'frozen local CUDA run specification','path':wsl(sp),
            'sha256':sha(sp),'archive_sha256':sha(sp),'integrity':'complete'})
        target=contract['targets'][0]
        target.update(target_id=job_id,paper_endpoint=spec['endpoint'],comparison_endpoint='new local CUDA common-data '+original['stage'],
            denominator=original['sample_counts']['test'],unit=spec['endpoint'],repetitions=1,
            statistical_unit='source observation' if original['task']!='effect' else 'metadata-silver effect pair')
        contract['environment'].update(environment_path='/root/.venvs/peptide-omnipanel-v31-web311-20260723',
            isolation='Existing private WSL runtime plus existing task-owned dependency overlay; no installation',
            lockfile_path=wsl(runtime),lockfile_sha256=sha(runtime),runtime_versions=load(runtime),
            shared_environment_modified=False)
        contract['environment']['numerical_policy'].update(parameter_dtype='float32',input_dtype='float32',
            autocast=False,float32_matmul_precision='highest',cuda_matmul_allow_tf32=False,cudnn_allow_tf32=False,
            determinism='seeded deterministic_algorithms warn_only; CUDA bitwise identity not guaranteed',
            applied_before_model_instantiation=True)
        contract['resources'].update(expected_hostname='cihebi',cpu_threads=1,data_loader_workers=0,
            memory_limit_bytes=6*1024**3,gpu_devices=[uuid],gpu_memory_budget_bytes=spec['gpu_allocator_budget_bytes'],
            resource_probe_path=wsl(resource),resource_probe_at=historical_time,
            start_gate='Standard exact-byte validation + fresh three-sample local GPU admission + global max3 across Node1/local + singleton local project slot + watchdog',
            budget_basis='User maximum three non-preemptive GPUs; Node1 other tasks use two cards, this local device is the third',
            no_preemption=True)
        contract['execution'].update(command=shlex.join(argv),working_directory=wsl(ROOT),seeds=[spec['seed']],
            seed_policy='Fixed original partitions across seeds0-9, validation-only checkpoint/LR selection',
            timeout_seconds=spec['timeout_seconds'],
            process_control={'platform':'linux','mechanism':'Resource-owner local CUDA private-PGID watchdog; CPU/RSS/GPU/global-count gate','whole_tree_bounded':True},
            stdout_path=wsl(logdir/'stdout.log'),stderr_path=wsl(logdir/'stderr.log'))
        cp=LOCAL/'contracts'/(job_id+'.json')
        write(cp,contract,immutable=True)
        jobs.append({'issued':True,'job_id':job_id,'method_id':original['method_id'],
            'stage':original['stage'],'view_id':original['view_id'],'task':original['task'],'seed':spec['seed'],
            'spec_path':wsl(sp),'spec_sha256':sha(sp),'contract_path':wsl(cp),'contract_sha256':sha(cp),
            'argv':argv,'cwd':wsl(ROOT),'run_dir':wsl(logdir),'output_root':spec['run_root'],
            'gpu_uuid':uuid,'gpu_budget_mib':spec['gpu_allocator_budget_bytes']//1048576,
            'timeout_seconds':spec['timeout_seconds'],'memory_limit_bytes':6*1024**3,
            'environment':{'PYTHONPATH':OVERLAY,'PYTHONHASHSEED':str(spec['seed'])},
            'requires_smoke':original['stage']=='formal'})
    jobs.sort(key=lambda j:(j['stage']!='smoke',j['view_id'],j['method_id'],j['seed']))
    write(LOCAL/'jobs.json',{'schema':'fourtask.local-cuda-dta.v1','jobs':jobs,
        'global_deadline':DEADLINE.isoformat(),'sequential_one_gpu_only':True,
        'source_environment_unchanged':True,'old_node1_outputs_preserved':True},immutable=True)
    print(json.dumps({'jobs':len(jobs),'smoke_jobs':sum(j['stage']=='smoke' for j in jobs),
        'formal_jobs':sum(j['stage']=='formal' for j in jobs),'path':str(LOCAL/'jobs.json'),
        'sha256':sha(LOCAL/'jobs.json')}))

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--gpu-uuid',required=True)
    prepare(parser.parse_args().gpu_uuid)
