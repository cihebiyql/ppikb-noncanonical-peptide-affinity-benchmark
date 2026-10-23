"""Issue standard frozen contracts for already prepared DTA jobs."""
import argparse
import json
from pathlib import Path
from freeze_gpu_contract import ROOT, REMOTE, dump, freeze, load, remote_reference, sha

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', choices=['smoke', 'formal'], required=True)
    parser.add_argument('--gpus', nargs='+', required=True)
    parser.add_argument('--view-id', default=None)
    parser.add_argument('--batch-name', default=None)
    parser.add_argument('--admission', default=None, help='New resource admission revision; original scientific spec stays immutable')
    args = parser.parse_args()
    if not 1 <= len(args.gpus) <= 2:
        raise ValueError('Current existing third GPU is reserved for other work; at most two new cards.')
    jobs = load(ROOT / 'methods/dta/jobs.json')['jobs']
    issued = []
    selected = [j for j in jobs if j['stage'] == args.stage and (not args.view_id or j['view_id'] == args.view_id)]
    for index, job in enumerate(selected):
        source_spec = load(ROOT / job['spec'])
        dispatch_id = job['job_id'] + ('--' + args.admission if args.admission else '')
        cp = ROOT / 'protocol' / 'contracts' / (dispatch_id + '.json')
        spec = dict(job)
        spec['job_id'] = dispatch_id
        spec.update(view_path=str(ROOT / source_spec['input_view']['path']),
                    code_path=str(ROOT / 'methods/dta/train.py'),
                    environment_path=job['argv'][0],
                    gpu_uuid=args.gpus[index % len(args.gpus)],
                    resource_probe_path=str(ROOT / 'resources/probe-node1-task-runtime.json'),
                    runtime_receipt_path=str(ROOT / 'resources/probe-node1-task-runtime.json'),
                    scope_assessed=True, denominator=sum(job['sample_counts'].values()),
                    unit=job['endpoint'], intended_level='smoke' if args.stage == 'smoke' else 'training',
                    run_dir=REMOTE + '/runs/resource-' + dispatch_id)
        freeze(spec, cp)
        # Contract is not issued until full split and run-config byte references
        # are attached. No workload has started during this construction.
        contract = load(cp)
        for role, item in source_spec['paths'].items():
            local = ROOT / item['path']
            if sha(local) != item['sha256']:
                raise ValueError('Prepared split hash changed')
            contract['assets']['datasets'].append(dict(name=role, path=remote_reference(local),
                sha256=sha(local), manifest_sha256=sha(local), sample_count=item['n'], integrity='complete',
                notes='Exact prepared partition; not independently generated observations.'))
        config = ROOT / job['spec']
        contract['assets']['code'].append(dict(role='frozen run configuration', path=remote_reference(config),
            sha256=sha(config), archive_sha256=sha(config), integrity='complete'))
        # Construction-only replacement, before publication to dispatcher.
        cp.write_text(json.dumps(contract, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
        payload = dict(issued=True, job_id=dispatch_id, scientific_job_id=job['job_id'], contract_path=remote_reference(cp),
            contract_sha256=sha(cp), argv=job['argv'], cwd=REMOTE, gpu_uuid=spec['gpu_uuid'],
            gpu_budget_mib=job['gpu_memory_budget_bytes'] // 1048576, run_dir=spec['run_dir'],
            environment={'PYTHONHASHSEED': str(job['seed'])}, stage=args.stage,
            method_id=job['method_id'], view_id=job['view_id'])
        job_file = ROOT / 'protocol/dispatch' / (dispatch_id + '.json')
        dump(job_file, payload)
        issued.append(dict(job_id=dispatch_id, scientific_job_id=job['job_id'], path=str(job_file), sha256=sha(job_file),
                           contract_path=str(cp), contract_sha256=sha(cp)))
    output = ROOT / 'protocol/dispatch' / ((args.batch_name or args.stage) + '-issued.json')
    dump(output, {'schema': 'fourtask.issued-contracts.v1', 'stage': args.stage, 'jobs': issued,
                  'statement': 'Issued contracts require remote standard validation, current resources and bounded smoke; issuance is not a completed run.'})
    print(json.dumps({'count': len(issued), 'path': str(output)}))

if __name__ == '__main__':
    main()
