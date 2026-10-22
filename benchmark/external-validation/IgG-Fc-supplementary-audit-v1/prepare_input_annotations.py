"""Post-freeze source transcription of already measured IgG affinity entities."""
from pathlib import Path
from collections import Counter
import hashlib,json,re
import fitz

HERE=Path(__file__).resolve().parent;EXTERNAL=HERE.parent
SUPPORTED=set('ACDEFGHIKLMNPQRSTVWY')|{'Abu','D-Asp','1-Nal','2-Nal','alloThr','D-Arg','2-Pya'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 src=HERE/'author-SI-0.pdf';doc=fitz.open(src);annotations={}
 for page in range(4,len(doc)):
  text=doc[page].get_text()
  blocks=re.split(r'\n(?=15(?:-|LGH))',text)
  for block in blocks:
   hit=re.search(r'(15(?:-|LGH)[^:\n]*):\s*(Ac-[^\n]+)',block)
   if not hit:continue
   name=hit.group(1).strip();chem=hit.group(2).strip()
   form=re.search(r'calcd for\s+([A-Z][A-Za-z0-9]+)\s*\[(M\+H|MH)\]\+',block)
   assert form,(name,page)
   assert chem.endswith(', *disulfide'),(name,chem)
   chain=chem.split(',')[0];assert chain.startswith('Ac-')
   if chain.endswith('-NH2'):terminal='NH2';core=chain[3:-4]
   elif chain.endswith('-OH'):terminal='OH';core=chain[3:-3]
   else:raise ValueError(chain)
   tokens=[];cys=[]
   for m in re.finditer(r'\([^)]+\)|[A-Z]|\*',core):
    token=m.group()
    if token=='*':cys.append(len(tokens));assert tokens[-1]=='C'
    else:tokens.append(token.strip('()'))
   assert ''.join('('+x+')' if len(x)>1 else x for x in tokens)==core.replace('*',''),(name,core,tokens)
   annotations[name]={'author_name':name,'actual_chemical_notation':chem,'actual_residue_tokens':tokens,'n_terminal':'Ac','c_terminal':terminal,'disulfide_residue_positions_1based':cys,'author_protonated_molecular_formula':form.group(1),'author_formula_ion':form.group(2)+'+','source_SI_page_1based':page+1,'source_SI_sha256':sha(src)}
 assert len(annotations)==23,len(annotations)
 kegg=HERE/'KEGG-D03257.txt';text=kegg.read_text(encoding='utf-8');seqsection=text[text.index('SEQUENCE'):text.index('TYPE',text.index('SEQUENCE')) if 'TYPE' in text[text.index('SEQUENCE'):] else len(text)]
 # The reference record explicitly separates Heavy/Light chains; keep both.
 hm=re.search(r'\(Heavy chain\)\s*([A-Z\s]+?)\(Light chain\)',seqsection)
 lm=re.search(r'\(Light chain\)\s*([A-Z\s]+?)\(Disulfide bridge',seqsection)
 assert hm and lm
 heavy=re.sub(r'\s+','',hm.group(1));light=re.sub(r'\s+','',lm.group(1));assert set(heavy)<=set('ACDEFGHIKLMNPQRSTVWY') and set(light)<=set('ACDEFGHIKLMNPQRSTVWY')
 assert len(heavy)==449 and len(light)==214,(len(heavy),len(light))
 target={'identity':'Trastuzumab monoclonal humanized IgG1, not pooled serum IgG','reference_source_url':'https://rest.kegg.jp/get/D03257','reference_source_sha256':sha(kegg),'reference_components':[{'chain':'heavy','sequence':heavy,'stoichiometry':2},{'chain':'light','sequence':light,'stoichiometry':2}],'proposed_single_input_view':'full heavy-chain reference for Fc-side binding, preserves whole2H2L identity in metadata; not original assay target or exact isolated Fc construct','target_reference_heavy_sequence':heavy,'target_reference_light_sequence':light,'actual_assay_molecular_entity_certified':False,'actual_glycoform_or_lot_certified':False,'requires_new_root_manifest_before_any_external_evaluation':True}
 (HERE/'target-reference-multichain.json').write_text(json.dumps(target,ensure_ascii=False,indent=2),encoding='utf-8')
 tables=[json.loads(l) for l in (EXTERNAL/'new-resource-leads/IgG-Fc-2025-new-observations-not-model-ready.jsonl').open(encoding='utf-8')]
 rows=[];excluded=[]
 for obs in tables:
  name=obs['author_peptide_or_substitution'];wanted='15-'+re.sub(r'\s+[ab]\s*\)\s*$','',name)
  for prefix,new in [('IAPG-1','15LGH'),('IAPG-2','15LGH-Tyr6(1-Nal)'),('IAPG-3','15LGH-Tyr6(2-Nal)'),('IAPG-4','15LGH-Y6Tpi')]:
   if name.startswith(prefix):wanted=new;break
  assert wanted in annotations,(name,wanted)
  a=annotations[wanted];reasons=[]
  if obs['qualifier']!='=':reasons.append('not_exact_measured_point_Kd')
  unknown=sorted(set(a['actual_residue_tokens'])-SUPPORTED)
  if unknown:reasons.append('unsupported_or_counterion_ambiguous_chemical_tokens:'+','.join(unknown))
  if len(a['actual_residue_tokens'])!=15:reasons.append('author_SI_sequence_vs_series_length_identity_conflict_no_repair')
  if len(a['disulfide_residue_positions_1based'])!=2:reasons.append('disulfide_connectivity_unresolved')
  obj={'record_id':obs['lead_id'],'author_measured_entity_name':name,'study_id':obs['study_id'],'actual_chemical_annotation':a,'source_original_observation':obs,'target_reference':target}
  if reasons:excluded.append({**obj,'exclusion_reasons':reasons})
  else:rows.append(obj)
 with (HERE/'explicit-input-format-annotations.jsonl').open('w',encoding='utf-8') as f:
  for row in rows:f.write(json.dumps(row,ensure_ascii=False)+'\n')
 with (HERE/'explicit-label-free-inputs.jsonl').open('w',encoding='utf-8') as f:
  for row in rows:
   clean=dict(row);clean['source_original_observation']={k:v for k,v in row['source_original_observation'].items() if k in ('lead_id','study_id','table','author_peptide_or_substitution','residue_evidence','nc_annotation_axis','source_file','source_sha256','source_location')}
   f.write(json.dumps(clean,ensure_ascii=False)+'\n')
 with (HERE/'chemistry-exclusions-preserved.jsonl').open('w',encoding='utf-8') as f:
  for row in excluded:f.write(json.dumps(row,ensure_ascii=False)+'\n')
 (HERE/'SI-all-23-entity-annotations.json').write_text(json.dumps(annotations,ensure_ascii=False,indent=2),encoding='utf-8')
 summary={'original_new_author_entities':23,'format_conversion_candidates':len(rows),'nc_format_candidates':sum(r['source_original_observation']['residue_evidence']=='noncanonical' for r in rows),'standard_format_candidates':sum(r['source_original_observation']['residue_evidence']!='noncanonical' for r in rows),'held_out_missing_or_ambiguous':len(excluded),'target_identity':'reference mono-clonal full2H2L composition saved; proposed heavy-chain Fc reference view not adopted or assayed-construct certified','root_new_manifest_required':True,'original_frozen75_modified':False,'model_training':False}
 assert summary['format_conversion_candidates']==14 and summary['nc_format_candidates']==9 and summary['standard_format_candidates']==5
 (HERE/'annotation-preparation-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
