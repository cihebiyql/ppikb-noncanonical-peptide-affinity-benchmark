"""Root-only postscore orchestration; metrics are delegated to frozen scripts.

Preparation never reads actual issuance, selections, predictions, labels, weights
or matrices. Real runs use Windows Python; WSL runs only the original joint
metadata preflight, followed by unchanged Windows numerical CLIs.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
REVIEW = HERE.parent
PROJECT = REVIEW.parent
DEADLINE = datetime.fromisoformat('2026-10-22T01:45:00+00:00').timestamp()
PANELS = ('source_peptide_dependency_cold', 'target_reference_homology_cold')
REGIMES = ('NC_only', 'standard_only')
NN_METHODS = ('GraphDTA-GIN', 'MGraphDTA', 'DGDTA-CL', 'DeepNC-GEN', 'GS-DTA')
RF_METHOD = 'RF-Morgan2-chiral-AAC-DP'
RULES = ('train_mean', 'train_median', 'target_reference_train_median')
RAW_N = {'source_test': 1039, 'target_test': 1443, 'external75': 75, 'supplement13': 13}
NORMALIZED = {'source_test': 'PPIKB-internal', 'target_test': 'PPIKB-internal', 'external75': 'PTM-external75', 'supplement13': 'IgG-supplement13'}


def path(value):
    value = str(value).replace('\\', '/')
    if os.name == 'nt' and value.startswith('/mnt/') and len(value) > 7 and value[6] == '/':
        value = value[5].upper() + ':' + value[6:]
    elif os.name != 'nt' and len(value) > 2 and value[1:3] == ':/':
        value = '/mnt/' + value[0].lower() + '/' + value[3:]
    return Path(value)


def wsl(value):
    value = str(path(value).resolve()).replace('\\', '/')
    if len(value) > 2 and value[1:3] == ':/':
        return '/mnt/' + value[0].lower() + '/' + value[3:]
    return value


def sha(value):
    h = hashlib.sha256()
    with path(value).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1048576), b''):
            h.update(chunk)
    return h.hexdigest()


def read(value):
    return json.loads(path(value).read_text(encoding='utf-8-sig'))


def ref(value):
    return {'path': str(path(value).resolve()), 'sha256': sha(value)}


def bound(entry):
    if sha(entry['path']) != entry['sha256']:
        raise ValueError('Metadata SHA differs: ' + entry['path'])
    return read(entry['path'])


def write_new(file, data):
    file = path(file); file.parent.mkdir(parents=True, exist_ok=True)
    with file.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False); handle.write('\n')
    return ref(file)


def exact_grid(keys, family):
    expected = {(m, p, r, s) for m in NN_METHODS for p in PANELS for r in REGIMES for s in range(10)} if family == 'NN' else {(RF_METHOD, p, r, s) for p in PANELS for r in REGIMES for s in range(10)}
    if len(keys) != len(expected) or set(keys) != expected:
        raise ValueError('Issued coordinate grid incomplete or duplicate: ' + family)


def mapper(issuance, top_proofs):
    """Metadata-only deterministic720 mapping, exclusively via issued bindings."""
    if issuance.get('schema') != 'postjoint-240-stage-issuance.v1' or issuance.get('stage_contracts') != {'NN': 200, 'RF': 40}:
        raise ValueError('Real root-issued240-stage issuance required')
    maps = {'NN': [], 'RF': []}; internal = []; references = {}; counts = Counter(); unique_scores = set()
    for family in ('NN', 'RF'):
        pool_ref = issuance['pools'][family]; pool = bound(pool_ref); proof = bound(top_proofs[family])
        if type(proof.get('exit_code')) is not int or proof['exit_code'] != 0 or proof.get('private_session_handles_absent') is not True or proof.get('pool_index_sha256') != pool_ref['sha256'] or not proof.get('observed_at'):
            raise ValueError('Actual closed pool exit0/root session evidence required: ' + family)
        expected_units = 200 if family == 'NN' else 40
        if pool.get('issued') is not True or len(pool['units']) != expected_units:
            raise ValueError('Pool not root-issued exact unit count')
        keys = []
        for entry in pool['units']:
            binding = bound(entry['binding']); contract = bound(binding['central_contract'])
            cell = contract['benchmark_metadata']; method = cell['method_id']
            if family == 'RF':
                if method not in (RF_METHOD, 'RF-Classic'):
                    raise ValueError('Unknown RF administrative alias')
                method = RF_METHOD
            key = method, cell['split_id'], cell['regime_id'], cell['seed']; keys.append(key)
            if entry['unit_id'] != binding['unit_id'] or contract['run_id'] != binding['unit_id']:
                raise ValueError('Issued unit/binding/contract identity differs')
            root = path(binding['receipt_root']); unit_path = root / 'unit-complete.json'; unit = read(unit_path)
            exit_path = root / 'pool-exit-verification.json'; closed = read(exit_path)
            if unit.get('status') != 'complete' or unit.get('unit_id') != entry['unit_id'] or unit.get('binding_sha256') != entry['binding']['sha256'] or unit.get('contract_sha256') != binding['central_contract']['sha256']:
                raise ValueError('Actual complete issued-unit receipt missing')
            if closed.get('exit_code') != 0 or closed.get('private_session_handles_absent') is not True or closed.get('binding_sha256') != entry['binding']['sha256'] or closed.get('unit_id') != entry['unit_id'] or closed.get('index_sha256') != pool_ref['sha256'] or closed.get('pid') != unit.get('pid'):
                raise ValueError('Actual unit side-exit proof differs')
            datasets = {d['role']: d for d in contract['evaluation_stage']['datasets']}
            if set(datasets) != {'internal', 'external75', 'supplement13'} or len(unit.get('scores', [])) != 3 or {s['role'] for s in unit['scores']} != set(datasets):
                raise ValueError('Exactly3 issued datasets/producer scores required')
            specs = {s['sha256'] for s in binding['score_specs']}
            for score in unit['scores']:
                frozen = datasets[score['role']]; score_spec = frozen['score_spec']
                if score_spec['sha256'] not in specs:
                    raise ValueError('Dataset spec absent from issued binding')
                spec = bound(score_spec); raw = spec['dataset_id']
                expected_raw = ('source_test' if key[1] == PANELS[0] else 'target_test') if score['role'] == 'internal' else score['role']
                if raw != expected_raw or score['dataset_id'] != raw or frozen['dataset_id'] != raw or score['n'] != RAW_N[raw] or frozen['n'] != RAW_N[raw]:
                    raise ValueError('Issued dataset/panel/count mapping differs')
                score_ref = {'path': score['complete_path'], 'sha256': score['complete_sha256']}
                produced = bound(score_ref)
                actual_key = (produced['method_id'], produced.get('split_id', produced.get('panel')), produced['regime'], produced['seed'])
                if produced.get('status') != 'complete' or actual_key != key or produced['n'] != RAW_N[raw] or produced['holdout_id'] != raw or produced['score_spec_sha256'] != score_spec['sha256'] or produced['selection_sha256'] != binding['selection']['sha256']:
                    raise ValueError('Producer receipt/spec/selected identity differs')
                stage = 'post-selection-score-only' if family == 'NN' else 'additional_classical_RF_post_joint_barrier_score'
                if produced.get('stage') != stage:
                    raise ValueError('Unexpected producer stage')
                resolved = str(path(score_ref['path']).resolve())
                if resolved in unique_scores:
                    raise ValueError('Producer score reused')
                unique_scores.add(resolved); counts[family] += produced['n']
                maps[family].append({'score_receipt': score_ref['path'], 'holdout_spec': score_spec['path']})
                if family == 'NN' and method == 'GraphDTA-GIN':
                    candidate = {'split_id': key[1], 'dataset_id': NORMALIZED[raw], 'holdout_spec': score_spec['path']}
                    reference_key = key[1], NORMALIZED[raw]
                    if reference_key in references and references[reference_key] != candidate:
                        raise ValueError('Reference input differs across seed/regime; never choose one')
                    references[reference_key] = candidate
                if score['role'] == 'internal':
                    internal.append({'family': family, 'source_receipt': score_ref, 'produced': produced, 'spec': spec})
        exact_grid(keys, family)
    if (len(maps['NN']), len(maps['RF']), counts['NN'], counts['RF'], len(internal), len(references)) != (600, 120, 265800, 53160, 240, 6):
        raise ValueError('Expected600NN/120RF receipts and six fixed reference inputs')
    return maps, internal, [references[k] for k in sorted(references)]


def guard(inputs, explicit):
    if explicit is not True or inputs.get('root_postscore_audit_authorized') is not True:
        raise PermissionError('Explicit root --root-postscore-audit-authorized and signed input permission required')
    if os.name != 'nt':
        raise RuntimeError('Run this driver with existing WindowsPython311; only joint metadata preflight uses WSL')
    if inputs.get('deadline_unix', 0) > DEADLINE or time.time() >= inputs.get('deadline_unix', 0):
        raise TimeoutError('Original01:45UTC absolute cutoff reached or reset attempted')
    output = path(inputs['output_root']).resolve()
    if output == HERE or not output.is_relative_to(HERE):
        raise ValueError('Postscore driver output must be a new folder inside its owned directory')
    frozen = bound(inputs['driver_freeze'])
    if frozen['source_sha256']['driver.py'] != sha(__file__):
        raise ValueError('Driver source changed')
    for entry in frozen['frozen_dependencies']:
        bound_source(entry)
    return frozen


def bound_source(entry):
    if sha(entry['path']) != entry['sha256']:
        raise ValueError('Frozen dependency changed: ' + entry['path'])


def reuse_nn_audit(inputs, nn_map):
    previous_failure = bound(inputs['prior_failed_pipeline'])
    if previous_failure['status'] != 'failed_preserved_no_retry' or previous_failure['source_issuance'] != inputs['issuance']:
        raise ValueError('Explicit original failed-pipeline provenance required')
    completed = {s['name']: s['exit_code'] for s in previous_failure['completed_steps']}
    if completed.get('02-NN600-independent') != 0 or completed.get('03-RF120-independent') != 1:
        raise ValueError('Only the documented RF metadata failure can be resumed')
    if bound(inputs['prior_NN_task_map']) != read(nn_map['path']):
        raise ValueError('Previously audited NN600 task mapping changed')
    files = inputs['prior_NN_audit_files']
    if set(files) != {'independent-audit-manifest.json', 'independent-matched-target-ten-seed-summary.json', 'independent-ten-seed-summary.json', 'per-score-audit.json'}:
        raise ValueError('Bind all four completed independent NN audit artifacts')
    for name, entry in files.items():
        if path(entry['path']).name != name:
            raise ValueError('NN audit file identity differs')
        bound(entry)
    root = path(files['independent-audit-manifest.json']['path']).parent
    if any(path(e['path']).parent != root for e in files.values()):
        raise ValueError('NN artifacts must come from one actual completed audit')
    check = bound(files['independent-audit-manifest.json'])
    if check['evaluator_sha256'] != sha(REVIEW / 'recompute_metrics.py') or check['real_score_tasks_audited'] != 600 or not check['complete600_scores_265800_rows'] or check['metric_difference_count'] != 0 or check['all_predictions_true_labels_match'] is not True:
        raise ValueError('Original NN600 audit incomplete or source changed')
    return root, check


def execute(inputs, explicit):
    guard(inputs, explicit)
    import numpy
    if numpy.__version__ != '2.4.6':
        raise ValueError('Use verified existing Windows NumPy2.4.6 environment')
    out = path(inputs['output_root']); out.mkdir(parents=True, exist_ok=False)
    try:
        issuance = bound(inputs['issuance']); joint = bound(inputs['joint_barrier'])
        if issuance['joint_barrier']['sha256'] != inputs['joint_barrier']['sha256'] or joint.get('status') != 'all_200_NN_plus_40_RF_frozen':
            raise ValueError('Issuance and joint proof differ')
        for family in ('NN', 'RF'):
            if issuance[family + '_barrier']['sha256'] != joint[family + '_barrier_sha256'] or path(issuance[family + '_barrier']['path']).resolve() != path(joint[family + '_barrier_path']).resolve():
                raise ValueError('Issuance and joint must use the same linked barrier path and SHA')
        maps, internal, reference_specs = mapper(issuance, inputs['pool_exit_proofs'])
    except BaseException as error:
        write_new(out / 'POSTSCORE-AUDIT-FAILED.json', dict(status='metadata_preflight_failed_no_numeric_started', error=repr(error), traceback=traceback.format_exc(),
            source_issuance=inputs['issuance'], joint_barrier=inputs['joint_barrier'], original_deadline=inputs['deadline_unix'], numeric_or_metric_repair_attempted=False))
        raise
    steps = []; deadline = inputs['deadline_unix']; joint_ref = inputs['joint_barrier']; nn_ref = issuance['NN_barrier']
    def save(name, value): return write_new(out / 'maps-and-authorizations' / name, value)
    def run(name, argv):
        remaining = deadline - time.time()
        if remaining <= 0: raise TimeoutError('Original cutoff reached before ' + name)
        started = datetime.now(timezone.utc).isoformat()
        with (out / (name + '.stdout.log')).open('x', encoding='utf-8') as stdout, (out / (name + '.stderr.log')).open('x', encoding='utf-8') as stderr:
            result = subprocess.run(argv, stdout=stdout, stderr=stderr, timeout=remaining, check=False,
                env=dict(os.environ, CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', PYTHONUTF8='1', PYTHONIOENCODING='utf-8'))
        step = dict(name=name, argv=argv, exit_code=result.returncode, started_at=started, finished_at=datetime.now(timezone.utc).isoformat())
        steps.append(step); write_new(out / (name + '.step.json'), step)
        if result.returncode: raise RuntimeError('Frozen audit stage failed: ' + name)
    def numeric(name, script, args): run(name, [sys.executable, str(REVIEW / script), *[str(a) for a in args]])
    def joint_auth():
        return save('joint-NN-reference-auth.json', dict(root_joint_real_audit_authorized=True, allowed_modes=['nn', 'references'], deadline_unix=deadline,
            outer_gate_sha256=sha(REVIEW / 'joint_audit_gate_v4.py'), allowed_target_sha256={'nn': sha(REVIEW / 'recompute_metrics.py'), 'references': sha(REVIEW / 'deterministic_references.py')}, joint_barrier_sha256=joint_ref['sha256']))
    def preflight(name, mode, auth):
        code = "import runpy,sys,json; m=runpy.run_path(sys.argv[1]); j,t=m['require_joint'](sys.argv[2],sys.argv[3],sys.argv[4]); print(json.dumps({'status':j['status'],'mode':sys.argv[4],'metadata_only':True}))"
        run(name, ['wsl.exe', '--exec', '/usr/bin/python3', '-c', code, wsl(REVIEW / 'joint_audit_gate_v4.py'), wsl(auth['path']), wsl(joint_ref['path']), mode])
    def common_auth(task):
        return dict(root_RF_independent_audit_authorized=True, deadline_unix=deadline, script_sha256=sha(REVIEW / 'recompute_RF_v5.py'),
                    numeric_helper_sha256=sha(REVIEW / 'recompute_metrics.py'), task_map_sha256=task['sha256'], joint_barrier_sha256=joint_ref['sha256'])
    try:
        nn_map = save('NN600-map.json', maps['NN']); rf_map = save('RF120-map.json', maps['RF']); refs_map = save('reference6-input-map.json', reference_specs)
        ja = joint_auth(); preflight('01-NN-joint-metadata', 'nn', ja)
        nn_audit_root, nn_check = reuse_nn_audit(inputs, nn_map)
        save('reused-complete-NN600-audit.json', dict(original_files=inputs['prior_NN_audit_files'], original_map=inputs['prior_NN_task_map'], previous_failed_pipeline=inputs['prior_failed_pipeline'], numeric_recomputation_repeated=False))
        if not nn_check.get('complete600_scores_265800_rows') or nn_check.get('metric_difference_count') != 0 or nn_check.get('all_predictions_true_labels_match') is not True:
            raise ValueError('NN independent review incomplete/disagrees; stop before further stages')
        rf_auth = common_auth(rf_map)
        rf_auth['script_sha256'] = sha(REVIEW / 'rf-subgroup-audit-recovery-v1/recompute_RF_v6.py')
        ra = save('RF120-audit-auth.json', rf_auth)
        numeric('03-RF120-independent', 'rf-subgroup-audit-recovery-v1/recompute_RF_v6.py', ['--root-authorization', ra['path'], '--joint-barrier', path(joint_ref['path']), '--task-map', rf_map['path'], '--matched-target-manifest', REVIEW / 'matched-target-diagnostics-v1/manifest.json', '--output', out / 'RF-audit'])
        rf_check = read(out / 'RF-audit/independent-RF-audit-manifest.json')
        if rf_check.get('status') != 'complete_independent_RF_audit' or not rf_check.get('complete120_53160') or rf_check.get('metric_difference_count') != 0:
            raise ValueError('RF independent review incomplete/disagrees; stop')
        preflight('04-reference-joint-metadata', 'references', ja)
        numeric('05-three-references-ten-seeds', 'deterministic_references.py', ['--reference-plan', REVIEW / 'deterministic-reference-plan-v2.json', '--reference-plan-sha256', sha(REVIEW / 'deterministic-reference-plan-v2.json'),
            '--selection-barrier', path(nn_ref['path']), '--barrier-sha256', nn_ref['sha256'], '--holdout-specs-map', refs_map['path'], '--output', out / 'references', '--audit-authorized-after-freeze'])
        nn_manifest = ref(nn_audit_root / 'independent-audit-manifest.json'); rf_manifest = ref(out / 'RF-audit/independent-RF-audit-manifest.json')
        nn_scores = ref(nn_audit_root / 'per-score-audit.json'); rf_scores = ref(out / 'RF-audit/per-score-audit.json'); ref_manifest = ref(out / 'references/reference-run-manifest.json')
        reference_receipts = []; reference_internal = []
        for rule, panel, regime, seed in itertools.product(RULES, PANELS, REGIMES, range(10)):
            for dataset in ('PPIKB-internal', 'PTM-external75', 'IgG-supplement13'):
                r = ref(out / 'references' / rule / panel / regime / ('seed-' + str(seed)) / dataset / 'score-receipt.json'); reference_receipts.append(r)
                if dataset == 'PPIKB-internal': reference_internal.append(r)
        combined_map = save('combined-input-map.json', dict(NN_audit_manifest=nn_manifest, RF_audit_manifest=rf_manifest, reference_run_manifest=ref_manifest,
            NN_per_score_audit=nn_scores, RF_per_score_audit=rf_scores, reference_score_receipts=reference_receipts))
        ca = common_auth(combined_map); ca.update(root_combined_metric_report_authorized=True, combiner_script_sha256=sha(REVIEW / 'combine_audit_tables_v5.py'))
        ca = save('combine-auth.json', ca)
        numeric('06-base-v5-combine', 'combine_audit_tables_v5.py', ['--root-authorization', ca['path'], '--joint-barrier', path(joint_ref['path']), '--input-map', combined_map['path'], '--output', out / 'base-v5'])
        group_manifest_ref = ref(REVIEW / 'nc-scope-frozen-groups-v6/manifest.json'); groups = read(group_manifest_ref['path']); bypanel = {p['panel']: p for p in groups['panels']}
        cases = []
        for item in internal:
            receipt_ref = item['source_receipt']; produced = item['produced']; folder = path(receipt_ref['path']).parent
            panel = produced.get('split_id', produced.get('panel'))
            cases.append(dict(category='five_prior_paper_NN' if item['family'] == 'NN' else 'auxiliary_handcrafted_RF', source_receipt=receipt_ref,
                predictions={'path': str(folder / 'predictions.jsonl'), 'sha256': produced['predictions_sha256']},
                blind_predictions={'path': str(folder / 'blind-predictions.jsonl'), 'sha256': produced['blind_predictions_sha256']}, blind_proof=ref(folder / 'blind-complete.json'), input_metadata=bypanel[panel]['input_metadata']))
        for r in reference_internal:
            receipt = read(r['path']); panel = receipt['identity']['split_id']; folder = path(r['path']).parent
            cases.append(dict(category='three_deterministic_references', source_receipt=r, predictions={'path': str(folder / 'predictions.jsonl'), 'sha256': receipt['prediction_sha256']}, blind_predictions=None, input_metadata=bypanel[panel]['input_metadata']))
        case_map = save('internal360-case-map.json', cases)
        ea = common_auth(case_map); ea.update(root_NC_scope_extension_authorized=True, extension_script_sha256=sha(REVIEW / 'nc_scope_extension_v6.py'), group_manifest_sha256=group_manifest_ref['sha256'],
            base_NN_audit_manifest=nn_manifest, base_RF_audit_manifest=rf_manifest, reference_run_manifest=ref_manifest, base_NN_per_score_audit=nn_scores, base_RF_per_score_audit=rf_scores)
        ea = save('v6-extension-auth.json', ea)
        numeric('07-v6-internal360-extension', 'nc_scope_extension_v6.py', ['audit', '--root-authorization', ea['path'], '--joint-barrier', path(joint_ref['path']), '--case-map', case_map['path'], '--group-manifest', group_manifest_ref['path'], '--output', out / 'extension-v6'])
        merge_map = save('v6-merge-input-map.json', dict(base_v5_manifest=ref(out / 'base-v5/unified-table-manifest.json'), v6_extension_manifest=ref(out / 'extension-v6/extension-manifest.json')))
        ma = common_auth(merge_map); ma.update(root_NC_metric_merge_authorized=True, merge_script_sha256=sha(REVIEW / 'merge_metric_extension_v6.py'), extension_script_sha256=sha(REVIEW / 'nc_scope_extension_v6.py'))
        ma = save('v6-merge-auth.json', ma)
        numeric('08-v6-metric-merge', 'merge_metric_extension_v6.py', ['--root-authorization', ma['path'], '--joint-barrier', path(joint_ref['path']), '--input-map', merge_map['path'], '--output', out / 'unified-v6'])
        result = dict(status='complete_postscore_independent_pipeline', source_issuance=inputs['issuance'], joint_barrier=joint_ref,
            driver_freeze=inputs['driver_freeze'], root_explicit_driver_authorization=True, prior_failed_pipeline=inputs['prior_failed_pipeline'], reused_prior_NN_audit_files=inputs['prior_NN_audit_files'], RF_subgroup_audit_recovery_freeze=inputs['RF_subgroup_audit_recovery_freeze'],
            NN_independent_per_score_audit=nn_scores, RF_independent_per_score_audit=rf_scores, NN_audit_manifest=nn_manifest, RF_audit_manifest=rf_manifest,
            reference_run_manifest=ref_manifest, base_v5_manifest=ref(out / 'base-v5/unified-table-manifest.json'), v6_extension_manifest=ref(out / 'extension-v6/extension-manifest.json'),
            actual_unified_manifest=ref(out / 'unified-v6/unified-table-manifest.json'), completed_steps=steps,
            original_counts=dict(NN600=600, RF120=120, references360=360, total_prediction_rows=478440, papers=5), diagnostic_cases_not_new_scores=360,
            scientific_payloads_read_by_driver=False, numeric_functions_reimplemented=0, monkeypatch=False, original_deadline=deadline,
            environment=dict(python=sys.executable, numpy=numpy.__version__, numeric_platform='Windows; original joint metadata function alone uses WSL'))
        write_new(out / 'POSTSCORE-AUDIT-READY.json', result); return result
    except BaseException as error:
        write_new(out / 'POSTSCORE-AUDIT-FAILED.json', dict(status='failed_preserved_no_retry', error=repr(error), traceback=traceback.format_exc(), completed_steps=steps,
            source_issuance=inputs['issuance'], joint_barrier=joint_ref, original_deadline=deadline, numeric_or_metric_repair_attempted=False))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--inputs', required=True)
    parser.add_argument('--root-postscore-audit-authorized', action='store_true'); args = parser.parse_args()
    if not args.root_postscore_audit_authorized:
        raise PermissionError('Root explicit execution flag required before reading input/issuance')
    execute(read(args.inputs), True)


if __name__ == '__main__': main()
