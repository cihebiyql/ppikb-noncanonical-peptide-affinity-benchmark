"""Freeze external evaluation scope after label-free independence checks."""
from pathlib import Path
from collections import Counter,defaultdict
import csv,hashlib,json
HERE=Path(__file__).resolve().parent;PROTOCOL=HERE.parent/'data-protocol'
def read(p):return [json.loads(l) for l in p.open(encoding='utf-8') if l.strip()]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 manifest=HERE/'acceptance-manifest.json'
 assert not manifest.exists(),'Immutable v1 already frozen; write a versioned sidecar for changes.'
 inputs=read(HERE/'inputs/blind-inputs-with-certified-format-conversion.jsonl')
 gold={r['external_id']:r for r in read(HERE/'gold/posttraining-gold.jsonl')}
 chem={r['external_id']:r for r in read(PROTOCOL/'external-chemical-overlap.jsonl')}
 targets={r['external_id']:r for r in read(PROTOCOL/'external-target-overlap.jsonl')}
 full={r['external_id']:r for r in read(HERE/'full-PPIKB-audit-runtime/external-versus-all-PPIKB-chemical-overlap.jsonl')}
 blacklist=json.loads((HERE/'training-blacklist.json').read_text(encoding='utf-8'))
 assert len(inputs)==len(gold)==len(targets)==127 and len(chem)==len(full)==75
 assert len(blacklist['source_blacklist_record_ids'])==len(blacklist['conservative_related_entity_blacklist_record_ids'])==0
 grades=[]
 for r in inputs:
  key=r['external_id'];g=gold[key];assert g['endpoint']=='Kd'
  t=targets[key];hasgraph=bool(r.get('peptide_smiles'))
  if hasgraph:
   c=chem[key];fc=full[key]
   assert not c['neighbor_edges'] and not fc['same_isomeric_graph_records'] and not fc['same_achiral_graph_records'] and not fc['neighbors_ge_0_8']
  grades.append({'external_id':key,'resource_id':r['resource_id'],'residue_group':r['residue_group'],
   'source_doi_pmid_title_no_match_in_all_PPIKB':True,
   'chemical_graph_input_present':hasgraph,
   'entity_cold_against_main_declared_graph_rule':True if hasgraph else None,
   'entity_cold_against_full_21845_declared_graph_rule':True if hasgraph else None,
   'target_reference_or_domain_cold_against_all_main_declared_rule':t['target_cold_against_all_main_declared_rule'],
   'target_family_cold_certified':False,'actual_assay_clone_sequence_certified':False,
   'input_cohort':'primary_unconditioned_reference_view' if r.get('primary_external_input_eligibility') else 'conditional_construct_or_binding_site_sensitivity' if hasgraph else 'assets_only_unresolved_real_linker_or_fusion',
   'candidate_for_posttraining_inference':hasgraph,
   'forbidden_for_hyperparameter_selection':True,
   'prospective_blind':False,
   'model_pretraining_supervised_label_contamination_gate':'model-specific required before claiming fully independent model evaluation',
   'scope':'Declared reference/domain and chemical graph views; not complete experimental construct certification.'})
 out=HERE/'external-evaluation-grades.csv'
 with out.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(grades[0]));w.writeheader();w.writerows(grades)
 eligible=[r for r in grades if r['candidate_for_posttraining_inference']]
 primary=[r for r in grades if r['input_cohort']=='primary_unconditioned_reference_view']
 counts={'external_point_records_preserved':127,'posttraining_inference_candidates':75,'primary_unconditioned_reference_view':67,'conditional_construct_or_binding_site_sensitivity':8,'assets_only_missing_ligand_graph_or_fusion':52,'PTM_only':127,'nonproteinogenic_D_backbone_ready':0,
  'source_cold_records':127,'molecular_entity_cold_records_against_main_and_full_PPIKB':75,
  'target_reference_cold_inference_candidates':sum(r['target_reference_or_domain_cold_against_all_main_declared_rule'] for r in eligible),
  'target_reference_cold_primary_candidates':sum(r['target_reference_or_domain_cold_against_all_main_declared_rule'] for r in primary),
  'target_reference_cold_assets_only':sum(r['target_reference_or_domain_cold_against_all_main_declared_rule'] for r in grades if not r['candidate_for_posttraining_inference']),
  'actual_assay_clone_sequence_certified':0,'family_cold_certified':0,'source_or_entity_train_blacklist_records':0}
 assert counts['target_reference_cold_inference_candidates']==counts['target_reference_cold_primary_candidates']==2
 files=[HERE/'inputs/blind-inputs-with-certified-format-conversion.jsonl',HERE/'inputs/external-targets.fasta',HERE/'gold/posttraining-gold.jsonl',HERE/'training-blacklist.json',out,HERE/'external-final-input-summary.json',HERE/'full-PPIKB-audit-runtime/full-PPIKB-chemical-runtime-receipt.json',HERE/'full-PPIKB-audit-runtime/external-versus-all-PPIKB-chemical-overlap.jsonl',HERE/'chemistry-format-conversion-v3/execution-receipt.json',PROTOCOL/'external-chemical-overlap.jsonl',PROTOCOL/'external-chemical-runtime-receipt.json',PROTOCOL/'external-target-overlap.jsonl',PROTOCOL/'external-target-overlap-summary.json']
 obj={'schema_version':'external-retrospective-holdout-acceptance.v1','status':'frozen_reference_view_external_scope_with_explicit_remaining_model_gates','counts':counts,'resource_counts':dict(Counter(r['resource_id'] for r in grades)),'eligible_external_ids':[r['external_id'] for r in eligible],'primary_external_ids':[r['external_id'] for r in primary],'conditional_sensitivity_external_ids':[r['external_id'] for r in grades if r['input_cohort']=='conditional_construct_or_binding_site_sensitivity'],'assets_only_external_ids':[r['external_id'] for r in grades if not r['candidate_for_posttraining_inference']],
  'target_reference_cold_inference_ids':[r['external_id'] for r in eligible if r['target_reference_or_domain_cold_against_all_main_declared_rule']],
  'graph_rule':'RDKit canonical isomeric and achiral graph equality; achiral Morgan radius2 2048bits Tanimoto>=0.8; raw charge/stereochemical representation preserved, no tautomer/protonation identity claim',
  'target_rule':'Main protocol frozen BLOSUM62 local best alignment, >=30% identical paired residues and >=80% paired-residue coverage of both references, plus exact domain containment and actual model-prefix identity; not a broad target-family negative certificate',
  'gold_policy':{'location':'gold/posttraining-gold.jsonl','usage':'After all model/seed hyperparameters frozen; same 10 fixed seeds as main evaluation; no external calibration/model selection','prior_exposure':'These labels were already inspected in prior audits, so retrospective independently sourced evaluation, not prospective blind validation','technical_isolation':'Separate files and dataflow checks under shared account; no claim of OS/user credential access isolation','affinity_derived_QC_flags':'Removed from model inputs, retained only in gold/provenance; model-invariant sensitivity masks may be predeclared from inherited flags'},
  'evaluation_contract':{'endpoint':'pKd=-log10(Kd in mol/L), label kept exactly from prior normalization','denominator':'75 eligible candidates and separately67/8 predeclared input cohorts; missing/model-rejected inputs reported per model with reasons, never silently drop','primary_metrics':['MAE','RMSE','Pearson_r','Spearman_rho'],'aggregation':'Per source, combined and NC/PTM subtype; model-seed individual results retained; source/entity grouped uncertainty reflects dependence','nonproteinogenic_D_backbone':'No ready external group currently; cannot claim PTM evidence covers this stratum','actual_model_results_in_this_manifest':False},
  'model_specific_remaining_gates':['Verify fitted feature pipeline supports exact measured SMILES/caps/PTM representation without replacing nc residues by canonical analogues.','Freeze train/validation-selected parameters before opening external gold.','Audit each author model or pretrained checkpoint supervised dataset provenance for these source studies.','Preserve target reference/domain view in model inputs and output scope; no verified-clone claim.'],
  'excluded_resources':['PepLand and its inherited IBM binding data','Predicted Propedia affinities','HSM enzyme/substrate labels as affinity','MRBLE apparent Kd as exact physical Kd'],
  'new_nonPTM_lead':'new-resource-leads/IgG-Fc-2025-lead-summary.json;19new point Kd incl13NC but0model-ready, not included in v1',
  'artifacts':[{'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in files],
  'freeze_policy':'After v1 accepted by main protocol, changes only through a new versioned sidecar; do not overwrite v1.'}
 manifest.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'path':str(manifest),'sha256':sha(manifest),'counts':counts},ensure_ascii=False))
if __name__=='__main__':main()
