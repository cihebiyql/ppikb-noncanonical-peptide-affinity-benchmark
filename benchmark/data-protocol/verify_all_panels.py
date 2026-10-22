"""Read frozen candidate assignments and independently check declared overlaps."""
import json,hashlib,csv
from pathlib import Path
from collections import defaultdict,Counter
P=Path(__file__).resolve().parent
def read(name):
 with (P/name).open(encoding='utf-8') as f:return list(map(json.loads,f))
rows=read('label-free-grouping-input.jsonl');chem={r['record_id']:r for r in read('chemical-entity-mapping.jsonl')};aliases={r['record_id']:r['source_aliases'] for r in read('label-free-study-aliases.jsonl')}
targetedges=read('target-homology-pairs.jsonl');chemedges=read('chemical-neighbor-edges.jsonl');report={}
for panel in ['source_peptide_dependency_cold','target_reference_homology_cold','dual_source_peptide_target_diagnostic']:
 path=P/'split-proposals'/panel/'assignments.csv'
 with path.open(encoding='utf-8-sig') as f:a={r['record_id']:r for r in csv.DictReader(f)}
 assert set(a)=={r['record_id'] for r in rows}
 def cross(kind):
  d=defaultdict(set)
  for r in rows:
   values=aliases[r['record_id']] if kind=='source' else [chem[r['record_id']][kind]] if kind in {'chemical_entity_id','achiral_entity_id'} else [r['target_sequence'][:1000]] if kind=='target_effective_prefix_1000' else [r[kind]]
   for value in values:d[value].add(a[r['record_id']]['split'])
  return sum(len(v)>1 for v in d.values())
 target_parts=defaultdict(set);chemical_parts=defaultdict(set)
 for r in rows:
  target_parts[hashlib.sha256(r['target_sequence'].encode()).hexdigest()[:20]].add(a[r['record_id']]['split']);chemical_parts[chem[r['record_id']]['chemical_entity_id']].add(a[r['record_id']]['split'])
 targetcross=sum(len(target_parts[e['a']]|target_parts[e['b']])>1 for e in targetedges if e['a'] in target_parts and e['b'] in target_parts)
 chemcross=sum(len(chemical_parts[e['a']]|chemical_parts[e['b']])>1 for e in chemedges)
 result={'exact_source_aliases_cross_partition':cross('source'),'exact_isomeric_graphs_cross_partition':cross('chemical_entity_id'),'exact_achiral_graphs_cross_partition':cross('achiral_entity_id'),'exact_target_reference_sequences_cross_partition':cross('target_sequence'),'target_effective_prefix_1000_cross_partition':cross('target_effective_prefix_1000'),'declared_target_similarity_edges_cross_partition':targetcross,'declared_chemical_neighbor_edges_cross_partition':chemcross,'rows':len(a),'assignment_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
 if panel!='target_reference_homology_cold':assert result['exact_source_aliases_cross_partition']==result['exact_isomeric_graphs_cross_partition']==result['exact_achiral_graphs_cross_partition']==chemcross==0
 if panel!='source_peptide_dependency_cold':assert result['exact_target_reference_sequences_cross_partition']==result['target_effective_prefix_1000_cross_partition']==targetcross==0
 report[panel]=result
source=json.loads((P/'input-manifest.json').read_text(encoding='utf-8'))
for name,expected in source['source_files'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==expected
out={'all_checks_passed':True,'source_inputs_unchanged':True,'target_all_pair_runtime_receipt':json.loads((P/'target-homology-runtime-receipt.json').read_text()),'panel_audits':report,'models_fit':0,'claimed_scope':'Zero overlaps only for each panel declared constraints. Crossings intentionally allowed on other axes are reported.'}
(P/'independent-leakage-verification.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out,indent=2))
