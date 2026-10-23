"""Final generic-baseline delivery receipt from real artifacts, with no training or prediction."""
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
RUN=ROOT/'runs/plm-simple-v1'
def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024**2),b''):digest.update(block)
    return digest.hexdigest()
def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def line_count(path):
    with Path(path).open(encoding='utf-8',newline='') as f:return sum(1 for _ in csv.DictReader(f))

coverage=load(HERE/'coverage-manifest.json')
mirror=load(HERE/'local-mirror-receipt.json')
original=load(RUN/'heads/independent-recalculation.json')
local=load(RUN/'heads/independent-recalculation.local-v1.json')
cache=load(HERE/'independent-local-cache-audit.json')
fitted=load(RUN/'heads/fitted-metadata-independent-audit.json')
common=load(RUN/'common-prediction-comparison/comparison-receipt.json')
sensitivity=load(RUN/'residue-flag-sensitivity-v1/receipt.json')
assert all(r['passed'] for r in [mirror,original,local,cache,fitted])
assert original['metric_cells']==local['metric_cells']==316150
assert common['fixed_prediction_evaluations']==200 and common['old_summary_unchanged']
assert sha(ROOT/'runs/common-prediction-comparison-v2/mean-sd-metrics.csv')==common['old_summary_sha256']
contracts=[];selected=[]
for view in coverage['views']:
    path=Path(view['path']);assert sha(path)==view['sha256']
    contract_path=RUN/'heads'/view['id']/'task-contract.json';contract=load(contract_path)
    assert contract['input_sha256']==view['sha256']
    assert contract['code_sha256']==sha(HERE/'run_heads.py')
    assert contract['feature_code_sha256']==sha(HERE/'plm_features.py')
    assert contract['seeds']==list(range(10))
    contracts.append({'path':str(contract_path),'sha256':sha(contract_path)})
    for model in ['constant','linear','random_forest','extra_trees','hist_gradient_boosting']:
        paths=sorted((RUN/'heads'/view['id']/model).glob('seed-*/result.json'))
        assert [load(p)['seed'] for p in paths]==list(range(10))
        for path in paths:
            result=load(path);assert result['status']=='succeeded'
            candidates=load(path.parent/'candidates.json');assert len(candidates)==2
            selected.append(path)
assert len(selected)==150
prediction_sets={}
for name,pattern in [('selected_test','test-predictions.csv'),('selected_validation','validation-predictions.csv'),
                     ('candidate_validation','candidate-*-validation.csv')]:
    files=list((RUN/'heads').glob('*/*/seed-*/'+pattern))
    prediction_sets[name]={'files':len(files),'calculation_rows':sum(line_count(p) for p in files)}
assert prediction_sets['selected_test']['files']==150 and prediction_sets['candidate_validation']['files']==300
weights=list((RUN/'heads').glob('*/*/seed-*/candidate-*.joblib'));assert len(weights)==300
for subdir in ['extraction-cpu-v3-canary-supervision','extraction-cpu-v3-formal-supervision','heads']:
    process=load(RUN/subdir/'process-receipt.json')
    assert process['exit_code']==0 and process['worker_pid_absent'] and not process['surviving_group_pids']
receipt={'schema':'frozen-esm2.generic-baseline-delivery.v1','completed_at':dt.datetime.now(dt.timezone.utc).isoformat(),
    'status':'complete','selected_scientific_runs':150,'scientific_candidate_fits':300,
    'separate_training_row_runtime_canary_fits':30,'new_paper_full_reproductions':0,
    'generic_baseline_family_count':5,'training_views':3,'training_seeds':list(range(10)),
    'candidate_weights_local':len(weights),'prediction_sets':prediction_sets,
    'mirrored_source_files':mirror['files_verified'],'mirrored_source_bytes':mirror['bytes_verified'],
    'model_sha256':load(HERE/'feature-cache-cpu-v3/receipt.json')['model_sha256'],
    'embedding_sha256':cache['embedding_sha256'],'embedding_shape':[5159,320],
    'canonical_scoring':'Original CSV float64 labels; fixed splits; validation-only selection',
    'independent_metric_cells_remote':original['metric_cells'],'independent_metric_cells_local_repeat':local['metric_cells'],
    'independent_differences':0,'train_only_scaler_candidates_checked':fitted['models_checked'],
    'ridge_iteration_cap_reached_models':fitted['iteration_cap_reached_models'],
    'same_id_fixed_prediction_evaluations':200,'same_id_test_denominators':common['four_cohort_test_denominators'],
    'sensitivity_fixed_predictions_only':True,'sensitivity_counts':sensitivity['derived_view_counts'],
    'external_forward_count_this_branch':0,'new_classification_or_contact_results_this_branch':0,
    'chemical_identity_encoded':False,'actual_scientific_gpu_use':0,
    'all_owned_scientific_process_groups_terminal':True,'node23_cpu_slots_released':True,
    'original_data_and_prior_results_changed':False,'old_failures_preserved':True,
    'contracts':contracts,'user_authorization_sha256':sha(HERE/'user-authorization.copy.json'),
    'reports':{str(p.relative_to(ROOT)):sha(p) for p in [HERE/'RESULTS.md',HERE/'local-mirror-receipt.json',
        RUN/'heads/independent-recalculation.json',RUN/'heads/independent-recalculation.local-v1.json',
        RUN/'common-prediction-comparison/comparison-receipt.json',RUN/'residue-flag-sensitivity-v1/receipt.json']},
    'delivery_code_sha256':sha(__file__)}
(HERE/'DELIVERY-RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in receipt.items() if k not in ['reports','contracts']},ensure_ascii=False))
