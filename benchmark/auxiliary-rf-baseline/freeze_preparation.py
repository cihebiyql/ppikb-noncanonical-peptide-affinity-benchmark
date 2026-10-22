"""Verify/freeze preparation metadata and fixed X, never fit/read real gold/models."""
import numpy as np
import common
import rf_runner

def main():
    output=common.HERE/'SOURCE-FREEZE-v1.json'
    if output.exists():raise FileExistsError('Prepared source freeze already exists')
    assets=rf_runner.installed_assets(common.HERE/'installed-assets-v1.json')
    x=common.read(common.HERE/'X-final-manifest-v1.json')
    if x['feature_code_sha256']!=common.sha(common.HERE/'features.py') or x['feature_spec_sha256']!=common.sha(common.HERE/'feature-spec-v1.json') or x['installed_assets_sha256']!=common.sha(common.HERE/'installed-assets-v1.json'):
        raise ValueError('Fixed X differs from final feature implementation/spec/environment')
    matrices=[]
    for entry in x['entries']:
        array,lookup,verified=common.load_feature_dataset(x,entry['dataset_id'])
        if not np.isfinite(array).all():raise ValueError('Invalid fixed RF X')
        matrices.append(dict(dataset_id=entry['dataset_id'],n=len(lookup),shape=list(array.shape),dtype=str(array.dtype),matrix_sha256=entry['matrix_sha256']))
        del array,lookup
    index=common.read(common.HERE/'specs-v1/task-spec-index.json')
    if len(index['units'])!=40 or index['candidate_fit_count']!=80:raise ValueError('RF task grid incomplete')
    identities=set()
    for unit in index['units']:
        common.require(unit['spec_path'],unit['spec_sha256']);spec=common.read(unit['spec_path'])
        identities.add((spec['panel'],spec['regime'],spec['seed']))
        if len(common.read(spec['train_ids']))!=spec['train_n'] or len(common.read(spec['validation_ids']))!=spec['validation_n']:raise ValueError('RF frozen ID counts wrong')
    if identities!={(p,r,s) for p in common.PANELS for r in common.REGIMES for s in range(10)}:raise ValueError('RF grid identity mismatch')
    scores=common.read(common.HERE/'score-specs-v1/score-spec-index.json')
    if len(scores['entries'])!=6:raise ValueError('RF score metadata incomplete')
    for entry in scores['entries']:common.require(entry['score_spec_path'],entry['score_spec_sha256'])
    log=(common.HERE/'mechanics-tests.log').read_text(encoding='utf-8-sig')
    if 'Ran 11 tests' not in log or 'OK' not in log:raise ValueError('Final mechanical tests unavailable')
    if (common.HERE/'real-runs-v1').exists() or (common.HERE/'rf-scores-v1').exists():raise ValueError('Preparation must not create scientific fit/score output roots')
    common.require(common.PROJECT/rf_runner.NN_APPROVED_INDEX_RELATIVE,rf_runner.NN_APPROVED_INDEX_SHA)
    artifacts=['feature-spec-v1.json','protocol-v1.json','installed-assets-v1.json','installed-binaries-v1.json','X-final-manifest-v1.json',
               'specs-v1/task-spec-index.json','score-specs-v1/score-spec-index.json','representation-alias-audit-v1.json',
               'fit-authorization.example.json','score-authorization.example.json','mechanics-tests.log','README.md']
    result=dict(status='RF_preparation_frozen_no_real_fit_or_score_authorized',method_id=common.METHOD,paper_count=0,
        source_sha256=rf_runner.source_hashes(),artifact_sha256={name:common.sha(common.HERE/name) for name in artifacts},
        all_RF_python_source_sha256={path.name:common.sha(path) for path in sorted(common.HERE.glob('*.py'))},
        installed_versions=assets['versions'],raw_sklearn_source=assets['source_files'],fixed_X=matrices,
        RF_units=40,RF_candidate_fits_predeclared=80,RF_scores_future=120,RF_prediction_rows_future=53160,
        NN_selections_unchanged=200,NN_candidate_fits_unchanged=400,NN_scores_unchanged=600,NN_prediction_rows_unchanged=265800,
        NN_approved_index_relative=rf_runner.NN_APPROVED_INDEX_RELATIVE,NN_approved_index_sha256=rf_runner.NN_APPROVED_INDEX_SHA,
        deterministic_reference_scores_separate=360,deterministic_reference_rows_separate=159480,
        synthetic_mechanical_tests_passed=11,synthetic_library_fit_calls_in_tests=5,
        real_RF_fits=0,real_RF_selections=0,real_holdout_predictions=0,actual_gold_or_trained_model_reads=0,
        whole_label_container_used_for_fit=False,primary_split_changed=False,deadline_reset=False,
        sharing_conflict_handling='unique tmp; PermissionError bounded 0.05..1s retries; persistent failclosed; independent root budget supervisor remains active',
        worker_CLI='rf_runner.py fit --spec SPEC --authorization ROOT_NEW_BOUNDED_AUTH',
        required_next_step='root-issued bounded fit authorization and external supervisor; score only after NN200+RF40 joint gate')
    common.write(output,result)
    print('RF preparation frozen:40units80fits planned,6score specs,9707X rows;0realfit/score.')
if __name__=='__main__':main()
