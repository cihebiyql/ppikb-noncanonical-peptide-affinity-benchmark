"""Extract published measured tables as an asset lead, never as ready model data."""
from pathlib import Path
from collections import Counter
import csv,hashlib,json,math,re
from bs4 import BeautifulSoup
HERE=Path(__file__).resolve().parent

def main():
 source=HERE/'IgG-Fc-2025-author-fulltext.html';digest=hashlib.sha256(source.read_bytes()).hexdigest()
 soup=BeautifulSoup(source.read_text(encoding='utf-8'),'html.parser');rows=[]
 for number,table in enumerate(soup.select('table'),1):
  for ordinal,tr in enumerate(table.select('tr'),1):
   cells=[c.get_text(' ',strip=True) for c in tr.find_all(['th','td'],recursive=False)]
   if len(cells)!=4 or cells[1].startswith('K') or not cells[0]:continue
   name,raw=cells[0],cells[1]
   if raw=='(nM)' or name=='Substitution' or name=='Peptide':continue
   inherited=bool(re.search(r'a\s*\)',name))
   missing=raw in ('–','—','-','')
   bound=raw.startswith('>')
   match=re.fullmatch(r'([\d.]+)\s*±\s*([\d.]+)',raw)
   if not (missing or bound or match):raise ValueError((name,raw))
   flags=[]
   if any(t in name for t in ['Abu','D-Asp','Nal','MeTrp','Tpi','alloThr','IAPG-']):flags.append('explicit_nonproteinogenic_stereoisomer_or_backbone')
   if 'Cya' in name:flags.append('cysteic_acid_sidechain_oxidation_derivative_separate_from_named_nonproteinogenic')
   residue='noncanonical' if flags else 'standard_residue_derivative_or_reference'
   point=bool(match);val=float(match.group(1)) if match else None
   rows.append({'lead_id':f'IgG_Fc_2025:table{number}:row{ordinal}','study_id':'10.1248/cpb.c25-00637','table':number,'author_peptide_or_substitution':name,'Kd_raw':raw,'unit':'nM','qualifier':'=' if point else '>' if bound else None,'Kd_M':val*1e-9 if point else None,'pKd':-math.log10(val*1e-9) if point else None,'reported_uncertainty':float(match.group(2)) if match else None,'uncertainty_type':'author reported, do not infer SEM/SD','historical_reference_value_not_new_measurement':inherited,'residue_evidence':residue,'nc_annotation_axis':';'.join(flags),'measured_target_raw':'human IgG1 Trastuzumab','target_sequence':None,'peptide_SMILES':None,'model_ready':False,'not_ready_reason':'Actual commercial antibody full molecular identity/input chain and full ligand graph unresolved; source/analogue overlap not yet audited.','source_file':str(source),'source_sha256':digest,'source_location':f'HTML table{number} row{ordinal}'})
 assert len(rows)==28
 new=[r for r in rows if not r['historical_reference_value_not_new_measurement']]
 assert len(new)==23
 assert sum(r['qualifier']=='=' for r in new)==19
 assert sum(r['qualifier']=='>' for r in new)==2
 assert sum(r['qualifier'] is None for r in new)==2
 ncpoints=[r for r in new if r['qualifier']=='=' and r['residue_evidence']=='noncanonical']
 assert len(ncpoints)==13
 assert sum('explicit_nonproteinogenic' in r['nc_annotation_axis'] for r in ncpoints)==11
 with (HERE/'IgG-Fc-2025-all-author-table-slots.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 with (HERE/'IgG-Fc-2025-new-observations-not-model-ready.jsonl').open('w',encoding='utf-8') as f:
  for r in new:f.write(json.dumps(r,ensure_ascii=False)+'\n')
 summary={'study_id':'10.1248/cpb.c25-00637','official_source_url':'https://www.jstage.jst.go.jp/article/cpb/73/12/73_c25-00637/_html/-char/en','publication_date':'2025-12-18','license':'CC BY-NC 4.0; journal author license','raw_author_table_slots':28,'historical_reference_slots_excluded':5,'new_unique_author_entities':23,'new_exact_Kd_points':19,'new_noncanonical_exact_points':13,'new_explicit_nonproteinogenic_D_backbone_points':11,'new_cysteic_acid_oxidation_derivative_points':2,'new_standard_residue_point_controls':6,'new_censored_Kd':2,'new_no_numeric_affinity':2,'new_model_ready_external_rows':0,'actual_target_construct_sequence_present':False,'full_ligand_SMILES_present':False,'exact_source_doi_in_PPIKB_21845_rows':0,'source_cold_not_entity_cold':'Prior scaffold references in paper explicitly recur; bibliography and chemical similarity require audit before external use.','supplementary_download':'Official supplementary endpoint attempted once returned404; no guessed chemistry adopted.','scope':'Only author raw observations bookkeeping, no design or ranking optimization; no new primary-unit correction investigation.','frozen_benchmark_inclusion':False,'raw_source_sha256':digest}
 (HERE/'IgG-Fc-2025-lead-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
