import unittest,json,hashlib,csv
from pathlib import Path
from collections import defaultdict
import assemble_split_proposal as m
P=Path(__file__).resolve().parent
class ProtocolTest(unittest.TestCase):
 def test_no_label_in_grouping(self):
  forbidden={'p_value','value','value_molar','affinity','label','y'}
  for r in m.load('label-free-grouping-input.jsonl'):self.assertFalse(set(r)&forbidden)
 def test_counts_and_endpoint(self):
  rs=m.load('observations-with-audit.jsonl');self.assertEqual(len(rs),9619)
  self.assertEqual(sum(r['residue_audit']['NC_core'] for r in rs),2099)
  for r in rs:
   o=r['original_observation'];self.assertEqual(o['endpoint'],'Kd');self.assertEqual(o['qualifier'],'=');self.assertTrue(r['residue_audit']['technical_exact_molecular_candidate'])
   self.assertNotIn(o['source_record_id'],{'PPIRE08361','PPIRE08362'})
 def test_order_independent_assignment(self):
  comps=[['a','b'],['c'],['d','e','f'],['g'],['h'],['i']]
  self.assertEqual(m.assign(comps),m.assign([list(reversed(x)) for x in reversed(comps)]))
 def test_actual_chemical_input_alignment(self):
  receipt=json.loads((P/'chemical-runtime-receipt.json').read_text());self.assertEqual(receipt['input_sha256'],hashlib.sha256((P/'label-free-grouping-input.jsonl').read_bytes()).hexdigest())
  mapping=m.load('chemical-entity-mapping.jsonl');self.assertEqual(len(mapping),9619);self.assertEqual(len({r['record_id'] for r in mapping}),9619)
 def test_source_panel_every_constraint(self):
  rows=m.load('label-free-grouping-input.jsonl');chem={r['record_id']:r for r in m.load('chemical-entity-mapping.jsonl')}
  with (P/'split-proposals/source_peptide_dependency_cold/assignments.csv').open(encoding='utf-8-sig') as f:assignments={r['record_id']:r['split'] for r in csv.DictReader(f)}
  u,_=m.source_components(rows,chem);groups=defaultdict(set)
  for i,r in enumerate(rows):groups[u.find(i)].add(assignments[r['record_id']])
  self.assertTrue(all(len(s)==1 for s in groups.values()));self.assertEqual(set(assignments),{r['record_id'] for r in rows})
if __name__=='__main__':unittest.main()
