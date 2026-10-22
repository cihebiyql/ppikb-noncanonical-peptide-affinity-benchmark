"""Independent RF120/53160 audit. Preparation is synthetic; real access is gated.

No production metric implementation, sklearn, RDKit, feature matrices or model
weights are imported/read. The preserved independent NumPy numeric helper is
SHA-pinned. RF accounting remains separate from the five-paper NN600 audit.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import importlib.util
import itertools
import json
import math
import os
from pathlib import Path
import statistics
import time

REVIEW = Path(__file__).resolve().parent.parent
P = REVIEW.parent
R = P / 'auxiliary-rf-baseline'
METHOD = 'RF-Morgan2-chiral-AAC-DP'
PANELS = ('source_peptide_dependency_cold', 'target_reference_homology_cold')
REGIMES = ('NC_only', 'standard_only')
METHODS_NN = ('GraphDTA-GIN', 'MGraphDTA', 'DGDTA-CL', 'DeepNC-GEN', 'GS-DTA')
RAW_COUNTS = {'source_test': 1039, 'target_test': 1443, 'external75': 75, 'supplement13': 13}
RAW_ROWS = {'source_test': 20780, 'target_test': 28860, 'external75': 3000, 'supplement13': 520}
NORMALIZED = {'source_test': 'PPIKB-internal', 'target_test': 'PPIKB-internal',
              'external75': 'PTM-external75', 'supplement13': 'IgG-supplement13'}
CANONICAL_HOLDOUT = {'PPIKB-internal': 'internal-test', 'PTM-external75': 'external75-PTM-reference-view-v1',
                     'IgG-supplement13': 'postfreeze-supplement13-reference-view-v1'}
RF_FREEZE_SHA = '078c507e790140d66e3419246d01d18f6bb2fa785afdb6ef6075cec0df3998ab'
NN_INDEX_SHA = 'c7b3bde68c9a741c0ac3f255a825e4a55dd7234e2b4e6d48f212fee8d5609ab1'
HELPER_SHA = 'baf78bfa88bf2ba49fcd1f6baae5560c0d89215934c62236e53e9045d36832c8'
MATCHED_SHA = '60b3d8e00d10f6d6dde0ee645e18715692c8b271c3e4926ca73c40d8aad89099'
MATCHED_EXPECTED = {PANELS[0]: (26, 90, 124), PANELS[1]: (45, 174, 203)}
SUPPLEMENT_SHA = 'eba3933184782b1eed6f178c30edbd4eeb6c9414758adb5584b2acc46beb3c92'
METRICS = ('MAE', 'RMSE', 'Pearson', 'Spearman', 'R2')
STRATA = ('synthetic_D_backbone', 'PTM', 'synthetic_and_PTM', 'other_NC', 'standard20_control')
RAW_EXCLUDED = {'peptide_smiles', 'canonical_isomeric_smiles', 'target_sequence', 'peptide_sequence', 'peptide_sequence_raw'}
GOLD_FIELDS = {'pKd', 'pKd_true', 'p_value', 'value', 'value_raw', 'value_molar', 'affinity', 'gold', 'label', 'y'}
SUBGROUP_SHA = {
    'ids-primary67.json': 'a7fbd733cd2eeb254f2a7f073c3ebf4c4be0be2586f081c39a15331120fb7cff',
    'ids-conditional-sensitivity8.json': 'df4206f0d91106942a05ba2b76389d8b0678d97885b64617632c7103ee4532f6',
    'ids-reference-target-cold2.json': '4ce9d1cf6487dbdb8c755d3f835e6411d2d90208e897c2864ab389eff799b05a',
    'ids-nc8.json': '21561c5995ea66f718ba86eba891560ae2a98ec84ecf256f4ab659d47418ebd7',
    'ids-standard5.json': '33e360fc361d7dab54777d71d524d6adf2914de6106017350810bf31df00cbc5',
}


def local(path):
    value = str(path).replace('\\', '/')
    if os.name != 'nt' and len(value) > 2 and value[1:3] == ':/':
        value = '/mnt/' + value[0].lower() + '/' + value[3:]
    elif os.name == 'nt' and value.startswith('/mnt/') and len(value) > 7 and value[6] == '/':
        value = value[5].upper() + ':' + value[6:]
    return Path(value)


def read(path):
    return json.loads(local(path).read_text(encoding='utf-8-sig'))


def lines(path):
    with local(path).open(encoding='utf-8-sig') as handle:
        return [json.loads(line) for line in handle if line.strip()]


def sha(path):
    digest = hashlib.sha256()
    with local(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1048576), b''):
            digest.update(chunk)
    return digest.hexdigest()


def require(path, digest):
    if sha(path) != digest:
        raise ValueError('SHA mismatch: ' + str(path))


def write(path, value):
    local(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def unique(rows, scope):
    result = {}
    for row in rows:
        key = row['record_id']
        if key in result:
            raise ValueError('Duplicate record_id: ' + scope)
        result[key] = row
    return result


def numeric_helper():
    path = REVIEW / 'recompute_metrics.py'
    require(path, HELPER_SHA)
    spec = importlib.util.spec_from_file_location('independent_numeric_RF_v5', path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    # Private module instance: path decoding only, no change to preserved source.
    helper.local_path = local
    return helper


def authorize(root_auth_path, joint_path, task_map_path):
    """Gate precedes any actual receipt/prediction/label access; never reads weights."""
    auth = read(root_auth_path)
    if auth.get('root_RF_independent_audit_authorized') is not True:
        raise PermissionError('Await new root post-joint independent RF audit authorization')
    if time.time() >= auth.get('deadline_unix', 0):
        raise TimeoutError('Original root absolute deadline reached')
    require(__file__, auth['script_sha256'])
    if auth.get('numeric_helper_sha256') != HELPER_SHA:
        raise ValueError('Independent numeric helper not authorized')
    require(REVIEW / 'recompute_metrics.py', HELPER_SHA)
    require(task_map_path, auth['task_map_sha256'])
    require(joint_path, auth['joint_barrier_sha256'])
    joint = read(joint_path)
    if (joint.get('status'), joint.get('NN_selections'), joint.get('RF_selections')) != ('all_200_NN_plus_40_RF_frozen', 200, 40):
        raise ValueError('Full joint NN200/RF40 barrier required')
    if joint.get('NN_execution_index_sha256') != NN_INDEX_SHA:
        raise ValueError('Wrong recovery-aware NN index')
    require(joint['NN_execution_index_path'], NN_INDEX_SHA)
    approved_index = read(joint['NN_execution_index_path'])
    require(joint['NN_barrier_path'], joint['NN_barrier_sha256'])
    require(joint['RF_barrier_path'], joint['RF_barrier_sha256'])
    nn, rf = read(joint['NN_barrier_path']), read(joint['RF_barrier_path'])
    if (nn.get('status'), nn.get('selection_count'), nn.get('candidate_fit_count'), len(nn.get('selections', []))) != ('all_selections_frozen', 200, 400, 200):
        raise ValueError('Original NN200/400 hard barrier missing')
    if (rf.get('status'), rf.get('selection_count'), rf.get('candidate_fit_count'), len(rf.get('selections', []))) != ('all_40_RF_selections_frozen', 40, 80, 40):
        raise ValueError('RF40/80 barrier missing')
    if nn.get('execution_index_sha256') != NN_INDEX_SHA:
        raise ValueError('NN barrier index differs')
    approved = {str(local(e['selection_path']).resolve()) for e in approved_index['per_seed_selections']}
    actual = {str(local(e['path']).resolve()) for e in nn['selections']}
    if actual != approved or len(actual) != 200:
        raise ValueError('NN selection paths not exactly approved200')
    seen = set()
    for entry in nn['selections']:
        require(entry['path'], entry['sha256']); selected = read(entry['path'])
        key = tuple(selected[k] for k in ('method_id', 'split_id', 'regime', 'seed'))
        if key in seen or selected.get('status') != 'frozen' or selected.get('holdout_metrics_consulted') is not False:
            raise ValueError('Invalid NN metadata selection')
        seen.add(key)
    if seen != set(itertools.product(METHODS_NN, PANELS, REGIMES, range(10))):
        raise ValueError('NN200 exact coordinate grid missing')
    require(R / 'SOURCE-FREEZE-v1.json', RF_FREEZE_SHA)
    freeze = read(R / 'SOURCE-FREEZE-v1.json')
    for name, digest in freeze['source_sha256'].items():
        require(R / name, digest)
    if rf['selections'] != joint.get('RF_selection_entries'):
        raise ValueError('Joint and RF barriers differ')
    selections = {}; keys = set()
    for entry in rf['selections']:
        require(entry['selection_path'], entry['selection_sha256']); selected = read(entry['selection_path'])
        key = tuple(selected[k] for k in ('panel', 'regime', 'seed'))
        if key in keys or selected.get('status') != 'frozen' or selected.get('validation_only') is not True or selected.get('gold_reads') != 0:
            raise ValueError('Invalid RF metadata selection')
        if key != tuple(entry[k] for k in ('panel', 'regime', 'seed')) or selected['source_sha256'] != freeze['source_sha256'] or selected['model_sha256'] != entry['model_sha256']:
            raise ValueError('RF source/coordinate/declared model identity mismatch')
        keys.add(key); selections[entry['selection_sha256']] = {'key': key, 'model_sha256': entry['model_sha256']}
    if keys != set(itertools.product(PANELS, REGIMES, range(10))) or len(selections) != 40:
        raise ValueError('RF40 exact coordinate/selection-hash grid missing')
    return auth, joint, selections, freeze


def validate_blind(inputs, blind, proof, receipt):
    """Blind metadata/proof checks can finish before any sealed gold is opened."""
    ins, bs = unique(inputs, 'input'), unique(blind, 'blind')
    if not ins or set(ins) != set(bs):
        raise ValueError('Input/blind ID coverage differs')
    if receipt['n'] != len(ins) or proof.get('n') != len(ins) or proof.get('status') != 'RF_blind_saved_before_gold_access' or proof.get('gold_reads') != 0:
        raise ValueError('Blind proof count/status/gold boundary differs')
    for rid, inp in ins.items():
        b = bs[rid]
        if GOLD_FIELDS & set(inp) or GOLD_FIELDS & set(b):
            raise ValueError('Input or blind row contains sealed labels')
        retained = {k: v for k, v in inp.items() if k not in RAW_EXCLUDED}
        if set(b) != set(retained) | {'pKd_pred'} or any(b[k] != v for k, v in retained.items()):
            raise ValueError('RF blind metadata changed or subgroup flag dropped')
        if not math.isfinite(float(b['pKd_pred'])):
            raise ValueError('Nonfinite blind prediction')
    return ins, bs


def validate_rows(inputs, blind, predicted, gold, proof, receipt):
    """Pure record-mapping checks, usable with independently constructed fixtures."""
    ins, bs = validate_blind(inputs, blind, proof, receipt)
    ps, gs = unique(predicted, 'joined'), unique(gold, 'gold')
    if set(ins) != set(ps) or not set(ins) <= set(gs):
        raise ValueError('Input/join/gold ID coverage differs')
    rows = []
    for rid, inp in ins.items():
        b, p = bs[rid], ps[rid]
        if set(p) != set(b) | {'pKd_true', 'residual'} or any(p[k] != v for k, v in b.items()):
            raise ValueError('RF predictions/metadata changed when gold joined')
        truth, value = float(gs[rid]['pKd']), float(b['pKd_pred'])
        if not math.isfinite(truth) or not math.isfinite(value) or float(p['pKd_true']) != truth:
            raise ValueError('Nonfinite or mismatched frozen gold/prediction')
        if float(p['residual']) != value - truth:
            raise ValueError('Saved residual differs')
        if type(inp.get('NC_core')) is not bool or inp.get('evaluation_stratum') not in STRATA:
            raise ValueError('Invalid explicit NC/standard stratum')
        if inp['NC_core'] != (inp['evaluation_stratum'] != 'standard20_control'):
            raise ValueError('NC/standard stratum mismatch')
        if not isinstance(inp.get('target_sequence'), str) or not inp['target_sequence']:
            raise ValueError('Full target-reference sequence missing')
        ref = hashlib.sha256(inp['target_sequence'].encode()).hexdigest()
        if inp.get('target_reference_sequence_sha') is not None and inp['target_reference_sequence_sha'] != ref:
            raise ValueError('Declared full reference SHA differs')
        rows.append(dict(inp, pKd_true=truth, pKd_pred=value, target_reference_sequence_sha=ref))
    return rows


def attach_frozen_subgroups(rows, raw_dataset, subgroup_ids):
    ids = {r['record_id'] for r in rows}
    for flag, wanted in subgroup_ids.items():
        wanted = set(wanted)
        if not wanted <= ids:
            raise ValueError('External frozen subgroup outside score IDs')
        for row in rows:
            if flag in row and (type(row[flag]) is not bool or row[flag] != (row['record_id'] in wanted)):
                raise ValueError('Existing external subgroup flag changed')
            if flag not in row:
                # Private audit rows only: frozen ID membership, never gold or predictions.
                row[flag] = row['record_id'] in wanted
    if raw_dataset == 'external75':
        primary, sensitive, cold = (set(subgroup_ids[f]) for f in ('external_primary', 'external_conditional_sensitivity', 'external_reference_target_cold'))
        if (len(rows), len(primary), len(sensitive), len(cold)) != (75, 67, 8, 2) or primary & sensitive or primary | sensitive != ids or not cold <= primary:
            raise ValueError('External67/8/2 partition changed')
        if any(r['evaluation_stratum'] != 'PTM' or r['NC_core'] is not True for r in rows):
            raise ValueError('External75 chemistry changed')
    if raw_dataset == 'supplement13':
        nc, standard = (set(subgroup_ids[f]) for f in ('external_supplement_NC', 'external_supplement_standard'))
        if (len(rows), len(nc), len(standard)) != (13, 8, 5) or nc & standard or nc | standard != ids:
            raise ValueError('Supplement8/5 partition changed')
        if any(r['NC_core'] != (r['record_id'] in nc) for r in rows) or Counter(r['evaluation_stratum'] for r in rows) != {'synthetic_D_backbone': 8, 'standard20_control': 5}:
            raise ValueError('Supplement NC/standard chemistry changed')


def compute_rows(rows, raw_dataset, helper):
    groups = helper.group_metrics(rows, NORMALIZED[raw_dataset])
    for stratum in STRATA:
        subset = [r for r in rows if r['evaluation_stratum'] == stratum]
        groups[stratum] = helper.metrics([r['pKd_true'] for r in subset], [r['pKd_pred'] for r in subset])
    macros = {}
    for name, nc in (('NC_core', True), ('standard', False), ('all_diagnostic', None)):
        subset = [r for r in rows if nc is None or r['NC_core'] is nc]
        clean = [r for r in subset if not helper.is_discordant(r)]
        groups[name + '_exclude_discordant_sensitivity'] = helper.metrics([r['pKd_true'] for r in clean], [r['pKd_pred'] for r in clean])
        macros[name] = {field: helper.macro_metrics(subset, field) for field in ('target_id', 'target_reference_sequence_sha', 'study_id')}
    return groups, macros


def metric_differences(saved, expected):
    differences = []
    for group, values in saved.items():
        if group not in expected:
            raise ValueError('Production group lacks independent definition: ' + group)
        for metric in ('n',) + METRICS:
            a, b = values[metric], expected[group][metric]
            equal = (a is None and b is None) or (a is not None and b is not None and math.isfinite(float(a)) and math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-10))
            if not equal:
                differences.append({'group': group, 'metric': metric, 'saved': a, 'independent': b})
    if not {'all', 'NC_core', 'standard'} <= set(saved):
        raise ValueError('Production RF receipt missing primary groups')
    return differences


def metadata_specs(freeze):
    path = R / 'score-specs-v1/score-spec-index.json'
    require(path, freeze['artifact_sha256']['score-specs-v1/score-spec-index.json'])
    result = {}
    for entry in read(path)['entries']:
        require(entry['score_spec_path'], entry['score_spec_sha256'])
        result[entry['score_spec_sha256']] = read(entry['score_spec_path'])
    if len(result) != 6:
        raise ValueError('Frozen six score-spec metadata not complete')
    return result


def subgroups(raw):
    def frozen_ids(base, pairs):
        result = {}
        for flag, file in pairs:
            require(base / file, SUBGROUP_SHA[file])
            result[flag] = read(base / file)
        return result
    if raw == 'external75':
        base = P / 'external-validation/scoring-views-v1'
        return frozen_ids(base, (
            ('external_primary', 'ids-primary67.json'), ('external_conditional_sensitivity', 'ids-conditional-sensitivity8.json'), ('external_reference_target_cold', 'ids-reference-target-cold2.json')))
    if raw == 'supplement13':
        base = P / 'external-validation/scoring-supplement13-v1'
        require(base / 'root-accepted-manifest.json', SUPPLEMENT_SHA)
        return frozen_ids(base, (('external_supplement_NC', 'ids-nc8.json'), ('external_supplement_standard', 'ids-standard5.json')))
    return {}


def audit_task(task, selections, joint_sha, frozen_specs, helper, matched):
    receipt_path = local(task['score_receipt']); receipt = read(receipt_path)
    if (receipt.get('status'), receipt.get('stage'), receipt.get('method_id')) != ('complete', 'additional_classical_RF_post_joint_barrier_score', METHOD):
        raise ValueError('Not a final RF score receipt')
    if receipt['joint_barrier_sha256'] != joint_sha or receipt['selection_sha256'] not in selections:
        raise ValueError('RF receipt outside authorized joint selections')
    selected = selections[receipt['selection_sha256']]
    key = tuple(receipt[k] for k in ('panel', 'regime', 'seed'))
    if key != selected['key'] or receipt['selected_model_sha256'] != selected['model_sha256']:
        raise ValueError('RF receipt coordinate/declared model identity differs')
    digest = receipt['score_spec_sha256']
    if digest not in frozen_specs:
        raise ValueError('RF score spec not among frozen six')
    require(task['holdout_spec'], digest); spec = read(task['holdout_spec'])
    if spec != frozen_specs[digest] or spec['panel'] != receipt['panel'] or spec['dataset_id'] != receipt['dataset_id'] or receipt['holdout_id'] != spec['dataset_id']:
        raise ValueError('RF score spec dataset/panel identity differs')
    raw = spec['dataset_id']
    if raw not in RAW_COUNTS or (raw == 'source_test' and receipt['panel'] != PANELS[0]) or (raw == 'target_test' and receipt['panel'] != PANELS[1]) or receipt['n'] != RAW_COUNTS[raw]:
        raise ValueError('RF raw dataset count/panel differs')
    if receipt['parameter_updates'] != 0 or receipt['blind_before_gold'] is not True or receipt['paper_count_contribution'] != 0:
        raise ValueError('RF scoring protocol changed')
    if receipt['feature_manifest_sha256'] != spec['feature_manifest_sha256'] or receipt['gold_source_sha256'] != spec['gold_rows_sha256']:
        raise ValueError('RF feature/gold source metadata binding differs')
    if receipt['source_sha256'] != read(R / 'SOURCE-FREEZE-v1.json')['source_sha256']:
        raise ValueError('RF receipt source changed')
    blind_path = receipt_path.parent / 'blind-predictions.jsonl'
    require(blind_path, receipt['blind_predictions_sha256'])
    proof = read(receipt_path.parent / 'blind-complete.json')
    if proof.get('blind_sha256') != receipt['blind_predictions_sha256'] or proof.get('status') != 'RF_blind_saved_before_gold_access' or proof.get('gold_reads') != 0 or proof.get('n') != receipt['n']:
        raise ValueError('Blind proof SHA differs')
    # Verify persisted blind evidence and metadata before opening the gold source.
    blind = lines(blind_path)
    require(spec['input_rows'], spec['input_rows_sha256']); inputs = lines(spec['input_rows'])
    validate_blind(inputs, blind, proof, receipt)
    pred_path = receipt_path.parent / 'predictions.jsonl'
    require(pred_path, receipt['predictions_sha256']); predictions = lines(pred_path)
    require(spec['gold_rows'], spec['gold_rows_sha256']); gold = lines(spec['gold_rows'])
    rows = validate_rows(inputs, blind, predictions, gold, proof, receipt)
    attach_frozen_subgroups(rows, raw, subgroups(raw))
    grouped, macros = compute_rows(rows, raw, helper)
    dataset = NORMALIZED[raw]
    identity = dict(method_id=METHOD, split_id=receipt['panel'], regime=receipt['regime'], seed=receipt['seed'], dataset_id=dataset, holdout_id=CANONICAL_HOLDOUT[dataset])
    result = {'category': 'auxiliary_handcrafted_RF', 'paper_count_contribution': 0, 'identity': identity,
              'raw_scoring_dataset_id': raw, 'n': len(rows), 'score_receipt': str(receipt_path), 'score_receipt_sha256': sha(receipt_path),
              'metrics': grouped, 'cohort_macros': macros, 'source_refs': sorted({str(r.get('study_id') or '__missing__') for r in rows}),
              'source_ref_scope': 'Machine study_id references, not independently certified papers or biological experiments.',
              'runner_metric_differences': metric_differences(receipt['metrics'], grouped),
              'all_truths_match_frozen_gold': True, 'blind_before_gold_proof_verified': True,
              'selected_model_payload_opened': False, 'numeric_helper_sha256': HELPER_SHA}
    if raw in ('source_test', 'target_test'):
        diagnostic = helper.matched_target_metrics(rows, receipt['panel'], matched)
        expected = MATCHED_EXPECTED[receipt['panel']]
        actual = (diagnostic['same_fixed_reference_target_count'], diagnostic['cohorts']['NC_matched']['n'], diagnostic['cohorts']['standard_matched']['n'])
        if actual != expected:
            raise ValueError('Frozen matched26/45 NC/standard cohort counts changed')
        result['matched_target_diagnostics'] = diagnostic
    return result


def completeness(records):
    expected = {(p, r, s, d) for p in PANELS for r in REGIMES for s in range(10)
                for d in (('source_test' if p == PANELS[0] else 'target_test'), 'external75', 'supplement13')}
    keys = [(x['identity']['split_id'], x['identity']['regime'], x['identity']['seed'], x['raw_scoring_dataset_id']) for x in records]
    count = Counter()
    for row in records:
        count[row['raw_scoring_dataset_id']] += row['n']
    return {'expected_score_receipts': 120, 'actual_score_receipts': len(records), 'unique_score_coordinates': len(set(keys)),
            'missing': sorted(expected - set(keys)), 'extra': sorted(set(keys) - expected),
            'expected_prediction_rows_by_raw_dataset': RAW_ROWS, 'actual_prediction_rows_by_raw_dataset': dict(count),
            'expected_total_prediction_rows': 53160, 'actual_total_prediction_rows': sum(count.values()),
            'complete120_53160': len(keys) == len(set(keys)) == 120 and set(keys) == expected and dict(count) == RAW_ROWS}


def table_rows(records, category='auxiliary_handcrafted_RF'):
    result = []
    for record in records:
        identity = record['identity']
        # Metric rows never add papers; paper count is five DISTINCT NN methods.
        base = dict(category=category, paper_count_contribution=0,
                    prior_paper_method_id=identity['method_id'] if category == 'five_prior_paper_NN' else None,
                    dataset_id=identity['dataset_id'], raw_dataset_id=record.get('raw_scoring_dataset_id', identity.get('holdout_id')),
                    panel=identity['split_id'], method_id=identity['method_id'], regime=identity['regime'], seed=identity['seed'])
        for scope, values in record['metrics'].items():
            for metric in METRICS:
                result.append(dict(base, cohort=scope, aggregation='row_micro', metric=metric, value=values[metric], n=values['n'], n_unit='observation_rows', defined_group_count=None))
        for cohort, fields in record.get('cohort_macros', {}).items():
            for field, macro in fields.items():
                for metric in METRICS:
                    result.append(dict(base, cohort=cohort, aggregation='equal_weight_' + field, metric=metric, value=macro['macro_mean'][metric], n=macro['group_count'], n_unit=field + '_groups', defined_group_count=macro['defined_group_counts'][metric]))
        for cohort, data in record.get('matched_target_diagnostics', {}).get('cohorts', {}).items():
            choices = [('matched_row_micro', data['row_micro_metrics'], data['n'], 'observation_rows', {}),
                       ('matched_equal_target_reference', data['target_reference_equal_weight_macro']['macro_mean'], data['target_count'], 'target_reference_groups', data['target_reference_equal_weight_macro']['defined_group_counts']),
                       ('matched_equal_study_id', data['study_id_equal_weight_macro']['macro_mean'], data['study_id_equal_weight_macro']['group_count'], 'study_id_groups', data['study_id_equal_weight_macro']['defined_group_counts'])]
            for aggregation, values, n, unit, defined in choices:
                for metric in METRICS:
                    result.append(dict(base, cohort=cohort, aggregation=aggregation, metric=metric, value=values[metric], n=n, n_unit=unit, defined_group_count=defined.get(metric)))
    return result


def summarize_table(rows):
    grouped = defaultdict(list)
    fields = ('category', 'dataset_id', 'panel', 'method_id', 'regime', 'cohort', 'aggregation', 'metric')
    for row in rows:
        grouped[tuple(row[k] for k in fields)].append(row)
    result = []
    for key, values in sorted(grouped.items()):
        seeds = [r['seed'] for r in values]
        if len(seeds) != len(set(seeds)) or set(seeds) != set(range(10)):
            raise ValueError('Per-metric table must contain exactly ten unique seeds')
        numeric = [float(r['value']) for r in values if r['value'] is not None]
        if not all(math.isfinite(v) for v in numeric):
            raise ValueError('Nonfinite per-seed metric')
        result.append(dict(zip(fields, key), completed_seed_count=10, defined_seed_count=len(numeric),
                           mean=statistics.mean(numeric) if numeric else None, sample_sd=statistics.stdev(numeric) if len(numeric) > 1 else None,
                           n_min=min(r['n'] for r in values), n_max=max(r['n'] for r in values), n_unit=values[0]['n_unit'],
                           defined_group_count_by_seed={str(r['seed']): r['defined_group_count'] for r in values},
                           variability_scope='Training-seed variation, not biological confidence intervals.'))
    return result


def write_csv(path, rows):
    fields = sorted({k for row in rows for k in row})
    with local(path).open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in row.items()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root-authorization', required=True)
    parser.add_argument('--joint-barrier', required=True)
    parser.add_argument('--task-map', required=True, help='Explicit120 {score_receipt,holdout_spec}; no directory scan')
    parser.add_argument('--matched-target-manifest', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    auth, joint, selections, freeze = authorize(args.root_authorization, args.joint_barrier, args.task_map)
    helper = numeric_helper()
    require(args.matched_target_manifest, MATCHED_SHA)
    matched = helper.load_matched_manifest(args.matched_target_manifest, MATCHED_SHA)
    specs = metadata_specs(freeze)
    tasks = read(args.task_map)
    if len(tasks) != 120:
        raise ValueError('Exactly120 explicitly listed RF audit tasks required')
    if len({str(local(t['score_receipt']).resolve()) for t in tasks}) != 120:
        raise ValueError('Repeated RF score-receipt paths')
    out = local(args.output); out.mkdir(parents=True, exist_ok=False)
    records = []
    for task in tasks:
        if time.time() >= auth['deadline_unix']:
            raise TimeoutError('Root absolute deadline reached during RF audit')
        records.append(audit_task(task, selections, auth['joint_barrier_sha256'], specs, helper, matched))
    shape = completeness(records)
    write(out / 'per-score-audit.json', records)
    per_seed = table_rows(records); summary = summarize_table(per_seed)
    write(out / 'per-seed-table.json', per_seed); write_csv(out / 'per-seed-table.csv', per_seed)
    write(out / 'mean-sampleSD-table.json', summary); write_csv(out / 'mean-sampleSD-table.csv', summary)
    write(out / 'independent-matched-target-summary.json', helper.summarize_matched_targets(records))
    differences = sum(len(r['runner_metric_differences']) for r in records)
    status = 'complete_independent_RF_audit' if shape['complete120_53160'] and not differences else 'RF_audit_requires_review'
    report = dict(shape, status=status,
                  category='auxiliary_handcrafted_RF', paper_count_contribution=0, NN600_denominator_unchanged=True,
                  references360_denominator_unchanged=True, metric_difference_count=differences,
                  joint_barrier_sha256=auth['joint_barrier_sha256'], task_map_sha256=auth['task_map_sha256'],
                  numeric_helper_sha256=HELPER_SHA, script_sha256=sha(__file__), selected_model_payloads_read=0,
                  raw_feature_matrices_read=0, fitting_or_hyperparameter_selection=0, source_ref_scope='Machine study IDs do not certify independent studies.',
                  blind_order_evidence='Persisted proof and file SHA plus independently reviewed source control flow; not an independent operating-system access trace.',
                  seed_SD_scope='Training repetition only; no biological CI.',
                  external_scope='75PTM split67primary/8sensitivity/2referencecold(not familycold); separate13=8nonPTM+5standard, one target-related study.',
                  per_score_audit_sha256=sha(out / 'per-score-audit.json'), per_seed_table_sha256=sha(out / 'per-seed-table.json'),
                  summary_table_sha256=sha(out / 'mean-sampleSD-table.json'))
    write(out / 'independent-RF-audit-manifest.json', report)
    if not shape['complete120_53160']:
        raise ValueError('RF120 completeness failure retained in report')
    if differences:
        raise ValueError('RF metric discrepancies retained for review')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
