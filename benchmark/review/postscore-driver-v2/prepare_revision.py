"""Create an explicit audit-resume revision, retaining the failed v1 unchanged."""
from pathlib import Path
import hashlib
import json

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / 'postscore-driver-v1'


def main():
    text = (OLD / 'driver.py').read_text(encoding='utf-8-sig')
    changes = [
        ("def execute(inputs, explicit):", '''def reuse_nn_audit(inputs, nn_map):
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


def execute(inputs, explicit):'''),
        ("numeric_helper_sha256=sha(REVIEW / 'recompute_metrics.py'),", "numeric_helper_sha256=sha(REVIEW / 'recompute_metrics.py'),"),
        ("        ra = save('RF120-audit-auth.json', common_auth(rf_map))", "        rf_auth = common_auth(rf_map)\n        rf_auth['script_sha256'] = sha(REVIEW / 'rf-subgroup-audit-recovery-v1/recompute_RF_v6.py')\n        ra = save('RF120-audit-auth.json', rf_auth)"),
        ("        numeric('02-NN600-independent', 'recompute_metrics.py', ['--selection-barrier', path(nn_ref['path']), '--barrier-sha256', nn_ref['sha256'], '--task-map', nn_map['path'],\n            '--matched-target-manifest', REVIEW / 'matched-target-diagnostics-v1/manifest.json', '--matched-target-manifest-sha256', sha(REVIEW / 'matched-target-diagnostics-v1/manifest.json'), '--output', out / 'NN-audit', '--audit-authorized-after-freeze'])\n        nn_check = read(out / 'NN-audit/independent-audit-manifest.json')", "        nn_audit_root, nn_check = reuse_nn_audit(inputs, nn_map)\n        save('reused-complete-NN600-audit.json', dict(original_files=inputs['prior_NN_audit_files'], original_map=inputs['prior_NN_task_map'], previous_failed_pipeline=inputs['prior_failed_pipeline'], numeric_recomputation_repeated=False))"),
        ("numeric('03-RF120-independent', 'recompute_RF_v5.py'", "numeric('03-RF120-independent', 'rf-subgroup-audit-recovery-v1/recompute_RF_v6.py'"),
        ("ref(out / 'NN-audit/independent-audit-manifest.json')", "ref(nn_audit_root / 'independent-audit-manifest.json')"),
        ("ref(out / 'NN-audit/per-score-audit.json')", "ref(nn_audit_root / 'per-score-audit.json')"),
        ("driver_freeze=inputs['driver_freeze'], root_explicit_driver_authorization=True,", "driver_freeze=inputs['driver_freeze'], root_explicit_driver_authorization=True, prior_failed_pipeline=inputs['prior_failed_pipeline'], reused_prior_NN_audit_files=inputs['prior_NN_audit_files'], RF_subgroup_audit_recovery_freeze=inputs['RF_subgroup_audit_recovery_freeze'],"),
    ]
    for before, after in changes:
        if before == after:
            continue
        assert text.count(before) == 1, (before, text.count(before))
        text = text.replace(before, after)
    compile(text, str(HERE / 'driver.py'), 'exec')
    with (HERE / 'driver.py').open('x', encoding='utf-8', newline='\n') as handle:
        handle.write(text)
    with (HERE / 'test_driver.py').open('x', encoding='utf-8', newline='\n') as handle:
        handle.write((OLD / 'test_driver.py').read_text(encoding='utf-8-sig'))
    report = dict(source_original_sha256=hashlib.sha256((OLD / 'driver.py').read_bytes()).hexdigest(),
                  source_revision_sha256=hashlib.sha256((HERE / 'driver.py').read_bytes()).hexdigest(),
                  exact_replacements=[dict(before=a, after=b) for a,b in changes if a != b],
                  original_sources_modified=False, numerical_functions_modified=False,
                  training_scoring_or_parameter_selection_called=False)
    with (HERE / 'revision-diff.json').open('x', encoding='utf-8') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    print(json.dumps({k:v for k,v in report.items() if k != 'exact_replacements'}))


if __name__ == '__main__':
    main()
