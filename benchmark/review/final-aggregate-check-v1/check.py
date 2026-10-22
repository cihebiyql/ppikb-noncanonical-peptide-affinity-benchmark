"""Independent final aggregate-only acceptance. No raw gold/prediction/model IO."""
import hashlib
import itertools
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

P = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent
B = P / 'reporting/final-v1'
METRICS = ('MAE', 'RMSE', 'Pearson', 'Spearman', 'R2')
PANELS = ('source_peptide_dependency_cold', 'target_reference_homology_cold')
REGIMES = ('NC_only', 'standard_only')
NN = ('GraphDTA-GIN', 'MGraphDTA', 'DGDTA-CL', 'DeepNC-GEN', 'GS-DTA')
RF = 'RF-Morgan2-chiral-AAC-DP'
REFS = ('reference:train_mean', 'reference:train_median', 'reference:target_reference_train_median')
CATEGORIES = {'five_prior_paper_NN': set(NN), 'auxiliary_handcrafted_RF': {RF}, 'three_deterministic_references': set(REFS)}
FIELDS = ('category', 'dataset_id', 'panel', 'method_id', 'regime', 'cohort', 'aggregation', 'metric')
checks = []; differences = []


def read(file): return json.loads(Path(file).read_text(encoding='utf-8-sig'))
def sha(file): return hashlib.sha256(Path(file).read_bytes()).hexdigest()
def check(name, value, detail=None): checks.append(dict(item=name, passed=bool(value), detail=detail))
def same(a, b):
    if a is None or b is None: return a is None and b is None
    return math.isfinite(float(a)) and math.isfinite(float(b)) and math.isclose(float(a), float(b), rel_tol=1e-10, abs_tol=1e-12)
def bound(ref):
    if sha(ref['path']) != ref['sha256']: raise ValueError('Source digest mismatch: ' + ref['path'])
    return read(ref['path'])


summary, rows, coverage, receipt = (read(B / f) for f in ('summary.json', 'metrics-per-seed.json', 'coverage.json', 'report-receipt.json'))
review = read(P / 'review/root-final-summary-review-v1.json')
check('summary_expected_SHA', sha(B / 'summary.json') == 'e5f5d346c5a5ed2de98cdccd8142cbf2e0c0299df02ca7250556cca27c2ba000')
check('root_review_expected_SHA', sha(P / 'review/root-final-summary-review-v1.json') == '8f4c9879ce356ddce03451bb2b5bf2798c503828ebc7587efd6665a6900d188f')
check('root_summary_and_report_receipt_bound', review['source_summary']['sha256'] == sha(B / 'summary.json') and review['source_report_receipt']['sha256'] == sha(B / 'report-receipt.json'))
check('actual_summary_rows_11540', len(summary) == 11540, len(summary))
check('actual_per_seed_rows_115400', len(rows) == 115400, len(rows))
groups = defaultdict(list)
for row in rows:
    groups[tuple(row[k] for k in FIELDS)].append(row)
check('summary_unique_keys_match_per_seed', len({tuple(r[k] for k in FIELDS) for r in summary}) == len(summary) == len(groups) and {tuple(r[k] for k in FIELDS) for r in summary} == set(groups))
for record in summary:
    key = tuple(record[k] for k in FIELDS); values = groups[key]
    byseed = {r['seed']: r for r in values}
    if len(values) != 10 or set(byseed) != set(range(10)) or record['completed_seed_count'] != 10 or record['missing_seeds']:
        differences.append({'identity': key, 'problem': 'ten_seed_grid'})
        continue
    numbers = [float(r['value']) for r in values if r['value'] is not None]
    if not all(math.isfinite(x) for x in numbers):
        differences.append({'identity': key, 'problem': 'nonfinite'}); continue
    # Independently center on the first value: identical deterministic values
    # must have SD0 even when their large sum/n rounds by one ULP.
    shifts = [v - numbers[0] for v in numbers] if numbers else []
    mean_shift = math.fsum(shifts) / len(numbers) if numbers else None
    mean = numbers[0] + mean_shift if numbers else None
    sd = math.sqrt(math.fsum((v - mean_shift) ** 2 for v in shifts) / (len(numbers) - 1)) if len(numbers) > 1 else None
    if record['defined_seed_count'] != len(numbers) or not same(record['mean'], mean) or not same(record['sample_sd'], sd):
        differences.append({'identity': key, 'problem': 'mean_sampleSD_defined_null', 'independent_mean': mean, 'independent_SD': sd})
    for seed, r in byseed.items():
        if not same(record['values_by_seed'][str(seed)], r['value']) or record['n_by_seed'][str(seed)] != r['n'] or record['defined_group_count_by_seed'][str(seed)] != r['defined_group_count'] or record['n_unit'] != r['n_unit']:
            differences.append({'identity': key, 'seed': seed, 'problem': 'per_seed_value_n_defined_group_mapping'})
