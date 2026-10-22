"""Pure-metric v5 base + declared v6 extension merge; no raw prediction reads."""
import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).parent
loader = importlib.util.spec_from_file_location('NC_metric_extension_v6_utilities', HERE / 'nc_scope_extension_v6.py')
ext = importlib.util.module_from_spec(loader); loader.loader.exec_module(ext)
v5 = ext.v5
FIELDS = ('category', 'dataset_id', 'panel', 'method_id', 'regime', 'seed', 'cohort', 'aggregation', 'metric')


def merge_rows(base, extra):
    result = list(base); lookup = {}
    for row in base:
        key = tuple(row[k] for k in FIELDS)
        if key in lookup:
            raise ValueError('Duplicate base metric key')
        lookup[key] = row
    duplicates = 0
    for row in extra:
        key = tuple(row[k] for k in FIELDS)
        if row['category'] not in ('five_prior_paper_NN', 'auxiliary_handcrafted_RF', 'three_deterministic_references') or row['dataset_id'] != 'PPIKB-internal' or row.get('additional_score_count', 0) != 0:
            raise ValueError('Out-of-scope metric extension')
        micro = row['cohort'] in ('NC_core_exclude_discordant_sensitivity', 'standard_exclude_discordant_sensitivity') and row['aggregation'] == 'row_micro'
        macro = row['cohort'] in ext.MACRO_COHORTS and row['aggregation'] in ('equal_weight_target_reference_sequence_sha', 'equal_weight_study_id')
        if not (micro or macro):
            raise ValueError('Unregistered diagnostic cohort/aggregation')
        if key in lookup:
            old = lookup[key]
            if any(old.get(k) != row.get(k) for k in ('value', 'n', 'n_unit', 'defined_group_count')):
                raise ValueError('Conflicting duplicate metric key')
            duplicates += 1
        else:
            lookup[key] = row; result.append(row)
    return result, duplicates


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ('root-authorization', 'joint-barrier', 'input-map', 'output'):
        parser.add_argument('--' + field, required=True)
    args = parser.parse_args(); auth = v5.read(args.root_authorization)
    if auth.get('root_NC_metric_merge_authorized') is not True:
        raise PermissionError('Await explicit post-joint metric-merge authorization')
    v5.require(__file__, auth['merge_script_sha256'])
    v5.require(HERE / 'nc_scope_extension_v6.py', auth['extension_script_sha256'])
    v5.require(HERE / 'recompute_RF_v5.py', ext.V5_SHA)
    auth, joint, _, _ = v5.authorize(args.root_authorization, args.joint_barrier, args.input_map)
    inputs = v5.read(args.input_map); base = ext.bound(inputs['base_v5_manifest']); extension = ext.bound(inputs['v6_extension_manifest'])
    if base.get('status') != 'complete_postjoint_metric_table_assembly' or (base['ledger_score_receipts'], base['ledger_prediction_rows'], base['distinct_prior_paper_methods']) != (1080, 478440, 5):
        raise ValueError('Complete v5 base metric assembly required')
    if extension.get('status') != 'complete_metric_only_NC_scope_extension' or (extension['diagnostic_cases'], extension['additional_scores'], extension['additional_prediction_rows']) != (360, 0, 0):
        raise ValueError('Complete v6 diagnostic supplement required')
    if base['joint_barrier_sha256'] != auth['joint_barrier_sha256'] or extension['joint_barrier_sha256'] != auth['joint_barrier_sha256']:
        raise ValueError('Different joint barrier')
    base_path = v5.local(inputs['base_v5_manifest']['path']).parent / 'unified-per-seed-metrics.json'
    extra_path = v5.local(inputs['v6_extension_manifest']['path']).parent / 'extension-long-metrics.json'
    v5.require(base_path, base['per_seed_table_sha256']); v5.require(extra_path, extension['long_metrics_sha256'])
    old_rows = v5.read(base_path); extra_rows = v5.read(extra_path); rows, dedup = merge_rows(old_rows, extra_rows)
    if len(extra_rows) != 25200 or dedup != 1200 or len(rows) - len(old_rows) != 24000:
        raise ValueError('Expected25200 diagnostic metric rows,1200 equal RF duplicates,24000 new metric keys')
    if rows[:len(old_rows)] != old_rows:
        raise ValueError('Base rows altered')
    # No added all/row_micro scores: original completeness/rows remain exact.
    def all_keys(rs):
        return [tuple(r[k] for k in FIELDS) for r in rs if r['cohort'] == 'all' and r['aggregation'] == 'row_micro']
    if all_keys(rows) != all_keys(old_rows):
        raise ValueError('Diagnostic rows changed original scoring denominator')
    summary = v5.summarize_table(rows)
    out = v5.local(args.output); out.mkdir(parents=True, exist_ok=False)
    v5.write(out / 'unified-per-seed-metrics.json', rows); v5.write_csv(out / 'unified-per-seed-metrics.csv', rows)
    v5.write(out / 'unified-mean-sampleSD-metrics.json', summary); v5.write_csv(out / 'unified-mean-sampleSD-metrics.csv', summary)
    manifest = dict(base)
    manifest.update(schema='postjoint_metric_table_assembly_with_preregistered_extension_v6', schema_version=6,
                    status='complete_postjoint_metric_table_assembly', generated_by='review/merge_metric_extension_v6.py',
                    basis='Unchanged independently audited v5 base plus preregistered v6 metric-only diagnostic extension; not output of the old v5 generator.',
                    original_v5_manifest=inputs['base_v5_manifest'], v6_extension_manifest=inputs['v6_extension_manifest'],
                    original_v5_rows_sha256=base['per_seed_table_sha256'], original_v5_row_count=len(old_rows),
                    original_v5_rows_preserved_verbatim_values=True, extension_diagnostic_cases=360, additional_scores=0,
                    additional_prediction_rows=0, extension_metric_rows=len(extra_rows), equal_duplicate_keys_deduplicated=dedup,
                    per_seed_table_sha256=v5.sha(out / 'unified-per-seed-metrics.json'), summary_table_sha256=v5.sha(out / 'unified-mean-sampleSD-metrics.json'),
                    script_sha256=v5.sha(__file__), raw_gold_predictions_models_or_feature_matrices_read_by_merge=False,
                    missing_source_metadata='Explicit missing_source_refs/counts stay in bound v6 case sidecars; canonical columns match frozen reporting v1.',
                    generic_status_scope='Complete assembly is a truthful cross-version state; schema_version6, generator and both source manifests remain explicit.',
                    RF_scope='Original RF rows preserved; forty existing internal prediction cases add fourNC-stratum macros. Existing RF NCclean/standardclean and NC/standard macros match exactly and equal duplicate keys deduplicate; no new RF score or prediction.')
    v5.write(out / 'unified-table-manifest.json', manifest)


if __name__ == '__main__':
    main()
