"""Independent RF audit/combiner synthetic fixtures; no benchmark truth read."""
import copy
import hashlib
import importlib.util
import itertools
import json
import math
from pathlib import Path
import tempfile
from unittest.mock import patch

HERE = Path(__file__).parent


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


rf = load('synthetic_RF_audit_v5', 'recompute_RF_v5.py')
combine = load('synthetic_combine_v5', 'combine_audit_tables_v5.py')
h = rf.numeric_helper()
cases = []


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    cases.append({'case': name, 'passed': True})


def reject(name, function, expected=ValueError):
    try:
        function()
    except expected:
        cases.append({'case': name, 'passed': True})
    else:
        raise AssertionError('Expected rejection: ' + name)


def fixture(n=4):
    inputs, blind, pred, gold = [], [], [], []
    for i in range(n):
        nc = i % 2 == 0
        row = dict(record_id='SYNTHETIC-' + str(i), target_sequence='AC' if i % 4 < 2 else 'CA',
                   peptide_smiles='NCC(=O)O', NC_core=nc,
                   evaluation_stratum='synthetic_D_backbone' if nc else 'standard20_control',
                   chemical_entity_id='SYNTHETIC_CHEM' + str(i), target_id='T' + str(i % 2),
                   study_id='SYNTHETIC_STUDY' + str(i % 2), residue_class_graph_discordance=False,
                   retained_unrelated_metadata={'synthetic': True, 'index': i})
        value, truth = 2.0 + i, 1.0 + i
        b = {k: v for k, v in row.items() if k not in rf.RAW_EXCLUDED}
        b['pKd_pred'] = value
        inputs.append(row); blind.append(b); gold.append({'record_id': row['record_id'], 'pKd': truth})
        pred.append(dict(b, pKd_true=truth, residual=value - truth))
    proof = dict(status='RF_blind_saved_before_gold_access', gold_reads=0, n=n)
    receipt = {'n': n}
    return inputs, blind, pred, gold, proof, receipt


base = fixture()
rows = rf.validate_rows(*base)
check('valid_exact_record_join_and_reference_sha', len(rows) == 4 and rows[0]['target_reference_sequence_sha'] == hashlib.sha256(b'AC').hexdigest())
bad = copy.deepcopy(base); bad[1][0].pop('retained_unrelated_metadata')
reject('blind_dropped_metadata_rejected', lambda: rf.validate_rows(*bad))
bad = copy.deepcopy(base); bad[1][0]['pKd'] = 1
reject('gold_in_blind_rejected', lambda: rf.validate_rows(*bad))
bad = copy.deepcopy(base); bad[0].append(copy.deepcopy(bad[0][0]))
reject('duplicate_input_ID_rejected', lambda: rf.validate_rows(*bad))
bad = copy.deepcopy(base); bad[2][0]['pKd_pred'] += .1
reject('prediction_changed_on_gold_join_rejected', lambda: rf.validate_rows(*bad))
bad = copy.deepcopy(base); bad[2][0]['pKd_true'] += .1
reject('saved_truth_differs_from_gold_rejected', lambda: rf.validate_rows(*bad))
bad = copy.deepcopy(base); bad[2][0]['residual'] = 99
reject('residual_mapping_rejected', lambda: rf.validate_rows(*bad))
bad = copy.deepcopy(base); bad[3].pop()
reject('missing_frozen_gold_ID_rejected', lambda: rf.validate_rows(*bad))
bad = copy.deepcopy(base); bad[4]['gold_reads'] = 1
reject('blind_proof_gold_reads_rejected', lambda: rf.validate_rows(*bad))
bad = copy.deepcopy(base); bad[0][0]['NC_core'] = 1
reject('boolean_NC_status_required', lambda: rf.validate_rows(*bad))
bad = copy.deepcopy(base)
for part in (bad[0], bad[1], bad[2]):
    part[0]['evaluation_stratum'] = 'standard20_control'
reject('NC_standard_stratum_inconsistency_rejected', lambda: rf.validate_rows(*bad))
bad = copy.deepcopy(base); bad[1][0]['pKd_pred'] = float('inf'); bad[2][0]['pKd_pred'] = float('inf')
reject('nonfinite_prediction_rejected', lambda: rf.validate_rows(*bad))

