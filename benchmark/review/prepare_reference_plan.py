"""Freeze train-only reference rules and ID/provenance SHA; do not read labels."""
from datetime import datetime,timezone
from pathlib import Path
import json
import recompute_metrics as audit
import deterministic_references as refs

R=Path(__file__).resolve().parent;P=R.parent;F=P/'data-protocol/frozen-v1'

def main():
 manifest=audit.read_json(F/'manifest.json')
 sourcefiles=[F/'manifest.json',F/'inputs.jsonl']
 contexts=[]
 for panel in sorted(audit.PANELS):
  for regime in ['NC_only','standard_only']:
   path=F/'splits'/panel/regime/'train-ids.json';ids=audit.read_json(path)
   if len(ids)!=len(set(ids)):raise ValueError('Duplicate frozen train IDs')
   contexts.append({'split_id':panel,'regime':regime,'train_n':len(ids),'train_ids_path':str(path),'train_ids_sha256':audit.sha(path)})
   sourcefiles.append(path)
 matched=R/'matched-target-diagnostics-v1/manifest.json'
 plan={'schema':'deterministic-train-only-reference-plan.v2','status':'frozen_prepared_not_fit','created_utc':datetime.now(timezone.utc).isoformat(),
  'previous_plan_preserved':{'path':str(R/'deterministic-reference-plan-v1.json'),'sha256':audit.sha(R/'deterministic-reference-plan-v1.json')},
  'revision_reason':'No rule/train-ID change. Bind decimal-constant stable metric helper and read-only compatibility with final cached-scorer metadata schema; no labels or true performance consulted.',
  'reference_rule_ids':list(refs.RULES),
  'rules':{
   'train_mean':'Predict arithmetic mean of pKd over all corresponding panel/regime training observations. No feature,validation or holdout fitting.',
   'train_median':'Predict median pKd over corresponding panel/regime training observations. No feature,validation or holdout fitting.',
   'target_reference_train_median':'Exact complete database target_sequence SHA256 lookup: median of corresponding panel/regime training labels at that reference. If unseen target, fall back to same training subset global median. No minimum-count tuning or source/target similarity model.'},
  'labels_read_during_preparation':False,'reference_statistics_fitted_during_preparation':False,'holdout_predictions_or_gold_read':False,
  'training_label_source':{'path':str(F/'labels.jsonl'),'declared_sha256':manifest['files']['labels.jsonl']['sha256'],
   'declaration_source':str(F/'manifest.json'),'label_file_opened_or_rehashed_now':False,
   'runtime_scope':'After all200 NN selections and explicit root authorization only. Only frozen train IDs below may enter fit_reference; never validation/test/external values.'},
  'label_free_inputs':{'path':str(F/'inputs.jsonl'),'sha256':manifest['files']['inputs.jsonl']['sha256']},
  'source_files_verified_during_preparation':[{'path':str(p),'sha256':audit.sha(p)} for p in sourcefiles],
  'training_contexts':contexts,'training_regimes':['NC_only','standard_only'],'pooled_training':False,
  'seed_ids':list(range(10)),'seed_policy':'Actual same deterministic functions are re-evaluated for each seed0..9 and saved per run. No RNG parameters: prediction vectors should be identical; defined-metric SD expected0, undefined metrics staynull. Not10 independent biological replicates.',
  'reference_run_identities':120,'unique_rule_by_training_contexts':12,'reference_score_receipts':360,
  'reference_prediction_rows_by_dataset':{'PPIKB-internal':148920,'PTM-external75':9000,'IgG-supplement13':1560},
  'reference_prediction_rows_total':159480,
  'NN_reference_accounting_separation':{'NN_papers':5,'NN_candidate_fits':400,'NN_selected_units':200,'NN_score_receipts':600,'NN_prediction_rows':265800,
   'deterministic_rules_do_not_increment_paper_count_or_NN_fits':True},
  'datasets':['PPIKB-internal','PTM-external75','IgG-supplement13'],
  'matched_target_manifest':{'path':str(matched),'sha256':audit.sha(matched)},
  'metrics':'Same stable independent metrics/strata/608flag sensitivity/67+8+2/NC8+standard5/matched-target/source_ref rules as frozen evaluation-plan-v2; NC main performance is NC_core, not mixedall.',
  'source_reference_scope':'study_id macros retain source_refs; metadata aliases are not independent original experiments',
  'dependency_limits':['Repeated measurements and peptide/chemical/source/target dependence remain; no new independent biology from ten deterministic seed files.','Training statistics are observation-row summaries, preserving repeats under existing benchmark protocol.','An exact target-reference lookup does not certify actual assay constructs or transfer to target families.'],
  'gate':'CLI requires verified unchanged complete200 selection barrier plus separate root real-audit authorization before any training labels are opened. No fit/inference run now.',
  'reference_script_path':str(R/'deterministic_references.py'),'reference_script_sha256':audit.sha(R/'deterministic_references.py'),
  'metric_helper_sha256':audit.sha(R/'recompute_metrics.py')}
 audit.write_json(R/'deterministic-reference-plan-v2.json',plan)
 print(json.dumps({'status':plan['status'],'references':3,'training_labels_read':False,'contexts':[{'panel':c['split_id'],'regime':c['regime'],'train_n':c['train_n']} for c in contexts],'separate_reference_scores':360,'separate_reference_prediction_rows':159480},ensure_ascii=False))

if __name__=='__main__':main()
