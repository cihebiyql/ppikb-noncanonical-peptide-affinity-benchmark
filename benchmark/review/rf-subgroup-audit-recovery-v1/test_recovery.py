"""Synthetic-only checks for missing optional subgroup metadata assembly."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).parent; REVIEW = HERE.parent
spec = importlib.util.spec_from_file_location('RF_subgroup_v6_synthetic', HERE / 'recompute_RF_v6.py')
r = importlib.util.module_from_spec(spec); spec.loader.exec_module(r)
cases = []


def check(name, condition):
    if not condition: raise AssertionError(name)
    cases.append({'case': name, 'passed': True})


def reject(name, callback):
    try: callback()
    except ValueError: check(name, True)
    else: raise AssertionError('Expected rejection: ' + name)


rows = [dict(record_id='SYNTHETIC-' + str(i), NC_core=i < 8,
             evaluation_stratum='synthetic_D_backbone' if i < 8 else 'standard20_control') for i in range(13)]
ids = {'external_supplement_NC': [x['record_id'] for x in rows[:8]], 'external_supplement_standard': [x['record_id'] for x in rows[8:]]}
original = copy.deepcopy(rows); private = copy.deepcopy(rows)
r.attach_frozen_subgroups(private, 'supplement13', ids)
check('missing_supplement_flags_derived_from_frozen_IDs', sum(x['external_supplement_NC'] for x in private) == 8 and sum(x['external_supplement_standard'] for x in private) == 5)
check('source_metadata_not_changed_by_private_assembly', rows == original and all('external_supplement_NC' not in x for x in rows))
before = copy.deepcopy(private); r.attach_frozen_subgroups(private, 'supplement13', ids)
check('existing_correct_flags_preserved_idempotently', private == before)
bad = copy.deepcopy(private); bad[0]['external_supplement_NC'] = False
reject('existing_wrong_flag_never_overwritten', lambda: r.attach_frozen_subgroups(bad, 'supplement13', ids))
bad = copy.deepcopy(private); bad[0]['external_supplement_NC'] = None
reject('existing_null_flag_not_silently_imputed', lambda: r.attach_frozen_subgroups(bad, 'supplement13', ids))
bad = copy.deepcopy(private); bad[0]['external_supplement_NC'] = 1
reject('integer_flag_not_accepted_as_boolean', lambda: r.attach_frozen_subgroups(bad, 'supplement13', ids))
bad = copy.deepcopy(rows); bad[0]['NC_core'] = False
reject('frozen_NC_metadata_disagreement_still_rejected', lambda: r.attach_frozen_subgroups(bad, 'supplement13', ids))
badids = copy.deepcopy(ids); badids['external_supplement_NC'][0] = 'OUTSIDE'
reject('frozen_ID_outside_cohort_rejected', lambda: r.attach_frozen_subgroups(copy.deepcopy(rows), 'supplement13', badids))
ext = [dict(record_id='SYNTHETIC-'+str(i), NC_core=True, evaluation_stratum='PTM') for i in range(75)]
sets = {'external_primary': [x['record_id'] for x in ext[:67]], 'external_conditional_sensitivity': [x['record_id'] for x in ext[67:]], 'external_reference_target_cold': [x['record_id'] for x in ext[:2]]}
r.attach_frozen_subgroups(ext, 'external75', sets)
check('external67_8_2_exact_definition_retained', [sum(x[k] for x in ext) for k in sets] == [67, 8, 2])
bad = copy.deepcopy(ext); bad[0]['external_primary'] = False
reject('external_existing_mapping_conflict_rejected', lambda: r.attach_frozen_subgroups(bad, 'external75', sets))
old = (REVIEW / 'recompute_RF_v5.py').read_text(); new = (HERE / 'recompute_RF_v6.py').read_text()
functions = lambda text: {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(text).body if isinstance(n, ast.FunctionDef)}
of, nf = functions(old), functions(new)
changed = sorted(n for n in of if of[n] != nf[n])
check('only_subgroup_assembly_and_two_path_dependent_functions_changed', changed == ['attach_frozen_subgroups', 'authorize', 'numeric_helper'])
check('true_join_blind_SHA_metrics_tables_unchanged', all(of[n] == nf[n] for n in ('validate_blind', 'validate_rows', 'compute_rows', 'metric_differences', 'audit_task', 'subgroups', 'table_rows', 'summarize_table', 'main')))
check('project_helper_paths_point_to_original_review_root', r.P == REVIEW.parent and r.numeric_helper().__file__ == str(REVIEW / 'recompute_metrics.py'))
check('numeric_helper_SHA_unchanged', hashlib.sha256((REVIEW / 'recompute_metrics.py').read_bytes()).hexdigest() == r.HELPER_SHA)
check('old_RFv5_SHA_unchanged', hashlib.sha256((REVIEW / 'recompute_RF_v5.py').read_bytes()).hexdigest() == '9d6f1e67d6a08c45316014729ffc850e1d59bd6ab3da1c989bcb4280e731e905')
report = dict(schema='RF-subgroup-audit-recovery-mechanics.v1', status='passed', passed_cases=len(cases), cases=cases,
    changed_functions=changed, actual_gold_prediction_model_matrix_or_label_reads=False, actual_RF_audit_or_score_runs=0,
    numeric_helper_sha256=r.HELPER_SHA, new_script_sha256=hashlib.sha256((HERE / 'recompute_RF_v6.py').read_bytes()).hexdigest())
(HERE / 'mechanical-verification.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'status': 'passed', 'cases': len(cases)}))
