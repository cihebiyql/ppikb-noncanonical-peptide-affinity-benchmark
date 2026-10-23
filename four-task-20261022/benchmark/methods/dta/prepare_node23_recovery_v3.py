"""CPU2 revision only for not-yet-started jobs; never interrupt CPU1 workers."""
import copy
import datetime as dt
import json
from pathlib import Path
import shlex
from cpu_fallback import ROOT,HERE,load,sha,write

OLD=HERE/'node23-cpu-recovery-v2'
DEST=HERE/'node23-cpu-recovery-v3'
REMOTE='/data/qlyu/projects/peptide-four-task-benchmark-20261022'
def remote(path):return REMOTE+'/'+Path(path).relative_to(ROOT).as_posix()
def local(path):return ROOT/Path(path).relative_to(REMOTE)

def main():
    index=load(OLD/'jobs.json')
    inflight={x['job_id'] for x in load(OLD/'inherited-progress-at-routing-v3.json')['active']}
    DEST.mkdir(exist_ok=True)
    probe=DEST/'probe-runtime.json';probe.write_bytes((OLD/'probe-runtime.json').read_bytes())
    jobs=[];inherited=[]
    for old in index['jobs']:
        if old['job_id'] in inflight:
            inherited.append(old);continue
        spec=copy.deepcopy(load(local(old['spec_path'])))
        jid=old['job_id'].replace('--node23-cpu-recovery-v2','--node23-cpu-recovery-v3')
        spec.update(job_id=jid,cpu_threads=2,
            run_root=spec['run_root'].replace('runs/dta_node23_cpu_recovery_v2/','runs/dta_node23_cpu_recovery_v3/'),
            resource_revision='Node23 CPU2 for previously unstarted jobs; old CPU1 workers continue unchanged',
            runtime_stratum='node23_CPU_Torch2.6.0_threads2',previous_cpu1_prepared_spec_sha256=old['spec_sha256'])
        sp=DEST/'specs'/(jid+'.json');write(sp,spec,immutable=True)
        cp0=local(old['contract_path']);contract=copy.deepcopy(load(cp0));stamp=dt.datetime.now(dt.timezone.utc).isoformat()
        argv=[old['argv'][0],REMOTE+'/methods/dta/train.py','--spec',remote(sp),'--device','cpu']
        logs=DEST/'dispatch'/jid
        contract.update(run_id=jid,created_at=stamp,frozen_at=stamp,revision=3,previous_contract_sha256=sha(cp0),
            revision_reason='Parent23:28Z authorizes CPU2,max15 combined DTA workers given actual idle96%; unstarted jobs only',
            cross_environment_seed_stratification='GPU/CPU and CPU1/CPU2 results are separate runtime strata; mixed SD not pure seed noise')
        contract['execution_scope'].update(prior_run_ids=[old['job_id']],
            relation_to_prior_run='Only resource/thread revision of an unlaunched CPU1 job; original bytes preserved; eleven already-running CPU1 jobs not interrupted.')
        for asset in contract['assets']['code']:
            if asset['role']=='frozen Node23 CPU specification':asset.update(path=remote(sp),sha256=sha(sp),archive_sha256=sha(sp))
        contract['targets'][0]['target_id']=jid
        contract['environment'].update(lockfile_path=remote(probe),lockfile_sha256=sha(probe))
        contract['resources'].update(cpu_threads=2,resource_probe_path=remote(probe),
            start_gate='Fresh3frames>=40%idle,>=36GiB available; UIDRSS+4GiB<=80GiB; combined oldCPU1+newCPU2<=15 workers; avoid inherited CPU affinity; CPU2/nice15/RSS4GiB',
            budget_basis='Parent explicit latest resource revision,15x2cores plus other <=~35/64 cores and retain>=32GiB; no epoch/LR/sample/seed changes')
        contract['execution'].update(command=shlex.join(argv),stdout_path=remote(logs/'stdout.log'),stderr_path=remote(logs/'stderr.log'))
        cp=DEST/'contracts'/(jid+'.json');write(cp,contract,immutable=True)
        job=copy.deepcopy(old)
        job.update(job_id=jid,cpu_threads=2,argv=argv,spec_path=remote(sp),spec_sha256=sha(sp),
            contract_path=remote(cp),contract_sha256=sha(cp),output_root=spec['run_root'],run_dir=remote(logs),
            previous_unlaunched_job_id=old['job_id'])
        jobs.append(job)
    index.update(schema='fourtask.node23-dta-recovery.v3',jobs=jobs,inherited_running_cpu1=inherited,
        max_concurrent=15,reserved_cpu_offsets=list(range(11,64)),resource_revision='CPU2 new workers; dynamic oldCPU1 accounting')
    write(DEST/'jobs.json',index,immutable=True)
    print(json.dumps({'new_CPU2_jobs':len(jobs),'inherited_CPU1_workers':len(inherited),'sha256':sha(DEST/'jobs.json')}))

if __name__=='__main__':main()
