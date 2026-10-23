"""Freeze standard contracts for the new common-data objective; run no workload."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import shlex
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT.parent / 'peptide-binding-nc-benchmark-20261021'
STANDARD = ROOT.parents[1] / '复现' / '规范'
REMOTE = '/data/qlyu/projects/peptide-four-task-benchmark-20261022'
START = datetime(2026, 10, 22, 15, 31, 20, tzinfo=timezone.utc)

def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError('Frozen contracts are append-only: ' + str(path))
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')

def remote_reference(path):
    path = Path(path)
    try:
        return REMOTE + '/' + path.relative_to(ROOT).as_posix()
    except ValueError:
        raise ValueError('Stage external reference inside new root before freezing: ' + str(path))

def freeze(spec, output):
    """Spec must identify a real frozen input, exact argv and an assessed scope."""
    for k in ('method_id', 'job_id', 'argv', 'view_path', 'code_path', 'environment_path',
              'gpu_uuid', 'resource_probe_path', 'runtime_receipt_path', 'scope_assessed',
              'denominator', 'endpoint'):
        if not spec.get(k):
            raise ValueError('Missing truthful execution prerequisite: ' + k)
    if spec['scope_assessed'] is not True:
        raise ValueError('Scope not assessed')
    now = datetime.now(timezone.utc)
    deadline = START + timedelta(hours=10)
    timeout = min(int(spec.get('timeout_seconds', 3600)), 3600)
    if now + timedelta(seconds=timeout + 120) >= deadline:
        raise ValueError('Not enough time remaining in current common-task window')
    contract = load(STANDARD / 'task-contract.template.json')
    registry = load(ROOT / 'protocol' / 'method_registry.json')['methods']
    method = next(m for m in registry if m['id'] == spec['method_id'] or
                  (m['id'] == 'DGDTA' and spec['method_id'] == 'DGDTA-CL'))
    old_registry = load(OLD / 'control' / 'registered-paper-map.json')
    old_id = old_registry.get(spec['method_id'], {})
    pdf = old_id.get('pdf_path') or spec.get('pdf_path')
    if not pdf:
        asset_name = {'PepInter': 'PepInter.pdf', 'SWING': 'swing.pdf'}.get(method['id'])
        if asset_name:
            pdf = str(ROOT.parent / 'peptide-binding-benchmark-20261020' / 'assets' / asset_name)
    if not pdf or not Path(pdf).is_file() or Path(pdf).read_bytes()[:5] != b'%PDF-':
        raise ValueError('Missing actual identified paper PDF')
    staged_pdf = ROOT / 'resources' / 'papers' / (spec['method_id'] + '.pdf')
    staged_pdf.parent.mkdir(parents=True, exist_ok=True)
    if not staged_pdf.exists():
        shutil.copyfile(pdf, staged_pdf)
    if sha(staged_pdf) != sha(pdf):
        raise ValueError('Staged paper hash mismatch')
    pdf = str(staged_pdf)
    view, code = Path(spec['view_path']), Path(spec['code_path'])
    for path in (view, code, Path(spec['resource_probe_path']), Path(spec['runtime_receipt_path'])):
        if not path.is_file():
            raise FileNotFoundError(path)
    job_id = spec['job_id']
    run_dir = spec.get('run_dir', REMOTE + '/runs/resource-' + job_id)
    argv = spec['argv']
    if not isinstance(argv, list) or not all(isinstance(v, str) for v in argv):
        raise ValueError('argv must be a list of exact strings')
    command = shlex.join(argv)
    contract.update(is_template=False, task_id='fourtask-common-' + method['id'],
                    run_id=job_id, contract_status='frozen', created_at=now.isoformat(),
                    frozen_at=now.isoformat(), linked_original_task_id=old_id.get('task_id'))
    contract['identity'].update(title=method['id'] + ' new four-task common-data evaluation',
                                doi=method['doi'], publication_status='published',
                                pdf={'path': pdf, 'sha256': sha(pdf), 'version': 'retained identified source',
                                     'source_url': 'https://doi.org/' + method['doi']})
    contract['execution_scope'].update(
        objective=spec.get('objective', 'New user-authorized common-data training; no original-paper full reproduction claim'),
        authorization_reference=str(ROOT / 'protocol' / 'USER_REQUEST.txt'),
        relation_to_prior_run='New four-source/four-task common-data objective explicitly requested this turn. Prior original-paper clocks, limitations and outputs are preserved; this does not resume any rejected workflow.',
        prior_run_ids=spec.get('prior_run_ids', []), safety_assessment='allowed',
        scope_coverage='partial_subset', intended_level=spec.get('intended_level', 'training'),
        excluded_claims=['full original paper reproduction', 'unmeasured biological validation',
                         'eight methods applicable to all four tasks'],
        restriction_check={'prior_platform_restriction': False,
                           'reason': 'Only new assessed benign common-task inputs; rejected workflows excluded.',
                           'evidence_paths': [str(ROOT / 'protocol' / 'USER_REQUEST.txt')]})
    contract['timing'].update(first_substantive_started_at=START.isoformat(),
        earliest_associated_preparation_at=START.isoformat(), wall_clock_cap_hours=10,
        original_deadline_at=deadline.isoformat(), effective_deadline_at=deadline.isoformat(),
        prior_window_expired=False, retry_resets_clock=False,
        scope_of_clock='This newly requested common-data objective only; no historical paper clock is reset.')
    contract['assets'] = {
        'datasets': [{'name': spec.get('view_id', view.stem), 'path': str(view),
                      'manifest_sha256': sha(view), 'sample_count': spec['denominator'],
                      'statistical_unit': spec.get('statistical_unit', 'source observation'),
                      'integrity': 'complete', 'notes': 'Exact local bytes; remote copy must independently hash-match before dispatch.'}],
        'code': [{'role': 'common-task adapter', 'path': str(code), 'archive_sha256': sha(code),
                  'integrity': 'complete', 'source_url': method['source'],
                  'notes': 'Upstream and dependency manifests remain separate from this entrypoint hash.'}],
        'models': spec.get('models', [{'integrity': 'not_applicable',
                    'notes': 'Randomly initialized training; no pretrained supervised weights requested for this run.'}])}
    contract['targets'] = [{'target_id': job_id, 'paper_endpoint': spec['endpoint'], 'required': True,
        'comparison_endpoint': 'new common-task evaluation', 'metric': spec.get('metric', 'MAE'),
        'metric_definition': spec.get('metric_definition', 'Mean absolute prediction error on frozen test; selection uses validation only.'),
        'statistical_unit': spec.get('statistical_unit', 'source observation'),
        'denominator': spec['denominator'], 'unit': spec.get('unit', spec['endpoint']),
        'paper_value': None, 'checkpoint_selection': 'validation only; retain all candidates',
        'repetitions': len(spec.get('seeds', [spec.get('seed', 0)])),
        'tolerance': {'kind': 'not_comparable', 'reason': 'New common-data endpoint/split, not original paper table denominator.'}}]
    contract['environment'].update(isolation='Read-only existing task-specific virtual environment; new outputs isolated',
        environment_path=spec['environment_path'], lockfile_path=spec['runtime_receipt_path'],
        lockfile_sha256=sha(spec['runtime_receipt_path']), runtime_versions=spec.get('runtime_versions', {}),
        shared_environment_modified=False)
    contract['resources'].update(expected_hostname=spec.get('expected_hostname', 'node1'),
        cpu_threads=1, data_loader_workers=0, memory_limit_bytes=int(spec.get('memory_limit_bytes', 6442450944)),
        gpu_devices=[spec['gpu_uuid']], gpu_memory_budget_bytes=int(spec.get('gpu_memory_budget_bytes', 2147483648)),
        resource_probe_path=spec['resource_probe_path'], resource_probe_at=spec.get('resource_probe_at', now.isoformat()),
        start_gate='standard validator + remote exact byte hashes + three current GPU samples + global max3 + memory reserve + bounded smoke',
        budget_basis='User maximum three low-use GPUs; reserve other users memory growth; one CPU thread', no_preemption=True)
    contract['execution'].update(command=command, working_directory=REMOTE,
        seed_policy='Frozen split across seeds0-9; each seed is an independent fit; validation-only selection.',
        seeds=spec.get('seeds', [spec.get('seed', 0)]), timeout_seconds=timeout,
        process_control={'platform': 'linux', 'mechanism': 'private setsid process group, watchdog, resource limits', 'whole_tree_bounded': True},
        stdout_path=run_dir + '/stdout.log', stderr_path=run_dir + '/stderr.log')
    contract['numerical_policy_specification'] = spec.get('numerical_policy', 'Use frozen method adapter; record actual torch dtype/determinism/TF32 at runtime.')
    # Freeze remote execution references directly. They must be byte-checked by
    # the Node1 standard validator; local Windows skips are not execution proof.
    contract['identity']['pdf']['path'] = remote_reference(pdf)
    contract['assets']['datasets'][0].update(path=remote_reference(view), sha256=sha(view))
    contract['assets']['code'][0].update(path=remote_reference(code), sha256=sha(code))
    contract['execution_scope']['authorization_reference'] = REMOTE + '/protocol/USER_REQUEST.txt'
    contract['execution_scope']['restriction_check']['evidence_paths'] = [REMOTE + '/protocol/USER_REQUEST.txt']
    contract['environment']['lockfile_path'] = remote_reference(spec['runtime_receipt_path'])
    contract['resources']['resource_probe_path'] = remote_reference(spec['resource_probe_path'])
    dump(output, contract)
    return {'contract_path': str(output), 'contract_sha256': sha(output), 'argv': argv,
            'gpu_uuid': spec['gpu_uuid'], 'run_dir': run_dir}

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--spec', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    print(json.dumps(freeze(load(a.spec), a.output), ensure_ascii=False))