check('all_11540_mean_SD_null_and_seed_mappings_independently_verified', not differences, {'differences': len(differences), 'tolerance': 'relative1e-10/absolute1e-12; null exact'})
check('six_trainable_and_five_prior_papers_plus_RF0', {r['method_id'] for r in rows if r['category'] != 'three_deterministic_references'} == set(NN) | {RF} and {r['method_id'] for r in rows if r['category'] == 'five_prior_paper_NN'} == set(NN) and all(r['paper_count_contribution'] == 0 for r in rows))
check('all_method_category_identities_valid', all(r['category'] in CATEGORIES and r['method_id'] in CATEGORIES[r['category']] for r in rows))
check('defined_group_counts_valid_or_null', all(r['defined_group_count'] is None or (type(r['defined_group_count']) is int and 0 <= r['defined_group_count'] <= r['n']) for r in rows))
reference_summaries = [r for r in summary if r['category'] == 'three_deterministic_references']
check('deterministic_references_values_identical_and_SD0_or_null', all(r['sample_sd'] in (None, 0) and len(set(r['values_by_seed'].values())) == 1 for r in reference_summaries))
score_rows = [r for r in rows if r['cohort'] == 'all' and r['aggregation'] == 'row_micro' and r['metric'] == 'MAE']
derived = {}
for category, methods in CATEGORIES.items():
    values = [r for r in score_rows if r['category'] == category]
    keys = [(r['method_id'], r['panel'], r['regime'], r['seed'], r['dataset_id']) for r in values]
    expected = set(itertools.product(methods, PANELS, REGIMES, range(10), ('PPIKB-internal', 'PTM-external75', 'IgG-supplement13')))
    derived[category] = {'score_receipts': len(values), 'prediction_rows': sum(r['n'] for r in values), 'grid_complete': len(keys) == len(set(keys)) and set(keys) == expected}
    c = coverage[category]
    check('independent_coverage:' + category, derived[category]['grid_complete'] and len(values) == c['expected_scores'] == c['actual_complete_score_metric_sets'] and derived[category]['prediction_rows'] == c['expected_prediction_rows'] == c['actual_complete_prediction_rows'] and c['complete'] and c['missing_metric_coordinates'] == 0)
check('global_score_ledger_1080_rows478440', sum(v['score_receipts'] for v in derived.values()) == 1080 and sum(v['prediction_rows'] for v in derived.values()) == 478440)

index = {tuple(r[k] for k in FIELDS): r for r in summary}
def require_cohort(dataset, cohort, aggregation, expected_n_by_panel=None):
    missing = []; bad_n = []
    for category, methods in CATEGORIES.items():
        for method, panel, regime, metric in itertools.product(methods, PANELS, REGIMES, METRICS):
            key = (category, dataset, panel, method, regime, cohort, aggregation, metric)
            record = index.get(key)
            if record is None: missing.append(key)
            elif expected_n_by_panel is not None and set(record['n_by_seed'].values()) != {expected_n_by_panel[panel]}: bad_n.append(key)
    check('coverage:' + dataset + ':' + cohort + ':' + aggregation, not missing and not bad_n, {'missing': len(missing), 'bad_denominators': len(bad_n)})

internal = {
 'NC_core': (303, 332), 'standard': (736, 1111), 'NC_core_exclude_discordant_sensitivity': (274, 261), 'standard_exclude_discordant_sensitivity': (724, 1067),
 'synthetic_D_backbone': (100, 93), 'PTM': (158, 190), 'synthetic_and_PTM': (39, 37), 'other_NC': (6, 12)}
for cohort, n in internal.items(): require_cohort('PPIKB-internal', cohort, 'row_micro', dict(zip(PANELS, n)))
for cohort in ('NC_core', 'synthetic_D_backbone', 'PTM', 'synthetic_and_PTM', 'other_NC', 'standard'):
    for agg in ('equal_weight_target_reference_sequence_sha', 'equal_weight_study_id'): require_cohort('PPIKB-internal', cohort, agg)
for cohort, n in (('NC_matched', (90, 174)), ('standard_matched', (124, 203))):
    require_cohort('PPIKB-internal', cohort, 'matched_row_micro', dict(zip(PANELS, n)))
    require_cohort('PPIKB-internal', cohort, 'matched_equal_target_reference', dict(zip(PANELS, (26, 45))))
    require_cohort('PPIKB-internal', cohort, 'matched_equal_study_id')
for cohort, n in (('external_primary67', 67), ('external_conditional_sensitivity8', 8), ('external_reference_target_cold2', 2)):
    require_cohort('PTM-external75', cohort, 'row_micro', dict.fromkeys(PANELS, n))
for cohort, n in (('supplement_NC8', 8), ('supplement_standard5', 5)):
    require_cohort('IgG-supplement13', cohort, 'row_micro', dict.fromkeys(PANELS, n))
