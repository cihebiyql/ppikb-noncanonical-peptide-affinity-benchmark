"""Synthetic metadata-only end-to-end exercise of combined table CLI.

No real training/holdout/model/prediction records are used. The joint metadata
gate is tested separately; here it is explicitly mocked to test file plumbing.
"""
import contextlib
import hashlib
import importlib.util
import io
import itertools
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location('synthetic_combiner_e2e_v5', HERE / 'combine_audit_tables_v5.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
rf = module.rf
cases = []


def check(name, result):
    if not result:
        raise AssertionError(name)
    cases.append({'case': name, 'passed': True})


with tempfile.TemporaryDirectory(prefix='synthetic_combined_metrics_') as folder:
    tmp = Path(folder)
    def save(name, value):
        path = tmp / name; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, allow_nan=False))
        return {'path': str(path), 'sha256': rf.sha(path)}
    def records(methods, reference=False):
        result = []
        for method, panel, regime, seed in itertools.product(methods, rf.PANELS, rf.REGIMES, range(10)):
            for raw in (('source_test' if panel == rf.PANELS[0] else 'target_test'), 'external75', 'supplement13'):
                dataset = rf.NORMALIZED[raw]
                n = rf.RAW_COUNTS[raw]; nc = {'source_test': 303, 'target_test': 332, 'external75': 75, 'supplement13': 8}[raw]
                value = 2.0 if reference else float(seed + 1)
                groups = {key: dict(n=count, **{metric: value if count else None for metric in rf.METRICS}) for key, count in [('all', n), ('NC_core', nc), ('standard', n - nc)]}
                row = {'identity': dict(method_id=method, split_id=panel, regime=regime, seed=seed, dataset_id=dataset, holdout_id=rf.CANONICAL_HOLDOUT[dataset]),
                       'raw_scoring_dataset_id': raw, 'metrics': groups}
                if reference:
                    row.update(stage='post-freeze-deterministic-reference', global200_selection_barrier_sha256='SYNTHETIC_NN_BARRIER',
                               random_parameters=False, no_validation_or_holdout_fitting=True,
                               reference_plan_sha256=rf.sha(HERE / 'deterministic-reference-plan-v2.json'),
                               prediction_vector_sha256=hashlib.sha256((method + panel + regime + dataset).encode()).hexdigest())
                result.append(row)
        return result
    nn = records(rf.METHODS_NN); classical = records([rf.METHOD]); refs = records(sorted(module.EXPECTED[module.CATEGORIES[2]]['methods']), True)
    nn_scores = save('NN/per-score-audit.json', nn); rf_scores = save('RF/per-score-audit.json', classical)
    nn_manifest = save('NN/manifest.json', {'complete600_scores_265800_rows': True, 'metric_difference_count': 0, 'barrier_sha256': 'SYNTHETIC_NN_BARRIER'})
    rf_manifest_data = {'status': 'complete_independent_RF_audit', 'complete120_53160': True, 'metric_difference_count': 0, 'joint_barrier_sha256': 'SYNTHETIC_JOINT', 'per_score_audit_sha256': rf_scores['sha256']}
    rf_manifest = save('RF/manifest.json', rf_manifest_data)
    ref_manifest = save('references/manifest.json', dict(status='complete_deterministic_references_only', rule_count=3, score_receipts=360, prediction_rows_total=159480,
                        global200_selection_barrier_sha256='SYNTHETIC_NN_BARRIER', all_seed_predictions_identical=True,
                        script_sha256=rf.sha(HERE / 'deterministic_references.py'), reference_plan_sha256=rf.sha(HERE / 'deterministic-reference-plan-v2.json')))
    ref_entries = [save('references/receipt-' + str(i) + '.json', row) for i, row in enumerate(refs)]
    input_data = dict(NN_audit_manifest=nn_manifest, RF_audit_manifest=rf_manifest, reference_run_manifest=ref_manifest,
                      NN_per_score_audit=nn_scores, RF_per_score_audit=rf_scores, reference_score_receipts=ref_entries)
    input_map = save('input-map.json', input_data)
    auth = {'root_combined_metric_report_authorized': True, 'combiner_script_sha256': rf.sha(HERE / 'combine_audit_tables_v5.py'),
            'task_map_sha256': input_map['sha256'], 'joint_barrier_sha256': 'SYNTHETIC_JOINT'}
    auth_path = save('SYNTHETIC_ONLY_auth.json', auth)['path']
    joint = {'NN_barrier_sha256': 'SYNTHETIC_NN_BARRIER'}
    def invoke(out):
        argv = ['combine_audit_tables_v5.py', '--root-authorization', auth_path, '--joint-barrier', 'SYNTHETIC_NO_REAL_JOINT', '--input-map', input_map['path'], '--output', str(out)]
        with patch.object(sys, 'argv', argv), patch.object(rf, 'authorize', lambda *args: (auth, joint, None, None)), contextlib.redirect_stdout(io.StringIO()):
            module.main()
    invoke(tmp / 'out')
    manifest = rf.read(tmp / 'out/unified-table-manifest.json')
    table = rf.read(tmp / 'out/unified-per-seed-metrics.json')
    summary = rf.read(tmp / 'out/unified-mean-sampleSD-metrics.json')
    check('synthetic_full_cli_writes1080_478440_ledger', (manifest['ledger_score_receipts'], manifest['ledger_prediction_rows']) == (1080, 478440))
    check('separate_three_category_denominators_retained', [manifest['categories'][c]['score_receipts'] for c in module.CATEGORIES] == [600, 120, 360])
    check('all_metric_rows_zero_additive_paper_contribution', len(table) == 16200 and all(row['paper_count_contribution'] == 0 for row in table))
    check('distinct_five_NN_paper_identity_only', {r['prior_paper_method_id'] for r in table if r['prior_paper_method_id']} == set(rf.METHODS_NN) and manifest['distinct_prior_paper_methods'] == 5)
    check('ten_seed_mean_sampleSD_table_complete', len(summary) == 1620 and all(r['completed_seed_count'] == 10 for r in summary))
    reference_summary = [r for r in summary if r['category'] == module.CATEGORIES[2]]
    check('deterministic_reference_SD0_or_null', all(r['sample_sd'] in (None, 0) for r in reference_summary))
    check('null_empty_standard_external_metrics_preserved', any(r['cohort'] == 'standard' and r['dataset_id'] == 'PTM-external75' and r['mean'] is None and r['defined_seed_count'] == 0 for r in summary))
    check('JSON_and_CSV_both_materialized', all((tmp / 'out' / f).is_file() for f in ('unified-per-seed-metrics.json', 'unified-per-seed-metrics.csv', 'unified-mean-sampleSD-metrics.json', 'unified-mean-sampleSD-metrics.csv')))
    rf_manifest_data['metric_difference_count'] = 1
    input_data['RF_audit_manifest'] = save('RF/manifest.json', rf_manifest_data)
    input_map = save('input-map.json', input_data)
    try:
        invoke(tmp / 'out_bad_metrics')
    except ValueError:
        check('refuses_to_publish_discrepant_RF_metrics', not (tmp / 'out_bad_metrics').exists())
    else:
        raise AssertionError('Discrepant RF metrics were accepted')

report = {'schema': 'synthetic-combined-metric-CLI-e2e-v5', 'status': 'passed', 'passed_cases': len(cases), 'cases': cases,
          'combiner_sha256': rf.sha(HERE / 'combine_audit_tables_v5.py'), 'RF_auditor_sha256': rf.sha(HERE / 'recompute_RF_v5.py'),
          'scope': 'Temporary synthetic metric metadata only, mocked joint authorization for file-plumbing tests; separate gate tests exercise authorization logic.',
          'real_training_labels_holdout_gold_predictions_models_or_matrices_read': False, 'actual_reference_fit_or_benchmark_score': 0}
(HERE / 'combined-table-e2e-synthetic-verification-v5.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status': report['status'], 'passed_cases': len(cases)}))
