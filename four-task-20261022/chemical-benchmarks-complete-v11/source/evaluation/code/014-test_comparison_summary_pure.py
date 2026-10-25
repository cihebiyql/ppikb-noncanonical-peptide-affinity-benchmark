import ast,json,pathlib,runpy,statistics,sys,unittest
u=runpy.run_path(sys.argv[1]);job,proc=u['guard']();src=pathlib.Path(sys.argv[2]).read_text();ns={'statistics':statistics,'METRICS':['mae','rmse','pearson','spearman','r2','bias']};f=[n for n in ast.parse(src).body if isinstance(n,ast.FunctionDef) and n.name in ['num','summary']];exec(compile(ast.Module(body=f,type_ignores=[]),'independent_summary_helpers','exec'),ns)
class Tests(unittest.TestCase):
 def fixture(self):return [dict(kind='test',method='toy',seed=s,n=685,**{m:float(s) for m in ns['METRICS']}) for s in range(10)]
 def test_arithmetic_mean_and_sampleSD(self):
  r=ns['summary'](self.fixture(),['kind','method'])[0];self.assertEqual(r['mae_mean'],4.5);self.assertAlmostEqual(r['mae_sampleSD'],statistics.stdev(range(10)));self.assertEqual(r['mae_valid_seeds'],10)
 def test_constant_keeps_zeroSD(self):
  a=self.fixture()
  for q in a:q['mae']=1.25
  r=ns['summary'](a,['kind','method'])[0];self.assertEqual(r['mae_sampleSD'],0.)
 def test_undefined_correlations_NA_not_zero(self):
  a=self.fixture()
  for q in a:q['pearson']=None;q['spearman']=''
  r=ns['summary'](a,['kind','method'])[0];self.assertIsNone(r['pearson_mean']);self.assertIsNone(r['spearman_sampleSD']);self.assertEqual(r['pearson_valid_seeds'],0)
 def test_valid_group_range_kept(self):
  a=self.fixture()
  for q in a:
   q['all_groups']=155
   for m in ns['METRICS']:q[m+'_valid_groups']=100+q['seed']
  r=ns['summary'](a,['kind','method'])[0];self.assertEqual(r['all_groups'],155);self.assertEqual(r['mae_valid_groups_min'],100);self.assertEqual(r['mae_valid_groups_max'],109)
 def test_missing_seed_rejected(self):
  with self.assertRaises(AssertionError):ns['summary'](self.fixture()[:-1],['kind','method'])
 def test_duplicate_seed_rejected(self):
  a=self.fixture();a[-1]['seed']=0
  with self.assertRaises(AssertionError):ns['summary'](a,['kind','method'])
s=unittest.defaultTestLoader.loadTestsFromTestCase(Tests);r=unittest.TextTestRunner(verbosity=2).run(s);print(json.dumps({'status':'PASS' if r.wasSuccessful() else 'FAIL','tests':r.testsRun,'errors':len(r.errors),'failures':len(r.failures),'process':proc,'NN':0,'torch_imported':'torch' in sys.modules,'scope':'synthetic arithmetic only, no model metrics audited'}));raise SystemExit(not r.wasSuccessful())
