"""Freeze reporting plan from existing accepted label-free metadata, never gold."""
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import json
import recompute_metrics as independent

R=Path(__file__).resolve().parent;P=R.parent
S=P/'external-validation/scoring-supplement13-v1'

def main():
 mp=S/'root-accepted-manifest.json';independent.require_hash(mp,independent.SUPPLEMENT_ACCEPTED_SHA)
 accepted=independent.read_json(mp)
 verified=[]
 for a in accepted['artifacts']:
  path=Path(a['path'])
  # Numeric gold remains sealed. Its manifest-declared SHA is not reread here.
  if 'gold' in path.parts or 'gold' in path.name.lower():continue
  independent.require_hash(path,a['sha256']);verified.append(str(path))
 ip=S/'inputs/input13.jsonl';rows=independent.read_jsonl(ip)
 if any(any(k in r for k in ('pKd','Kd_M','reported_value','pKd_true','pKd_pred')) for r in rows):raise ValueError('Not label-free supplement input')
 ids=set(independent.read_json(S/'ids-all13.json'));nc=set(independent.read_json(S/'ids-nc8.json'));std=set(independent.read_json(S/'ids-standard5.json'))
 assert len(rows)==len(ids)==13 and len(nc)==8 and len(std)==5 and not nc&std and nc|std==ids
 assert {r['record_id'] for r in rows}==ids
 assert {r['record_id'] for r in rows if r['NC_core']}==nc
 assert Counter(r['evaluation_stratum'] for r in rows)=={'synthetic_D_backbone':8,'standard20_control':5}
 assert {len(r['target_sequence']) for r in rows}=={449}
 assert len({r['target_sequence'] for r in rows})==1
 assert all(r['external_source_cold_against_PPIKB'] and r['external_chemical_cold_against_full_PPIKB'] and r['external_reference_target_related'] for r in rows)
 assert not any(r['external_family_cold_certified'] or r['external_reference_target_cold'] or r['actual_assay_clone_verified'] for r in rows)
 matchedpath=R/'matched-target-diagnostics-v1/manifest.json';matched=independent.load_matched_manifest(matchedpath,independent.sha(matchedpath))
 # Inspect declared score specifications only: never dereference their gold paths.
 barrier_specs=[]
 for folder,glob in [(P/'external-validation/scoring-views-v1','*-score.cpu.json'),(S,'*-score.cpu.json')]:
  for path in sorted(folder.glob(glob)):
   spec=independent.read_json(path)
   assert spec.get('selection_barrier_path') and spec['selection_barrier_path'].endswith('/formal-runs-gpu-v4/all-selections-frozen.json')
   barrier_specs.append({'path':str(path),'sha256':independent.sha(path),'global200_barrier_explicit':True,'numeric_files_dereferenced':False})
 expected=[]
 for ds in independent.EXPECTED_PREDICTION_ROWS:
  for method in sorted(independent.METHODS):
   for panel in sorted(independent.PANELS):
    for regime in ['NC_only','standard_only']:
     for seed in range(10):
      n=(1039 if panel=='source_peptide_dependency_cold' else 1443) if ds=='PPIKB-internal' else (75 if ds=='PTM-external75' else 13)
      expected.append({'dataset_id':ds,'method_id':method,'split_id':panel,'regime':regime,'seed':seed,'expected_prediction_rows':n})
 assert len(expected)==600 and sum(r['expected_prediction_rows'] for r in expected)==265800
 plan={'schema':'independent-postfreeze-evaluation-plan.v3','status':'prepared_no_inference','created_utc':datetime.now(timezone.utc).isoformat(),
  'previous_plan_preserved':{'path':str(R/'evaluation-plan-v2.json'),'sha256':independent.sha(R/'evaluation-plan-v2.json')},
  'revision_reason':'Bind final frozen cached-scorer schema and stable decimal-constant independent metrics; metadata cohorts and matched-target IDs unchanged; no true performance consulted.',
  'production_dataset_ids_unchanged':['source_test','target_test','external75','supplement13'],
  'analysis_dataset_groups_only':{'source_test':'PPIKB-internal','target_test':'PPIKB-internal','external75':'PTM-external75','supplement13':'IgG-supplement13'},
  'frozen_cached_scorer_review':{'path':str(R/'frozen-cached-scorer-source-review-v1.json'),'sha256':independent.sha(R/'frozen-cached-scorer-source-review-v1.json')},
  'score_spec_metadata_independent_review':{'path':str(R/'score-spec-independent-review-v1.json'),'sha256':independent.sha(R/'score-spec-independent-review-v1.json')},
  'deterministic_references_separate_plan':{'path':str(R/'deterministic-reference-plan-v2.json'),'sha256':independent.sha(R/'deterministic-reference-plan-v2.json'),'counts_not_added_to_NN_600':True},
  'model_selection_count':200,'candidate_fit_count':400,'expected_score_receipts':600,
  'expected_score_receipts_by_dataset':{d:200 for d in independent.EXPECTED_PREDICTION_ROWS},
  'expected_prediction_rows_by_dataset':independent.EXPECTED_PREDICTION_ROWS,'expected_prediction_rows_total':265800,
  'datasets':[
   {'dataset_id':'PPIKB-internal','holdout_id':'internal-test','n_per_selected_model':{'source_peptide_dependency_cold':1039,'target_reference_homology_cold':1443},'primary':'NC_core and mutually exclusive NC strata; standard control separately; all is mixed diagnostic only'},
   {'dataset_id':'PTM-external75','holdout_id':'external75-PTM-reference-view-v1','n':75,'primary':67,'conditional_sensitivity':8,'reference_target_cold_subset':2,'all_PTM':True,'family_cold_certified':0},
   {'dataset_id':'IgG-supplement13','holdout_id':'postfreeze-supplement13-reference-view-v1','n':13,'synthetic_D_backbone':8,'standard20_control':5,'PTM':0,'source_and_declared_chemical_cold':True,'all_reference_targets_related':True,'single_heavy_reference_length':449,'whole2H2L_reference_identity_provenance_preserved':True,'whole2H2L_actual_construct_lot_glycoform_family_certified':False,'single_study_not13independent_systems':True,'do_not_merge_with_external75':True}],
  'supplement_root_manifest':{'path':str(mp),'sha256':independent.sha(mp)},
  'supplement_label_free_verified':{'rows':13,'NC8':8,'standard5':5,'all_target_length449':True,'shared_full_target_reference_count':1,'source_id_references':sorted({r['study_id'] for r in rows}), 'source_ref_scope':'machine study_id; one original study, not13independent biological systems','non_gold_artifacts_verified':verified},
  'gold_artifact_read_or_rehashed':False,'real_prediction_read':False,'model_loaded':False,
  'matched_target_manifest':{'path':str(matchedpath),'sha256':independent.sha(matchedpath)},'matched_target_panels':matched['panels'],
  'statistical_rules':['Per fixed selected model/seed generate each dataset prediction once; all subgroup metrics reuse it.','Separate dataset_id for internal,PTM75,IgG13; never sum case sets into universal external family validation.','Main paired training-regime comparison uses identical heldout NC IDs; matched-target diagnostic additionally uses same common full-reference target SHA sets.','Target-reference macros are equal-weight per target; report observation n,target n,metric-defined-group n. Study macros include source_refs and are not independent-paper counts.','Seed SD ddof1 quantifies optimization randomness; data/source/chemical/target dependencies remain, no biological CI claim.'],
  'runtime_gate':'Every score and independent real-data audit must explicitly require unchanged full200 global selection barrier. This preparation grants no real-gold/prediction audit permission.',
  'external_score_spec_barriers':barrier_specs,'internal_v4_score_binding':'must be issued/verified by administrative lane before scoring; no modification to frozenfit/training here',
  'evaluator_sha256_at_preparation':independent.sha(R/'recompute_metrics.py'),'expected_unit_identities':expected}
 independent.write_json(R/'evaluation-plan-v3.json',plan)
 print(json.dumps({'status':'prepared_no_inference','datasets':3,'expected_score_receipts':600,'expected_prediction_rows':265800,'supplement13_non_gold_verified':True,'matched_targets':[{'panel':x['panel'],'targets':x['shared_target_reference_count'],'NC_n':x['NC_matched_test_n'],'standard_n':x['standard_matched_test_n']} for x in matched['panels']],'gold_reads':0,'real_prediction_reads':0},ensure_ascii=False))

if __name__=='__main__':main()