# Construct exactly75 generic synthetic rows with the frozen subgroup sizes.
external = rf.validate_rows(*fixture(75))
sets75 = {'external_primary': [r['record_id'] for r in external[:67]],
          'external_conditional_sensitivity': [r['record_id'] for r in external[67:]],
          'external_reference_target_cold': [r['record_id'] for r in external[:2]]}
for row in external:
    row.update(NC_core=True, evaluation_stratum='PTM')
    row.update({k: row['record_id'] in ids for k, ids in sets75.items()})
rf.attach_frozen_subgroups(external, 'external75', sets75)
groups75, macros75 = rf.compute_rows(external, 'external75', h)
check('external67_8_2_separate_metrics', [groups75[k]['n'] for k in ('external_primary67', 'external_conditional_sensitivity8', 'external_reference_target_cold2')] == [67, 8, 2])
check('all_five_strata_emitted_with_empty_nulls', all(k in groups75 for k in rf.STRATA) and groups75['synthetic_D_backbone']['n'] == 0 and groups75['synthetic_D_backbone']['MAE'] is None)
bad = copy.deepcopy(external); bad[0]['external_primary'] = False
reject('frozen_external_flag_change_rejected', lambda: rf.attach_frozen_subgroups(bad, 'external75', sets75))
badsets = copy.deepcopy(sets75); badsets['external_reference_target_cold'] = sets75['external_conditional_sensitivity'][:2]
bad = copy.deepcopy(external)
for row in bad:
    row['external_reference_target_cold'] = row['record_id'] in badsets['external_reference_target_cold']
reject('cold2_outside_primary_rejected', lambda: rf.attach_frozen_subgroups(bad, 'external75', badsets))
supp = rf.validate_rows(*fixture(13))
sets13 = {'external_supplement_NC': [r['record_id'] for r in supp[:8]], 'external_supplement_standard': [r['record_id'] for r in supp[8:]]}
for i, row in enumerate(supp):
    row.update(NC_core=i < 8, evaluation_stratum='synthetic_D_backbone' if i < 8 else 'standard20_control')
    row.update({k: row['record_id'] in ids for k, ids in sets13.items()})
rf.attach_frozen_subgroups(supp, 'supplement13', sets13)
groups13, _ = rf.compute_rows(supp, 'supplement13', h)
check('supplement8_5_separate_from75', [groups13[k]['n'] for k in ('supplement_NC8', 'supplement_standard5')] == [8, 5] and 'external_primary67' not in groups13)
bad = copy.deepcopy(supp); bad[0]['evaluation_stratum'] = 'PTM'
reject('supplement_chemistry_change_rejected', lambda: rf.attach_frozen_subgroups(bad, 'supplement13', sets13))

m = h.metrics([1, 2, 4, 8], [2, 2, 3, 7])
check('numeric_MAE_RMSE_R2_independent_hand_calculation', math.isclose(m['MAE'], .75) and math.isclose(m['RMSE'], math.sqrt(.75)) and math.isclose(m['R2'], 1 - 3 / 28.75))
constant = h.metrics([.1] * 3, [.1] * 3)
check('decimal_constant_correlations_R2_null', all(constant[k] is None for k in ('Pearson', 'Spearman', 'R2')) and constant['MAE'] == constant['RMSE'] == 0)
check('tie_rank_Spearman', math.isclose(h.metrics([1, 1, 3], [1, 3, 2])['Spearman'], 0))
check('negative_R2_kept', h.metrics([1, 2, 3], [10, 10, 10])['R2'] < 0)
macro_rows = [dict(rows[0], pKd_true=0, pKd_pred=0, target_id='A'), dict(rows[0], pKd_true=0, pKd_pred=0, target_id='A'), dict(rows[0], pKd_true=0, pKd_pred=9, target_id='B')]
macro = h.macro_metrics(macro_rows, 'target_id')
check('macro_and_row_weighted_not_confused', macro['macro_mean']['MAE'] == 4.5 and macro['row_weighted_MAE'] == 3 and math.isclose(macro['row_weighted_RMSE'], math.sqrt(27)))
check('constant_target_groups_defined_counts', macro['defined_group_counts']['R2'] == 0 and macro['macro_mean']['R2'] is None)
sens = copy.deepcopy(rows)
sens[0].update(pKd_pred=sens[0]['pKd_true'] + 99, residue_class_graph_discordance=True)
groups, macros = rf.compute_rows(sens, 'source_test', h)
check('NC_608_flag_sensitivity_excludes_without_retraining', groups['NC_core']['n'] == 2 and groups['NC_core_exclude_discordant_sensitivity']['n'] == 1 and groups['NC_core']['MAE'] == 50 and groups['NC_core_exclude_discordant_sensitivity']['MAE'] == 1)
check('NC_and_standard_target_source_macros_separate', set(macros) == {'NC_core', 'standard', 'all_diagnostic'} and set(macros['NC_core']) == {'target_id', 'target_reference_sequence_sha', 'study_id'})
check('study_macros_expose_machine_source_refs', macros['NC_core']['study_id']['source_refs'] == ['SYNTHETIC_STUDY0'] and 'not independently' in macros['NC_core']['study_id']['source_ref_scope'])
saved = {k: groups[k] for k in ('all', 'NC_core', 'standard')}
check('saved_metric_exact_match', not rf.metric_differences(saved, groups))
bad = copy.deepcopy(saved); bad['NC_core']['MAE'] += 1
check('saved_metric_discrepancy_detected', len(rf.metric_differences(bad, groups)) == 1)

