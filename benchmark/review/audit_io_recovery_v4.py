"""Metadata-only independent audit. Run in WSL; never open model/gold/predictions."""
import hashlib
import itertools
import json
from datetime import datetime, timezone
from pathlib import Path

P = Path('/mnt/d/work/科研工作台/research-tasks/peptide-binding-nc-benchmark-20261021')
checks = []


def read(rel):
    return json.loads((P / rel).read_text(encoding='utf-8-sig'))


def sha(rel):
    return hashlib.sha256((P / rel).read_bytes()).hexdigest()


def check(name, condition, detail=None):
    checks.append({'check': name, 'passed': bool(condition), 'detail': detail})


def delta(a, b, prefix=''):
    if type(a) is not type(b):
        return [prefix]
    if isinstance(a, dict):
        result = []
        for key in sorted(set(a) | set(b)):
            path = f'{prefix}.{key}' if prefix else key
            result.extend([path] if key not in a or key not in b else delta(a[key], b[key], path))
        return result
    return [] if a == b else [prefix]


def coord(u):
    return u['method_id'], u['split_id'], u['regime_id'], u['seed']


def local(path):
    text = path.replace('\\', '/')
    if text.startswith('D:/'):
        text = '/mnt/d/' + text[3:]
    return Path(text)


old_id = 'MGraphDTA__target_reference_homology_cold__NC_only__seed08'
new_id = old_id + '__io_recovery01'
old_spec = f'control/gpu-fit-specs-v4/{old_id}.json'
new_spec = f'administration/io-recovery01/{new_id}.fit-spec.json'
index_path = 'administration/io-recovery01/execution-index-v5-recovery.json'
freeze_path = 'administration/io-recovery01/eligible-training-freeze-index-v5.json'
pool_path = 'control/unit-index-v5-all-recovery.json'
expected_sha = {
    index_path: 'c7b3bde68c9a741c0ac3f255a825e4a55dd7234e2b4e6d48f212fee8d5609ab1',
    freeze_path: '81e3ab0226a94cd27238be75ca6e8b26f08b7496f08b9e52e456e67cd580864f',
    pool_path: 'fe51a0d03f4f9c08e710e9d8b582d56c497d8c59dc5d14e8cbc6e6d8b41e51d2',
    old_spec: 'ca9d1bf2e92647e6585660cc368b139eb9d532182540a01160a554683744a572',
    new_spec: '28f86c0e59cb45fad9e35eee82ffa219ca77cd8f48feb3a2468e819c33fa17e3',
    'execution/runner.py': '9abe4a9fba5840a6200aecf40fdfb436abbf61d78c3a9a2f28baae7712c6913e',
}
for file, expected in expected_sha.items():
    check('sha256:' + file, sha(file) == expected)
old, new = read(old_spec), read(new_spec)
changes = delta(old, new)
check('only_two_output_path_spec_deltas', changes == ['launch_proof.receipt_root', 'run_root'], changes)
old_index = read('control/gpu-fit-specs-v4/execution-index.json')
index, freeze, pool = read(index_path), read(freeze_path), read(pool_path)
old_units = {coord(u): u for u in old_index['units']}
units = {coord(u): u for u in index['units']}
expected_coords = set(itertools.product(
    ['GraphDTA-GIN', 'MGraphDTA', 'DGDTA-CL', 'DeepNC-GEN', 'GS-DTA'],
    ['source_peptide_dependency_cold', 'target_reference_homology_cold'],
    ['NC_only', 'standard_only'], range(10)))
# Preserve concrete frozen method spellings while verifying the full rectangular grid.
actual_methods = sorted({c[0] for c in units})
grid = set(itertools.product(actual_methods,
    ['source_peptide_dependency_cold', 'target_reference_homology_cold'],
    ['NC_only', 'standard_only'], range(10)))
check('200_unique_complete_scientific_coordinates', len(index['units']) == len(units) == 200 and len(actual_methods) == 5 and set(units) == grid,
      {'methods': actual_methods, 'count': len(units)})
