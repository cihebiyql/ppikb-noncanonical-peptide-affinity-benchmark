"""Resource-only recovery after control-service interruption; do not repeat completed work."""
import copy
import datetime as dt
import json
from pathlib import Path
from cpu_fallback import ROOT,HERE,load,sha,write

OLD=HERE/'node23-cpu-v1'
DEST=HERE/'node23-cpu-recovery-v2'
REMOTE='/data/qlyu/projects/peptide-four-task-benchmark-20261022'

def remote(path):return REMOTE+'/'+Path(path).relative_to(ROOT).as_posix()

def main():
    source=load(OLD/'jobs.json')
    DEST.mkdir(exist_ok=True)
    probe=DEST/'probe-runtime.json'
    if not probe.exists():probe.write_bytes((HERE/'node23-probe-runtime-recovery-v2.json').read_bytes())
    fresh=load(probe)
    if fresh['runtime']['exit_code'] or not fresh['all_idle_ge40']:raise ValueError('Fresh runtime/capacity gate failed')
    carried=[];jobs=[]
    for old in source['jobs']:
        if old['stage']!='formal':continue
        if old['method_id']=='GraphDTA-GIN' and old['view_id']=='ppikb_kd_source_cold_scope_v2' and old['seed']==4:
            carried.append({'job':old,'reason':'Actual worker3308967 terminated17:20Z exit0; preserved complete/prediction reanalysis passed23:22Z; never retrained'})
            continue
        spec=copy.deepcopy(load(ROOT/Path(old['spec_path']).relative_to(REMOTE)))
        jid=old['job_id'].replace('--node23-cpu-v1','--node23-cpu-recovery-v2')
        timeout=1800 if old['method_id']=='GraphDTA-GIN' or old['task']=='effect' else 3600
        spec.update(job_id=jid,run_root=spec['run_root'].replace('runs/dta_node23_cpu/','runs/dta_node23_cpu_recovery_v2/'),
            timeout_seconds=timeout,resource_revision='Node23 CPU backend-control-recovery-v2; max11 CPU1; no scientific change',
            previous_prepared_spec_sha256=old['spec_sha256'],runtime_stratum='node23_CPU_Torch2.6.0')
        sp=DEST/'specs'/(jid+'.json');write(sp,spec,immutable=True)
        oldcp=ROOT/Path(old['contract_path']).relative_to(REMOTE)
        contract=copy.deepcopy(load(oldcp))
        stamp=dt.datetime.now(dt.timezone.utc).isoformat()
        newlog=DEST/'dispatch'/jid
        argv=[old['argv'][0],REMOTE+'/methods/dta/train.py','--spec',remote(sp),'--device','cpu']
        contract.update(run_id=jid,created_at=stamp,frozen_at=stamp,revision=2,
            previous_contract_sha256=sha(oldcp),revision_reason='Control backend403 interruption; old process state audited before new resource-only route',
            resource_revision='max11 sequential slots CPU1/RSS4GiB/nice15; scientific data/20epochs/patience5/twoLR/seed unchanged')
        contract['execution_scope'].update(prior_run_ids=[old['job_id']],
            relation_to_prior_run='Prior Node23 job was only prepared and never launched, except separately carried Graph source seed4. Control-service interruption is not scientific platform refusal. New resource job/output; no rejected workflow revived.')
        for asset in contract['assets']['code']:
            if asset['role']=='frozen Node23 CPU specification':
                asset.update(path=remote(sp),sha256=sha(sp),archive_sha256=sha(sp))
        contract['targets'][0]['target_id']=jid
        contract['environment'].update(lockfile_path=remote(probe),lockfile_sha256=sha(probe),runtime_versions=json.loads(fresh['runtime']['stdout']))
        contract['resources'].update(resource_probe_path=remote(probe),resource_probe_at=fresh['at'],
            start_gate='Fresh3frames CPUidle>=40%; memoryavailable>=36GiB; UIDRSS+4GiB<=68GiB; max11 DTA CPU1/nice15, reserved CPU11-21; exact standard validator; no GPU',
            budget_basis='Parent explicit recovery authorization23:17Z; coordinate with SWING/molecular/head; preserve >=32GiB and40%idle')
        contract['execution'].update(command=__import__('shlex').join(argv),timeout_seconds=timeout,
            stdout_path=remote(newlog/'stdout.log'),stderr_path=remote(newlog/'stderr.log'))
        cp=DEST/'contracts'/(jid+'.json');write(cp,contract,immutable=True)
        job=copy.deepcopy(old)
        job.update(job_id=jid,spec_path=remote(sp),spec_sha256=sha(sp),contract_path=remote(cp),contract_sha256=sha(cp),
            argv=argv,output_root=spec['run_root'],run_dir=remote(newlog),timeout_seconds=timeout,
            previous_unlaunched_job_id=old['job_id'])
        jobs.append(job)
    # Prioritize complete source-view coverage, then short effect tasks, with the
    # slowest source model started early rather than deferred to the deadline.
    jobs.sort(key=lambda j:(0 if j['view_id']=='ppikb_kd_source_cold_scope_v2' else 1 if j['task']=='effect' else 2,
                           {'MGraphDTA':0,'GraphDTA-GIN':1,'DGDTA-CL':2,'DeepNC-GEN':3,'GS-DTA':4}[j['method_id']],j['seed']))
    data=copy.deepcopy(source)
    data.update(schema='fourtask.node23-dta-recovery.v2',jobs=jobs,carried_forward=carried,
        prerequisite_smokes=[j for j in source['jobs'] if j['stage']=='smoke'],max_concurrent=11,
        reserved_cpu_offsets=list(range(11,22)),control_interruption_reason='backend403; not a scientific safety/platform refusal')
    write(DEST/'jobs.json',data,immutable=True)
    print(json.dumps({'new_jobs':len(jobs),'carried_forward':len(carried),'sha256':sha(DEST/'jobs.json')}))

if __name__=='__main__':main()
