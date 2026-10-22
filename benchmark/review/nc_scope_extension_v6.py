"""Preregistered metric-only supplement: NN200+RF40+reference120 internal cases.

No training, gold file, weight or matrix access. Joined predictions must already
be bound to completed base audits; no value is changed. Old v3-v5 remain intact.
"""
import argparse
from collections import Counter
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import time

HERE = Path(__file__).parent
loader = importlib.util.spec_from_file_location('preserved_v5_RF_utilities_for_v6', HERE / 'recompute_RF_v5.py')
v5 = importlib.util.module_from_spec(loader); loader.loader.exec_module(v5)
V5_SHA = '9d6f1e67d6a08c45316014729ffc850e1d59bd6ab3da1c989bcb4280e731e905'
REFERENCES = ('reference:train_mean', 'reference:train_median', 'reference:target_reference_train_median')
EXPECTED = {v5.PANELS[0]: (1039, 303, 274, 736, 724), v5.PANELS[1]: (1443, 332, 261, 1111, 1067)}
MACRO_COHORTS = ('NC_core', 'synthetic_D_backbone', 'PTM', 'synthetic_and_PTM', 'other_NC', 'standard')


def bound(entry):
    v5.require(entry['path'], entry['sha256']); return v5.read(entry['path'])


def freeze_groups(output):
    """Run before any holdout: label-free membership only, no affinity values."""
    out = v5.local(output); out.mkdir(parents=True, exist_ok=False)
    helper = v5.numeric_helper(); panels = []
    for panel in v5.PANELS:
        path = v5.P / 'execution/prepared-panels-wsl-v3' / panel / 'test-inputs.jsonl'
        inputs = v5.lines(path)
        if any(v5.GOLD_FIELDS & set(r) for r in inputs):
            raise ValueError('Group preparation received label-bearing rows')
        if len(v5.unique(inputs, 'group metadata')) != len(inputs):
            raise ValueError('Duplicate metadata IDs')
        groups = {key: [] for key in MACRO_COHORTS + ('NC_core_exclude_discordant_sensitivity', 'standard_exclude_discordant_sensitivity')}
        metadata = []
        for row in inputs:
            if type(row['NC_core']) is not bool or row['evaluation_stratum'] not in v5.STRATA:
                raise ValueError('Unknown NC/standard metadata')
            if row['NC_core'] != (row['evaluation_stratum'] != 'standard20_control'):
                raise ValueError('NC class/stratum conflict')
            cls = 'NC_core' if row['NC_core'] else 'standard'
            groups[cls].append(row['record_id'])
            if row['NC_core']:
                groups[row['evaluation_stratum']].append(row['record_id'])
            discordant = helper.is_discordant(row)
            if not discordant:
                groups[cls + '_exclude_discordant_sensitivity'].append(row['record_id'])
            if not row.get('target_sequence'):
                raise ValueError('Missing full reference sequence')
            metadata.append(dict(record_id=row['record_id'], NC_core=row['NC_core'], evaluation_stratum=row['evaluation_stratum'],
                                 discordant=discordant, target_reference_sequence_sha=hashlib.sha256(row['target_sequence'].encode()).hexdigest(),
                                 study_id=row.get('study_id'), missing_source_ref=not bool(row.get('study_id'))))
        counts = (len(inputs), len(groups['NC_core']), len(groups['NC_core_exclude_discordant_sensitivity']), len(groups['standard']), len(groups['standard_exclude_discordant_sensitivity']))
        if counts != EXPECTED[panel]:
            raise ValueError('Frozen test/clean counts differ: ' + panel)
        target = out / (panel + '.json')
        v5.write(target, dict(panel=panel, groups=groups, metadata=metadata))
        panels.append(dict(panel=panel, path=str(target), sha256=v5.sha(target), input_metadata=dict(path=str(path), sha256=v5.sha(path)),
                           group_counts={k: len(v) for k, v in groups.items()}, missing_source_refs=[r['record_id'] for r in metadata if r['missing_source_ref']]))
    manifest = dict(schema='preregistered-NC-scope-groups-v6', status='frozen_label_free_before_holdout', panels=panels,
                    numeric_helper_sha256=v5.HELPER_SHA, grouping='fixed existing test rows; no split, training or filtering change',
                    source_scope='study_id aliases are machine source refs, not certified independent experiments', actual_gold_prediction_model_matrix_label_reads=False)
    v5.write(out / 'manifest.json', manifest)
    return manifest


