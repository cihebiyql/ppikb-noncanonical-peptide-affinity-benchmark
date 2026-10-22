"""Prepare runner-compatible external inputs; never fit, infer, or select models.

Immutable acceptance-v1 inputs/gold are read, never modified.  All 75 predictions
should be generated once per frozen model; 67/8/2 summaries reuse those predictions.
"""
from pathlib import Path
from collections import Counter
import csv,hashlib,json,math

HERE=Path(__file__).resolve().parent
EXTERNAL=HERE.parent
PROJECT=EXTERNAL.parent
EXPECTED_ACCEPTANCE_SHA='85973838adc28c0b6b9134a28a90312162a158eafd20f8b2bf14e68e13d36c4d'
PANELS=('source_peptide_dependency_cold','target_reference_homology_cold')
def readl(path):return [json.loads(l) for l in path.open(encoding='utf-8') if l.strip()]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(path,value):
 assert not path.exists(),'Output exists; use a new scoring view version: '+str(path)
 path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
def writel(path,rows):
 assert not path.exists(),'Output exists; use a new scoring view version: '+str(path)
 with path.open('w',encoding='utf-8') as f:
  for row in rows:f.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
def wsl(path):
 p=str(path).replace('\\','/');assert p[1:3]==':/'
 return '/mnt/'+p[0].lower()+p[2:]

