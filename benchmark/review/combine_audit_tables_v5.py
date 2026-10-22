"""Combine already audited NN600, RF120 and reference360 METRIC artifacts.

No raw gold/predictions/weights are read. No file discovery: root provides every
manifest and all360 reference receipt paths with SHA. Three denominators stay
separate. This is post-joint reporting, never a training/model-selection step.
"""
from __future__ import annotations
import argparse
from collections import Counter
import importlib.util
import itertools
import json
from pathlib import Path

SOURCE = Path(__file__).with_name('recompute_RF_v5.py')
loader = importlib.util.spec_from_file_location('independent_RF_table_schema_v5', SOURCE)
rf = importlib.util.module_from_spec(loader)
loader.loader.exec_module(rf)

CATEGORIES = ('five_prior_paper_NN', 'auxiliary_handcrafted_RF', 'three_deterministic_references')
EXPECTED = {
    CATEGORIES[0]: {'scores': 600, 'rows': 265800, 'methods': set(rf.METHODS_NN)},
    CATEGORIES[1]: {'scores': 120, 'rows': 53160, 'methods': {rf.METHOD}},
    CATEGORIES[2]: {'scores': 360, 'rows': 159480, 'methods': {'reference:train_mean', 'reference:train_median', 'reference:target_reference_train_median'}}}


def normalize_record(record, category):
    row = dict(record)
    ident = dict(row['identity'])
    if ident['dataset_id'] not in rf.CANONICAL_HOLDOUT:
        raise ValueError('Unknown normalized score dataset')
    panel = ident['split_id']
    raw = ('source_test' if panel == rf.PANELS[0] else 'target_test') if ident['dataset_id'] == 'PPIKB-internal' else ('external75' if ident['dataset_id'] == 'PTM-external75' else 'supplement13')
    if row.get('raw_scoring_dataset_id', raw) != raw:
        raise ValueError('Raw/normalized dataset mismatch')
    row['raw_scoring_dataset_id'] = raw
    row['n'] = row['metrics']['all']['n']
    if row['n'] != rf.RAW_COUNTS[raw]:
        raise ValueError('Metric artifact row count differs from frozen cohort')
    if 'cohort_macros' not in row:
        # Older NN/ref artifacts expose full-cohort macros only. Never invent
        # NC-specific macros by relabeling those all-row diagnostic summaries.
        macros = {}
        for old, field in (('macro_by_target', 'target_id'), ('macro_by_full_target_reference', 'target_reference_sequence_sha'), ('macro_by_source', 'study_id')):
            if old in row:
                macros[field] = row[old]
        row['cohort_macros'] = {'all_diagnostic': macros} if macros else {}
    row['category'] = category
    return row


def validate_category(records, category):
    expected = EXPECTED[category]
    methods = expected['methods']
    desired = {(m, p, r, s, d) for m in methods for p in rf.PANELS for r in rf.REGIMES for s in range(10)
               for d in (('source_test' if p == rf.PANELS[0] else 'target_test'), 'external75', 'supplement13')}
    keys = [(x['identity']['method_id'], x['identity']['split_id'], x['identity']['regime'], x['identity']['seed'], x['raw_scoring_dataset_id']) for x in records]
    count = Counter()
    for row in records:
        count[row['raw_scoring_dataset_id']] += row['n']
    factor = len(methods)
    expected_rows = {k: v * factor for k, v in rf.RAW_ROWS.items()}
    if len(keys) != len(set(keys)) or set(keys) != desired or len(keys) != expected['scores'] or dict(count) != expected_rows or sum(count.values()) != expected['rows']:
        raise ValueError('Category completeness failure: ' + category)
    return {'score_receipts': len(keys), 'prediction_rows': sum(count.values()), 'prediction_rows_by_raw_dataset': dict(count),
            'distinct_method_ids': sorted(methods), 'paper_count': 5 if category == CATEGORIES[0] else 0,
            'paper_count_scope': 'Distinct original NN paper methods only; metric/seed/receipt rows do not add papers.'}