# Exercise the actual file-bound RF audit path using synthetic files only.
with tempfile.TemporaryDirectory(prefix='synthetic_RF_receipt_') as folder:
    tmp = Path(folder); synthetic_R = tmp / 'RF_assets'; synthetic_R.mkdir()
    (synthetic_R / 'SOURCE-FREEZE-v1.json').write_text(json.dumps({'source_sha256': {}}))
    f = list(fixture(75))
    for i, row in enumerate(f[0]):
        row.update(NC_core=True, evaluation_stratum='PTM')
        row.update({k: row['record_id'] in ids for k, ids in sets75.items()})
    f[1] = [dict({k: v for k, v in row.items() if k not in rf.RAW_EXCLUDED}, pKd_pred=2.0 + i) for i, row in enumerate(f[0])]
    f[2] = [dict(row, pKd_true=f[3][i]['pKd'], residual=row['pKd_pred'] - f[3][i]['pKd']) for i, row in enumerate(f[1])]
    def jlines(path, values):
        path.write_text(''.join(json.dumps(v) + '\n' for v in values))
    for name, values in (('inputs.jsonl', f[0]), ('blind-predictions.jsonl', f[1]), ('predictions.jsonl', f[2]), ('gold.jsonl', f[3])):
        jlines(tmp / name, values)
    proof = dict(f[4], blind_sha256=rf.sha(tmp / 'blind-predictions.jsonl'))
    (tmp / 'blind-complete.json').write_text(json.dumps(proof))
    score_spec = dict(panel=rf.PANELS[0], dataset_id='external75', input_rows=str(tmp / 'inputs.jsonl'), input_rows_sha256=rf.sha(tmp / 'inputs.jsonl'),
                      gold_rows=str(tmp / 'gold.jsonl'), gold_rows_sha256=rf.sha(tmp / 'gold.jsonl'), feature_manifest_sha256='SYNTHETIC_FEATURE_SHA')
    (tmp / 'score-spec.json').write_text(json.dumps(score_spec))
    computed = rf.compute_rows(rf.validate_rows(*f), 'external75', h)[0]
    receipt = dict(status='complete', stage='additional_classical_RF_post_joint_barrier_score', method_id=rf.METHOD,
                   joint_barrier_sha256='SYNTHETIC_JOINT', selection_sha256='SYNTHETIC_SELECTION', panel=rf.PANELS[0], regime='NC_only', seed=0,
                   selected_model_sha256='SYNTHETIC_MODEL_DECLARATION_NO_PAYLOAD', score_spec_sha256=rf.sha(tmp / 'score-spec.json'),
                   dataset_id='external75', holdout_id='external75', n=75, parameter_updates=0, blind_before_gold=True, paper_count_contribution=0,
                   feature_manifest_sha256='SYNTHETIC_FEATURE_SHA', gold_source_sha256=score_spec['gold_rows_sha256'], source_sha256={},
                   blind_predictions_sha256=rf.sha(tmp / 'blind-predictions.jsonl'), predictions_sha256=rf.sha(tmp / 'predictions.jsonl'),
                   metrics={k: computed[k] for k in ('all', 'NC_core', 'standard')})
    (tmp / 'complete.json').write_text(json.dumps(receipt))
    task = {'score_receipt': str(tmp / 'complete.json'), 'holdout_spec': str(tmp / 'score-spec.json')}
    selections = {'SYNTHETIC_SELECTION': {'key': (rf.PANELS[0], 'NC_only', 0), 'model_sha256': receipt['selected_model_sha256']}}
    frozen_specs = {receipt['score_spec_sha256']: score_spec}
    original_read, original_lines = rf.read, rf.lines
    accesses = []
    def tracked_read(path):
        accesses.append(('json', Path(path).name)); return original_read(path)
    def tracked_lines(path):
        accesses.append(('jsonl', Path(path).name)); return original_lines(path)
    with patch.object(rf, 'R', synthetic_R), patch.object(rf, 'subgroups', lambda _: sets75), patch.object(rf, 'read', tracked_read), patch.object(rf, 'lines', tracked_lines):
        actual = rf.audit_task(task, selections, 'SYNTHETIC_JOINT', frozen_specs, h, None)
    check('synthetic_full_file_RF_receipt_audit', actual['n'] == 75 and actual['blind_before_gold_proof_verified'] and actual['all_truths_match_frozen_gold'] and not actual['runner_metric_differences'])
    check('audit_reads_blind_proof_and_blind_before_gold', accesses.index(('json', 'blind-complete.json')) < accesses.index(('jsonl', 'blind-predictions.jsonl')) < accesses.index(('jsonl', 'gold.jsonl')))
    proof['gold_reads'] = 1; (tmp / 'blind-complete.json').write_text(json.dumps(proof)); accesses.clear()
    with patch.object(rf, 'R', synthetic_R), patch.object(rf, 'subgroups', lambda _: sets75), patch.object(rf, 'read', tracked_read), patch.object(rf, 'lines', tracked_lines):
        reject('bad_blind_proof_rejected_before_gold_read', lambda: rf.audit_task(task, selections, 'SYNTHETIC_JOINT', frozen_specs, h, None))
    check('invalid_proof_no_sealed_gold_access', ('jsonl', 'gold.jsonl') not in accesses)
    proof['gold_reads'] = 0; (tmp / 'blind-complete.json').write_text(json.dumps(proof))
    original_blind = (tmp / 'blind-predictions.jsonl').read_text()
    (tmp / 'blind-predictions.jsonl').write_text(original_blind + '\n')
    with patch.object(rf, 'R', synthetic_R):
        reject('blind_payload_SHA_change_rejected', lambda: rf.audit_task(task, selections, 'SYNTHETIC_JOINT', frozen_specs, h, None))

