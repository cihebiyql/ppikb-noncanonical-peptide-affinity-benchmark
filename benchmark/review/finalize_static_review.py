import datetime,hashlib,json,pathlib
R=pathlib.Path(__file__).resolve().parent;P=R.parent
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
test=json.loads((R/'synthetic-metrics-verification.json').read_text(encoding='utf-8'))
meta=json.loads((R/'label-free-metadata-verification.json').read_text(encoding='utf-8'))
assert test['successful'] and test['tests_run']==17
assert test['real_gold_reads']==meta['real_gold_reads']==0
assert test['real_prediction_reads']==meta['real_prediction_reads']==0
assert sha(P/'execution/runner.py')==test['runner_sha256']
assert sha(P/'execution/summarize.py')==test['summarizer_sha256']
assert meta['flagged_discordance_rows']==608
assert all(r['sensitivity_membership_exactly_matches_flags'] for r in meta['sensitivity_panels'])
findings=[
 {'id':'REPORT-NC-PRIMARY','priority':'P1-reporting','evidence':'execution/runner.py:score_holdout evaluates full test input; grouped_metrics supplies NC_core and standard separately','finding':'all group mixes NC and standard; must not label it NC-only primary performance','resolution_without_frozen_code_change':'Use NC_core and four mutually exclusive NC strata for primary table; compare NC_only/standard_only trained models on identical NC test IDs; standard test group is a separate control.'},
 {'id':'REPORT-EXTERNAL-COHORTS','priority':'P1-reporting','evidence':'execution/runner.py:grouped_metrics and prediction_rows; external scoring spec frozen67/8/2 IDs','finding':'runner does not summarize external67/8/2 subgroups and drops external flags in saved predictions','resolution_without_frozen_code_change':'After all200 selections freeze and root explicit authorization, independent evaluator joins frozen label-free inputs and subgroup IDs to same75 saved predictions; no refit or selection.'},
 {'id':'COVERAGE-NOT-OBSERVED-ONLY','priority':'P2-completeness','evidence':'execution/summarize.py:all_observed_groups_have_ten_seeds; synthetic10receipt singlemethod fixture','finding':'true only describes observed groups, not full five-method/two-panel/two-regime/ten-seed grid','resolution_without_frozen_code_change':'Independently enumerate exact expected200 internal score identities plus separately declared external scoring coverage; preserve missing/failure states.'},
 {'id':'V4-INTERNAL-SCORE-BINDING','priority':'P2-before-scoring','evidence':'control/prepare_gpu_fit_specs.py builds only v4 fit specs; v3 internal-score specs retain v3 paths','finding':'Old internal scoring drafts must not accidentally point at v3 selections/output','resolution_without_frozen_code_change':'Administrative new v4 score bindings with explicit global selection barrier and immutable input/gold hashes before any numeric holdout read.'},
 {'id':'EXTERNAL-CLAIM-LIMIT','priority':'P1-claim-boundary','evidence':'label-free-metadata-verification.json external_metadata','finding':'All75 are PTM,67primary+8conditional,2target-reference-cold subset;0 familycold and0 actual-assay-clone certification','resolution_without_frozen_code_change':'Report retrospective PTM independent-source/entity evaluation and underpowered2row target-reference-cold diagnostic; do not claim nonproteinogenic/D-backbone external validation or broad family transfer.'},
 {'id':'CHIRALITY-AND-INPUT-VIEW','priority':'P1-claim-boundary','evidence':'methods graphdta-deepnc/mgraph-dgdta/gs-dta adapter declarations and frozen author graph features','finding':'All5 formal graph models omit chirality;4 omit explicit bond order; protein caps1000 or1200 with reference-view construct limitation','resolution_without_frozen_code_change':'Report full atom coverage separately from stereochemical feature fidelity; never claim D/L discrimination or untruncated experimental-clone inputs.'},
 {'id':'MICRO-MACRO-SEEDS','priority':'P2-statistical-interpretation','evidence':'17synthetic fixtures; sampleSD production ddof1','finding':'Row micro error, equal-weight target/source macro, and training-seed SD represent different quantities','resolution_without_frozen_code_change':'Label aggregation explicitly; globalRMSE is square-root weightedMSE, not weightedRMSE mean; disclose defined counts and that10seeds do not create biological replicates.'}
]
report={'scope':'static_source_and_synthetic_mechanical_only_before_global_selection_freeze','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'real_holdout_metrics_evaluated':False,'real_gold_reads':0,'real_prediction_reads':0,'model_checkpoint_loads':0,'training_or_model_selection':False,
 'synthetic_tests':{'passed':17,'failed':0,'first_attempt_preserved':str(R/'synthetic-metrics-verification-first-attempt.json'),'initial_fixture_failure_reason':'Strict dictionary equality on floating correlation1 versus0.9999999999999999; corrected test tolerance, production unchanged'},
 'numeric_formula_check':'passed on hand-computable and seeded synthetic cases; Spearman rank reference is independent average-tie implementation, not a SciPy runtime dependency test',
 'fit_select_test_optimum_path_found':False,'declared_holdout_barrier':'existing score specs must bind explicit all200 barrier; code field is optional, independent evaluator requires it',
 'metadata':{'rows':9619,'NC':2099,'standard':7520,'strata_mapping_errors':0,'discordant_rows':608,'sensitivity_ID_membership_check':'all4 panels/regimes exact','external_counts':meta['external_metadata']},
 'findings':findings,'frozen_production_files_modified':False,'frozen_protocol_or_contract_files_modified':False,
 'runner_sha256':sha(P/'execution/runner.py'),'summarizer_sha256':sha(P/'execution/summarize.py'),
 'independent_evaluator':str(R/'recompute_metrics.py'),'independent_evaluator_sha256':sha(R/'recompute_metrics.py'),
 'real_recomputation_status':'prepared_not_run; await parent separate explicit authorization after200 global selection freeze',
 'reporting_status':'17synthetic checks and label-free metadata verified; no final model performance or training completion claim'}
(R/'static-evaluation-review.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
files=[]
for p in sorted(R.iterdir()):
 if p.is_file() and p.name!='REVIEW-MANIFEST.json':files.append({'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)})
manifest={'scope':report['scope'],'static_review_sha256':sha(R/'static-evaluation-review.json'),'outputs':files,'gold_or_real_predictions_read':False,'production_file_edits':False}
(R/'REVIEW-MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'synthetic_checks_passed':17,'findings':len(findings),'real_gold_reads':0,'real_prediction_reads':0,'report':str(R/'static-evaluation-review.json'),'review_artifacts':len(files)},ensure_ascii=False))