def bound(entry):
    rf.require(entry['path'], entry['sha256'])
    return rf.read(entry['path'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root-authorization', required=True)
    parser.add_argument('--joint-barrier', required=True)
    parser.add_argument('--input-map', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    auth = rf.read(args.root_authorization)
    if auth.get('root_combined_metric_report_authorized') is not True:
        raise PermissionError('Await explicit root post-joint combined metric-report authorization')
    rf.require(__file__, auth['combiner_script_sha256'])
    # Shared RF authorization additionally verifies unchanged fullNN200+RF40
    # metadata and root-bound script/helper/input-map SHA; no weights are opened.
    auth, joint, _, _ = rf.authorize(args.root_authorization, args.joint_barrier, args.input_map)
    source = rf.read(args.input_map)
    nn_manifest = bound(source['NN_audit_manifest'])
    rf_manifest = bound(source['RF_audit_manifest'])
    reference_manifest = bound(source['reference_run_manifest'])
    if not nn_manifest.get('complete600_scores_265800_rows') or nn_manifest.get('metric_difference_count') != 0 or nn_manifest['barrier_sha256'] != joint['NN_barrier_sha256']:
        raise ValueError('NN independent audit incomplete, discrepant or different barrier')
    if rf_manifest.get('status') != 'complete_independent_RF_audit' or not rf_manifest.get('complete120_53160') or rf_manifest.get('metric_difference_count') != 0 or rf_manifest['joint_barrier_sha256'] != auth['joint_barrier_sha256']:
        raise ValueError('RF independent audit incomplete, discrepant or different joint gate')
    if (reference_manifest.get('status'), reference_manifest.get('rule_count'), reference_manifest.get('score_receipts'), reference_manifest.get('prediction_rows_total')) != ('complete_deterministic_references_only', 3, 360, 159480):
        raise ValueError('Deterministic reference run incomplete')
    if reference_manifest['global200_selection_barrier_sha256'] != joint['NN_barrier_sha256'] or reference_manifest.get('all_seed_predictions_identical') is not True:
        raise ValueError('Deterministic references use different NN barrier or variable predictions')
    if reference_manifest['script_sha256'] != rf.sha(Path(__file__).with_name('deterministic_references.py')) or reference_manifest['reference_plan_sha256'] != rf.sha(Path(__file__).with_name('deterministic-reference-plan-v2.json')):
        raise ValueError('Reference script/plan differs from preserved preparation')
    nn_records = bound(source['NN_per_score_audit'])
    rf_records = bound(source['RF_per_score_audit'])
    if source['RF_per_score_audit']['sha256'] != rf_manifest['per_score_audit_sha256']:
        raise ValueError('RF per-score artifact not bound by its audit manifest')
    reference_entries = source['reference_score_receipts']
    if len(reference_entries) != 360 or len({str(rf.local(e['path']).resolve()) for e in reference_entries}) != 360:
        raise ValueError('Explicit unique360 reference receipts required')
    reference_records = [bound(entry) for entry in reference_entries]
    vectors = {}
    for record in reference_records:
        if record.get('stage') != 'post-freeze-deterministic-reference' or record['global200_selection_barrier_sha256'] != joint['NN_barrier_sha256'] or record.get('random_parameters') is not False or record.get('no_validation_or_holdout_fitting') is not True or record['reference_plan_sha256'] != reference_manifest['reference_plan_sha256']:
            raise ValueError('Invalid deterministic reference metric receipt')
        ident = record['identity']
        key = tuple(ident[k] for k in ('method_id', 'split_id', 'regime', 'dataset_id'))
        if key in vectors and vectors[key] != record['prediction_vector_sha256']:
            raise ValueError('Deterministic reference vectors differ across seeds')
        vectors[key] = record['prediction_vector_sha256']
    categories = {CATEGORIES[0]: nn_records, CATEGORIES[1]: rf_records, CATEGORIES[2]: reference_records}
    all_rows, ledger = [], {}
    for category, records in categories.items():
        normalized = [normalize_record(r, category) for r in records]
        ledger[category] = validate_category(normalized, category)
        all_rows.extend(rf.table_rows(normalized, category))
    summary = rf.summarize_table(all_rows)
    out = rf.local(args.output); out.mkdir(parents=True, exist_ok=False)
    rf.write(out / 'unified-per-seed-metrics.json', all_rows); rf.write_csv(out / 'unified-per-seed-metrics.csv', all_rows)
    rf.write(out / 'unified-mean-sampleSD-metrics.json', summary); rf.write_csv(out / 'unified-mean-sampleSD-metrics.csv', summary)
    rf.write(out / 'separate-category-completeness.json', ledger)
    report = {'status': 'complete_postjoint_metric_table_assembly', 'categories': ledger,
              'ledger_score_receipts': sum(x['score_receipts'] for x in ledger.values()),
              'ledger_prediction_rows': sum(x['prediction_rows'] for x in ledger.values()),
              'distinct_prior_paper_methods': 5, 'new_paper_count_from_RF_or_references': 0,
              'input_map_sha256': auth['task_map_sha256'], 'joint_barrier_sha256': auth['joint_barrier_sha256'],
              'per_seed_table_sha256': rf.sha(out / 'unified-per-seed-metrics.json'), 'summary_table_sha256': rf.sha(out / 'unified-mean-sampleSD-metrics.json'),
              'raw_gold_predictions_models_or_feature_matrices_read_by_combiner': False,
              'numeric_metric_recalculation_from_raw_data': False, 'no_fitting_selection_or_retraining': True,
              'seed_SD_scope': 'Training-seed variation only; deterministic values repeat, undefined metrics remain null.',
              'macro_scope': 'Older NN/reference all-row macros stay all_diagnostic; only available cohort macros are displayed. Matched target NC/standard diagnostics retain frozen subsets.',
              'paper_count_scope': 'Count five distinct NN methods once; table rows and 1080receipts are not papers.', 'script_sha256': rf.sha(__file__)}
    if (report['ledger_score_receipts'], report['ledger_prediction_rows']) != (1080, 478440):
        raise ValueError('Cross-category ledger does not match separate preregistrations')
    rf.write(out / 'unified-table-manifest.json', report)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