# Matched-reference test uses a tiny independently constructed metadata fixture.
with tempfile.TemporaryDirectory(prefix='synthetic_RF_matched_') as folder:
    tmp = Path(folder)
    ncs = [r['record_id'] for r in rows if r['NC_core']]
    std = [r['record_id'] for r in rows if not r['NC_core']]
    refs = sorted({r['target_reference_sequence_sha'] for r in rows})
    for name, value in (('nc.json', ncs), ('std.json', std), ('refs.json', refs)):
        (tmp / name).write_text(json.dumps(value))
    manifest = {'panels': [{'panel': rf.PANELS[0], 'NC_ids': str(tmp / 'nc.json'), 'standard_ids': str(tmp / 'std.json'), 'target_reference_shas': str(tmp / 'refs.json')}]}
    matched = h.matched_target_metrics(rows, rf.PANELS[0], manifest)
    check('matched_equal_reference_NC_standard_cohorts', [matched['cohorts'][k]['n'] for k in ('NC_matched', 'standard_matched')] == [2, 2] and matched['same_fixed_reference_target_count'] == 2)
    check('matched_singleton_targets_count_undefined_R2', matched['cohorts']['NC_matched']['target_reference_equal_weight_macro']['defined_group_counts']['R2'] == 0)

def metadata_records(methods):
    result = []
    for method, panel, regime, seed in itertools.product(methods, rf.PANELS, rf.REGIMES, range(10)):
        for raw in (('source_test' if panel == rf.PANELS[0] else 'target_test'), 'external75', 'supplement13'):
            dataset = rf.NORMALIZED[raw]
            result.append({'identity': dict(method_id=method, split_id=panel, regime=regime, seed=seed, dataset_id=dataset, holdout_id=rf.CANONICAL_HOLDOUT[dataset]),
                           'raw_scoring_dataset_id': raw, 'n': rf.RAW_COUNTS[raw], 'metrics': {'all': {'n': rf.RAW_COUNTS[raw]}}})
    return result