def supplement(rows, group_spec, helper):
    byid = v5.unique(rows, 'supplement predictions')
    meta = v5.unique(group_spec['metadata'], 'frozen group metadata')
    if set(byid) != set(meta):
        raise ValueError('Prediction IDs differ from frozen full test')
    for rid, row in byid.items():
        for key in ('NC_core', 'evaluation_stratum', 'study_id'):
            if row.get(key) != meta[rid].get(key):
                raise ValueError('Prediction chemistry/source metadata changed')
        if row.get('target_reference_sequence_sha') != meta[rid]['target_reference_sequence_sha']:
            raise ValueError('Full target-reference SHA differs')
    groups = group_spec['groups']; metrics = {}; macros = {}; missing = {}
    for cohort in ('NC_core_exclude_discordant_sensitivity', 'standard_exclude_discordant_sensitivity'):
        selected = [byid[rid] for rid in groups[cohort]]
        metrics[cohort] = helper.metrics([r['pKd_true'] for r in selected], [r['pKd_pred'] for r in selected])
    for cohort in MACRO_COHORTS:
        selected = [byid[rid] for rid in groups[cohort]]
        macros[cohort] = {field: helper.macro_metrics(selected, field) for field in ('target_reference_sequence_sha', 'study_id')}
    for cohort in MACRO_COHORTS + ('NC_core_exclude_discordant_sensitivity', 'standard_exclude_discordant_sensitivity'):
        selected = [byid[rid] for rid in groups[cohort]]
        missing[cohort] = dict(observation_n=len(selected), missing_source_refs=[r['record_id'] for r in selected if not r.get('study_id')],
                               missing_source_ref_count=sum(not bool(r.get('study_id')) for r in selected),
                               nonmissing_source_refs=sorted({str(r['study_id']) for r in selected if r.get('study_id')}))
    return metrics, macros, missing


def expected_cases():
    return {(category, method, panel, regime, seed) for category, methods in (
        ('five_prior_paper_NN', v5.METHODS_NN), ('auxiliary_handcrafted_RF', (v5.METHOD,)), ('three_deterministic_references', REFERENCES))
        for method, panel, regime, seed in itertools.product(methods, v5.PANELS, v5.REGIMES, range(10))}


def authorize(auth_path, joint_path, case_map):
    auth = v5.read(auth_path)
    if auth.get('root_NC_scope_extension_authorized') is not True:
        raise PermissionError('Await new root post-joint NC metric-extension authorization')
    v5.require(__file__, auth['extension_script_sha256']); v5.require(HERE / 'recompute_RF_v5.py', V5_SHA)
    auth, joint, _, _ = v5.authorize(auth_path, joint_path, case_map)
    nn, rf, refs = (bound(auth[k]) for k in ('base_NN_audit_manifest', 'base_RF_audit_manifest', 'reference_run_manifest'))
    if not nn.get('complete600_scores_265800_rows') or nn.get('metric_difference_count') != 0 or not nn.get('all_predictions_true_labels_match') or nn['barrier_sha256'] != joint['NN_barrier_sha256']:
        raise ValueError('Completed consistent NN600 base audit required')
    if rf.get('status') != 'complete_independent_RF_audit' or not rf.get('complete120_53160') or rf.get('metric_difference_count') != 0 or rf['joint_barrier_sha256'] != auth['joint_barrier_sha256']:
        raise ValueError('Completed consistent RF120 base audit required')
    if refs.get('status') != 'complete_deterministic_references_only' or refs.get('score_receipts') != 360 or refs.get('prediction_rows_total') != 159480 or refs['global200_selection_barrier_sha256'] != joint['NN_barrier_sha256']:
        raise ValueError('Completed reference360 base run required')
    audited = {category: {r['score_receipt_sha256']: r for r in bound(auth[key])} for category, key in (
        ('five_prior_paper_NN', 'base_NN_per_score_audit'), ('auxiliary_handcrafted_RF', 'base_RF_per_score_audit'))}
    return auth, joint, audited


