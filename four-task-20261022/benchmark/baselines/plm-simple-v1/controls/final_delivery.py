"""Final matched-cohort control receipt, keeping original ESM and full-manual tracks separate."""
import csv
import datetime as dt
import json
from pathlib import Path
from verify_manual_controls import sha

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
RUN=ROOT/'runs/plm-cohort-manual-controls-v1'
ESM=ROOT/'runs/plm-simple-v1/heads'
def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def count(path):
    with Path(path).open(encoding='utf-8',newline='') as f:return sum(1 for _ in csv.DictReader(f))

mirror=load(HERE/'local-mirror-receipt.json')
remote=load(RUN/'independent-recalculation.json');local=load(RUN/'independent-recalculation.local-v1.json')
paired=load(RUN/'paired-with-esm/comparison-receipt.json');pairaudit=load(RUN/'paired-with-esm/independent-recalculation.json')
fitted=load(RUN/'fitted-metadata-independent-audit.json');process=load(RUN/'process-receipt.json')
assert all(r['passed'] for r in [mirror,remote,local,pairaudit,fitted])
assert remote['selected_runs']==local['selected_runs']==paired['paired_runs']==150
assert remote['candidate_fits']==local['candidate_fits']==300
assert process['exit_code']==0 and process['worker_pid_absent'] and not process['surviving_group_pids']
assert paired['test_rows_removed_to_match']==0 and paired['constant_prediction_rows_exactly_identical']==20160
views=load(HERE/'coverage-manifest.json')['views'];contracts=[]
for view in views:
    control=load(RUN/view['id']/'task-contract.json');esm=load(ESM/view['id']/'task-contract.json')
    assert control['input_sha256']==esm['input_sha256']==view['sha256']
    assert control['code_sha256']==sha(HERE/'run_manual_controls.py')
    assert control['seeds']==esm['seeds']==list(range(10))
    assert control['sklearn']==esm['sklearn'] and control['numpy']==esm['numpy']
    contracts.append({'view_id':view['id'],'control_sha256':sha(RUN/view['id']/'task-contract.json'),
        'esm_contract_sha256':sha(ESM/view['id']/'task-contract.json'),'input_sha256':view['sha256'],
        'split_counts':view['split_counts'],'manual_feature_dimensions':435 if view['task']=='effect' else 174})
counts={}
for name,pattern in [('selected_test','test-predictions.csv'),('selected_validation','validation-predictions.csv'),('candidate_validation','candidate-*-validation.csv')]:
    files=list(RUN.glob('*/*/seed-*/'+pattern));counts[name]={'files':len(files),'calculation_rows':sum(count(p) for p in files)}
weights=list(RUN.glob('*/*/seed-*/candidate-*.joblib'));assert len(weights)==300
gate=load(RUN/'capacity-gate.json');assert gate['admitted']
for sample in gate['attempts'][-1]['samples']:
    assert sample['global_idle_percent']>=40 and min(sample['reserved_core_idle_percent'].values())>=60
reports=[HERE/'RESULTS.md',HERE/'comparison-protocol.json',HERE/'execution-contract.json',HERE/'local-mirror-receipt.json',
         RUN/'independent-recalculation.json',RUN/'independent-recalculation.local-v1.json',
         RUN/'paired-with-esm/comparison-receipt.json',RUN/'paired-with-esm/independent-recalculation.json']
receipt={'schema':'plm.matched-cohort.manual-control-delivery.v1','status':'complete',
    'completed_at':dt.datetime.now(dt.timezone.utc).isoformat(),'additional_selected_scientific_runs':150,
    'additional_candidate_fits':300,'separate_training_row_canary_fits':30,'candidate_weights_local':len(weights),
    'training_views':3,'seeds':list(range(10)),'prediction_sets':counts,
    'mirrored_files':mirror['files_verified'],'mirrored_bytes':mirror['bytes_verified'],
    'independent_numeric_checks_remote':remote['metric_cells'],'independent_numeric_checks_local_repeat':local['metric_cells'],
    'independent_differences':0,'paired_runs':150,'paired_prediction_calculation_rows':paired['paired_prediction_calculation_rows'],
    'independent_paired_checks':pairaudit['numeric_checks'],'paired_differences':len(pairaudit['errors']),
    'constant_prediction_rows_identical':20160,'matched_test_rows_removed':0,'p_values_reported_or_used_for_selection':0,
    'same_raw_input_train_validation_test_and_runtime_versions':True,
    'known_recipe_differences':['Original manual Ridgeauto vs ESM LSQR','Original manual435D vs ESM960D effect layout'],
    'pure_encoder_causal_claim':False,'new_paper_full_reproductions':0,'gpu_used':False,
    'cpu_affinity':[25,30],'reserved_siblings':[57,62],'cpu_slots_released':True,
    'scientific_process_pid':process['pid'],'exit_code':process['exit_code'],'all_owned_scientific_group_terminal':True,
    'old_full_manual_and_ESM_tracks_modified':False,'contracts':contracts,
    'reports':{str(path.relative_to(ROOT)):sha(path) for path in reports},
    'new_fit_or_forward_during_pair_scoring':0,'delivery_code_sha256':sha(__file__)}
(HERE/'DELIVERY-RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in receipt.items() if k not in ['contracts','reports']},ensure_ascii=False))
