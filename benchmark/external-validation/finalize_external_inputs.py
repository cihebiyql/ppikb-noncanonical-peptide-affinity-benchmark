"""Integrate retained format-conversion receipts without changing source labels."""
from pathlib import Path
from collections import Counter
import hashlib,json

HERE=Path(__file__).resolve().parent
def loadl(p):return [json.loads(l) for l in p.open(encoding='utf-8') if l.strip()]
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def main():
    source=HERE/'inputs/blind-inputs.jsonl';rows=loadl(source)
    converted_path=HERE/'chemistry-format-conversion-v3/Kliche-exact-annotation-format-converted.jsonl'
    converted={r['external_id']:r for r in loadl(converted_path)}
    assert len(converted)==75
    for row in rows:
        key=row['external_id']
        if key not in converted:
            row['primary_external_input_eligibility']=False
            continue
        conv=converted[key]
        assert row['residue_modifications']==conv['source_modifications']
        assert row['n_terminal']==conv['source_terminal_annotation']['n_terminal']
        assert row['c_terminal']==conv['source_terminal_annotation']['c_terminal']
        row.update(peptide_smiles=conv['peptide_smiles'],representation_origin=conv['representation_origin'],protonation_convention=conv['phosphate_protonation_convention'],input_status='chemical_graph_exact_author_annotation_converted_target_reference_view')
        row['primary_external_input_eligibility']=not bool(row['source_flags'].get('target_boundary_conflict') or row['source_flags'].get('binding_site_conditioned'))
        row['primary_eligibility_scope']='input-only candidate; posttraining evaluation requires source/entity overlap and model-specific frozen input checks'
    out=HERE/'inputs/blind-inputs-with-certified-format-conversion.jsonl'
    with out.open('w',encoding='utf-8') as f:
        for r in rows:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    assert sum(bool(r.get('peptide_smiles')) for r in rows)==75
    assert sum(r['primary_external_input_eligibility'] for r in rows)==67
    # Eliminate label-derived QC from model-readable flags. Provenance/gold keep it.
    assert all(not any(term in k.lower() for term in ('kd','sem','mean','value','magnitude','fit')) for r in rows for k in (r.get('source_flags')or{}))
    summary={'external_input_rows':127,'chemical_graph_rows':75,'primary_unconditioned_reference_view_candidates':67,'conditional_construct_or_binding_site_sensitivity_rows':8,'unresolved_linker_or_full_fusion_rows':52,'residue_groups':{'PTM_only':127,'nonproteinogenic_D_backbone':0},'resource_molecular_input_counts':dict(Counter(r['resource_id'] for r in rows if r.get('peptide_smiles'))),'primary_resource_counts':dict(Counter(r['resource_id'] for r in rows if r['primary_external_input_eligibility'])),'source_input_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'converted_source_sha256':hashlib.sha256(converted_path.read_bytes()).hexdigest(),'molecular_inputs_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'chemical_entity_claim':'Derived chemical format faithfully encodes existing annotation, not new experimental identity certification. Neutral phosphate protonation is a representation convention.','gold_isolation':'retrospective previously inspected; programmatic only, not user/OS-level access enforcement','label_derived_QC_removed_from_blind_inputs':True,'original_assay_clone_sequence_verified_rows':0,'model_training':False}
    dump(HERE/'external-final-input-summary.json',summary)
    print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
