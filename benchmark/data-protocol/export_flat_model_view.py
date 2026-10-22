"""Export labels only for the frozen task, not for grouping or split selection."""
import json,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent
def read(name):
 with (P/name).open(encoding='utf-8') as f:return list(map(json.loads,f))
def main():
 chem={r['record_id']:r for r in read('chemical-entity-mapping.jsonl')}
 count=0
 with (P/'model-observations.jsonl').open('w',encoding='utf-8') as f:
  for item in read('observations-with-audit.jsonl'):
   o=item['original_observation'];a=item['residue_audit'];c=chem[o['record_id']]
   r={'record_id':o['record_id'],'source_record_id':o['source_record_id'],'peptide_smiles':o['peptide_smiles'],'canonical_isomeric_smiles':c['canonical_isomeric_smiles'],'chemical_entity_id':c['chemical_entity_id'],'achiral_entity_id':c['achiral_entity_id'],'peptide_sequence':o.get('peptide_sequence'),'peptide_sequence_raw':o.get('peptide_sequence_raw'),'target_sequence':o['target_sequence'],'target_id':o['target_id'],'target_sequence_scope':item['target_sequence_scope'],'study_id':o['study_id'],'endpoint':'Kd','pKd':o['p_value'],'evaluation_stratum':item['evaluation_stratum'],'noncanonical_subtypes':a['noncanonical_subtypes'],'NC_core':a['NC_core'],'chemistry_flags':{k:a[k] for k in ['terminal_n_nonfree','terminal_c_nonfree','terminal_n_unknown','terminal_c_unknown','assay_tag_present','linker_present','cyclic_topology']},'annotation_unresolved_components':a['annotation_unresolved_components'],'source_location':o['source_location']}
   assert isinstance(r['pKd'],(int,float));f.write(json.dumps(r,ensure_ascii=False)+'\n');count+=1
 out={'rows':count,'file':'model-observations.jsonl','sha256':hashlib.sha256((P/'model-observations.jsonl').read_bytes()).hexdigest(),'label_source':'unchanged original_observation.p_value = -log10(molar Kd)','input_features':'SMILES and reference target protein sequence; residue labels are evaluation metadata, not default model features','split_join_key':'record_id','training_seed_list':list(range(10)),'endpoint':'Kd'}
 (P/'model-view-manifest.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
