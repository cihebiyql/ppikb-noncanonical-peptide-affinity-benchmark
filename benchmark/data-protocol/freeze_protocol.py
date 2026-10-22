"""Coordinator-adopted v1 release. Fail if an existing release would be overwritten."""
import json,csv,hashlib,shutil,datetime
from pathlib import Path
P=Path(__file__).resolve().parent
EXT=P.parent/'external-validation'
F=P/'frozen-v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def read(path):
 with path.open(encoding='utf-8') as f:return list(map(json.loads,f))
def main():
 assert not F.exists(),'Never overwrite a frozen release'
 assert (EXT/'acceptance-manifest.json').exists(),'External acceptance must precede release'
 verify=json.loads((P/'independent-leakage-verification.json').read_text());assert verify['all_checks_passed']
 F.mkdir();rows=read(P/'model-observations.jsonl');flags={r['record_id']:r for r in read(P/'derived-quality-flags.jsonl')}
 with (F/'inputs.jsonl').open('w',encoding='utf-8') as inp,(F/'labels.jsonl').open('w',encoding='utf-8') as gold:
  for r in rows:
   label=r.pop('pKd');r['residue_class_graph_discordance']=flags[r['record_id']]['residue_class_graph_discordance']
   inp.write(json.dumps(r,ensure_ascii=False)+'\n');gold.write(json.dumps({'record_id':r['record_id'],'endpoint':'Kd','pKd':label})+'\n')
 shutil.copyfile(P/'derived-quality-flags.jsonl',F/'quality-flags.jsonl')
 for panel in ['source_peptide_dependency_cold','target_reference_homology_cold']:
  shutil.copytree(P/'split-proposals'/panel,F/'splits'/panel)
  assignment=list(csv.DictReader((F/'splits'/panel/'assignments.csv').open(encoding='utf-8-sig')))
  for regime,nc in [('NC_only',True),('standard_only',False)]:
   d=F/'splits'/panel/regime;d.mkdir();byid={r['record_id']:r for r in rows}
   for part in ['train','validation','test']:
    ids=sorted(r['record_id'] for r in assignment if r['split']==part and byid[r['record_id']]['NC_core']==nc)
    dump(d/(part+'-ids.json'),ids)
    if part=='test':dump(d/'test-sensitivity-excluding-graph-discordance-ids.json',[rid for rid in ids if not flags[rid]['residue_class_graph_discordance']])
 protocol=json.loads((P/'protocol-v1.json').read_text());protocol['status']='frozen_coordinator_accepted_v1';protocol['training_regimes']=['NC_only','standard_only'];protocol['pooled_training_this_release']=False
 protocol['target_panel']['effective_input_edges']='identical first1000 target amino acids; all five planned methods have >=1000 prefix views, MGraph1200; full SMILES retained'
 protocol['class_graph_discordance']={'molecular_graphs':60,'NC_rows':357,'standard_rows':251,'policy':'all 9619 preserved; primary result called annotation-stratified; use same saved test predictions excluding flagged rows as required sensitivity; do not guess corrected chemistry'}
 protocol['dual_cold_panel']='diagnostic only; largest component 8948/9619=93.02%; not a primary table'
 protocol['external_acceptance_manifest']={'path':str(EXT/'acceptance-manifest.json'),'sha256':sha(EXT/'acceptance-manifest.json')}
 dump(F/'protocol.json',protocol)
 for name in ['independent-leakage-verification.json','split-feasibility-report.json','input-manifest.json','granularity-audit.json','residue-class-graph-discordance.json','external-chemical-runtime-receipt.json','external-target-overlap-summary.json']:shutil.copyfile(P/name,F/name)
 files={str(p.relative_to(F)).replace('\\','/'):{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(F.rglob('*')) if p.is_file()}
 manifest={'version':1,'status':'frozen_for_authorized_baseline_execution','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'rows':9619,'NC':2099,'standard':7520,'task':'Kd affinity; annotation-stratified chemistry classes','input_file':'inputs.jsonl','label_file':'labels.jsonl','join_key':'record_id','seed_list':list(range(10)),'fixed_split_seed':'nc-protocol-20261021-v1','primary_training_regime':'NC_only','control_training_regime':'standard_only','primary_panels':['source_peptide_dependency_cold','target_reference_homology_cold'],'pooled_training':False,'graph_discordance_test_sensitivity_required':True,'external':protocol['external_acceptance_manifest'],'external_exclusion_authority':'referenced frozen external acceptance-manifest; do not infer all externally new molecules are novel targets','files':files,'scientific_limits':['No actual assay target constructs certified; database reference view','Sources are metadata aliases, not full primary-paper certification','Cold panels enforce their respective axis, not all axes simultaneously','Residue annotations conflict on 60 actual graphs; no correction asserted','10 training seeds quantify training variability, not independent experiments']}
 dump(F/'manifest.json',manifest);print(json.dumps({'manifest':str(F/'manifest.json'),'sha256':sha(F/'manifest.json'),'files':len(files),'rows':9619},indent=2))
if __name__=='__main__':main()
