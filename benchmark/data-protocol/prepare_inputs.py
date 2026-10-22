"""Prepare immutable observations and label-free grouping input. No fitting."""
import json, hashlib, csv, re
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parent
OLD=ROOT.parents[1]/'peptide-binding-expanded-corpus-20261021'
AUDIT=OLD/'rescreen-noncanonical-priority-20261021/PPIKB'
RAW=OLD/'resources/PPIKB_all_endpoints/normalized-observations.jsonl'
SYN={'d_stereoisomer','n_substituted_or_peptoid','nonalpha_or_backbone_modified','nonproteinogenic_named','nonproteinogenic_substituted_aminoacid','reviewed_nonproteinogenic_residue'}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def jsonl(p,rs):
 with p.open('w',encoding='utf-8') as f:
  for r in rs:f.write(json.dumps(r,ensure_ascii=False)+'\n')
def main():
 ROOT.mkdir(exist_ok=True,parents=True)
 original={r['source_record_id']:r for r in map(json.loads,RAW.open(encoding='utf-8'))}
 audit=list(map(json.loads,(AUDIT/'all-21845-status.jsonl').open(encoding='utf-8')))
 nc=list(map(json.loads,(AUDIT/'NC-conservative-Kd-candidates.jsonl').open(encoding='utf-8')))
 controls=[{'original_observation':original[a['source_record_id']],'residue_audit':a} for a in audit if a['residue_class']=='standard20_supported' and a['endpoint']=='Kd' and a['technical_exact_molecular_candidate']]
 rows=[];grouping=[];aliases=[]
 for x in nc+controls:
  o=x['original_observation'];a=x['residue_audit'];sub=set(a['noncanonical_subtypes'])
  synthetic=bool(sub&SYN);ptm=any(s.startswith('ptm_') for s in sub)
  group=('synthetic_and_PTM' if synthetic and ptm else 'synthetic_D_backbone' if synthetic else 'PTM' if ptm else 'other_NC') if a['NC_core'] else 'standard20_control'
  row={**x,'benchmark_record_id':o['record_id'],'evaluation_stratum':group,'target_sequence_scope':'database_reference_not_certified_assay_construct'}
  rows.append(row)
  study=str(o.get('study_id') or '').strip().lower().removeprefix('https://doi.org/').removeprefix('http://dx.doi.org/')
  if not study:study='missing_source:'+o['record_id']
  grouping.append({'record_id':o['record_id'],'study_group':study,'study_group_evidence':'database_study_id_not_primary_verified','target_id':o.get('target_id'),'target_sequence':o['target_sequence'],'peptide_smiles':o['peptide_smiles'],'peptide_sequence_raw':o.get('peptide_sequence_raw'),'peptide_sequence':o.get('peptide_sequence'),'parent_series_id':o.get('parent_series_id'),'evaluation_stratum':group})
  raw=o['row_raw'];aa=['study:'+study]
  doi=str(raw.get('DOI') or '').strip().lower().removeprefix('https://doi.org/').removeprefix('http://dx.doi.org/')
  if doi.startswith('10.'):aa.append('doi:'+doi)
  pmid=str(raw.get('PMID') or '').strip().removesuffix('.0')
  if pmid.isdigit():aa.append('pmid:'+pmid)
  title=re.sub(r'[^a-z0-9]','',str(raw.get('Title') or '').lower())
  if len(title)>=20:aa.append('title:'+title)
  aliases.append({'record_id':o['record_id'],'source_aliases':aa})
 jsonl(ROOT/'observations-with-audit.jsonl',rows);jsonl(ROOT/'label-free-grouping-input.jsonl',grouping);jsonl(ROOT/'label-free-study-aliases.jsonl',aliases)
 targets={o['target_sequence'] for o in grouping}
 with (ROOT/'targets.fasta').open('w') as f:
  for seq in sorted(targets):f.write('>'+hashlib.sha256(seq.encode()).hexdigest()[:20]+'\n'+seq+'\n')
 dump(ROOT/'input-manifest.json',{'source_files':{str(p):sha(p) for p in [RAW,AUDIT/'all-21845-status.jsonl',AUDIT/'NC-conservative-Kd-candidates.jsonl']},'NC_rows':len(nc),'standard_control_rows':len(controls),'total_rows':len(rows),'strata':dict(Counter(r['evaluation_stratum'] for r in rows)),'unique_studies':len({r['study_group'] for r in grouping}),'unique_target_sequences':len(targets),'unique_smiles_strings':len({r['peptide_smiles'] for r in grouping}),'grouping_file_sha256':sha(ROOT/'label-free-grouping-input.jsonl'),'label_policy':'Kd exact quantitative only; p_value is -log10(molar Kd), not statistical p value; no label repairs; original fields preserved','test_policy':'single fixed label-blind split, training seeds 0..9; tune validation only','actual_assay_target_constructs_certified':0})
 print((ROOT/'input-manifest.json').read_text(encoding='utf-8'))
if __name__=='__main__':main()
