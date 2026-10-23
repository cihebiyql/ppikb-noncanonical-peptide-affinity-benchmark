"""Freeze original manual feature heads on exactly the already adopted ESM observation cohort."""
import datetime as dt
import difflib
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PLM=HERE.parent
REMOTE='/data/qlyu/projects/peptide-four-task-benchmark-20261022'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    source=ROOT/'baselines/frozen-code/cpu-baselines-v2.py'
    original=source.read_text(encoding='utf-8');text=original
    for before,after in [
        ('ROOT = Path(__file__).resolve().parents[1]','ROOT = Path(__file__).resolve().parents[3]'),
        ('ROOT / "runs" / "cpu-v1"','ROOT / "runs" / "plm-cohort-manual-controls-v1"'),
        ('x, feature_audit = build_features(frame, task)',
         'x, feature_audit = build_features(frame, task)\n    np.savez_compressed(view_root / "features.npz", features=x, row_ids=frame.row_id.to_numpy(dtype=str))')]:
        assert text.count(before)==1,before
        text=text.replace(before,after)
    target=HERE/'run_manual_controls.py';assert not target.exists()
    target.write_bytes(text.encode('utf-8'))
    (HERE/'adaptation.diff').write_text(''.join(difflib.unified_diff(original.splitlines(True),text.splitlines(True),
        fromfile=str(source),tofile=str(target))),encoding='utf-8')
    coverage=PLM/'coverage-manifest.json'
    (HERE/'coverage-manifest.json').write_bytes(coverage.read_bytes())
    manifest=json.loads(coverage.read_text(encoding='utf-8'))
    remote={**manifest,'views':[]}
    for view in manifest['views']:
        path=Path(view['path']);assert sha(path)==view['sha256']
        replacement=dict(view);replacement['original_local_path']=view['path']
        replacement['path']=REMOTE+'/'+path.relative_to(ROOT).as_posix()
        remote['views'].append(replacement)
    (HERE/'remote-manifest.json').write_text(json.dumps(remote,ensure_ascii=False,indent=2),encoding='utf-8')
    independent=PLM/'verify_results.py'
    verify=independent.read_text(encoding='utf-8')
    before="here/'inputs'/(view['id']+'.csv')";assert verify.count(before)==1
    verify=verify.replace(before,"here.parent/'inputs'/(view['id']+'.csv')")
    (HERE/'verify_manual_controls.py').write_bytes(verify.encode('utf-8'))
    protocol={'schema':'plm.matched-cohort.manual-control-protocol.v1',
        'prepared_at':dt.datetime.now(dt.timezone.utc).isoformat(),
        'purpose':'Assess ESM versus original manual-feature baselines on identical raw observations and frozen train/validation/test; remove eligible-cohort differences from the primary comparison',
        'manual_source_path':str(source),'manual_source_sha256':sha(source),'runner_sha256':sha(target),
        'source_adaptation_changes':['Path root for isolated directory','Separate output','Preserve actual fixed feature matrices'],
        'feature_definitions_or_model_grid_changed':False,'original_ridge_auto_solver_retained':True,
        'ESM_ridge_lsqr_tolerance':1e-4,'ESM_ridge_iteration_cap':1000,
        'effect_manual_layout':'mutant87,target87,WT87,mutant-WT87,targetMut-targetWT87',
        'effect_ESM_layout':'WT320,mutant-WT320,identical_target320',
        'pure_encoder_causal_claim':False,
        'train_validation_test_row_ids_exactly_same_as_ESM':True,
        'seeds':list(range(10)),'candidate_count_per_family':2,
        'selected_runs_expected':150,'candidate_fits_expected':300,
        'selection':'Validation MAE only; report every family/seed. No test tuning or selective significance tests.',
        'paired_comparison':'Same view, head family, seed and exact test row_id with CSV64 label/endpoint equality; manual-minus-ESM per-seed metrics and rowwise absolute-error differences',
        'historical_full_manual':'Separate reference only. Historical Windows/sklearn1.9/numpy2.4 differs from matched Node23/sklearn1.4.2/numpy1.26, so its change is not attributed solely to cohort filtering.',
        'input_manifest_sha256':sha(coverage),'user_authorization_path':str(PLM/'user-authorization.copy.json'),
        'user_authorization_sha256':sha(PLM/'user-authorization.copy.json'),
        'shared_environment_modified':False,'new_dependencies':False,'gpu':False,
        'parent_original_results_changed':False,'new_paper_full_reproduction':False}
    (HERE/'comparison-protocol.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'views':[(v['id'],v['rows'],v['split_counts']) for v in manifest['views']],
        'runner_sha256':sha(target),'protocol_sha256':sha(HERE/'comparison-protocol.json')},ensure_ascii=False))

if __name__=='__main__':main()