main = [r for r in summary if r['category'] != 'three_deterministic_references' and r['dataset_id'] == 'PPIKB-internal' and r['cohort'] == 'NC_core' and r['aggregation'] == 'row_micro' and r['metric'] == 'MAE']
check('primary_trainable_MAE24_and_n303332', len(main) == 24 and all(set(r['n_by_seed'].values()) == {dict(zip(PANELS, (303, 332)))[r['panel']]} for r in main))
baseline = next(r for r in summary if r['method_id'] == 'reference:train_median' and r['panel'] == PANELS[0] and r['regime'] == 'standard_only' and r['dataset_id'] == 'PPIKB-internal' and r['cohort'] == 'NC_core' and r['aggregation'] == 'row_micro' and r['metric'] == 'MAE')
source_main = [r for r in main if r['panel'] == PANELS[0]]; target_main = [r for r in main if r['panel'] == PANELS[1]]
best = min(target_main, key=lambda r: r['mean'])
check('source_all12_trainable_MAE_worse_than_standard_train_median', len(source_main) == 12 and all(r['mean'] > baseline['mean'] for r in source_main) and round(baseline['mean'], 4) == 1.3178)
check('target_lowest_displayed_mean_DeepNC_NC_1_2978', best['method_id'] == 'DeepNC-GEN' and best['regime'] == 'NC_only' and round(best['mean'], 4) == 1.2978)
ready = bound(review['independent_pipeline']); unified = bound(ready['actual_unified_manifest'])
nn = bound(ready['NN_audit_manifest']); rf = bound(ready['RF_audit_manifest']); refs = bound(ready['reference_run_manifest'])
check('audited_manifests_complete_zero_metric_discrepancies', nn['complete600_scores_265800_rows'] and nn['metric_difference_count'] == 0 and rf['complete120_53160'] and rf['metric_difference_count'] == 0 and refs['score_receipts'] == 360 and refs['prediction_rows_total'] == 159480)
check('report_bound_to_actual_unified_v6', receipt['provenance']['audited_manifest_sha256'] == ready['actual_unified_manifest']['sha256'] and unified['schema_version'] == 6 and unified['ledger_score_receipts'] == 1080 and unified['ledger_prediction_rows'] == 478440 and unified['distinct_prior_paper_methods'] == 5)
check('report_per_seed_is_byte_bound_unified_table', unified['per_seed_table_sha256'] == sha(B / 'metrics-per-seed.json'))
for file in ('summary.json', 'metrics-per-seed.json', 'coverage.json', '完整报告.md'):
    check('report_receipt_artifact:' + file, receipt['artifacts'][file] == sha(B / file))
text = (B / '完整报告.md').read_text(encoding='utf-8-sig')
training_note = {'metric_report_optional_paragraph': 'Original metric-only report still says training metadata awaits authorization.',
    'actual_supplements': ['reporting/training-metadata-v1', 'reporting/training-logs-v1'],
    'evidence': review['optional_training_metadata'],
    'scope': 'The two independently bound training reports supplement/supersede the optional historical paragraph; this aggregate checker did not read/recompute raw training logs.'}
report = dict(schema='independent-final-aggregate-acceptance.v1', created_utc=datetime.now(timezone.utc).isoformat(),
    status='PASS' if all(c['passed'] for c in checks) else 'REQUIRES_REVIEW', checks=checks, check_count=len(checks),
    summary_rows=len(summary), per_seed_rows=len(rows), summary_statistic_or_mapping_differences=differences,
    all_11540_groups_have10_actual_seeds=all(len(v) == 10 and {r['seed'] for r in v} == set(range(10)) for v in groups.values()),
    primary_trainable_MAE_groups=len(main), independent_coverage=derived,
    source_standard_training_median_MAE=baseline['mean'], source_trainable12_all_worse=True if all(r['mean'] > baseline['mean'] for r in source_main) else False,
    target_lowest_displayed_trainable_mean={k: best[k] for k in ('method_id', 'regime', 'mean', 'sample_sd')},
    training_metadata_supplement_note=training_note,
    interpretation='Descriptive aggregate comparison only. No significance test, causal inference, universal superiority or biological confidence interval claim. Source all12 trainable means exceed the fixed standard-training median; target minimum is a displayed-table minimum, not a posthoc validated winner.',
    sources=[{'path': str(B / f), 'sha256': sha(B / f)} for f in ('summary.json', 'metrics-per-seed.json', 'coverage.json', 'report-receipt.json', '完整报告.md')],
    root_review_sha256=sha(P / 'review/root-final-summary-review-v1.json'),
    read_scope='Authorized aggregate metrics and closed audit manifests only; no raw prediction, gold, model, matrix or raw training log opened. No scoring/retraining/source changes.',
    actual_score_or_model_calls=0)
(OUT / 'aggregate-acceptance.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
print(json.dumps({'status': report['status'], 'checks': len(checks), 'failed': [c for c in checks if not c['passed']], 'stat_differences': len(differences), 'source_median': baseline['mean'], 'target_min': report['target_lowest_displayed_trainable_mean']}, ensure_ascii=False))