def audit_case(case, group_manifest, base_audits, joint, helper):
    receipt = bound(case['source_receipt']); category = case['category']
    if category == 'three_deterministic_references':
        ident = receipt['identity']
    else:
        ident = {k: receipt[k] for k in ('method_id', 'regime', 'seed')}
        ident['split_id'] = receipt['panel'] if category == 'auxiliary_handcrafted_RF' else receipt['split_id']
    panel = ident['split_id']; raw = 'source_test' if panel == v5.PANELS[0] else 'target_test'
    identity = dict(ident, dataset_id='PPIKB-internal', holdout_id='internal-test')
    panel_meta = next(e for e in group_manifest['panels'] if e['panel'] == panel)
    if case['input_metadata'] != panel_meta['input_metadata']:
        raise ValueError('Case input metadata not the frozen panel view')
    inputs = bound_lines(case['input_metadata'])
    if category in ('five_prior_paper_NN', 'auxiliary_handcrafted_RF'):
        expected_stage = 'post-selection-score-only' if category == 'five_prior_paper_NN' else 'additional_classical_RF_post_joint_barrier_score'
        existing = base_audits[category]
        if receipt.get('stage') != expected_stage or case['source_receipt']['sha256'] not in existing:
            raise ValueError('NN/RF case not in completed base audit')
        old_audit = existing[case['source_receipt']['sha256']]
        if old_audit['identity'] != identity or not old_audit['all_truths_match_frozen_gold']:
            raise ValueError('NN/RF audited identity/truth evidence differs')
        if case['predictions']['sha256'] != receipt['predictions_sha256']:
            raise ValueError('NN prediction SHA differs from base score')
        if case.get('blind_predictions', {}).get('sha256') != receipt['blind_predictions_sha256']:
            raise ValueError('Original NN blind file must be explicitly bound')
        blind = bound_lines(case['blind_predictions']); proof = bound(case['blind_proof'])
        if category == 'five_prior_paper_NN':
            good = proof.get('stage') == 'blind_predictions_persisted_before_gold_open' and proof.get('blind_predictions_sha256') == receipt['blind_predictions_sha256']
        else:
            good = proof.get('status') == 'RF_blind_saved_before_gold_access' and proof.get('blind_sha256') == receipt['blind_predictions_sha256']
        if not good or proof.get('gold_reads') != 0:
            raise ValueError('Original NN/RF blind proof differs')
    elif category == 'three_deterministic_references':
        if receipt.get('stage') != 'post-freeze-deterministic-reference' or receipt['global200_selection_barrier_sha256'] != joint['NN_barrier_sha256'] or not receipt.get('no_validation_or_holdout_fitting') or receipt.get('random_parameters') is not False:
            raise ValueError('Reference case not from frozen completed reference run')
        if case['predictions']['sha256'] != receipt['prediction_sha256'] or case.get('blind_predictions') is not None:
            raise ValueError('Reference has no separate blind artifact; do not invent one')
        blind = None
    else:
        raise ValueError('Unknown metric category')
    predictions = bound_lines(case['predictions']); inputs_byid = v5.unique(inputs, 'input'); pred = v5.unique(predictions, 'prediction')
    if set(pred) != set(inputs_byid) or len(pred) != EXPECTED[panel][0]:
        raise ValueError('Prediction/full frozen test IDs differ')
    if blind is not None:
        b = v5.unique(blind, 'blind')
        if set(b) != set(pred) or any(float(b[r]['pKd_pred']) != float(pred[r]['pKd_pred']) for r in pred):
            raise ValueError('Blind/join predictions differ')
    else:
        vector = hashlib.sha256(json.dumps([(r['record_id'], r['pKd_pred']) for r in predictions], separators=(',', ':')).encode()).hexdigest()
        if vector != receipt['prediction_vector_sha256']:
            raise ValueError('Reference prediction vector SHA differs')
    rows = []
    for rid, inp in inputs_byid.items():
        if v5.GOLD_FIELDS & set(inp):
            raise ValueError('Input metadata contains gold')
        for key in ('NC_core', 'evaluation_stratum', 'study_id'):
            if pred[rid].get(key) != inp.get(key):
                raise ValueError('Prediction annotation differs from frozen input')
        rows.append(dict(inp, pKd_true=float(pred[rid]['pKd_true']), pKd_pred=float(pred[rid]['pKd_pred']),
                         target_reference_sequence_sha=hashlib.sha256(inp['target_sequence'].encode()).hexdigest()))
    group_spec = bound(panel_meta)
    metrics, macros, missing = supplement(rows, group_spec, helper)
    if category == 'auxiliary_handcrafted_RF':
        if any(metrics[k] != old_audit['metrics'][k] for k in metrics) or any(macros[c][f] != old_audit['cohort_macros'][c][f] for c in ('NC_core', 'standard') for f in ('target_reference_sequence_sha', 'study_id')):
            raise ValueError('RF existing clean/NC-standard macro values differ from base v5 audit')
    return dict(category=category, identity=identity, raw_scoring_dataset_id=raw, metrics=metrics, cohort_macros=macros,
                missing_source_refs_by_cohort=missing, source_receipt_sha256=case['source_receipt']['sha256'],
                original_prediction_sha256=case['predictions']['sha256'], original_prediction_values_changed=False,
                diagnostic_case_not_new_score=True, additional_prediction_rows=0, paper_count_contribution=0)


