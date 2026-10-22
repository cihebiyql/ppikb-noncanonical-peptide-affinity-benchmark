"""Stage post-freeze supplemental candidate inputs/gold, never adopt or infer."""
from pathlib import Path
from collections import Counter
import hashlib,json,math,re
HERE=Path(__file__).resolve().parent;PROJECT=HERE.parents[1]
def read(p):return [json.loads(l) for l in p.open(encoding='utf-8') if l.strip()]
def write(p,rows):
 with p.open('w',encoding='utf-8') as f:
  for row in rows:f.write(json.dumps(row,ensure_ascii=False)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 formats={r['record_id']:r for r in read(HERE/'runtime-conversion-v1/author-entity-formats.jsonl')}
 annotated=read(HERE/'explicit-input-format-annotations.jsonl');target=json.loads((HERE/'target-reference-multichain.json').read_text(encoding='utf-8'));heavy=target['target_reference_heavy_sequence']
 rows=[];gold=[]
 for r in annotated:
  rid=r['record_id']
  if rid not in formats:continue
  f=formats[rid];obs=r['source_original_observation'];nc=obs['residue_evidence']=='noncanonical';a=r['actual_chemical_annotation']
  rows.append({'external_id':rid,'record_id':rid,'resource_id':'IgG_Fc_2025_postfreeze','source_record_id':obs['author_peptide_or_substitution'],'study_id':r['study_id'],'source_pmid':'41407376',
   'source_file':obs['source_file'],'source_sha256':obs['source_sha256'],'source_location':obs['source_location'],
   'peptide_sequence':None,'peptide_sequence_raw':a['actual_chemical_notation'],'peptide_smiles':f['peptide_smiles'],'canonical_isomeric_smiles':f['canonical_isomeric_smiles'],'chemical_entity_id':f['chemical_entity_id'],'achiral_entity_id':f['achiral_entity_id'],
   'NC_core':nc,'evaluation_stratum':'synthetic_D_backbone' if nc else 'standard20_control','noncanonical_subtypes':[x for x in a['actual_residue_tokens'] if len(x)>1],
   'actual_residue_tokens':a['actual_residue_tokens'],'disulfide_residue_positions_1based':a['disulfide_residue_positions_1based'],'n_terminal':a['n_terminal'],'c_terminal':a['c_terminal'],
   'source_chemical_annotation':a,'format_derived':True,'source_HRMS_formula_and_CIP_checks_passed':True,
   'target_id':'Trastuzumab_reference_2H2L_heavy_chain_view','target_sequence':heavy,'target_reference_components':target['reference_components'],
   'target_sequence_scope':'proposed_heavy_chain_reference_for_Fc_side_binding_not_whole2H2L_or_assayed_clone',
   'target_reference_source_url':target['reference_source_url'],'target_reference_source_sha256':target['reference_source_sha256'],
   'whole_commercial_antibody_or_lot_certified':False,'target_single_chain_view_requires_root_adoption':True,'external_family_cold_certified':False,
   'adoption_status':'postfreeze_supplementary_input_audit_only_not_in_current75','model_prediction_produced':False})
  mol=obs['Kd_M'];assert math.isclose(obs['pKd'],-math.log10(mol),abs_tol=1e-12)
  gold.append({'record_id':rid,'pKd':obs['pKd'],'Kd_M':mol,'reported_value':obs['Kd_M']/1e-9,'reported_unit':'nM','qualifier':'=','unit_conversion':'Kd_M=reported_nM*1e-9; pKd=-log10(Kd_M)','study_id':r['study_id'],'source_file':obs['source_file'],'source_sha256':obs['source_sha256'],'source_location':obs['source_location'],'raw_author_Kd':obs['Kd_raw'],'uncertainty_reported':obs['reported_uncertainty'],'exposure':'retrospective_raw_values_inspected_during_preparation','never_used_for_model_selection':True})
 assert len(rows)==13 and Counter(r['NC_core'] for r in rows)=={True:8,False:5}
 write(HERE/'supplement-inputs13-not-adopted.jsonl',rows);write(HERE/'supplement-gold13-not-adopted.jsonl',gold)
 pp=read(PROJECT.parent/'peptide-binding-expanded-corpus-20261021/resources/PPIKB_all_endpoints/normalized-observations.jsonl')
 norm=lambda s:re.sub('[^a-z0-9]','',str(s or '').lower())
 title='Structure–Activity Relationship Study of Affinity Peptides for the Fc Site of Human Immunoglobulin G';hits=[]
 for x in pp:
  raw=x.get('row_raw')or{}
  if x.get('study_id')=='10.1248/cpb.c25-00637' or raw.get('DOI')=='10.1248/cpb.c25-00637' or str(raw.get('PMID'))=='41407376' or norm(raw.get('Title'))==norm(title):hits.append(x['record_id'])
 (HERE/'supplement-source-audit.json').write_text(json.dumps({'PPIKB_rows_checked':len(pp),'DOI_PMID_title_source_matches':hits,'labels_used_to_decide_source_matching':False,'same_scaffold_ancestry':'Original study explicitly builds on earlier parent ligands; absence of this DOI is not family/chemical independence.','new_root_manifest_required':True},ensure_ascii=False,indent=2),encoding='utf-8')
 # All source/graph and target comparisons use label-free rows.
 copy=HERE/'all-PPIKB-label-free-molecules.jsonl'
 if not copy.exists():copy.write_bytes((HERE.parent/'inputs/all-PPIKB-label-free-molecules.jsonl').read_bytes())
 with (HERE/'target-reference-and-main-inputs.json').open('w',encoding='utf-8') as out:
  json.dump({'query_heavy_reference':heavy,'main_reference_targets':sorted({r['target_sequence'] for r in read(PROJECT/'data-protocol/frozen-v1/inputs.jsonl')}),'query_reference_sha256':hashlib.sha256(heavy.encode()).hexdigest()},out)
 summary={'ready_for_bounded_format_and_independence_audit':13,'NC':8,'standard_controls':5,'source_match_rows':len(hits),'target_input_proposal':'monoclonal2H2L identity retained; full heavy-chain reference only as explicit model view, not an assayed isolated Fc/whole antibody representation','current_frozen75_modified':False,'adopted_into_current_benchmark':False,'unit_conversion_checked':True,'input_sha256':sha(HERE/'supplement-inputs13-not-adopted.jsonl'),'gold_sha256':sha(HERE/'supplement-gold13-not-adopted.jsonl')}
 (HERE/'supplement-preparation-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
