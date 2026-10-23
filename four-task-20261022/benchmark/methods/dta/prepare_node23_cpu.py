"""Immutable Node23 CPU resource revision for formal seeds4-9; no execution."""
import copy
import datetime as dt
import json
from pathlib import Path
import shlex
from cpu_fallback import ROOT, HERE, HOME, START, DEADLINE, load, sha, write

REMOTE='/data/qlyu/projects/peptide-four-task-benchmark-20261022'
PYTHON='/data/qlyu/projects/peptide-binding-benchmark-20261020/common-prior-methods-20261021/.venv/bin/python'
DEST=HERE/'node23-cpu-v1'

def remote(path):
    return REMOTE+'/'+Path(path).relative_to(ROOT).as_posix()

def main():
    probe=load(HERE/'node23-probe-runtime.json')
    if probe['hostname']!='node23' or probe['runtime']['exit_code'] or not probe['all_idle_ge40']:
        raise ValueError('Live Node23 CPU/runtime gate failed')
    versions=json.loads(probe['runtime']['stdout'])
    if versions['cuda_available']:
        raise ValueError('CPU-only probe required')
    DEST.mkdir(parents=True,exist_ok=True)
    probe_path=DEST/'probe-runtime.json'
    if not probe_path.exists():
        probe_path.write_bytes((HERE/'node23-probe-runtime.json').read_bytes())
    base_cpu={j['method_id']:j for j in load(HOME/'jobs.json')['jobs']}
    selected=[j for j in load(HERE/'jobs.json')['jobs'] if
              (j['stage']=='formal' and j['seed'] in range(4,10)) or
              (j['stage']=='smoke' and j['view_id']=='ppikb_kd_source_cold_scope_v2')]
    jobs=[]
    for original in selected:
        base=load(ROOT/original['spec'])
        jid=original['job_id']+'--node23-cpu-v1'
        spec=copy.deepcopy(base)
        timeout=900 if original['stage']=='smoke' else 3600
        spec.update(job_id=jid,run_root=base['run_root'].replace('runs/dta/','runs/dta_node23_cpu/'),
            timeout_seconds=timeout,cpu_threads=1,gpu_allocator_budget_bytes=0,execution_device='cpu',
            resource_revision='node23-existing-Torch2.6-CPU-seeds4-9',
            prior_original_spec_sha256=original['spec_sha256'])
        sp=DEST/'specs'/(jid+'.json')
        write(sp,spec,immutable=True)
        basepath=Path(base_cpu[original['method_id']]['contract_path'].replace('/mnt/d/','D:/'))
        contract=copy.deepcopy(load(basepath))
        # All asset references in the validated CPU metadata lie under this new
        # campaign root. Point them at the actual shared Node23 storage.
        def remap(value):
            if isinstance(value,str):
                prefix='/mnt/d/work/科研工作台/research-tasks/peptide-four-task-benchmark-20261022'
                return value.replace(prefix,REMOTE)
            if isinstance(value,list):
                return [remap(x) for x in value]
            if isinstance(value,dict):
                return {k:remap(v) for k,v in value.items()}
            return value
        contract=remap(contract)
        now=dt.datetime.now(dt.timezone.utc).isoformat()
        argv=[PYTHON,REMOTE+'/methods/dta/train.py','--spec',remote(sp),'--device','cpu']
        logdir=DEST/'dispatch'/jid
        contract.update(run_id=jid,created_at=now,frozen_at=now,
            resource_revision='Node23 CPU seeds4-9; source/split/hyperparameters unchanged',
            cross_environment_seed_stratification='Local CUDA seeds0-3 and Node23 CPU seeds4-9 are different runtime strata; SD is not pure seed randomness.')
        contract['identity']['title']=original['method_id']+' Node23 CPU common-data '+original['stage']
        contract['execution_scope'].update(objective='New Node23 CPU '+original['stage']+' with unchanged data/split/hyperparameters; formal route seeds4-9 only; no original-paper full reproduction claim.',
            relation_to_prior_run='Resource-only revision in same newly authorized common-data objective; no original Node1 run resumed or overwritten.',
            prior_run_ids=[original['job_id']],intended_level='smoke' if original['stage']=='smoke' else 'training',
            excluded_claims=['full original paper','GPU execution','pure seed-only SD across heterogeneous host/runtime'])
        if original['task']=='effect':
            contract['execution_scope']['objective']+=' Metadata-silver ΔpKd pairs; potential-difference loss adaptation, not strict gold.'
        contract['assets']['datasets']=[]
        for name,item in spec['paths'].items():
            path=ROOT/item['path']
            if sha(path)!=item['sha256']:
                raise ValueError('Input changed')
            contract['assets']['datasets'].append({'name':name,'path':remote(path),'sha256':sha(path),
                'manifest_sha256':sha(path),'sample_count':item['n'],'integrity':'complete',
                'statistical_unit':'observation' if original['task']!='effect' else 'metadata-silver pair'})
        contract['assets']['code']=[x for x in contract['assets']['code'] if x['role'] not in
            ('frozen CPU configuration','CPU process-tree watchdog')]
        contract['assets']['code'].append({'role':'frozen Node23 CPU specification','path':remote(sp),
            'sha256':sha(sp),'archive_sha256':sha(sp),'integrity':'complete'})
        supervisor=ROOT/'resources/cpu_supervise_node23.py'
        contract['assets']['code'].append({'role':'existing owned process-group watchdog','path':remote(supervisor),
            'sha256':sha(supervisor),'archive_sha256':sha(supervisor),'integrity':'complete'})
        target=contract['targets'][0]
        target.update(target_id=jid,paper_endpoint=spec['endpoint'],comparison_endpoint='new Node23 CPU common-data '+original['stage'],
            denominator=original['sample_counts']['test'],unit=spec['endpoint'],repetitions=1,
            statistical_unit='observation' if original['task']!='effect' else 'metadata-silver pair')
        contract['environment'].update(environment_path=versions['prefix'],
            isolation='Existing shared-readable task-specific environment; CPU only, no installation',
            lockfile_path=remote(probe_path),lockfile_sha256=sha(probe_path),runtime_versions=versions,
            shared_environment_modified=False)
        contract['resources'].update(expected_hostname='node23',cpu_threads=1,data_loader_workers=0,
            memory_limit_bytes=4*1024**3,gpu_devices=[],gpu_memory_budget_bytes=0,
            resource_probe_path=remote(probe_path),resource_probe_at=probe['at'],
            start_gate='Standard exact-byte validation; max5 DTA workers; fresh3frames CPUidle>=40%; memoryavailable>=32GiB+4GiB; qlyu aggregate RSS+4GiB<=68GiB; nice15; campaign16core total budget',
            budget_basis='Parent explicit CPU resource split:8SWING+2molecular+1head+5DTA<=16; reserved logical slots11-15',
            no_preemption=True)
        contract['execution'].update(command=shlex.join(argv),working_directory=REMOTE,
            seeds=[spec['seed']],seed_policy='Fixed split; local CUDA0-3 vs Node23CPU4-9 reported separately and combined with runtime-stratification warning',
            timeout_seconds=timeout,
            process_control={'platform':'linux','mechanism':'Independent per-job owned process-group supervisor; totalRSS4GiB; wall deadline; CPU affinity slot11-15; nice15','whole_tree_bounded':True},
            stdout_path=remote(logdir/'stdout.log'),stderr_path=remote(logdir/'stderr.log'))
        cp=DEST/'contracts'/(jid+'.json')
        write(cp,contract,immutable=True)
        jobs.append({'job_id':jid,'original_job_id':original['job_id'],'method_id':original['method_id'],
            'view_id':original['view_id'],'task':original['task'],'stage':original['stage'],'seed':spec['seed'],
            'spec_path':remote(sp),'spec_sha256':sha(sp),'contract_path':remote(cp),'contract_sha256':sha(cp),
            'argv':argv,'cwd':REMOTE,'output_root':spec['run_root'],'run_dir':remote(logdir),
            'timeout_seconds':timeout,'memory_limit_bytes':4*1024**3,'cpu_threads':1,'nice':15,
            'sample_counts':original['sample_counts']})
    jobs.sort(key=lambda j:(j['stage']!='smoke',j['view_id']!='ppikb_kd_source_cold_scope_v2',j['method_id']!='GraphDTA-GIN',j['seed'],j['method_id']))
    write(DEST/'jobs.json',{'schema':'fourtask.node23-dta-cpu.v1','jobs':jobs,
        'global_deadline':DEADLINE.isoformat(),'max_concurrent':5,'reserved_cpu_offsets':[11,12,13,14,15],
        'formal_seed_route':[4,5,6,7,8,9],'GPU_used':False},immutable=True)
    print(json.dumps({'jobs':len(jobs),'formal':sum(j['stage']=='formal' for j in jobs),
        'smoke':sum(j['stage']=='smoke' for j in jobs),'jobs_sha256':sha(DEST/'jobs.json')}))

if __name__=='__main__':
    main()
