"""Full predefined synthetic/D/backbone stratum; runtime-selected CPU route, no test-based model selection."""
import argparse
import copy
import datetime as dt
import json
from pathlib import Path
import shlex
from cpu_fallback import ROOT, HERE, HOME, PYTHON, load, sha, write, wsl, execute

FORMAL = HERE/'cpu-formal-synthetic-v1'

def prepare():
    original = next(j for j in load(HERE/'jobs.json')['jobs']
                    if j['method_id']=='GraphDTA-GIN' and j['stage']=='formal' and j['seed']==0
                    and j['view_id']=='ppikb_kd_source_cold_scope_v2')
    base = load(ROOT/original['spec'])
    base_cpu = next(j for j in load(HOME/'jobs.json')['jobs'] if j['method_id']=='GraphDTA-GIN')
    base_contract = load(Path(base_cpu['contract_path'].replace('/mnt/d/', 'D:/')) if not str(HERE).startswith('/') else base_cpu['contract_path'])
    # Fixed scientific subset chosen by the user's stated NC priority. Preserve
    # every eligible stratum observation and its original partition.
    paths, counts = {}, {}
    for name, item in base['paths'].items():
        source = ROOT/item['path']
        if sha(source) != item['sha256']:
            raise ValueError('Original partition changed')
        rows = [json.loads(line) for line in source.read_text(encoding='utf-8').splitlines() if line]
        subset = [r for r in rows if (r.get('evaluation_stratum') or r.get('stratum')) == 'synthetic_D_backbone']
        path = FORMAL/'inputs'/(name+'.jsonl')
        path.parent.mkdir(parents=True,exist_ok=True)
        text = ''.join(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n' for r in subset)
        if path.exists() and path.read_text(encoding='utf-8') != text:
            raise FileExistsError(path)
        path.write_text(text,encoding='utf-8')
        paths[name] = {'path':path.relative_to(ROOT).as_posix(),'sha256':sha(path),'n':len(subset)}
        counts[name] = len(subset)
    if counts != {'train':451,'validation':83,'test':99}:
        raise ValueError('Unexpected fixed stratum membership')
    jobs = []
    for seed in range(10):
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        jid = f'ppikb_synthetic_D_backbone_source_cold--GraphDTA-GIN--formal--seed{seed}--cpu-v1'
        spec = copy.deepcopy(base)
        spec.update(job_id=jid,view_id='ppikb_synthetic_D_backbone_source_cold_cpu_v1',
            seed=seed,run_root=f'runs/dta_cpu_synthetic/GraphDTA-GIN/formal/seed-{seed}',paths=paths,
            max_epochs=20,patience=5,cpu_threads=1,gpu_allocator_budget_bytes=0,timeout_seconds=900,
            execution_device='cpu',smoke_subset_only=False,
            scientific_subset='all synthetic_D_backbone observations from unchanged frozen source-cold panel',
            model_choice_basis='CPU end-to-end smoke runtime; test scores not consulted for choice',
            stage='formal')
        sp = FORMAL/'specs'/(jid+'.json')
        write(sp,spec,immutable=True)
        argv = [PYTHON,wsl(HERE/'train.py'),'--spec',wsl(sp),'--device','cpu']
        logdir = FORMAL/'dispatch'/jid
        contract = copy.deepcopy(base_contract)
        contract.update(run_id=jid,created_at=now,frozen_at=now)
        contract['identity']['title']='GraphDTA-GIN full predefined synthetic/D/backbone CPU training'
        contract['execution_scope'].update(
            objective='New full predefined synthetic_D_backbone stratum: 451 train/83 validation/99 test, two LR candidates,20epochs/patience5; each seed is a separate fit.',
            intended_level='training',scope_coverage='partial_subset',
            excluded_claims=['whole9116-view training complete','full original-paper reproduction','ten seeds complete before all corresponding receipts exist'])
        contract['assets']['datasets'] = [{'name':k,'path':wsl(ROOT/r['path']),'sha256':r['sha256'],
            'manifest_sha256':r['sha256'],'sample_count':r['n'],'integrity':'complete',
            'statistical_unit':'original measurement','notes':'Complete predefined chemical stratum; original split retained'} for k,r in paths.items()]
        contract['assets']['code'] = [a for a in contract['assets']['code'] if a['role']!='frozen CPU configuration']
        contract['assets']['code'].append({'role':'frozen CPU configuration','path':wsl(sp),
            'sha256':sha(sp),'archive_sha256':sha(sp),'integrity':'complete'})
        contract['targets'][0].update(target_id=jid,paper_endpoint='pKd',comparison_endpoint='new full chemical-stratum common-data training',
                                     denominator=99,repetitions=1)
        contract['execution'].update(command=shlex.join(argv),seeds=[seed],
            seed_policy='Each fit seed0-9 uses identical frozen split; validation-only checkpoint/LR selection',
            stdout_path=wsl(logdir/'stdout.log'),stderr_path=wsl(logdir/'stderr.log'))
        cp = FORMAL/'contracts'/(jid+'.json')
        write(cp,contract,immutable=True)
        jobs.append({'job_id':jid,'method_id':'GraphDTA-GIN','spec_path':wsl(sp),'spec_sha256':sha(sp),
            'contract_path':wsl(cp),'contract_sha256':sha(cp),'argv':argv,'run_root':spec['run_root'],
            'log_dir':wsl(logdir),'timeout_seconds':900,'seed':seed,'stage':'formal'})
    write(FORMAL/'jobs.json',{'schema':'fourtask.cpu-formal-chemical-stratum.v1','jobs':jobs,
        'counts':counts,'choice_basis':'User priority predefined NC stratum; method chosen by smoke runtime only',
        'original_full_view':'ppikb_kd_source_cold_scope_v2'},immutable=True)
    print(json.dumps({'prepared_jobs':len(jobs),'counts':counts}))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--seed',type=int)
    args=parser.parse_args()
    if args.prepare:
        prepare()
    if args.seed is not None:
        job=next(j for j in load(FORMAL/'jobs.json')['jobs'] if j['seed']==args.seed)
        print(json.dumps(execute(job),ensure_ascii=False),flush=True)

if __name__=='__main__':
    main()
