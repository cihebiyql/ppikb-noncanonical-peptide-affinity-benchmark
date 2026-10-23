"""Predeclare both binary grids, threshold/evaluation rules and actual head/feature code before outcomes."""
import datetime as dt
import hashlib
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
REMOTE='/data/qlyu/projects/peptide-four-task-benchmark-20261022'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def remote(path):return REMOTE+'/'+Path(path).relative_to(ROOT).as_posix()
files=[HERE/name for name in ['assemble_cache.py','plm_binary_features.py','run_heads.py','supervise_heads.py','smoke_heads.py',
    'verify_heads.py','run_head_campaign.py','summarize_binary_results.py','prepare_head_spec.py','continue_binary_pipeline.py',
    'coverage-manifest.json','inputs/remote-manifest.json','inputs/contact-sequence-index-proof.json']]
contract={'schema':'frozen-esm2.classification-contact.binary-pipeline.v1','frozen_at':dt.datetime.now(dt.timezone.utc).isoformat(),
    'code_and_protocol_hashes':[{'path':remote(path),'sha256':sha(path)} for path in files],
    'feature_contract_sha256':sha(HERE/'feature-contract.json'),'resource_plan_sha256':sha(HERE/'resource-plan.json'),
    'task_order':['classification','contact'],'binary_model_families':['constant','linear','random_forest','extra_trees','hist_gradient_boosting'],
    'training_seeds':list(range(10)),'candidates_each_family':2,'scientific_selected_runs_expected':100,'scientific_candidate_fits_expected':200,
    'runtime_canary_fits_separate':20,'selection':'validation AUPRC only; fallback negativeBrier only if AUPRCundefined',
    'classification_threshold':'validation MCC on fixed0.1..0.9 step0.05; ties closest0.5; never test tuning',
    'test_metrics':['AUROC','AUPRC','MCC','F1','balanced_accuracy','Brier'],
    'contact_averaging':['micro observed residues','dependency component macro','experimental complex macro'],
    'test_label_meanings':['author constructed interaction labels, not all experimentally measured nonbinding',
        'observed experimental structure5A contacts, not functional binding energy truth'],
    'sequence_chemical_identity_encoded':False,'new_dependencies':False,'new_paper_full_reproductions':0,
    'no_label_or_geometry_inputs_to_representations':True,'unobserved_residues_never_assigned_negative_labels':True,
    'original_datasets_and_prior_results_changed':False,'p_values_used_for_selection':False,
    'user_authorization_sha256':sha(ROOT/'baselines/plm-simple-v1/user-authorization.copy.json')}
path=HERE/'binary-pipeline-contract.json';assert not path.exists();path.write_text(json.dumps(contract,indent=2),encoding='utf-8')
print(json.dumps({'path':str(path),'sha256':sha(path)}))
