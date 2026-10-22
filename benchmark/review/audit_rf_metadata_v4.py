"""Frozen RF source/spec audit only: never opens labels, matrices or models."""
import ast
import hashlib
import itertools
import json
from datetime import datetime, timezone
from pathlib import Path

P = Path('/mnt/d/work/科研工作台/research-tasks/peptide-binding-nc-benchmark-20261021')
R = P / 'auxiliary-rf-baseline'
checks = []


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def local(path):
    value = str(path).replace('\\', '/')
    return Path('/mnt/d/' + value[3:] if value.startswith('D:/') else value)


def check(name, result, detail=None):
    checks.append({'check': name, 'passed': bool(result), 'detail': detail})


freeze = read(R / 'SOURCE-FREEZE-v1.json')
check('final_RF_source_freeze_SHA', sha(R / 'SOURCE-FREEZE-v1.json') == '078c507e790140d66e3419246d01d18f6bb2fa785afdb6ef6075cec0df3998ab')
for group in ('source_sha256', 'artifact_sha256', 'all_RF_python_source_sha256'):
    for file, digest in freeze[group].items():
        check('frozen_' + group + ':' + file, sha(R / file) == digest)
for file in freeze['all_RF_python_source_sha256']:
    ast.parse((R / file).read_text())
check('all12_RF_python_sources_AST_parse', len(freeze['all_RF_python_source_sha256']) == 12)
manifest = read(R / 'X-final-manifest-v1.json')
check('fixed_X_metadata_feature_source_bound', manifest['feature_code_sha256'] == sha(R / 'features.py') and manifest['feature_spec_sha256'] == sha(R / 'feature-spec-v1.json') and manifest['installed_assets_sha256'] == sha(R / 'installed-assets-v1.json'))
check('fixed_X_three_datasets_declared_no_labels', {(e['dataset_id'], e['n'], e['dimensions'], e['dtype']) for e in manifest['entries']} == {('PPIKB9619', 9619, 2469, 'float32'), ('external75', 75, 2469, 'float32'), ('supplement13', 13, 2469, 'float32')} and manifest['gold_reads'] == manifest['real_fits'] == manifest['trained_model_reads'] == 0)
assets = read(R / 'installed-assets-v1.json')
params = assets['candidate_profiles']
check('RF_two_explicit_parameter_profiles', [e['candidate_index'] for e in params] == [0, 1] and [e['effective_parameters_seed0']['min_samples_leaf'] for e in params] == [2, 5])
for profile in params:
    value = profile['effective_parameters_seed0']
    check('fixed_RF_profile_' + str(profile['candidate_index']), value['n_estimators'] == 200 and value['max_features'] == 'sqrt' and value['max_depth'] is None and value['bootstrap'] is True and value['n_jobs'] == 1 and value['random_state'] == 0 and set(value) == set(assets['installed_RF_defaults']))
    for key in set(value) - {'n_estimators', 'max_features', 'min_samples_leaf', 'n_jobs', 'random_state'}:
        check('installed_default_profile_' + str(profile['candidate_index']) + ':' + key, value[key] == assets['installed_RF_defaults'][key])
for entry in freeze['raw_sklearn_source'].values():
    check('frozen_sklearn_source_copy:' + str(entry['frozen_copy']), sha(local(entry['frozen_copy'])) == entry['sha256'])
idx = read(R / 'specs-v1/task-spec-index.json')
panels = ('source_peptide_dependency_cold', 'target_reference_homology_cold')
regimes = ('NC_only', 'standard_only')
coords = {(e['panel'], e['regime'], e['seed']) for e in idx['units']}
check('RF40_exact_unique_grid', len(idx['units']) == len(coords) == 40 and coords == set(itertools.product(panels, regimes, range(10))))
check('RF80fit120score53160row_counts', idx['candidate_fit_count'] == 80 and idx['expected_RF_score_count'] == 120 and idx['expected_prediction_rows'] == 53160 and idx['actual_real_RF_fits'] == 0)
for unit in idx['units']:
    path = local(unit['spec_path'])
    check('RF_fit_spec_SHA:' + unit['unit_id'], sha(path) == unit['spec_sha256'])
    spec = read(path)
    check('RF_fit_spec_scope:' + unit['unit_id'], tuple(spec[k] for k in ('panel', 'regime', 'seed')) == tuple(unit[k] for k in ('panel', 'regime', 'seed')) and spec['method_id'] == 'RF-Morgan2-chiral-AAC-DP' and spec['feature_manifest_sha256'] == sha(R / 'X-final-manifest-v1.json') and spec['installed_assets_sha256'] == sha(R / 'installed-assets-v1.json') and spec['candidates'] == [{'candidate_index': 0, 'min_samples_leaf': 2}, {'candidate_index': 1, 'min_samples_leaf': 5}] and spec['real_fit_authorized'] is False)
    for role in ('train', 'validation'):
        expected = P / 'data-protocol/frozen-v1/splits' / spec['panel'] / spec['regime'] / (role + '-ids.json')
        check('RF_frozen_ID_binding:' + unit['unit_id'] + ':' + role, local(spec[role + '_ids']) == expected and sha(expected) == spec[role + '_ids_sha256'] and len(read(expected)) == spec[role + '_n'])
    allowed = P / 'execution/prepared-panels-wsl-v3' / spec['panel']
    check('RF_label_paths_train_val_only:' + unit['unit_id'], local(spec['train_rows']) == allowed / 'train.jsonl' and local(spec['validation_rows']) == allowed / 'validation.jsonl')
