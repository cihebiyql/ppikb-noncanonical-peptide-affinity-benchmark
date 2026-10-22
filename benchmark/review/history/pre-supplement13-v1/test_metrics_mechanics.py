"""Pure synthetic tests: no real sealed labels, model predictions or checkpoints."""
from __future__ import annotations
import argparse,ast,csv,hashlib,importlib.util,json,math
from collections import defaultdict
from pathlib import Path
import statistics,tempfile,types,unittest
import numpy as np
import recompute_metrics as independent

ROOT=Path(__file__).resolve().parent.parent
REVIEW=Path(__file__).resolve().parent
def production_functions():
 tree=ast.parse((ROOT/'execution/runner.py').read_text(encoding='utf-8'))
 names={'numeric_metrics','grouped_metrics','is_nc','filter_scope'}
 subset=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[])
 # Isolate only pure numeric functions; never import runner/Torch/model adapters.
 scope={'np':np,'rankdata':independent.average_ranks}
 exec(compile(subset,'runner_pure_numeric_AST_only','exec'),scope)
 return scope

P=production_functions()
class MetricMechanics(unittest.TestCase):
 def assert_metric(self,y,p,expected):
  a=independent.metrics(y,p);b=P['numeric_metrics'](y,p)
  for k,x in expected.items():
   if x is None:self.assertIsNone(a[k]);self.assertIsNone(b[k])
   else:self.assertAlmostEqual(a[k],x,places=12);self.assertAlmostEqual(b[k],x,places=12)
  for k in independent.METRICS:
   if a[k] is None:self.assertIsNone(b[k])
   else:self.assertAlmostEqual(a[k],b[k],places=12)

 def test_known_numeric_fixture(self):
  self.assert_metric([1,2,3],[1,3,2],dict(n=3,MAE=2/3,RMSE=math.sqrt(2/3),Pearson=.5,Spearman=.5,R2=0))

 def test_negative_R2_and_anticorrelation(self):
  self.assert_metric([1,2,3],[3,2,1],dict(MAE=4/3,RMSE=math.sqrt(8/3),Pearson=-1,Spearman=-1,R2=-3))

 def test_tied_average_ranks(self):
  self.assertEqual(independent.average_ranks([1,1,2,4]).tolist(),[1.5,1.5,3,4])
  self.assert_metric([0,0,1,4],[0,2,3,3],dict(Spearman=8/9))

 def test_constant_truth_null(self):
  self.assert_metric([2,2,2],[1,2,3],dict(MAE=2/3,RMSE=math.sqrt(2/3),Pearson=None,Spearman=None,R2=None))

 def test_constant_prediction_still_defined_R2(self):
  self.assert_metric([1,2,3],[2,2,2],dict(MAE=2/3,RMSE=math.sqrt(2/3),Pearson=None,Spearman=None,R2=0))

 def test_empty_and_singleton(self):
  self.assert_metric([],[],dict(n=0,MAE=None,RMSE=None,Pearson=None,Spearman=None,R2=None))
  self.assert_metric([1],[1.5],dict(n=1,MAE=.5,RMSE=.5,Pearson=None,Spearman=None,R2=None))

 def test_invalid_values_raise(self):
  for y,p in [([1],[1,2]),([math.nan],[1]),([1],[math.inf])]:
   with self.assertRaises(ValueError):independent.metrics(y,p)
   with self.assertRaises(ValueError):P['numeric_metrics'](y,p)

 def test_random_numeric_parity(self):
  rng=np.random.default_rng(903)
  for n in [2,5,13,100]:
   for _ in range(4):
    y=rng.normal(size=n);p=y+rng.normal(size=n)
    self.assert_metric(y,p,{})

 def test_sample_SD_ten_seeds(self):
  rows=[dict(seed=s,n=3,**{k:float(s) for k in independent.METRICS}) for s in range(10)]
  z=independent.summarize_seeds(rows)
  self.assertAlmostEqual(z['MAE_mean'],4.5)
  self.assertAlmostEqual(z['MAE_sd'],math.sqrt(82.5/9))
  self.assertNotAlmostEqual(z['MAE_sd'],math.sqrt(82.5/10))
  self.assertEqual(z['missing_seeds'],[])

 def test_null_metrics_and_incomplete_seeds_not_zero_imputed(self):
  rows=[dict(seed=s,n=1,MAE=2.,RMSE=2.,Pearson=None,Spearman=None,R2=None) for s in range(9)]
  z=independent.summarize_seeds(rows)
  self.assertEqual(z['missing_seeds'],[9]);self.assertEqual(z['Pearson_defined_seed_count'],0)
  self.assertIsNone(z['Pearson_mean']);self.assertIsNone(z['Pearson_sd'])
  with self.assertRaises(ValueError):independent.summarize_seeds([rows[0],rows[0]])

 def test_micro_vs_macro(self):
  rows=[dict(pKd_true=0.,pKd_pred=0.,target_id='A') for _ in range(9)]+[dict(pKd_true=0.,pKd_pred=10.,target_id='B')]
  micro=independent.metrics([r['pKd_true'] for r in rows],[r['pKd_pred'] for r in rows]);macro=independent.macro_metrics(rows,'target_id')
  self.assertEqual(micro['MAE'],1);self.assertEqual(macro['macro_mean']['MAE'],5)
  self.assertEqual(macro['row_weighted_MAE'],1)
  self.assertAlmostEqual(micro['RMSE'],math.sqrt(10));self.assertAlmostEqual(macro['row_weighted_RMSE'],math.sqrt(10))
  self.assertEqual(macro['macro_mean']['RMSE'],5)
  self.assertEqual(macro['defined_group_counts']['Pearson'],0)

 def test_discordance_and_strata_sensitivity_reuses_same_predictions(self):
  ss=['synthetic_D_backbone','PTM','synthetic_and_PTM','other_NC','standard20_control']
  rows=[dict(record_id=str(i),pKd=float(i+1),pKd_true=float(i+1),pKd_pred=float(i+1)+1,NC_core=i<4,evaluation_stratum=s,residue_class_graph_discordance=i==1) for i,s in enumerate(ss)]
  values=[r['pKd_pred'] for r in rows];a=independent.group_metrics(rows);b=P['grouped_metrics'](rows,values)
  self.assertEqual(set(a),set(b))
  for group in a:
   for metric in ('n',)+independent.METRICS:
    if a[group][metric] is None:self.assertIsNone(b[group][metric])
    else:self.assertAlmostEqual(a[group][metric],b[group][metric],places=12)
  self.assertEqual(a['all']['n'],5);self.assertEqual(a['NC_core']['n'],4)
  self.assertEqual(a['standard']['n'],1);self.assertEqual(a['exclude_discordant_sensitivity']['n'],4)
  self.assertEqual(a['exclude_discordant:PTM']['n'],0)

 def test_external_overlapping_target_subset_not_disjoint_third_cohort(self):
  rows=[dict(pKd_true=float(i),pKd_pred=float(i),NC_core=True,evaluation_stratum='PTM',external_primary=i<4,external_conditional_sensitivity=i>=4,external_reference_target_cold=i<2) for i in range(5)]
  z=independent.group_metrics(rows)
  self.assertEqual([z[k]['n'] for k in ['all','external_primary67','external_conditional_sensitivity8','external_reference_target_cold2']],[5,4,1,2])
  # Names refer to current actual cohorts; synthetic fixture is explicitly not real75.

 def test_real_holdout_authorization_required_before_any_read(self):
  with self.assertRaises(PermissionError):independent.authorize_barrier('must-not-be-opened','not-a-hash',False)

 def test_complete_synthetic_barrier_and_incomplete_rejection(self):
  with tempfile.TemporaryDirectory(prefix='barrier-fixture-',dir=REVIEW) as td:
   root=Path(td);entries=[]
   for method in sorted(independent.METHODS):
    for panel in sorted(independent.PANELS):
     for regime in ('NC_only','standard_only'):
      for seed in range(10):
       p=root/(str(len(entries))+'.json')
       independent.write_json(p,dict(status='frozen',method_id=method,split_id=panel,regime=regime,seed=seed,holdout_metrics_consulted=False))
       entries.append(dict(path=str(p),sha256=independent.sha(p)))
   barrier=root/'barrier.json'
   independent.write_json(barrier,dict(status='all_selections_frozen',selection_count=200,candidate_fit_count=400,selections=entries))
   b,h=independent.authorize_barrier(barrier,independent.sha(barrier),True)
   self.assertEqual(len(h),200)
   independent.write_json(barrier,dict(status='all_selections_frozen',selection_count=200,candidate_fit_count=400,selections=entries[:-1]))
   with self.assertRaises(ValueError):independent.authorize_barrier(barrier,independent.sha(barrier),True)

 def test_synthetic_receipt_truth_identity_and_numeric_recompute(self):
  # All fake gold/prediction data are under review temporary fixture, never any
  # actual model output. This verifies the future post-freeze interface.
  with tempfile.TemporaryDirectory(prefix='receipt-fixture-',dir=REVIEW) as td:
   r=Path(td)
   inputs=[dict(record_id=str(i),NC_core=True,evaluation_stratum='PTM',target_id='synthetic-target',study_id='synthetic-study') for i in range(2)]
   predicted=[dict(x,pKd_true=float(i),pKd_pred=float(i*2)) for i,x in enumerate(inputs)]
   gold=[dict(record_id=str(i),pKd=float(i)) for i in range(2)]
   for filename,rows in [('inputs.jsonl',inputs),('synthetic-gold.jsonl',gold),('predictions.jsonl',predicted)]:
    (r/filename).write_text(''.join(json.dumps(x)+'\n' for x in rows),encoding='utf-8')
   spec=dict(split_id='synthetic-panel',holdout_id='synthetic-test',input_rows=str(r/'inputs.jsonl'),input_rows_sha256=independent.sha(r/'inputs.jsonl'),label_rows=str(r/'synthetic-gold.jsonl'),label_rows_sha256=independent.sha(r/'synthetic-gold.jsonl'))
   independent.write_json(r/'spec.json',spec)
   expected=independent.group_metrics(predicted)
   receipt=dict(status='complete',stage='post-selection-score-only',split_id='synthetic-panel',holdout_id='synthetic-test',method_id='GraphDTA-GIN',regime='NC_only',seed=0,n=2,metrics=expected,selection_sha256='synthetic-selection-sha',holdout_spec_sha256=independent.sha(r/'spec.json'),predictions_sha256=independent.sha(r/'predictions.jsonl'))
   independent.write_json(r/'complete.json',receipt)
   task=dict(score_receipt=str(r/'complete.json'),holdout_spec=str(r/'spec.json'))
   out=independent.audit_task(task,{'synthetic-selection-sha'})
   self.assertTrue(out['all_truths_match_frozen_gold']);self.assertEqual(out['runner_metric_differences'],[])
   self.assertEqual(out['metrics']['all']['MAE'],.5)
   with self.assertRaises(ValueError):independent.audit_task(task,{'wrong-selection-sha'})

 def test_production_summarizer_with_only_synthetic_receipts(self):
  # Execute only summarize.main with injected IO helpers, all paths under a
  # temporary fixture directory. Never import execution.runner or scan real runs.
  import sys
  tree=ast.parse((ROOT/'execution/summarize.py').read_text(encoding='utf-8'))
  main=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=='main')
  module=ast.Module(body=[main],type_ignores=[])
  helper=types.SimpleNamespace(read_json=independent.read_json,require_hash=independent.require_hash,sha_file=independent.sha,write_json=independent.write_json)
  scope={'argparse':argparse,'defaultdict':defaultdict,'csv':csv,'Path':Path,'np':np,'runner':helper}
  exec(compile(module,'summarize_synthetic_only','exec'),scope)
  with tempfile.TemporaryDirectory(prefix='metric-fixture-',dir=REVIEW) as td:
   root=Path(td);scores=root/'scores';scores.mkdir()
   for seed in range(10):
    d=scores/str(seed);d.mkdir();p=d/'predictions.jsonl';p.write_text('{}\n')
    met=dict(n=1,MAE=float(seed),RMSE=float(seed),Pearson=None,Spearman=None,R2=None)
    independent.write_json(d/'complete.json',dict(stage='post-selection-score-only',split_id='synthetic',holdout_id='synthetic',method_id='synthetic-one-method-only',regime='NC_only',seed=seed,predictions_sha256=independent.sha(p),metrics={'all':met}))
   previous=sys.argv[:]
   try:sys.argv=['synthetic-summarize','--scoring-root',str(scores),'--output',str(root/'out')];scope['main']()
   finally:sys.argv=previous
   z=list(csv.DictReader((root/'out/ten-seed-summary.csv').open(encoding='utf-8-sig')))[0]
   self.assertAlmostEqual(float(z['MAE_sd']),math.sqrt(82.5/9));self.assertEqual(z['Pearson_defined_seed_count'],'0')
   m=independent.read_json(root/'out/summary-manifest.json')
   self.assertTrue(m['all_observed_groups_have_ten_seeds'])
   self.assertEqual(m['score_receipt_count'],10) # proves not a complete200-grid test

if __name__=='__main__':
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(MetricMechanics)
 result=unittest.TextTestRunner(verbosity=2).run(suite)
 report={'scope':'pure synthetic mechanical verification; no real holdout labels/predictions/checkpoints read',
         'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'successful':result.wasSuccessful(),
         'runner_sha256':independent.sha(ROOT/'execution/runner.py'),'summarizer_sha256':independent.sha(ROOT/'execution/summarize.py'),
         'independent_evaluator_sha256':independent.sha(REVIEW/'recompute_metrics.py'),
         'production_functions_loaded':'AST-isolated numeric/group functions only; rank reference is independent average-rank implementation; no Torch/adapter imports',
         'production_summarizer_loaded':'AST-isolated main; injected synthetic temp-directory IO only',
         'real_gold_reads':0,'real_prediction_reads':0,'model_evaluations':0}
 independent.write_json(REVIEW/'synthetic-metrics-verification.json',report)
 raise SystemExit(0 if result.wasSuccessful() else 1)
