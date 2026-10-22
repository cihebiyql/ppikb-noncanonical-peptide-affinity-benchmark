"""Stdlib-only post-barrier gates. Never imports models, runner, or scorer."""
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import sys
import time

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
LAUNCH = PROJECT / 'launch'
sys.path.insert(0, str(LAUNCH))
from common import checked, deadline, epoch, path, read, sha, utc, write, process_table, HARD_DEADLINE, GPU_UUID

GIB = 1024**3
HOST = 'cihebi'
PYTHON = '/root/.venvs/peptide-omnipanel-v31-web311-20260723/bin/python'
METHOD_FOLDERS = {'GraphDTA-GIN':'graphdta-deepnc', 'DeepNC-GEN':'graphdta-deepnc', 'MGraphDTA':'mgraph-dgdta', 'DGDTA-CL':'mgraph-dgdta', 'GS-DTA':'gs-dta'}


def same_path(a, b):
    return path(a).resolve() == path(b).resolve()


def reference(ref):
    if not isinstance(ref, dict) or set(ref) != {'path', 'sha256'}:
        raise ValueError('Reference must contain exactly path and sha256')
    return checked(ref['path'], ref['sha256'])


def tree_hash(root):
    root = path(root)
    entries = [(str(p.relative_to(root)).replace('\\', '/'), sha(p)) for p in sorted(root.rglob('*.py')) if '__pycache__' not in p.parts]
    return hashlib.sha256(json.dumps(entries, separators=(',', ':')).encode()).hexdigest()


def runtime_gate(meta):
    if os.name != 'posix' or not Path('/proc').is_dir():
        raise RuntimeError('Linux WSL process controls required')
    if socket.gethostname() != HOST or meta['expected_hostname'] != HOST:
        raise RuntimeError('Actual host mismatch')
    if not same_path(sys.executable, PYTHON) or not same_path(meta['python'], PYTHON):
        raise RuntimeError('Actual Python interpreter mismatch')
    if not same_path(sys.prefix, path(PYTHON).parent.parent):
        raise RuntimeError('Actual virtual environment mismatch')
    if meta['gpu_uuid'] != GPU_UUID or os.environ.get('CUDA_VISIBLE_DEVICES') != GPU_UUID:
        raise RuntimeError('Actual GPU identity mismatch')
    expected_overlay = PROJECT / 'resources/local-gpu-route/vendor-dependencies'
    if not same_path(meta['PYTHONPATH'], expected_overlay) or os.environ.get('PYTHONPATH') != meta['PYTHONPATH']:
        raise RuntimeError('Actual task-local dependency route mismatch')


