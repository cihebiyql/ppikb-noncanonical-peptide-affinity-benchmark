"""Only declared label-free inputs and frozen membership IDs are read.
Never reads labels.jsonl, any gold file, model predictions or run results.
"""
from collections import Counter
import json
from pathlib import Path
import recompute_metrics as independent

ROOT=Path(__file__).resolve().parent.parent;R=Path(__file__).resolve().parent
F=ROOT/'data-protocol/frozen-v1'
READS=[]
def read(path):
 p=Path(path)
 if p.name in {'labels.jsonl','gold75.jsonl','predictions.jsonl','posttraining-gold.jsonl'} or 'gold' in p.parts:
  raise PermissionError('Forbidden real sealed numeric artifact')
 READS.append(str(p));return independent.read_json(p)
def read_inputs(path):
 p=Path(path);READS.append(str(p));rows=independent.read_jsonl(p)
 for row in rows:
  if any(k in row for k in ('pKd','p_value','value_molar','Kd_M','pKd_true','pKd_pred','reported_value')):
   raise ValueError('Unexpected numerical label/prediction in declared label-free input')
 return rows

def main():
 rows=read_inputs(F/'inputs.jsonl');byid=independent.unique_by_id(rows,'frozen label-free input')
 SYN={'d_stereoisomer','n_substituted_or_peptoid','nonalpha_or_backbone_modified','nonproteinogenic_named','nonproteinogenic_substituted_aminoacid','reviewed_nonproteinogenic_residue'}
 strata=Counter();flags=Counter();mismatch=[];booleans=[]
 for row in rows:
  sub=set(row['noncanonical_subtypes']);syn=bool(sub&SYN);ptm=any(x.startswith('ptm_') for x in sub)
  expected=('synthetic_and_PTM' if syn and ptm else 'synthetic_D_backbone' if syn else 'PTM' if ptm else 'other_NC') if row['NC_core'] else 'standard20_control'
  if row['evaluation_stratum']!=expected:mismatch.append(row['record_id'])
  strata[row['evaluation_stratum']]+=1
  for k,v in row.items():
   if 'discord' in k.lower():flags[(k,str(type(v).__name__),str(v))]+=1
  if not isinstance(row['NC_core'],bool):booleans.append(row['record_id'])
 panels=[]
 for panel in sorted(independent.PANELS):
  for regime in ['NC_only','standard_only']:
   base=F/'splits'/panel/regime;ids=read(base/'test-ids.json');sensitive=read(base/'test-sensitivity-excluding-graph-discordance-ids.json')
   expected={rid for rid in ids if not independent.is_discordant(byid[rid])}
   panels.append({'panel':panel,'evaluation_regime':regime,'test_n':len(ids),'sensitivity_n':len(sensitive),
    'discordant_excluded':len(ids)-len(sensitive),'sensitivity_membership_exactly_matches_flags':set(sensitive)==expected,
    'strata_test_counts':dict(Counter(byid[rid]['evaluation_stratum'] for rid in ids)),
    'strata_sensitivity_counts':dict(Counter(byid[rid]['evaluation_stratum'] for rid in sensitive))})
 E=ROOT/'external-validation/scoring-views-v1'
 external=read_inputs(E/'inputs75.jsonl');sets={name:set(read(E/filename)) for name,filename in [
  ('all','ids-all75.json'),('primary','ids-primary67.json'),('sensitivity','ids-conditional-sensitivity8.json'),('target_reference_cold','ids-reference-target-cold2.json')]}
 ext={'rows':len(external),'strata':dict(Counter(r['evaluation_stratum'] for r in external)),
      'primary':len(sets['primary']),'conditional_sensitivity':len(sets['sensitivity']),'target_reference_cold':len(sets['target_reference_cold']),
      'primary_sensitivity_disjoint':not bool(sets['primary']&sets['sensitivity']),
      'primary_union_sensitivity_equals_all':sets['primary']|sets['sensitivity']==sets['all'],
      'target_reference_cold_is_subset_of_primary':sets['target_reference_cold']<=sets['primary'],
      'input_IDs_match_all':{r['record_id'] for r in external}==sets['all'],
      'external_family_cold_certified_rows':sum(r.get('external_family_cold_certified') is True for r in external),
      'actual_assay_clone_verified_rows':sum(r.get('actual_assay_clone_verified') is True for r in external),
      'resources':dict(Counter(r['resource_id'] for r in external)),
      'primary_resources':dict(Counter(r['resource_id'] for r in external if r['record_id'] in sets['primary']))}
 o={'scope':'label-free metadata/IDs mechanical audit only; no heldout numeric truth or model prediction read',
    'frozen_inputs_rows':len(rows),'NC_rows':sum(r['NC_core'] is True for r in rows),'standard_rows':sum(r['NC_core'] is False for r in rows),
    'input_fields':sorted(set().union(*(r.keys() for r in rows))),'strata':dict(strata),'strata_annotation_mapping_mismatches':len(mismatch),
    'NC_boolean_type_errors':len(booleans),'discordance_flag_value_types':[{'key':k[0],'type':k[1],'value':k[2],'n':v} for k,v in flags.items()],
    'flagged_discordance_rows':sum(independent.is_discordant(r) for r in rows),'sensitivity_panels':panels,'external_metadata':ext,
    'allowed_files_read':READS,'real_gold_reads':0,'real_prediction_reads':0,'training_or_model_selection':False}
 independent.write_json(R/'label-free-metadata-verification.json',o)
 print(json.dumps({k:v for k,v in o.items() if k not in ['allowed_files_read','input_fields','discordance_flag_value_types']},ensure_ascii=False))

if __name__=='__main__':main()