rf_records = metadata_records([rf.METHOD])
shape = rf.completeness(rf_records)
check('RF120_53160_complete_shape', shape['complete120_53160'] and shape['actual_total_prediction_rows'] == 53160)
check('RF119_incomplete', not rf.completeness(rf_records[:-1])['complete120_53160'])
check('duplicate_RF_receipt_does_not_fake120', not rf.completeness(rf_records[:-1] + [rf_records[0]])['complete120_53160'])
ledger = {}
for category in combine.CATEGORIES:
    records = metadata_records(sorted(combine.EXPECTED[category]['methods']))
    ledger[category] = combine.validate_category(records, category)
check('separate600_120_360_denominators', [ledger[c]['score_receipts'] for c in combine.CATEGORIES] == [600, 120, 360])
check('unified1080_478440_ledger_only', sum(v['prediction_rows'] for v in ledger.values()) == 478440 and sum(v['score_receipts'] for v in ledger.values()) == 1080)
check('paper_count_stays5', [ledger[c]['paper_count'] for c in combine.CATEGORIES] == [5, 0, 0])
reject('RF_cannot_enter_NN_denominator', lambda: combine.validate_category(rf_records, combine.CATEGORIES[0]))

record = {'identity': dict(method_id=rf.METHOD, split_id=rf.PANELS[0], regime='NC_only', dataset_id='PTM-external75', holdout_id=rf.CANONICAL_HOLDOUT['PTM-external75']),
          'raw_scoring_dataset_id': 'external75', 'metrics': groups75, 'cohort_macros': macros75}
seed_records = [dict(record, identity=dict(record['identity'], seed=seed)) for seed in range(10)]
table = rf.table_rows(seed_records); summary = rf.summarize_table(table)
check('ten_seed_per_metric_summary_and_defined_SD0', all(x['completed_seed_count'] == 10 and x['sample_sd'] in (None, 0) for x in summary))
nulls = [x for x in summary if x['cohort'] == 'synthetic_D_backbone']
check('empty_stratum_nulls_not_zeroed', bool(nulls) and all(x['mean'] is None and x['sample_sd'] is None and x['defined_seed_count'] == 0 for x in nulls))
reject('missing_seed_rejected', lambda: rf.summarize_table(rf.table_rows(seed_records[:-1])))
reject('duplicate_seed_rejected', lambda: rf.summarize_table(rf.table_rows(seed_records[:-1] + seed_records[:1])))
nn_table = rf.table_rows(seed_records, 'five_prior_paper_NN')
check('metric_rows_never_increment_paper_count', all(r['paper_count_contribution'] == 0 for r in nn_table))
legacy = copy.deepcopy(seed_records[0]); legacy.pop('cohort_macros'); legacy['macro_by_source'] = macros75['all_diagnostic']['study_id']
converted = combine.normalize_record(legacy, combine.CATEGORIES[0])
check('legacy_all_macro_not_mislabeled_NC', set(converted['cohort_macros']) == {'all_diagnostic'})

# No real paths touched by early denial. Full grid is validated by separate
# synthetic metadata fixtures and the preserved v4 eight gate cases.
reads = []
with patch.object(rf, 'read', lambda p: reads.append(str(p)) or {'root_RF_independent_audit_authorized': False}):
    reject('real_audit_auth_denied_before_joint_or_results', lambda: rf.authorize('SYNTHETIC_AUTH', 'NO_JOINT_ACCESS', 'NO_TASK_ACCESS'), PermissionError)
check('auth_denial_only_reads_auth', reads == ['SYNTHETIC_AUTH'])
reads = []
with patch.object(rf, 'read', lambda p: reads.append(str(p)) or {'root_RF_independent_audit_authorized': True, 'deadline_unix': 0}):
    reject('expired_auth_denied_before_joint_or_results', lambda: rf.authorize('SYNTHETIC_AUTH', 'NO_JOINT_ACCESS', 'NO_TASK_ACCESS'), TimeoutError)
check('expiry_denial_only_reads_auth', reads == ['SYNTHETIC_AUTH'])

# Full v5 authorization structure, entirely mocked generic metadata.
mapping = {}; nn_entries = []; rf_entries = []
auth = dict(root_RF_independent_audit_authorized=True, deadline_unix=10**12, script_sha256='SYNTHETIC',
            numeric_helper_sha256=rf.HELPER_SHA, task_map_sha256='SYNTHETIC', joint_barrier_sha256='SYNTHETIC')
