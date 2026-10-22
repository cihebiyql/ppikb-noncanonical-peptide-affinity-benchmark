"""Preregistered train-only descriptive references, not additional paper models.

Preparation imports this file without touching data. The CLI refuses to read any
training labels or real holdout until explicit root post200-freeze authorization.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
from pathlib import Path
import json,math
import numpy as np
import recompute_metrics as audit

RULES=('train_mean','train_median','target_reference_train_median')

def fit_reference(rule,train_rows):
 if rule not in RULES:raise ValueError('Unknown frozen descriptive reference')
 if not train_rows:raise ValueError('Empty training subset')
 if len({r['record_id'] for r in train_rows})!=len(train_rows):raise ValueError('Duplicate training ID')
 values=np.asarray([r['pKd'] for r in train_rows],dtype=np.float64)
 if not np.isfinite(values).all():raise ValueError('Nonfinite train value')
 state={'rule_id':rule,'train_n':len(values),'global_train_mean':float(np.mean(values)),
        'global_train_median':float(np.median(values)),'target_reference_train_medians':{},
        'fit_uses_training_rows_only':True,'validation_test_external_tuning':False,
        'random_parameters':False}
 if rule=='target_reference_train_median':
  target=defaultdict(list)
  for row in train_rows:target[row['target_reference_sequence_sha']].append(float(row['pKd']))
  state['target_reference_train_medians']={key:float(np.median(v)) for key,v in sorted(target.items())}
 return state

def predict_reference(state,target_reference_shas):
 rule=state['rule_id']
 if rule=='train_mean':return [state['global_train_mean'] for _ in target_reference_shas]
 if rule=='train_median':return [state['global_train_median'] for _ in target_reference_shas]
 if rule=='target_reference_train_median':
  return [state['target_reference_train_medians'].get(t,state['global_train_median']) for t in target_reference_shas]
 raise ValueError('Unknown descriptive reference')

def write_jsonl(path,rows):
 with Path(path).open('w',encoding='utf-8') as f:
  for row in rows:f.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')

def frozen_dataset_rows(spec,plan):
 audit.require_hash(spec['input_rows'],spec['input_rows_sha256'])
 rows=audit.read_jsonl(spec['input_rows']);audit.unique_by_id(rows,'reference holdout input')
 if any('pKd' in r for r in rows):raise ValueError('Reference holdout input not label-free')
 dataset=spec['normalized_dataset_id']
 for r in rows:r['target_reference_sequence_sha']=audit.hashlib.sha256(r['target_sequence'].encode('utf-8')).hexdigest()
 # Import only frozen ID membership; no numeric gold is needed for predictions.
 for field,flag in [('external_primary_ids','external_primary'),('external_conditional_sensitivity_ids','external_conditional_sensitivity'),('external_reference_target_cold_ids','external_reference_target_cold'),('nc_ids','external_supplement_NC'),('standard_control_ids','external_supplement_standard')]:
  if field not in spec:continue
  ids=set(audit.read_json(spec[field]))
  if not ids<={r['record_id'] for r in rows}:raise ValueError('Frozen reference subgroup ID mismatch')
  for row in rows:
   if flag in row and row[flag]!=(row['record_id'] in ids):raise ValueError('Reference subgroup flag disagrees with ID')
   row[flag]=row['record_id'] in ids
 if dataset=='IgG-supplement13':
  audit.require_hash(spec['root_accepted_manifest_path'],audit.SUPPLEMENT_ACCEPTED_SHA)
  if len(rows)!=13 or sum(r['external_supplement_NC'] for r in rows)!=8 or sum(r['external_supplement_standard'] for r in rows)!=5:raise ValueError('Supplement13 reference groups changed')
 return rows,dataset

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--reference-plan',required=True);p.add_argument('--reference-plan-sha256',required=True)
 p.add_argument('--selection-barrier',required=True);p.add_argument('--barrier-sha256',required=True)
 p.add_argument('--holdout-specs-map',required=True,help='Explicit6 entries {split_id,dataset_id,holdout_spec}; metadata only')
 p.add_argument('--audit-authorized-after-freeze',action='store_true');p.add_argument('--output',required=True)
 a=p.parse_args()
 # This gate precedes ALL numeric label reads, including training labels.
 audit.authorize_barrier(a.selection_barrier,a.barrier_sha256,a.audit_authorized_after_freeze)
 audit.require_hash(a.reference_plan,a.reference_plan_sha256);plan=audit.read_json(a.reference_plan)
 audit.require_hash(__file__,plan['reference_script_sha256'])
 audit.require_hash(audit.__file__,plan['metric_helper_sha256'])
 if tuple(plan['reference_rule_ids'])!=RULES or plan['status']!='frozen_prepared_not_fit':raise ValueError('Wrong reference preregistration')
 for source in plan['source_files_verified_during_preparation']:audit.require_hash(source['path'],source['sha256'])
 source=plan['training_label_source'];audit.require_hash(source['path'],source['declared_sha256'])
 # Full frozen label container is accessed only after global freeze. Only IDs
 # declared as train below are passed to fit_reference; no validation/holdout
 # values or scores are arguments to that fitting function.
 labels=audit.unique_by_id(audit.read_jsonl(source['path']),'frozen label container')
 inputmeta=audit.unique_by_id(audit.read_jsonl(plan['label_free_inputs']['path']),'frozen label-free metadata')
 matched=audit.load_matched_manifest(plan['matched_target_manifest']['path'],plan['matched_target_manifest']['sha256'])
 tasks=audit.read_json(a.holdout_specs_map);specs={}
 for entry in tasks:
  raw_spec=audit.read_json(entry['holdout_spec']);spec=audit.normalize_score_spec(raw_spec,entry['split_id']);key=(entry['split_id'],entry['dataset_id'])
  if key in specs:raise ValueError('Duplicate reference dataset specification')
  if spec['split_id']!=key[0] or spec['normalized_dataset_id']!=key[1]:raise ValueError('Reference holdout map identity mismatch')
  # New cached scoring specs bind their barrier in a separate root authorization;
  # this reference CLI already requires and verifies that full200 barrier itself.
  if spec.get('selection_barrier_path'):
   if audit.local_path(spec['selection_barrier_path']).resolve()!=audit.local_path(a.selection_barrier).resolve():raise ValueError('Every reference score must bind same full200 barrier')
  elif 'gold_rows' not in raw_spec:raise ValueError('Legacy reference spec lacks explicit global barrier')
  rows,ds=frozen_dataset_rows(spec,plan);specs[key]=(spec,rows,entry['holdout_spec'])
 if set(specs)!={(p,d) for p in audit.PANELS for d in audit.EXPECTED_PREDICTION_ROWS}:raise ValueError('Expected all6 reference holdout specs')
 out=Path(a.output);out.mkdir(parents=True,exist_ok=False)
 records=[];seed_vectors={};seed_groups=defaultdict(list);matched_scores=[]
 for context in plan['training_contexts']:
  panel=context['split_id'];regime=context['regime'];ids=audit.read_json(context['train_ids_path'])
  audit.require_hash(context['train_ids_path'],context['train_ids_sha256'])
  training=[]
  for rid in ids:
   row=inputmeta[rid]
   if row['NC_core'] is not (regime=='NC_only'):raise ValueError('Reference training regime mismatch')
   training.append({'record_id':rid,'pKd':float(labels[rid]['pKd']),
    'target_reference_sequence_sha':audit.hashlib.sha256(row['target_sequence'].encode('utf-8')).hexdigest()})
  for rule in RULES:
   for seed in range(10):
    # Real repeated computation, with no RNG. Never fake ten stochastic fits.
    state=fit_reference(rule,training)
    d=out/rule/panel/regime/('seed-'+str(seed));d.mkdir(parents=True)
    audit.write_json(d/'train-only-statistics.json',dict(state,seed=seed,seed_role='deterministic replicate identifier, no random parameters',train_ids_sha256=context['train_ids_sha256'],training_label_source_sha256=source['declared_sha256']))
    for ds in audit.EXPECTED_PREDICTION_ROWS:
     spec,inputs,specpath=specs[(panel,ds)];folder=d/ds;folder.mkdir()
     targets=[r['target_reference_sequence_sha'] for r in inputs]
     values=predict_reference(state,targets)
     # Prediction rule has already returned before these holdout truths are read.
     audit.require_hash(spec['label_rows'],spec['label_rows_sha256'])
     truth=audit.unique_by_id(audit.read_jsonl(spec['label_rows']),'reference scoring gold')
     rows=[dict(r,pKd_true=float(truth[r['record_id']]['pKd']),pKd_pred=float(v),dataset_id=ds) for r,v in zip(inputs,values)]
     write_jsonl(folder/'predictions.jsonl',rows)
     grouped=audit.group_metrics(rows,ds)
     identity=dict(dataset_id=ds,split_id=panel,holdout_id=spec['holdout_id'],method_id='reference:'+rule,regime=regime,seed=seed)
     vector_hash=audit.hashlib.sha256(json.dumps([(r['record_id'],r['pKd_pred']) for r in rows],separators=(',',':')).encode()).hexdigest()
     key=(rule,panel,regime,ds)
     if key in seed_vectors and seed_vectors[key]!=vector_hash:raise ValueError('Deterministic seed predictions changed')
     seed_vectors[key]=vector_hash
     receipt={'stage':'post-freeze-deterministic-reference','identity':identity,'n':len(rows),'metrics':grouped,
      'global200_selection_barrier_sha256':a.barrier_sha256,'reference_plan_sha256':a.reference_plan_sha256,
      'holdout_spec_sha256':audit.sha(audit.local_path(specpath)),'prediction_sha256':audit.sha(folder/'predictions.jsonl'),
      'prediction_vector_sha256':vector_hash,'training_statistic_sha256':audit.sha(d/'train-only-statistics.json'),
      'no_validation_or_holdout_fitting':True,'no_NN_fit_or_paper_reproduction_claim':True,'random_parameters':False,
      'unseen_target_fallback_count':sum(t not in state['target_reference_train_medians'] for t in targets) if rule=='target_reference_train_median' else None,
      'macro_by_full_target_reference':audit.macro_metrics(rows,'target_reference_sequence_sha'),
      'macro_by_source':audit.macro_metrics(rows,'study_id')}
     if ds=='PPIKB-internal':
      receipt['matched_target_diagnostics']=audit.matched_target_metrics(rows,panel,matched)
      matched_scores.append({'identity':identity,'matched_target_diagnostics':receipt['matched_target_diagnostics']})
     audit.write_json(folder/'score-receipt.json',receipt);records.append(receipt)
     for group,met in grouped.items():seed_groups[(rule,panel,regime,ds,group)].append(dict(seed=seed,**met))
 summaries=[{'identity':key,**audit.summarize_seeds(rows)} for key,rows in sorted(seed_groups.items())]
 audit.write_json(out/'ten-seed-reference-summary.json',summaries)
 audit.write_json(out/'matched-target-ten-seed-reference-summary.json',audit.summarize_matched_targets(matched_scores))
 counts=Counter()
 for row in records:counts[row['identity']['dataset_id']]+=row['n']
 expected={'PPIKB-internal':148920,'PTM-external75':9000,'IgG-supplement13':1560}
 if len(records)!=360 or dict(counts)!=expected:raise ValueError('Incomplete deterministic reference score grid')
 for row in summaries:
  if row['completed_seed_count']!=10:raise ValueError('Missing deterministic seed evaluations')
  if any(row[m+'_sd'] not in (None,0.) for m in audit.METRICS):raise ValueError('Unexpected nonzero deterministic seed SD')
 audit.write_json(out/'reference-run-manifest.json',{'status':'complete_deterministic_references_only','rule_count':3,'run_identities':120,
  'score_receipts':360,'prediction_rows_by_dataset':dict(counts),'prediction_rows_total':159480,
  'not_part_of_400_NN_fits':True,'not_part_of_five_previous_papers':True,'all_seed_predictions_identical':True,
  'seed_SD':'0 for defined deterministic metrics, null for undefined; not biological repetition or uncertainty',
  'reference_plan_sha256':a.reference_plan_sha256,'global200_selection_barrier_sha256':a.barrier_sha256,'script_sha256':audit.sha(__file__)})

if __name__=='__main__':main()
