"""Synthetic aggregate rows only. No real summaries or app import calls."""
import unittest,tempfile,json,copy
from pathlib import Path
import adapter as a
def fixture(**changes):
 row={'category':'five_prior_paper_NN','dataset_id':'PPIKB-internal','panel':a.PANELS[0],'method_id':'GraphDTA-GIN','regime':'NC_only','cohort':'NC_core','aggregation':'row_micro','metric':'MAE','mean':.25,'sample_sd':.125,'completed_seed_count':10,'defined_seed_count':10,'n_by_seed':{str(i):303 for i in range(10)},'n_unit':'observation_rows','missing_seeds':[]}
 row.update(changes);return row
def with_n(row,n):return dict(row,n_by_seed={str(i):n for i in range(row['completed_seed_count'])})
class AdapterTest(unittest.TestCase):
 def test_ten_seeds_and_SD_preserved(self):
  source=fixture();r=a.convert_rows([source])['rows'][0]
  self.assertEqual((r['mean'],r['sd'],r['n'],r['seed_count']),(.25,.125,303,10));self.assertEqual(r['chemistry_id'],'NC_all')
 def test_constant_correlation_null_not_zero(self):
  source=fixture(metric='Pearson',mean=None,sample_sd=None,defined_seed_count=0,values_by_seed={str(i):None for i in range(10)})
  r=a.convert_rows([source]);self.assertIsNone(r['rows'][0]['mean']);self.assertIsNone(r['rows'][0]['sd']);self.assertEqual(r['rows'][0]['seed_count'],0);self.assertEqual(r['mapping_trace'][0]['completed_seed_count'],10)
 def test_partial_defined_seeds_not_inflated(self):
  row=fixture(defined_seed_count=9,values_by_seed={str(i):None if i==4 else .25 for i in range(10)})
  self.assertEqual(a.convert_rows([row])['rows'][0]['seed_count'],9)
 def test_one_defined_keeps_nullSD(self):
  row=fixture(defined_seed_count=1,sample_sd=None,values_by_seed={str(i):.25 if i==0 else None for i in range(10)})
  self.assertIsNone(a.convert_rows([row])['rows'][0]['sd'])
 def test_external_2_8_67_denominators_separate(self):
  rs=[with_n(fixture(dataset_id='PTM-external75',cohort=c),n) for c,n in [('external_primary67',67),('external_conditional_sensitivity8',8),('external_reference_target_cold2',2)]]
  out=a.convert_rows(rs)['rows'];self.assertEqual([r['n'] for r in out],[67,8,2]);self.assertEqual(len({r['evaluation_set_id'] for r in out}),3);self.assertTrue(all(r['chemistry_id']=='PTM' for r in out))
 def test_supplement_8_5_not_merged_with_external(self):
  rows=[with_n(fixture(dataset_id='IgG-supplement13',cohort=c),n) for c,n in [('supplement_NC8',8),('supplement_standard5',5)]]
  out=a.convert_rows(rows)['rows'];self.assertEqual([r['chemistry_id'] for r in out],['synthetic_D_backbone','standard20_control']);self.assertTrue(all('IgG-supplement13' in r['evaluation_set_id'] for r in out))
 def test_all_is_never_renamed_NC(self):
  r=a.convert_rows([with_n(fixture(cohort='all'),1039)])['rows'][0];self.assertEqual(r['chemistry_id'],'all')
 def test_four_strata_explicit(self):
  for c,n in [('synthetic_D_backbone',100),('PTM',158),('synthetic_and_PTM',39),('other_NC',6)]:self.assertEqual(a.convert_rows([with_n(fixture(cohort=c),n)])['rows'][0]['chemistry_id'],c)
 def test_clean_all_stays_all_no_missing_NC_created(self):
  out=a.convert_rows([with_n(fixture(cohort='exclude_discordant_sensitivity'),998)])['rows'];self.assertEqual(len(out),1);self.assertEqual(out[0]['chemistry_id'],'all')
 def test_clean_NC_only_when_source_supplies(self):
  r=a.convert_rows([with_n(fixture(cohort='NC_core_exclude_discordant_sensitivity'),274)])['rows'][0];self.assertEqual(r['chemistry_id'],'NC_all')
 def test_clean_stratum_keeps_original_scope(self):
  r=a.convert_rows([with_n(fixture(cohort='exclude_discordant:PTM'),100)])['rows'][0];self.assertEqual(r['chemistry_id'],'PTM');self.assertIn('exclude_discordant%3APTM',r['evaluation_set_id'])
 def test_matched_observations_not_targets(self):
  r=a.convert_rows([with_n(fixture(cohort='NC_matched',aggregation='matched_row_micro'),90)])['rows'][0];self.assertEqual(r['n'],90);self.assertIn('matched_row_micro',r['evaluation_set_id'])
 def test_macro_excluded_preserved_not_appended(self):
  row=with_n(fixture(cohort='all_diagnostic',aggregation='equal_weight_study_id',n_unit='study_id_groups'),26)
  result=a.convert_rows([row]);self.assertEqual(result['rows'],[]);self.assertEqual(result['excluded_macros'][0]['original_row'],row)
 def test_macro_count_disguised_as_micro_rejected(self):
  with self.assertRaises(ValueError):a.convert_rows([fixture(n_unit='target_reference_groups')])
 def test_differing_n_by_seed_rejected(self):
  row=fixture();row['n_by_seed']['9']=302
  with self.assertRaises(ValueError):a.convert_rows([row])
 def test_unknown_cohort_not_silent(self):
  with self.assertRaises(ValueError):a.convert_rows([fixture(cohort='unrecognized_future_cohort')])
 def test_explicit_scoped_unknown_exclusion_preserved(self):
  row=fixture(cohort='future_unknown');rule={k:row[k] for k in ['category','dataset_id','cohort','aggregation']};rule['reason']='synthetic test: unsupported new scope'
  result=a.convert_rows([row],[rule]);self.assertEqual(result['rows'],[]);self.assertEqual(result['explicitly_excluded'][0]['original_row'],row)
 def test_wrong_dataset_named_group_rejected(self):
  with self.assertRaises(ValueError):a.convert_rows([with_n(fixture(cohort='external_primary67'),67)])
 def test_null_seed_count_rejected_not_guessed(self):
  with self.assertRaises(ValueError):a.convert_rows([fixture(defined_seed_count=None)])
 def test_wrong_frozen_denominator_rejected(self):
  with self.assertRaises(ValueError):a.convert_rows([with_n(fixture(cohort='external_primary67',dataset_id='PTM-external75'),75)])
 def test_NaN_rejected(self):
  with self.assertRaises(ValueError):a.convert_rows([fixture(mean=float('nan'))])
 def test_duplicate_summary_key_rejected(self):
  with self.assertRaises(ValueError):a.convert_rows([fixture(),fixture()])
 def test_unapproved_real_input_never_opened(self):
  with tempfile.TemporaryDirectory() as d:
   auth=Path(d)/'auth.json';auth.write_text('{"schema":"metric-adapter-authorization-v1","root_metric_adapter_authorized":false}')
   with self.assertRaises(PermissionError):a.run(auth,Path(d)/'does-not-exist-summary.json',Path(d)/'output')
 def test_structural_zero_group_keeps_null_metric(self):
  row=with_n(fixture(dataset_id='PTM-external75',cohort='standard',mean=None,sample_sd=None,defined_seed_count=0),0)
  out=a.convert_rows([row])['rows'][0];self.assertEqual(out['n'],0);self.assertIsNone(out['mean'])
 def test_authorized_synthetic_cli_writes_only_conversion_outputs(self):
  with tempfile.TemporaryDirectory(dir=a.HERE,prefix='synthetic-mechanics-') as temp:
   root=Path(temp);source=root/'synthetic-summary.json';joint=root/'synthetic-joint-barrier.json';review=root/'synthetic-source-review.json';auth=root/'synthetic-authorization.json';out=root/'converted'
   source.write_text(json.dumps([fixture(),with_n(fixture(cohort='all_diagnostic',aggregation='equal_weight_study_id',n_unit='study_id_groups'),3)]));joint.write_text('{"synthetic_only":true}');review.write_text('{"synthetic_only":true}')
   binding={'schema':'metric-adapter-authorization-v1','root_metric_adapter_authorized':True,'reviewed':True,'independently_recomputed':True,'all_required_selections_frozen':True,'adapter_sha256':a.sha(a.__file__),'source_summary':{'path':str(source),'sha256':a.sha(source)},'source_review':{'path':str(review),'sha256':a.sha(review)},'joint_barrier':{'path':str(joint),'sha256':a.sha(joint)}};auth.write_text(json.dumps(binding))
   result=a.run(auth,source,out);self.assertEqual(result['converted_row_count'],1);self.assertEqual(result['excluded_macro_rows'],1);self.assertFalse(result['app_modified']);self.assertFalse(result['import_or_build_called'])
   manifest=a.load(out/'import-review-json.template.json');self.assertFalse(manifest['reviewed']);self.assertEqual(manifest['summary_sha256'],a.sha(out/'app-metrics.json'));self.assertEqual(result['source_summary_sha256'],a.sha(source))
if __name__=='__main__':unittest.main()
