"""Bounded synthetic-only v6 metric-extension and merge tests."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

HERE = Path(__file__).parent


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


ext = load('synthetic_ext_v6', 'nc_scope_extension_v6.py')
merge = load('synthetic_merge_v6', 'merge_metric_extension_v6.py')
h = ext.v5.numeric_helper(); cases = []


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    cases.append({'case': name, 'passed': True})


def reject(name, function, error=ValueError):
    try:
        function()
    except error:
        check(name, True)
    else:
        raise AssertionError('Expected rejection: ' + name)


refs = [hashlib.sha256(x.encode()).hexdigest() for x in ('AA', 'CC')]
rows = [dict(record_id='SYNTHETIC-' + str(i), NC_core=i < 3,
             evaluation_stratum=('PTM' if i == 0 else 'synthetic_D_backbone') if i < 3 else 'standard20_control',
             study_id=None if i == 0 else 'SYNTHETIC_SOURCE', target_reference_sequence_sha=refs[i % 2],
             residue_class_graph_discordance=i in (0, 3),
             pKd_true=float(i), pKd_pred=float(i + (99 if i in (0, 3) else 1))) for i in range(5)]
groups = {cohort: [] for cohort in ext.MACRO_COHORTS + ('NC_core_exclude_discordant_sensitivity', 'standard_exclude_discordant_sensitivity')}
for i, row in enumerate(rows):
    cls = 'NC_core' if row['NC_core'] else 'standard'
    groups[cls].append(row['record_id'])
    if row['NC_core']:
        groups[row['evaluation_stratum']].append(row['record_id'])
    if i not in (0, 3):
        groups[cls + '_exclude_discordant_sensitivity'].append(row['record_id'])
group_spec = {'groups': groups, 'metadata': [{k: r[k] for k in ('record_id', 'NC_core', 'evaluation_stratum', 'study_id', 'target_reference_sequence_sha')} for r in rows]}
metrics, macros, missing = ext.supplement(rows, group_spec, h)
check('NCclean_recomputed_from_rows_not_stratum_means', metrics['NC_core_exclude_discordant_sensitivity']['n'] == 2 and metrics['NC_core_exclude_discordant_sensitivity']['MAE'] == 1 and metrics['NC_core_exclude_discordant_sensitivity']['RMSE'] == 1)
check('standard_clean_independently_filtered', metrics['standard_exclude_discordant_sensitivity']['n'] == 1 and metrics['standard_exclude_discordant_sensitivity']['MAE'] == 1)
check('both_clean_all_five_metrics_present', all(set(v) == {'n', *ext.v5.METRICS} for v in metrics.values()))
check('NC_plus_four_layers_plus_standard_macro_cohorts', set(macros) == set(ext.MACRO_COHORTS))
check('full_reference_and_study_equal_weight_only', all(set(v) == {'target_reference_sequence_sha', 'study_id'} for v in macros.values()))
check('missing_source_refs_explicit_not_imputed', missing['NC_core']['missing_source_refs'] == ['SYNTHETIC-0'] and missing['NC_core']['missing_source_ref_count'] == 1 and macros['NC_core']['study_id']['missing_group_rows'] == 1)
check('defined_macro_group_counts_retained', set(macros['NC_core']['study_id']['defined_group_counts']) == set(ext.v5.METRICS))
check('absent_strata_retained_empty_null', macros['synthetic_and_PTM']['study_id']['group_count'] == 0 and macros['synthetic_and_PTM']['study_id']['macro_mean']['MAE'] is None)
check('clean_missing_source_fields_explicit', missing['NC_core_exclude_discordant_sensitivity']['missing_source_ref_count'] == 0)
bad = copy.deepcopy(rows); bad.pop()
reject('missing_prediction_id_rejected', lambda: ext.supplement(bad, group_spec, h))
bad = copy.deepcopy(rows); bad[0]['NC_core'] = False
reject('chemistry_relabeling_rejected', lambda: ext.supplement(bad, group_spec, h))
bad = copy.deepcopy(rows); bad[0]['study_id'] = 'FAKE'
reject('source_relabeling_rejected', lambda: ext.supplement(bad, group_spec, h))
bad = copy.deepcopy(rows); bad[0]['target_reference_sequence_sha'] = 'WRONG'
reject('reference_identity_change_rejected', lambda: ext.supplement(bad, group_spec, h))
check('360_grid_is_NN200_RF40_reference120', len(ext.expected_cases()) == 360 and sum(c[0] == 'five_prior_paper_NN' for c in ext.expected_cases()) == 200)
check('RF40_reuses_existing_internal_predictions_only', sum(c[1] == ext.v5.METHOD for c in ext.expected_cases()) == 40)
record = {'category': 'five_prior_paper_NN', 'identity': dict(method_id='GraphDTA-GIN', split_id=ext.v5.PANELS[0], regime='NC_only', seed=0, dataset_id='PPIKB-internal'),
          'raw_scoring_dataset_id': 'source_test', 'metrics': metrics, 'cohort_macros': macros}
extra = ext.v5.table_rows([record], record['category'])
base = [dict(extra[0], cohort='NC_core', value=123.0)]
merged, duplicates = merge.merge_rows(base, extra)
check('base_rows_kept_verbatim_values', merged[:len(base)] == base and duplicates == 0)
check('no_all_score_rows_added', not any(r['cohort'] == 'all' for r in extra))
same, dedup = merge.merge_rows(base + [extra[0]], [copy.deepcopy(extra[0])])
check('equal_duplicate_key_deduplicates', same == base + [extra[0]] and dedup == 1)
bad = copy.deepcopy(extra[0]); bad['value'] = 999
reject('conflicting_duplicate_value_fails', lambda: merge.merge_rows(base + [extra[0]], [bad]))
bad = copy.deepcopy(extra[0]); bad['n'] += 1
reject('conflicting_duplicate_denominator_fails', lambda: merge.merge_rows(base + [extra[0]], [bad]))
bad = copy.deepcopy(extra[0]); bad['category'] = 'UNKNOWN'
reject('unknown_extra_category_rejected', lambda: merge.merge_rows(base, [bad]))
reads = []
with patch.object(ext.v5, 'read', lambda path: reads.append(str(path)) or {'root_NC_scope_extension_authorized': False}):
    reject('no_root_auth_no_prediction_or_joint_access', lambda: ext.authorize('SYNTHETIC_AUTH', 'NO_JOINT', 'NO_CASEMAP'), PermissionError)
check('auth_denial_reads_auth_only', reads == ['SYNTHETIC_AUTH'])
check('fixed_clean_counts_source_and_target', ext.EXPECTED[ext.v5.PANELS[0]][2:] == (274, 736, 724) and ext.EXPECTED[ext.v5.PANELS[1]][2:] == (261, 1111, 1067))
spec = importlib.util.spec_from_file_location('frozen_report_v1_source_only', HERE.parent / 'reporting/report_builder.py')
reporting = importlib.util.module_from_spec(spec); spec.loader.exec_module(reporting)
reporting.validate_rows(extra)
check('frozen_report_v1_accepts_canonical_v6_new_cohorts', all(set(r) <= reporting.ROW_FIELDS for r in extra))
bad = copy.deepcopy(extra[0]); bad['missing_source_refs'] = ['SYNTHETIC-0']
reject('frozen_report_rejects_rich_sidecar_column_as_expected', lambda: reporting.validate_rows([bad]))
check('explicit_v6_generator_and_schema', "schema_version=6" in (HERE / 'merge_metric_extension_v6.py').read_text() and "generated_by='review/merge_metric_extension_v6.py'" in (HERE / 'merge_metric_extension_v6.py').read_text())
RF_groups, RF_macros = ext.v5.compute_rows(rows, 'source_test', h)
check('existing_RF_clean_keys_same_semantics', all(metrics[k] == RF_groups[k] for k in metrics))
check('existing_RF_NC_standard_reference_source_macro_keys_same_semantics', all(macros[c][f] == RF_macros[c][f] for c in ('NC_core', 'standard') for f in ('target_reference_sequence_sha', 'study_id')))
RF_record = copy.deepcopy(record); RF_record['category'] = 'auxiliary_handcrafted_RF'; RF_record['identity']['method_id'] = ext.v5.METHOD
RF_extra = ext.v5.table_rows([RF_record], 'auxiliary_handcrafted_RF')
RF_base = [r for r in RF_extra if r['aggregation'] == 'row_micro' or r['cohort'] in ('NC_core', 'standard')]
RF_merged, RF_dedup = merge.merge_rows(RF_base, RF_extra)
check('RF_existing30keys_equal_deduplicate', RF_dedup == 30 and RF_merged[:len(RF_base)] == RF_base)
check('RF_four_strata_add40_macro_keys_only', len(RF_merged) - len(RF_base) == 40)
check('global_diagnostic25200_dedup1200_new24000', 360 * 70 == 25200 and 40 * RF_dedup == 1200 and 320 * 70 + 40 * 40 == 24000)
with tempfile.TemporaryDirectory(prefix='synthetic_v6_RF_case_') as folder:
    tmp = Path(folder)
    ins, pred, blind, meta = [], [], [], []
    gs = {k: [] for k in ext.MACRO_COHORTS + ('NC_core_exclude_discordant_sensitivity', 'standard_exclude_discordant_sensitivity')}
    for i in range(1039):
        nc = i < 303; cls = 'NC_core' if nc else 'standard'
        stratum = ext.v5.STRATA[i % 4] if nc else 'standard20_control'
        r = dict(record_id='SYNTHETIC_RF_' + str(i), NC_core=nc, evaluation_stratum=stratum, study_id='SYNTHETIC_SOURCE', target_sequence='AA', residue_class_graph_discordance=i < 29 or 303 <= i < 315)
        ref = hashlib.sha256(b'AA').hexdigest()
        ins.append(r); truth = float(i % 7); value = truth + .1
        b = {k: v for k, v in r.items() if k != 'target_sequence'}; b['pKd_pred'] = value; blind.append(b)
        pred.append(dict(b, pKd_true=truth, residual=value - truth))
        meta.append({k: v for k, v in dict(r, target_reference_sequence_sha=ref).items() if k in ('record_id', 'NC_core', 'evaluation_stratum', 'study_id', 'target_reference_sequence_sha')})
        gs[cls].append(r['record_id'])
        if nc: gs[stratum].append(r['record_id'])
        if not r['residue_class_graph_discordance']: gs[cls + '_exclude_discordant_sensitivity'].append(r['record_id'])
    def save(name, data, jsonl=False):
        p = tmp / name; p.write_text(''.join(json.dumps(r) + '\n' for r in data) if jsonl else json.dumps(data)); return {'path': str(p), 'sha256': ext.v5.sha(p)}
    inp = save('input.jsonl', ins, True); pp = save('pred.jsonl', pred, True); bp = save('blind.jsonl', blind, True)
    gp = save('groups.json', {'groups': gs, 'metadata': meta})
    identity = dict(method_id=ext.v5.METHOD, split_id=ext.v5.PANELS[0], regime='NC_only', seed=0, dataset_id='PPIKB-internal', holdout_id='internal-test')
    receipt = dict(method_id=ext.v5.METHOD, panel=ext.v5.PANELS[0], regime='NC_only', seed=0, stage='additional_classical_RF_post_joint_barrier_score', predictions_sha256=pp['sha256'], blind_predictions_sha256=bp['sha256'])
    rp = save('receipt.json', receipt); proof = save('proof.json', dict(status='RF_blind_saved_before_gold_access', gold_reads=0, blind_sha256=bp['sha256']))
    joined = [dict(r, pKd_true=p['pKd_true'], pKd_pred=p['pKd_pred'], target_reference_sequence_sha=hashlib.sha256(r['target_sequence'].encode()).hexdigest()) for r, p in zip(ins, pred)]
    old_groups, old_macros = ext.v5.compute_rows(joined, 'source_test', h)
    base_audits = {'auxiliary_handcrafted_RF': {rp['sha256']: dict(identity=identity, all_truths_match_frozen_gold=True, metrics=old_groups, cohort_macros=old_macros)}}
    case = dict(category='auxiliary_handcrafted_RF', source_receipt=rp, predictions=pp, blind_predictions=bp, blind_proof=proof, input_metadata=inp)
    group_manifest = {'panels': [dict(gp, panel=ext.v5.PANELS[0], input_metadata=inp)]}
    audited = ext.audit_case(case, group_manifest, base_audits, {}, h)
    check('synthetic_RF1039_file_case_reuses_bound_prediction_and_matches_v5', audited['metrics']['NC_core_exclude_discordant_sensitivity']['n'] == 274 and audited['metrics']['standard_exclude_discordant_sensitivity']['n'] == 724 and audited['additional_prediction_rows'] == 0)
report = {'schema': 'NC-scope-extension-v6-synthetic-mechanics', 'status': 'passed', 'passed_cases': len(cases), 'cases': cases,
          'extension_source_sha256': ext.v5.sha(HERE / 'nc_scope_extension_v6.py'), 'merge_source_sha256': ext.v5.sha(HERE / 'merge_metric_extension_v6.py'),
          'real_gold_prediction_model_matrix_or_training_label_reads': False, 'real_diagnostic_cases': 0, 'additional_scores': 0}
(HERE / 'NC-scope-synthetic-verification-v6.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({'status': report['status'], 'passed_cases': len(cases)}))