def bound_lines(entry):
    v5.require(entry['path'], entry['sha256']); return v5.lines(entry['path'])


def main():
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('freeze-groups'); prep.add_argument('--output', required=True)
    run = sub.add_parser('audit'); run.add_argument('--root-authorization', required=True); run.add_argument('--joint-barrier', required=True)
    run.add_argument('--case-map', required=True); run.add_argument('--group-manifest', required=True); run.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.command == 'freeze-groups':
        freeze_groups(args.output); return
    auth, joint, base_audits = authorize(args.root_authorization, args.joint_barrier, args.case_map)
    v5.require(args.group_manifest, auth['group_manifest_sha256']); group_manifest = v5.read(args.group_manifest)
    if group_manifest['status'] != 'frozen_label_free_before_holdout' or group_manifest['numeric_helper_sha256'] != v5.HELPER_SHA:
        raise ValueError('Groups were not preregistered')
    cases = v5.read(args.case_map)
    if len(cases) != 360:
        raise ValueError('Exactly360 diagnostic cases required')
    helper = v5.numeric_helper(); records = []
    for case in cases:
        if time.time() >= auth['deadline_unix']:
            raise TimeoutError('Original deadline reached')
        records.append(audit_case(case, group_manifest, base_audits, joint, helper))
    keys = [(r['category'], r['identity']['method_id'], r['identity']['split_id'], r['identity']['regime'], r['identity']['seed']) for r in records]
    if len(set(keys)) != 360 or set(keys) != expected_cases():
        raise ValueError('360 exact NN200/RF40/reference120 diagnostic grid missing')
    long = []
    for record in records:
        rows = v5.table_rows([record], record['category'])
        # Rich missing-source/provenance stays in sidecars. Canonical columns
        # deliberately match the frozen reporting v1 metric-only whitelist.
        long.extend(rows)
    if len(long) != 25200:
        raise ValueError('Expected360 diagnostic cases times70 canonical metric rows')
    out = v5.local(args.output); out.mkdir(parents=True, exist_ok=False)
    v5.write(out / 'metric-case-sidecars.json', records); v5.write(out / 'extension-long-metrics.json', long)
    v5.write_csv(out / 'extension-long-metrics.csv', long); v5.write(out / 'extension-ten-seed-summary.json', v5.summarize_table(long))
    v5.write(out / 'extension-manifest.json', dict(schema='preregistered-NC-scope-extension-v6', status='complete_metric_only_NC_scope_extension',
        diagnostic_cases=360, NN_internal_cases=200, RF_internal_cases=40, reference_internal_cases=120, reused_existing_prediction_rows=446760,
        RF_existing_metric_values_checked_exactly=True, additional_scores=0, additional_prediction_rows=0,
        joint_barrier_sha256=auth['joint_barrier_sha256'], group_manifest_sha256=auth['group_manifest_sha256'], case_map_sha256=auth['task_map_sha256'],
        sidecars_sha256=v5.sha(out / 'metric-case-sidecars.json'), long_metrics_sha256=v5.sha(out / 'extension-long-metrics.json'),
        generated_by='review/nc_scope_extension_v6.py', script_sha256=v5.sha(__file__), numeric_helper_sha256=v5.HELPER_SHA,
        raw_gold_models_matrices_or_training_labels_read=False, existing_predictions_changed=False, fitting=0))


if __name__ == '__main__':
    main()
