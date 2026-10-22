"""Pure synthetic authorization gates; no actual benchmark assets are read."""
import importlib.util
import copy
import itertools
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

source = Path(__file__).with_name('joint_audit_gate_v4.py')
spec = importlib.util.spec_from_file_location('joint_gate_synthetic_only', source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
cases = []


def rejected(name, auth, error, joint=None):
    calls = []
    def read(path):
        calls.append(str(path))
        if str(path) == 'synthetic-auth':
            return auth
        if str(path) == 'synthetic-joint':
            return joint
        raise AssertionError('Unexpected input access before rejection: ' + str(path))
    with patch.object(module, 'read', read), patch.object(module, 'require', lambda *a: None):
        try:
            module.require_joint('synthetic-auth', 'synthetic-joint', 'nn')
        except error:
            cases.append({'case': name, 'passed': True, 'read_paths': calls})
        else:
            raise AssertionError('Expected rejection: ' + name)


rejected('unauthorized_no_joint_read', {'root_joint_real_audit_authorized': False}, PermissionError)
rejected('mode_not_authorized_no_joint_read', {'root_joint_real_audit_authorized': True, 'allowed_modes': []}, PermissionError)
valid = {'root_joint_real_audit_authorized': True, 'allowed_modes': ['nn'], 'deadline_unix': 10**12,
         'outer_gate_sha256': 'synthetic', 'allowed_target_sha256': {'nn': 'synthetic'}, 'joint_barrier_sha256': 'synthetic'}
rejected('expired_no_joint_read', dict(valid, deadline_unix=0), TimeoutError)
rejected('NN_only_is_not_joint', valid, ValueError, {'status': 'all_selections_frozen', 'NN_selections': 200, 'RF_selections': 0})
rejected('wrong_recovery_identity', valid, ValueError, {'status': 'all_200_NN_plus_40_RF_frozen', 'NN_selections': 200, 'RF_selections': 40, 'NN_execution_index_sha256': 'wrong'})
if any(c['read_paths'] != ['synthetic-auth'] for c in cases[:3]):
    raise AssertionError('Early auth rejection read extra files')

# Full structural fixtures are synthetic metadata, with no real selection read.
nn_entries, rf_entries, mapping = [], [], {'synthetic-auth': valid}
for i, (method, panel, regime, seed) in enumerate(itertools.product(module.METHODS, module.PANELS, module.REGIMES, range(10))):
    path = 'SYNTHETIC-NN-' + str(i)
    nn_entries.append({'path': path, 'sha256': 'synthetic'})
    mapping[path] = {'method_id': method, 'split_id': panel, 'regime': regime, 'seed': seed,
                     'status': 'frozen', 'holdout_metrics_consulted': False}
for i, (panel, regime, seed) in enumerate(itertools.product(module.PANELS, module.REGIMES, range(10))):
    path = 'SYNTHETIC-RF-' + str(i)
    rf_entries.append({'selection_path': path, 'selection_sha256': 'synthetic', 'panel': panel, 'regime': regime, 'seed': seed})
    mapping[path] = {'panel': panel, 'regime': regime, 'seed': seed, 'status': 'frozen', 'validation_only': True, 'gold_reads': 0}
mapping['synthetic-joint'] = {'status': 'all_200_NN_plus_40_RF_frozen', 'NN_selections': 200, 'RF_selections': 40,
    'NN_execution_index_sha256': module.INDEX_SHA, 'NN_execution_index_path': 'synthetic-index',
    'NN_barrier_path': 'synthetic-NN-barrier', 'NN_barrier_sha256': 'synthetic',
    'RF_barrier_path': 'synthetic-RF-barrier', 'RF_barrier_sha256': 'synthetic', 'RF_selection_entries': rf_entries}
mapping['synthetic-index'] = {'per_seed_selections': [{'selection_path': x['path']} for x in nn_entries]}
mapping['synthetic-NN-barrier'] = {'status': 'all_selections_frozen', 'selection_count': 200, 'candidate_fit_count': 400,
    'execution_index_sha256': module.INDEX_SHA, 'selections': nn_entries}
mapping['synthetic-RF-barrier'] = {'status': 'all_40_RF_selections_frozen', 'selection_count': 40, 'candidate_fit_count': 80, 'selections': rf_entries}
with patch.object(module, 'read', lambda p: mapping[str(p)]), patch.object(module, 'require', lambda *a: None):
    module.require_joint('synthetic-auth', 'synthetic-joint', 'nn')
    cases.append({'case': 'synthetic_full200plus40_accepted', 'passed': True, 'real_reads': False})
for name, victim in [('duplicate_NN_grid_rejected', 'SYNTHETIC-NN-1'), ('duplicate_RF_grid_rejected', 'SYNTHETIC-RF-1')]:
    altered = copy.deepcopy(mapping)
    replacement = 'SYNTHETIC-NN-0' if 'NN' in name else 'SYNTHETIC-RF-0'
    altered[victim] = copy.deepcopy(altered[replacement])
    with patch.object(module, 'read', lambda p: altered[str(p)]), patch.object(module, 'require', lambda *a: None):
        try:
            module.require_joint('synthetic-auth', 'synthetic-joint', 'nn')
        except ValueError:
            cases.append({'case': name, 'passed': True, 'real_reads': False})
        else:
            raise AssertionError('Repeated coordinates were accepted')
result = {'schema': 'joint-audit-outer-gate-synthetic-verification-v4', 'passed': len(cases), 'cases': cases,
          'real_training_labels_gold_predictions_weights_read': False, 'actual_audit_or_reference_runs': 0}
Path(__file__).with_name('joint-gate-synthetic-verification-v4.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result))