score_index = read(R / 'score-specs-v1/score-spec-index.json')
expected_specs = {(p, d) for p in panels for d in ('external75', 'supplement13')} | {(panels[0], 'source_test'), (panels[1], 'target_test')}
check('RF_six_shared_score_specs_exact_grid', len(score_index['entries']) == 6 and {(e['panel'], e['dataset_id']) for e in score_index['entries']} == expected_specs)
for entry in score_index['entries']:
    path = local(entry['score_spec_path']); spec = read(path)
    check('RF_score_spec_SHA:' + path.name, sha(path) == entry['score_spec_sha256'])
    nnpath = local(spec['NN_metadata_source']); nn = read(nnpath)
    check('RF_NN_metadata_source_SHA:' + path.name, sha(nnpath) == spec['NN_metadata_source_sha256'])
    # Gold is compared as declared path/hash metadata only, never opened or rehashed.
    check('RF_NN_score_identity_paths_declared_SHA:' + path.name, spec['dataset_id'] == nn['dataset_id'] == entry['dataset_id'] and spec['panel'] == entry['panel'] and all(local(spec[k]) == local(nn[k]) for k in ('input_rows', 'gold_rows')) and all(spec[k + '_sha256'] == nn[k + '_sha256'] for k in ('input_rows', 'gold_rows')))
    check('RF_score_matrix_dataset_mapping:' + path.name, spec['feature_dataset_id'] == ('PPIKB9619' if spec['dataset_id'] in ('source_test', 'target_test') else spec['dataset_id']) and spec['feature_manifest_sha256'] == sha(R / 'X-final-manifest-v1.json'))
source = (R / 'rf_score.py').read_text()
check('source_gold_hash_after_blind_write_and_proof', source.index("common.write_jsonl(root/'blind-predictions.jsonl'") < source.index("common.write(root/'blind-complete.json'") < source.index("common.require(spec['gold_rows']"))
check('source_joint_before_model_load', source.index('auth,selected=authorize(') < source.index('joblib.load('))
check('source_blind_unchanged_rehashed_before_join', "common.require(root/'blind-predictions.jsonl',blind_sha)" in source)
check('score_and_fit_authorization_examples_unissued', read(R / 'score-authorization.example.json')['root_RF_holdout_score_authorized'] is False and read(R / 'fit-authorization.example.json')['root_real_RF_fit_authorized'] is False)
old_manifest = read(P / 'review/REVIEW-MANIFEST-v3.json')
items = old_manifest['artifacts']
if isinstance(items, dict):
    pairs = [(k, v if isinstance(v, str) else v['sha256']) for k, v in items.items()]
else:
    pairs = [(v['path'], v['sha256']) for v in items]
unchanged = []
for path, digest in pairs:
    resolved = local(path)
    if not resolved.is_absolute():
        resolved = P / 'review' / resolved
    unchanged.append(sha(resolved) == digest)
check('old_v3_nine_artifacts_preserved', len(unchanged) == 9 and all(unchanged))
report = {'schema': 'independent-frozen-RF-source-metadata-review-v4', 'created_at': datetime.now(timezone.utc).isoformat(),
          'status': 'passed' if all(c['passed'] for c in checks) else 'failed', 'checks_count': len(checks), 'checks': checks,
          'source_freeze_sha256': sha(R / 'SOURCE-FREEZE-v1.json'),
          'scope': 'Source, fixed specifications, ID-only lists and declared metadata. No real train/validation rows, holdout gold, feature matrix payload, prediction or selected model read.',
          'real_RF_fit_score_or_reference_runs_by_reviewer': 0, 'claim': 'Prepared source/spec identity and boundary audit, not executed performance validation.',
          'manual_source_review': ['Full supplied graph with assigned chirality; unknown stereo not imputed. Protein prefix cap and denominator explicit.', 'Each candidate fits corresponding regime train only, validates same regime, tie lower index; both candidates retained.', 'Root fit authorization plus CPU-only and fixed source SHA checked before real train rows.', 'Root score authorization plus full recovery-aware joint gate before selected model load. Blind file and zero-gold proof persisted before first gold hash/read.', 'All input subgroup flags preserved, allowing67/8/2 and8/5 independent reports. RF is not a paper reproduction.']}
(P / 'review/auxiliary-RF-source-metadata-review-v4.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'status': report['status'], 'checks': len(checks), 'failed': [c for c in checks if not c['passed']]}, ensure_ascii=False))
raise SystemExit(0 if report['status'] == 'passed' else 1)