changed_units = [c for c in units if units[c] != old_units.get(c)]
check('exactly_one_scientific_index_replacement', changed_units == [('MGraphDTA', 'target_reference_homology_cold', 'NC_only', 8)], changed_units)
check('199_unit_metadata_unchanged', sum(units[c] == old_units.get(c) for c in units) == 199)
check('recovery_same_coordinate_new_attempt_id', units[changed_units[0]]['unit_id'] == new_id)
records = freeze['records']
check('freeze_index_200_unique_matching_coordinates', len(records) == 200 and len({coord(r) for r in records}) == 200 and {coord(r) for r in records} == set(units))
check('freeze_all_records_valid_frozen', all(r['valid_for_execution'] and r['frozen'] for r in records))
check('old_failed_slot_preserved_but_not_eligible', freeze['superseded_failed_record']['run_id'] == old_id and old_id not in {r['run_id'] for r in records} and new_id in {r['run_id'] for r in records})
check('pool_200_unique_attempt_ids', len(pool['units']) == 200 and len({u['unit_id'] for u in pool['units']}) == 200)
check('pool_scientific_index_same_attempt_ids', {u['unit_id'] for u in pool['units']} == {u['unit_id'] for u in index['units']})
recovery_unit = next(u for u in pool['units'] if u['unit_id'] == new_id)
binding = json.loads(local(recovery_unit['unit_binding']).read_text())
contract = json.loads(local(recovery_unit['contract']).read_text())
meta = contract['recovery_metadata']
deadline = '2026-10-21T20:09:02.438325+00:00'
check('same_original_absolute_unit_deadline', binding['deadline'] == meta['original_absolute_unit_deadline'] == pool['recovery_issuance']['original_unit_absolute_deadline'] == deadline)
check('bounded_recovery_timeout_no_clock_reset', meta['new_unit_timeout_seconds'] <= 1200 and meta['first_scope_clock_unchanged'] is True)
check('global_deadline_unchanged', pool['deadline'] == meta['original_global_effective_deadline'] == '2026-10-22T01:45:00+00:00')
for field in ('spec', 'contract', 'validation', 'unit_binding'):
    check('pool_metadata_binding_sha:' + field, hashlib.sha256(local(recovery_unit[field]).read_bytes()).hexdigest() == recovery_unit[field + '_sha256'])
terminal_rel = f'control/recovery-diagnosis-v1/{old_id}.terminal.json'
terminal = read(terminal_rel)
check('old_failure_retained_minus15', terminal.get('exit_code') == -15 and terminal.get('status') == 'failed')
original_terminal = read(f'launch/pool-runs-v4-nc-all-seeds/{old_id}.terminal.json')
check('archived_terminal_identical', terminal == original_terminal)
proof = read('administration/io-recovery01/recovery-source-proof.json')
inventory = proof['interrupted_output_inventory_stat_only']
check('accounting_400_valid_configs_200_cells_plus1_interruption', index['total_fits'] == 400 and index['total_selections'] == 200 and index['attempt_accounting']['additional_retained_interrupted_attempts'] == 1)
report = {
    'schema': 'independent-io-recovery-metadata-review-v4',
    'created_at': datetime.now(timezone.utc).isoformat(),
    'scope': 'Static metadata/source bytes only, through WSL Python. No test/external gold, predictions, checkpoints or validation scores read.',
    'status': 'passed' if all(c['passed'] for c in checks) else 'failed',
    'checks': checks,
    'checks_count': len(checks),
    'interrupted_inventory_policy': 'Declared stat inventory retained; inventory model/prediction/metric file payloads were not opened.',
    'causal_scope': 'Windows default read sharing reproduces the exception type; attribution of the original event remains moderate because exact filename and stack were not captured.',
    'counting': {'expected_valid_candidate_fits': 400, 'scientific_cells': 200, 'additional_interrupted_attempts': 1, 'completed_performance_runs_claimed_by_this_review': 0},
    'no_holdout_access': True,
}
out = P / 'review/io-recovery-independent-metadata-review-v4.json'
out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status': report['status'], 'checks': len(checks), 'failures': [c for c in checks if not c['passed']], 'report': str(out)}, ensure_ascii=False))
raise SystemExit(0 if report['status'] == 'passed' else 1)