def main():
 acceptance=EXTERNAL/'acceptance-manifest.json'
 assert sha(acceptance)==EXPECTED_ACCEPTANCE_SHA
 frozen=json.loads(acceptance.read_text(encoding='utf-8'))
 for entry in frozen['artifacts']:
  p=Path(entry['path']);assert sha(p)==entry['sha256'] and p.stat().st_size==entry['bytes']
 inputs=readl(EXTERNAL/'inputs/blind-inputs-with-certified-format-conversion.jsonl')
 oldgold={r['external_id']:r for r in readl(EXTERNAL/'gold/posttraining-gold.jsonl')}
 chemistry={r['external_id']:r for r in readl(PROJECT/'data-protocol/external-chemical-overlap.jsonl')}
 grades={r['external_id']:r for r in csv.DictReader((EXTERNAL/'external-evaluation-grades.csv').open(encoding='utf-8-sig'))}
 allowed=set(frozen['eligible_external_ids']);primary=set(frozen['primary_external_ids'])
 sensitive=set(frozen['conditional_sensitivity_external_ids']);cold=set(frozen['target_reference_cold_inference_ids'])
 assert (len(allowed),len(primary),len(sensitive),len(cold))==(75,67,8,2)
 assert primary.isdisjoint(sensitive) and primary|sensitive==allowed and cold<=primary
 modelrows=[];goldrows=[]
 subtype={'phosphoserine':'PTM_pSer','phosphothreonine':'PTM_pThr','phosphotyrosine':'PTM_pTyr'}
 unit_to_M={'nM':1e-9,'uM':1e-6,'µM':1e-6,'μM':1e-6,'M':1.0}
 for r in inputs:
  rid=r['external_id']
  if rid not in allowed:continue
  g=oldgold[rid];graph=chemistry[rid]
  assert not graph['neighbor_edges'] and r['peptide_smiles'] and r['target_sequence_view']
  assert all(r['peptide_sequence'][m['position_1based']-1]=={'phosphoserine':'S','phosphothreonine':'T','phosphotyrosine':'Y'}[m['type']] for m in r['residue_modifications'])
  flags=r.get('source_flags')or{}
  assert not any(any(term in k.lower() for term in ['kd','sem','mean','magnitude','fit','value']) for k in flags)
  record={
   'record_id':rid,'source_record_id':r['source_record_id'],'resource_id':r['resource_id'],
   'peptide_smiles':r['peptide_smiles'],'canonical_isomeric_smiles':r['peptide_smiles'],
   'chemical_entity_id':graph['external_chemical_entity_id'],'achiral_entity_id':graph['external_achiral_entity_id'],
   'peptide_sequence':r['peptide_sequence'],'peptide_sequence_raw':r['peptide_sequence_raw'],
   'target_sequence':r['target_sequence_view'],'target_id':r['target_id'],'target_reference_accession':r.get('target_accession'),
   'target_sequence_scope':'reference_view_not_verified_assay_clone','study_id':r['study_id'],'endpoint':'Kd',
   'evaluation_stratum':'PTM','NC_core':True,
   'noncanonical_subtypes':['ptm_phosphorylation']+[subtype[m['type']] for m in r['residue_modifications']],
   'residue_modifications':r['residue_modifications'],'n_terminal':r['n_terminal'],'c_terminal':r['c_terminal'],
   'chemistry_flags':['derived_measured_entity_format','neutral_phosphate_representation_convention','terminal_caps_retained'],
   'annotation_unresolved_components':[],
   'source_file':r['source_file'],'source_sha256':r['source_sha256'],'source_location':r['source_location'],
   'chemical_source_file':r.get('chemical_source_file'),'chemical_source_sha256':r.get('chemical_source_sha256'),'chemical_source_location':r.get('chemical_source_location'),
   'target_reference_provenance':r['target_reference_provenance'],'target_reported_domain_boundary':r.get('target_reported_domain_boundary'),
   'target_reference_view':True,'actual_assay_clone_verified':False,
   'format_derived_from_exact_measured_entity_annotation':True,'experimental_identity_newly_certified':False,
   'representation_origin':r['representation_origin'],'phosphate_protonation_convention':r['protonation_convention'],
   'source_chemical_or_construct_flags':flags,
   'external_primary':rid in primary,'external_conditional_sensitivity':rid in sensitive,
   'external_reference_target_cold':rid in cold,'external_family_cold_certified':False,
   'external_source_cold_against_PPIKB':True,'external_chemical_cold_against_full_PPIKB':True,
   'external_evaluation_status':'retrospective_previously_inspected_gold_post_selection_only',
  }
  assert 'pKd' not in record
  modelrows.append(record)
  mol=float(g['reported_value'])*unit_to_M[g['reported_unit']]
  assert math.isclose(mol,float(g['Kd_M']),rel_tol=1e-12,abs_tol=1e-25)
  truth=-math.log10(mol);assert math.isclose(truth,float(g['pKd']),rel_tol=1e-12,abs_tol=1e-12)
  goldrows.append({'record_id':rid,'endpoint':'Kd','pKd':g['pKd'],'Kd_M':g['Kd_M'],'reported_value':g['reported_value'],'reported_unit':g['reported_unit'],
   'qualifier':'=','unit_conversion':{'formula':'pKd=-log10(reported_value * unit_to_molar_factor)','unit_to_molar_factor':unit_to_M[g['reported_unit']],'recomputed_pKd':truth,'matches_preserved_original_label':True},
   'uncertainty':g.get('uncertainty'),'affinity_derived_QC_flags':g.get('affinity_derived_QC_flags'),
   'study_id':r['study_id'],'resource_id':r['resource_id'],'source_file':r['source_file'],'source_sha256':r['source_sha256'],'source_location':r['source_location'],
   'preserved_original_gold_container':str(EXTERNAL/'gold/posttraining-gold.jsonl'),'gold_exposure':'previously_inspected_retrospective_not_prospective_blind','allowed_usage':'post_global_200_selection_freeze_score_only'})
 assert len(modelrows)==len(goldrows)==len({r['record_id'] for r in modelrows})==75
 assert Counter(r['evaluation_stratum'] for r in modelrows)=={'PTM':75}
 input_path=HERE/'inputs75.jsonl';gold_path=HERE/'gold75.jsonl'
 writel(input_path,modelrows);writel(gold_path,goldrows)
 for name,ids in [('all75',allowed),('primary67',primary),('conditional-sensitivity8',sensitive),('reference-target-cold2',cold)]:dump(HERE/('ids-'+name+'.json'),sorted(ids))
 specs=[]
 for panel in PANELS:
  path=HERE/(panel+'-external75-score.cpu.json')
  spec={'split_id':panel,'holdout_id':'external75-PTM-reference-view-v1','input_rows':wsl(input_path),'input_rows_sha256':sha(input_path),
   'label_rows':wsl(gold_path),'label_rows_sha256':sha(gold_path),'output_root':wsl(PROJECT/'formal-runs-gpu-v4/external-scores-v1'/panel),
   'selection_barrier_path':wsl(PROJECT/'formal-runs-gpu-v4/all-selections-frozen.json'),'methods_root':wsl(PROJECT/'methods'),
   'cpu_threads':2,'batch_size':32,'device':'cpu','gpu_explicitly_authorized':False,
   'scientific_external_status':'75 retrospective independently sourced chemical-entity-cold PTM cases;67 unconditioned and8 conditional;2 reference-target-cold; not family-cold or original clone-certified',
   'acceptance_manifest_path':wsl(acceptance),'acceptance_manifest_sha256':EXPECTED_ACCEPTANCE_SHA,
   'external_primary_ids':wsl(HERE/'ids-primary67.json'),'external_conditional_sensitivity_ids':wsl(HERE/'ids-conditional-sensitivity8.json'),
   'external_reference_target_cold_ids':wsl(HERE/'ids-reference-target-cold2.json'),
   'prepared_only_no_inference':True,'resource_note':'CPU-safe prepared scoring specification. GPU use requires a separate reviewed launch binding; retain200selection barrier.','subgroup_scoring':'Reuse all75 predictions for67/8/2 metrics; do not retrain or select on subgroup performance.'}
  dump(path,spec);specs.append(path)
 # Validate the static score_holdout schema without importing adapters or opening
 # any model checkpoint/selection. Barrier intentionally does not yet have to exist.
 runner=PROJECT/'execution/runner.py';runnertext=runner.read_text(encoding='utf-8')
 assert 'def score_holdout(' in runnertext and "holdout['input_rows']" in runnertext and "holdout['label_rows']" in runnertext
 for p in specs:
  spec=json.loads(p.read_text(encoding='utf-8'));assert spec['input_rows_sha256']==sha(input_path) and spec['label_rows_sha256']==sha(gold_path)
 assert sha(acceptance)==EXPECTED_ACCEPTANCE_SHA
 for entry in frozen['artifacts']:assert sha(Path(entry['path']))==entry['sha256']
 files=[input_path,gold_path,*sorted(HERE.glob('ids-*.json')),*specs]
 manifest={'schema':'runner-external-scoring-views.v1','status':'prepared_verified_not_inferred','rows':75,'source_counts':dict(Counter(r['resource_id'] for r in modelrows)),
  'input_has_no_pKd':True,'all_gold_conversion_records_checked':True,'NC_core_true_rows':75,'evaluation_stratum':'PTM','primary67':67,'conditional_sensitivity8':8,'reference_target_cold2':2,
  'acceptance_manifest_sha256':EXPECTED_ACCEPTANCE_SHA,'runner_sha256_at_schema_readback':sha(runner),
  'gold_isolation':'Procedural only under shared user account; raw labels previously inspected; no external hyperparameter selection',
  'model_results_produced':False,'model_checkpoint_loaded':False,'inference_executed':False,'training_executed':False,
  'artifacts':[{'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in files]}
 dump(HERE/'scoring-view-manifest.json',manifest)
 print(json.dumps({k:v for k,v in manifest.items() if k!='artifacts'},ensure_ascii=False))
if __name__=='__main__':main()
