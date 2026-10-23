"""Registry-only tests; no fabricated scientific results are exported."""
import importlib.util,unittest
from pathlib import Path
s=importlib.util.spec_from_file_location('report',Path(__file__).with_name('export_complete_dta_report.py'));r=importlib.util.module_from_spec(s);s.loader.exec_module(r)
class FinalGateTests(unittest.TestCase):
 def setUp(self):self.keys=[{'logical_key':[v,m,n]} for v in r.VIEWS for m in r.METHODS for n in range(10)]
 def test_every_registered_key_once_passes_metadata_gate(self):r.complete_gate(self.keys)
 def test_missing_seed_blocks_final(self):
  with self.assertRaises(ValueError):r.complete_gate(self.keys[:-1])
 def test_duplicate_cannot_fill_denominator(self):
  with self.assertRaises(ValueError):r.complete_gate(self.keys[:-1]+[self.keys[0]])
 def test_unregistered_seed_blocks_final(self):
  self.keys[-1]={'logical_key':[r.VIEWS[-1],r.METHODS[-1],10]}
  with self.assertRaises(ValueError):r.complete_gate(self.keys)
 def test_current_partial_census_cannot_export_final(self):
  current=r.load(r.H/'accepted-census-current.json');census=r.load(current['path'])
  if len(census['records'])==150:self.skipTest('scientific execution has naturally finished all150')
  with self.assertRaises(ValueError):r.complete_gate(census['records'])
if __name__=='__main__':unittest.main(verbosity=2)