mapping['AUTH'] = auth
for i, (method, panel, regime, seed) in enumerate(itertools.product(rf.METHODS_NN, rf.PANELS, rf.REGIMES, range(10))):
    path = 'SYNTHETIC-NN-' + str(i)
    nn_entries.append({'path': path, 'sha256': 'SHA-NN-' + str(i)})
    mapping[path] = dict(method_id=method, split_id=panel, regime=regime, seed=seed, status='frozen', holdout_metrics_consulted=False)
for i, (panel, regime, seed) in enumerate(itertools.product(rf.PANELS, rf.REGIMES, range(10))):
    path = 'SYNTHETIC-RF-' + str(i)
    rf_entries.append(dict(selection_path=path, selection_sha256='SHA-RF-' + str(i), panel=panel, regime=regime, seed=seed, model_sha256='DECLARED-MODEL-' + str(i)))
    mapping[path] = dict(panel=panel, regime=regime, seed=seed, status='frozen', validation_only=True, gold_reads=0, source_sha256={}, model_sha256='DECLARED-MODEL-' + str(i))
mapping['JOINT'] = dict(status='all_200_NN_plus_40_RF_frozen', NN_selections=200, RF_selections=40,
                        NN_execution_index_sha256=rf.NN_INDEX_SHA, NN_execution_index_path='NNINDEX',
                        NN_barrier_path='NNBARRIER', NN_barrier_sha256='SYNTHETIC', RF_barrier_path='RFBARRIER', RF_barrier_sha256='SYNTHETIC', RF_selection_entries=rf_entries)
mapping['NNINDEX'] = {'per_seed_selections': [{'selection_path': e['path']} for e in nn_entries]}
mapping['NNBARRIER'] = dict(status='all_selections_frozen', selection_count=200, candidate_fit_count=400, execution_index_sha256=rf.NN_INDEX_SHA, selections=nn_entries)
mapping['RFBARRIER'] = dict(status='all_40_RF_selections_frozen', selection_count=40, candidate_fit_count=80, selections=rf_entries)
mapping[str(rf.R / 'SOURCE-FREEZE-v1.json')] = {'source_sha256': {}}
with patch.object(rf, 'read', lambda p: mapping[str(p)]), patch.object(rf, 'require', lambda *a: None):
    authorized = rf.authorize('AUTH', 'JOINT', 'TASKMAP')
    check('v5_complete_joint_metadata_gate_accepts40_selections', len(authorized[2]) == 40)
for name in ('NN199', 'RF_duplicate', 'wrong_recovery', 'RF_source_changed'):
    altered = copy.deepcopy(mapping)
    if name == 'NN199':
        altered['NNBARRIER']['selections'] = altered['NNBARRIER']['selections'][:-1]
    elif name == 'RF_duplicate':
        altered['SYNTHETIC-RF-1']['seed'] = 0
    elif name == 'wrong_recovery':
        altered['JOINT']['NN_execution_index_sha256'] = 'UNAPPROVED'
    else:
        altered['SYNTHETIC-RF-0']['source_sha256'] = {'unexpected.py': 'SYNTHETIC'}
    with patch.object(rf, 'read', lambda p: altered[str(p)]), patch.object(rf, 'require', lambda *a: None):
        reject('v5_joint_gate_rejects_' + name, lambda: rf.authorize('AUTH', 'JOINT', 'TASKMAP'))

report = {'schema': 'independent-RF120-audit-v5-synthetic-verification', 'status': 'passed', 'passed_cases': len(cases), 'cases': cases,
          'numeric_helper_sha256': rf.HELPER_SHA, 'RF_auditor_sha256': rf.sha(HERE / 'recompute_RF_v5.py'),
          'combiner_sha256': rf.sha(HERE / 'combine_audit_tables_v5.py'),
          'actual_gold_training_labels_predictions_models_or_matrices_read': False,
          'actual_RF_audits_or_reference_fits': 0,
          'synthetic_scope': 'Generic synthetic numeric/mapping/metadata fixtures only; full120/600/360 grid arithmetic uses metadata counts, not real prediction rows.'}
(HERE / 'RF-audit-synthetic-verification-v5.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status': report['status'], 'passed_cases': len(cases)}, ensure_ascii=False))
