import json,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent/'frozen-v1'
def loadjsonl(name):
 with (P/name).open(encoding='utf-8') as f:return list(map(json.loads,f))
def main():
 manifest=json.loads((P/'manifest.json').read_text(encoding='utf-8'))
 for name,meta in manifest['files'].items():assert hashlib.sha256((P/name).read_bytes()).hexdigest()==meta['sha256'],name
 inputs=loadjsonl('inputs.jsonl');gold=loadjsonl('labels.jsonl');byid={r['record_id']:r for r in inputs}
 assert len(inputs)==len(byid)==9619;assert {r['record_id'] for r in gold}==set(byid);assert len(gold)==9619
 for r in inputs:assert not {'pKd','p_value','value','value_molar','label','y'}&set(r)
 assert sum(r['NC_core'] for r in inputs)==2099;assert sum(r['residue_class_graph_discordance'] for r in inputs)==608
 counts={}
 for panel in manifest['primary_panels']:
  counts[panel]={};allids=[]
  for regime,nc in [('NC_only',True),('standard_only',False)]:
   counts[panel][regime]={};parts=[]
   for split in ['train','validation','test']:
    ids=json.loads((P/'splits'/panel/regime/(split+'-ids.json')).read_text());parts.append(set(ids));allids+=ids
    assert all(byid[rid]['NC_core']==nc for rid in ids);assert len(ids)==len(set(ids));counts[panel][regime][split]=len(ids)
   assert not (parts[0]&parts[1] or parts[0]&parts[2] or parts[1]&parts[2])
   sensitivity=set(json.loads((P/'splits'/panel/regime/'test-sensitivity-excluding-graph-discordance-ids.json').read_text()))
   assert sensitivity=={rid for rid in parts[2] if not byid[rid]['residue_class_graph_discordance']};counts[panel][regime]['test_sensitivity_rows']=len(sensitivity)
  assert len(allids)==len(set(allids))==9619
 out={'all_checks_passed':True,'manifest_sha256':hashlib.sha256((P/'manifest.json').read_bytes()).hexdigest(),'hashed_files_verified':len(manifest['files']),'rows':len(inputs),'group_split_seed':manifest['fixed_split_seed'],'training_seeds':manifest['seed_list'],'regime_split_counts':counts,'labels_separated':True,'models_fit_by_data_agent':0}
 (P.parent/'frozen-v1-verification.json').write_text(json.dumps(out,indent=2),encoding='utf-8');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
