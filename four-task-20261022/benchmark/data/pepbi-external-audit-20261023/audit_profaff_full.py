from pathlib import Path
import importlib.util,json,hashlib,collections,re,sys
sys.dont_write_bytecode=True
O=Path(__file__).resolve().parent;R=O.parents[1];E=R.parent/'peptide-binding-benchmark-20261020/ten-seed-external-20261021/external/pepbi_pdz';p=E/'inspect_workbooks.py';spec=importlib.util.spec_from_file_location('prior_xlsx_parser',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
f=E/'pdz-raw/41467_2022_33018_MOESM4_ESM.xlsx';rows=None
for name,a in m.workbook(f):
 if name=='PDZ-PBM interactome':
  h={k:v for k,v in a[0]['cells'].items() if v};rows=[{'source_excel_row':x['excel_row'],**{v:x['cells'].get(k) for k,v in h.items()}} for x in a[1:]];break
assert len(rows)==70479
AA=set('ACDEFGHIKLMNPQRSTVWY');domain={x['target_source_name']:x['domain_sequence'] for x in json.loads((E/'pdzome2023-domain-construct-sequences.json').read_text(encoding='utf8'))};hu_path=R/'data/profaff-expansion-20261023/holdup-all-explicit-backbone-projections-external.csv';alias_proof={}
for x in __import__('csv').DictReader(hu_path.open(encoding='utf-8-sig')):
 n=x['target_name'];q=x['target_sequence']
 if n in alias_proof:assert alias_proof[n]==q
 alias_proof[n]=q
added_aliases={k:v for k,v in alias_proof.items() if k not in domain};domain.update(added_aliases)
old={int(x['source_excel_row']) for x in __import__('csv').DictReader((E/'pdz-human-raw-measurements.csv').open(encoding='utf-8-sig'))};excluded=[];compare=[]
for x in rows:
 if re.search(r'HPV|HTLV|SARS|MERS|HBV|WNV|EBV|HIV|VIRUS|TAX1',str(x.get('PBM') or ''),re.I):
  excluded.append({'source_excel_row':x['source_excel_row'],'PBM':x.get('PBM'),'PBM_uniprot':x.get('PBM_uniprot'),'scope':'explicit_viral_PBM;metadata_only_not_prepared_or_modeled'});continue
 pep=x.get('peptide_10mer') or '';pro=domain.get(x.get('PDZ')) or '';compare.append({'source_excel_row':x['source_excel_row'],'PDZ':x.get('PDZ'),'peptide_backbone_10mer':pep if set(pep)<=AA else None,'domain_sequence':pro,'human_previous_filter_membership':x['source_excel_row'] in old})
# Only exact sequence identities/containment: no biological functional inference or new peptide projection.
contexts=json.loads((O/'all188-measurement-contexts.json').read_text(encoding='utf8'));targets={x['domain_sequence'] for x in compare if x['domain_sequence']};pairs={(x['peptide_backbone_10mer'],x['domain_sequence']) for x in compare if x['peptide_backbone_10mer'] and x['domain_sequence']};exposure=[]
for x in contexts:
 pro=x['protein_sequence'];exposure.append({'context_id':x['context_id'],'exact_pair_overlap':(x['peptide_sequence'],pro) in pairs,'target_exact_or_subsequence_overlap':any(t==pro or t in pro or pro in t for t in targets)})
summary={'source_path':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'parser_path':str(p),'parser_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'all_original_matrix_record_rows':len(rows),'composite_pKd_present_rows':sum(x.get('COMP_neglogKd') is not None for x in rows),'composite_pKd_positive_rows':sum(float(x['COMP_neglogKd'])>0 for x in rows if x.get('COMP_neglogKd') is not None),'composite_pKd_zero_censored_rows':sum(float(x['COMP_neglogKd'])==0 for x in rows if x.get('COMP_neglogKd') is not None),'composite_pKd_missing_rows':sum(x.get('COMP_neglogKd') is None for x in rows),'prior_human_filtered_raw_rows':len(old),'metadata_registered_viral_PBM_excluded':len(excluded),'all_non_viral_rows_compared_regardless_human_status':len(compare),'new_nonhuman_or_unknown_rows_not_in_prior_human_subset':sum(not x['human_previous_filter_membership'] for x in compare),'domain_target_sequence_missing_rows':sum(not x['domain_sequence'] for x in compare),'literal_alias_mapping_from_existing_frozen_HU':sorted(added_aliases),'alias_source_path':str(hu_path),'alias_source_sha256':hashlib.sha256(hu_path.read_bytes()).hexdigest(),'exact_pair_overlapping_PEPBI_contexts':sum(x['exact_pair_overlap'] for x in exposure),'target_containment_overlapping_PEPBI_contexts':sum(x['target_exact_or_subsequence_overlap'] for x in exposure),'source_endpoint_values_not_converted_to_new_labels':True,'fitting_or_model_forward':False,'per_context':exposure,'scope_excluded_metadata_only':excluded}
(O/'ProfAff-all65151-source-completion.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in summary.items() if k not in ['per_context','scope_excluded_metadata_only']},ensure_ascii=False))