def private_pool_gate(binding_path, binding):
    if os.getpid() != os.getpgrp() or os.getsid(0) != os.getpid():
        raise RuntimeError('Unit must be a private process session/group leader')
    parent = os.getppid()
    if os.environ.get('NC_SCORE_POOL_OWNER_PID') != str(parent):
        raise RuntimeError('Unit requires its supervising scoring pool')
    table = process_table()
    p = table.get(parent)
    if p is None or p['uid'] != os.getuid() or str(p['start_ticks']) != os.environ.get('NC_SCORE_POOL_OWNER_START_TICKS'):
        raise RuntimeError('Scoring pool identity/start time mismatch')
    if not same_path(os.environ.get('NC_SCORE_POOL_BINDING_PATH', ''), binding_path):
        raise RuntimeError('Pool binding path mismatch')
    if os.environ.get('NC_SCORE_POOL_BINDING_SHA256') != sha(binding_path):
        raise RuntimeError('Pool did not issue this binding SHA')
    if not re.fullmatch(r'[0-9a-f]{64}', os.environ.get('NC_SCORE_POOL_INDEX_SHA256', '')):
        raise RuntimeError('Missing issued pool index SHA')
    command = (Path('/proc') / str(parent) / 'cmdline').read_bytes().split(b'\0')
    if str(HERE / 'score_pool.py').encode() not in command:
        raise RuntimeError('Parent is not the bound scoring supervisor')
    if len(os.sched_getaffinity(0)) != 2 or any(os.environ.get(key) != '2' for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS')):
        raise RuntimeError('Actual scoring CPU affinity/thread budget must be two')


def identity(selection):
    return (selection['method_id'], selection['split_id'], selection['regime'], int(selection['seed']))


def preflight(binding_path, require_private_session=True, now=None, reserve_full_timeout=True):
    """All metadata/code gates execute before scorer/checkpoint/gold access."""
    binding_path = path(binding_path)
    binding = read(binding_path)
    if binding.get('schema') != 'score-unit-binding-v1' or binding.get('issued') is not True:
        raise PermissionError('Root-issued scoring binding required')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', binding['unit_id']):
        raise ValueError('Unsafe unit identity')
    runtime_gate(binding)
    if require_private_session:
        private_pool_gate(binding_path, binding)
    cutoff = deadline(binding['deadline'])
    timeout = int(binding['timeout_seconds'])
    if timeout != 1200:
        raise ValueError('Each unit must reserve exactly 1200 seconds for three scores')
    clock = time.time() if now is None else now
    if reserve_full_timeout and clock + timeout > cutoff:
        raise TimeoutError('Cannot start: full unit timeout would exceed original deadline')
    checked(HERE / 'score_unit.py', binding['entrypoint_sha256'])
    checked(HERE / 'score_pool.py', binding['pool_sha256'])
    checked(__file__, binding['common_sha256'])
    # Authorization precedes any selection/spec/contract metadata traversal.
    auth_path = reference(binding['authorization'])
    auth = read(auth_path)
    if auth.get('root_scoring_authorized') is not True or 'score' not in auth.get('allowed_phases', []):
        raise PermissionError('Root post-barrier score authorization required')
    barrier_path = reference(binding['barrier'])
    audit_path = reference(binding['audit'])
    barrier, audit = read(barrier_path), read(audit_path)
    if binding['barrier']['sha256'] != auth['barrier_sha256'] or binding['audit']['sha256'] != auth['barrier_audit_sha256']:
        raise ValueError('Authorization barrier/audit SHA mismatch')
    if barrier.get('status') != 'all_selections_frozen' or barrier.get('selection_count') != 200 or barrier.get('candidate_fit_count') != 400 or len(barrier.get('selections', [])) != 200:
        raise PermissionError('All 200 selections / 400 fits must finish first')
    if audit.get('status') != 'all_200_selections_and_checkpoints_verified' or len(audit.get('selections', [])) != 200:
        raise PermissionError('Independent complete-grid audit required')
    if audit['barrier_sha256'] != auth['barrier_sha256'] or audit['execution_index_sha256'] != auth['execution_index_sha256']:
        raise ValueError('Audit lineage mismatch')
    contract_path = reference(binding['central_contract'])
    validation_path = reference(binding['validation'])
    contract, validation = read(contract_path), read(validation_path)
    if contract.get('is_template') is not False or contract.get('contract_status') != 'frozen' or contract['run_id'] != binding['unit_id']:
        raise PermissionError('Frozen actual evaluation contract required')
    vsha = validation.get('contract_sha256') or validation.get('launch_binding', {}).get('contract_sha256')
    if validation.get('valid_for_execution') is not True or vsha != binding['central_contract']['sha256']:
        raise PermissionError('Positive validation bound to exact evaluation contract required')
    if 'central_validation_path' in validation:
        central = read(checked(validation['central_validation_path'], validation['central_validation_sha256']))
        if central.get('valid_for_execution') is not True:
            raise PermissionError('Central validation rejected execution')
    timing = contract['timing']
    if cutoff > epoch(timing['effective_deadline_at']) or timing.get('prior_window_expired') is True or timing.get('retry_resets_clock') is not False:
        raise ValueError('Original contract clock cannot be reset/extended')
    command = [binding['python'], str(HERE / 'score_unit.py'), '--binding', str(binding_path)]
    if contract['execution']['command'] != command or int(contract['execution']['timeout_seconds']) != timeout:
        raise ValueError('Actual contract command/timeout differs from scoring unit')
    if contract['resources']['expected_hostname'] != HOST or not same_path(contract['environment']['environment_path'], sys.prefix):
        raise ValueError('Contract host/environment mismatch')
    resources = contract['resources']
    if int(resources.get('cpu_threads',0)) != 2 or int(resources.get('memory_limit_bytes',0)) != 4 * GIB or int(resources.get('gpu_memory_budget_bytes',0)) != 3 * GIB or resources.get('gpu_devices') != [GPU_UUID]:
        raise ValueError('Central scoring CPU/RSS/GPU budgets mismatch')
    receipt_root = path(binding['receipt_root']).resolve()
    if not receipt_root.is_relative_to(HERE.resolve()) or receipt_root == HERE.resolve():
        raise ValueError('Scoring unit receipts must stay inside owned launcher directory')
    code = binding['code_files']
    if not code or len({str(path(r['path']).resolve()) for r in code}) != len(code):
        raise ValueError('Missing/duplicate code proofs')
    code_paths = set()
    for ref in code:
        p = path(ref['path']).resolve()
        if p.suffix != '.py' and not (p.suffix == '.json' and p.name == 'vocabularies.json'):
            raise ValueError('Code proof cannot name gold, model checkpoints, or binary caches')
        code_paths.add(str(reference(ref).resolve()))
    required = [HERE / n for n in ('score_unit.py', 'score_pool.py', 'score_common.py')]
    required += [LAUNCH / n for n in ('common.py', 'pool_supervisor.py', 'run_unit.py')]
    required += [PROJECT / 'evaluation' / n for n in ('score_cached.py', 'common.py', 'feature_cache.py', 'metrics_stable.py')]
    if not {str(p.resolve()) for p in required} <= code_paths:
        raise ValueError('Incomplete launch/evaluation code proofs')
    eval_hashes = {p.name: sha(p) for p in required if p.parent == PROJECT / 'evaluation'}
    if auth['evaluation_code_sha256'] != eval_hashes or audit['evaluation_code_sha256'] != eval_hashes:
        raise ValueError('Evaluation code changed since authorization/full audit')
    specs = []
    if len(binding['score_specs']) != 3:
        raise ValueError('Each selection requires exactly three scoring specs')
    for ref in binding['score_specs']:
        if ref['sha256'] not in auth['allowed_score_spec_sha256']:
            raise PermissionError('Score spec absent from exact root authorization')
        spec = read(reference(ref))
        if not same_path(spec['output_root'], binding['score_root']) or not same_path(binding['score_root'], PROJECT / 'formal-runs-gpu-v4/scores'):
            raise ValueError('Unexpected scoring output root')
        if spec.get('device') != 'cuda:0' or spec.get('gpu_explicitly_authorized') is not True or int(spec.get('cpu_threads', 0)) != 2 or not 0 < int(spec.get('gpu_allocator_budget_bytes', 0)) <= 3 * GIB:
            raise ValueError('Scoring device/CPU/allocator budget mismatch')
        runner = path(spec['runner']).resolve()
        if str(runner) not in code_paths or sha(runner) != auth['runner_sha256']:
            raise ValueError('Original runner SHA not proved')
        method_root = path(spec['methods_root']) / METHOD_FOLDERS[spec['method_id']]
        if tree_hash(method_root) != spec['adapter_tree_sha256']:
            raise ValueError('Original method tree changed')
        if not {str(p.resolve()) for p in method_root.rglob('*.py') if '__pycache__' not in p.parts} <= code_paths:
            raise ValueError('Original method Python code proofs incomplete')
        vocab = method_root / 'vocabularies.json'
        if vocab.exists() and str(vocab.resolve()) not in code_paths:
            raise ValueError('Original method vocabulary not proved')
        specs.append(spec)
    if len({s['dataset_id'] for s in specs}) != 3:
        raise ValueError('Three distinct holdout datasets required')
    for spec in specs:
        if not re.fullmatch(r'[A-Za-z0-9_.-]+', spec['dataset_id']):
            raise ValueError('Unsafe dataset identity')
    selection_path = reference(binding['selection'])
    selection = read(selection_path)
    matches = [s for s in audit['selections'] if same_path(s['path'], selection_path) and s['sha256'] == binding['selection']['sha256']]
    if len(matches) != 1 or selection.get('status') != 'frozen' or selection.get('holdout_metrics_consulted') is not False:
        raise PermissionError('Selection is not one of the audited 200 frozen units')
    if selection['checkpoint_sha256'] != matches[0]['checkpoint_sha256']:
        raise ValueError('Selection checkpoint metadata differs from audit')
    ident = identity(selection)
    meta = contract['benchmark_metadata']
    if ident != (meta['method_id'], meta['split_id'], meta['regime_id'], int(meta['seed'])):
        raise ValueError('Evaluation contract identity differs from selection')
    if any(s['method_id'] != ident[0] or s.get('selection_split_id') not in (None, ident[1]) for s in specs):
        raise ValueError('Wrong method/panel score specs')
    if ident[0] not in METHOD_FOLDERS or ident[2] not in ('NC_only', 'standard_only') or not 0 <= ident[3] <= 9:
        raise ValueError('Not a registered five-method/two-regime/ten-seed coordinate')
    evaluation = contract['evaluation_stage']
    if evaluation['expected_score_receipts'] != 3 or not same_path(evaluation['score_root'], binding['score_root']):
        raise ValueError('Central evaluation count/output root mismatch')
    for contract_key, binding_key in [('selection','selection'), ('root_barrier','barrier'), ('root_barrier_audit','audit'), ('root_score_authorization','authorization')]:
        if evaluation[contract_key] != binding[binding_key]:
            raise ValueError('Central evaluation '+contract_key+' binding mismatch')
    datasets = evaluation['datasets']
    if len(datasets)!=3 or {d['role'] for d in datasets}!={'internal','external75','supplement13'}:
        raise ValueError('Central evaluation three dataset roles mismatch')
    expected_specs = {d['dataset_id']:d['score_spec'] for d in datasets}
    actual_specs = {s['dataset_id']:r for s,r in zip(specs,binding['score_specs'])}
    if expected_specs != actual_specs:
        raise ValueError('Central evaluation score-spec bindings differ')
    if sorted(evaluation['code_files'],key=lambda r:r['path']) != sorted(code,key=lambda r:r['path']):
        raise ValueError('Central evaluation code proofs differ from issued binding')
    return {'binding': binding, 'binding_path': binding_path, 'contract': contract,
            'selection': selection, 'specs': specs, 'deadline_epoch': cutoff,
            'unit_cutoff_epoch': min(cutoff, clock + timeout), 'identity': ident}


def score_outputs(context):
    binding, selection = context['binding'], context['selection']
    return [path(binding['score_root']) / spec['dataset_id'] / selection['split_id'] / selection['method_id'] / selection['regime'] / ('seed-' + str(selection['seed'])) for spec in context['specs']]


def validate_complete(receipt_root, binding_sha):
    root = path(receipt_root)
    receipt_path = checked(root / 'unit-complete.json', (root / 'unit-complete.sha256').read_text().strip())
    receipt = read(receipt_path)
    if receipt.get('status') != 'complete' or receipt['binding_sha256'] != binding_sha or len(receipt.get('scores', [])) != 3:
        raise ValueError('Completed score-unit lineage/count mismatch')
    for output in receipt['scores']:
        checked(output['complete_path'], output['complete_sha256'])
    for item in receipt['artifacts']:
        checked(item['path'], item['sha256'])
    exit_path = checked(root / 'pool-exit-verification.json', (root / 'pool-exit-verification.sha256').read_text().strip())
    exit_proof = read(exit_path)
    if exit_proof.get('exit_code') != 0 or exit_proof.get('private_session_handles_absent') is not True or exit_proof.get('binding_sha256') != binding_sha:
        raise ValueError('Actual pool exit verification absent/mismatched')
    for key in ('stdout', 'stderr'):
        checked(exit_proof[key+'_path'], exit_proof[key+'_sha256'])
    return receipt
