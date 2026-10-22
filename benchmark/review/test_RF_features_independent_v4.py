"""Independent synthetic-only feature checks, no train/holdout/model inputs."""
import hashlib
import importlib.util
import json
from pathlib import Path
import numpy as np

P = Path('/mnt/d/work/科研工作台/research-tasks/peptide-binding-nc-benchmark-20261021')
source = P / 'auxiliary-rf-baseline/features.py'
assert hashlib.sha256(source.read_bytes()).hexdigest() == 'f346de665d3ed60f5664d14918c62451a63b2ec1b9fc41de2f1b97bbb278cabf'
spec = importlib.util.spec_from_file_location('synthetic_RF_features_only', source)
feature = importlib.util.module_from_spec(spec)
spec.loader.exec_module(feature)
cases = []


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    cases.append({'case': name, 'passed': True})


def encode(target, smiles='NCC(=O)O'):
    return feature.encode_record({'record_id': 'SYNTHETIC_ONLY', 'peptide_smiles': smiles, 'target_sequence': target})


x, a = encode('ACXCA')
check('dimensions_dtype_finite', x.shape == (2469,) and x.dtype == np.float32 and np.isfinite(x).all())
expected = np.zeros(20); expected[0] = expected[1] = .4
check('AAC_includes_unknown_in_denominator', np.allclose(x[2048:2068], expected))
expected = np.zeros(400); expected[1] = expected[20] = .25
check('dipeptide_keeps_unknown_position_breaks_pairs', np.allclose(x[2068:2468], expected))
check('raw_effective_length_and_unknown_audit', x[2468] == 5 and a['prefix_unknown_count'] == 1 and a['prefix_unknown_characters'] == ['X'])
x, a = encode('A')
check('one_aa_DP_zero', x[2048] == 1 and not x[2068:2468].any() and x[2468] == 1)
x, a = encode('A' * 1000 + 'C' * 19)
check('prefix1000_raw_effective_length', x[2048] == 1 and x[2049] == 0 and x[2468] == 1000 and a['full_reference_length'] == 1019 and a['reference_truncated'] is True)
x, a = encode('aX')
check('unknown_lowercase_not_uppercased_imputed', not x[2048:2468].any() and x[2468] == 2 and a['prefix_unknown_count'] == 2)
left, la = encode('AA', 'N[C@@H](C)C(=O)O')
right, ra = encode('AA', 'N[C@H](C)C(=O)O')
check('supplied_stereochemistry_distinguishable_for_synthetic_pair', not np.array_equal(left[:2048], right[:2048]) and la['specified_chiral_atoms'] == ra['specified_chiral_atoms'] == 1)
_, a = encode('AA', 'NC(C)C(=O)O')
check('unspecified_stereo_not_inferred', a['specified_chiral_atoms'] == 0 and a['inferred_stereochemistry'] is False)
_, a = encode('AA', 'NCC(=O)O.[Na+]')
check('all_fragments_retained', a['molecule_fragments'] == 2 and a['molecule_atoms'] == 6 and a['all_fragments_retained'] is True)
_, a = encode('AA', '[H]NCC(=O)O')
check('explicit_hydrogen_retained', a['molecule_atoms'] == 6)
try:
    encode('')
except ValueError:
    check('empty_protein_rejected', True)
else:
    raise AssertionError('Empty target not rejected')
report = {'schema': 'independent-RF-feature-synthetic-review-v4', 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
          'passed': len(cases), 'cases': cases, 'real_data_rows_or_models_read': False,
          'RF_fits': 0, 'feature_scope': 'Only newly constructed generic small molecules and synthetic amino-acid strings.'}
(P / 'review/RF-feature-synthetic-verification-v4.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
print(json.dumps(report))
