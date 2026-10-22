"""Independent pre-barrier metadata review. No raw inputs/pickles/gold/models."""
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import hashlib,json
import recompute_metrics as audit

R=Path(__file__).resolve().parent;P=R.parent;A=P/'administration/score-spec-assets-v2';E=P/'evaluation'
OPENED=[]
def metadata(path):
 p=audit.local_path(path)
 if p.suffix!='.json' or 'gold' in p.parts:raise PermissionError('Metadata JSON only')
 OPENED.append(str(p));return audit.read_json(p)
def check(path,digest):
 p=audit.local_path(path)
 if p.suffix not in ('.json','.py'):raise PermissionError('No raw payload hashes in this review')
 audit.require_hash(p,digest)
def same_path(a,b):return audit.local_path(a).resolve()==audit.local_path(b).resolve()
def tree_hash(folder):
 entries=[(str(p.relative_to(folder)).replace('\\','/'),audit.sha(p)) for p in sorted(folder.rglob('*.py')) if '__pycache__' not in p.parts]
 return hashlib.sha256(json.dumps(entries,separators=(',',':')).encode()).hexdigest()

def main():
 frozen=metadata(E/'FROZEN-SCORER-v1.json')
 for name,digest in frozen['evaluation_code_sha256'].items():check(E/name,digest)
 check(P/'execution/runner.py',frozen['frozen_runner_sha256'])
 check(E/'X-cache-final-manifest-v2.json',frozen['X_cache_final_manifest_sha256'])
 X=metadata(E/'X-cache-final-manifest-v2.json');registry=metadata(E/'authorized-manifest-v2.json')
 sidepath=A/'spec-cache-identity-verification.json';side=metadata(sidepath)
 planpath=A/'evaluation-plan.prebarrier.json';plan=metadata(planpath)
 assert plan['root_authorized_after_barrier'] is False and plan['authorization'] is None
 assert plan['barrier']['sha256'] is None and plan['barrier_audit'] is None
 for f in plan['code_files']:check(f['path'],f['sha256'])
 entries=X['entries'];assert len(entries)==20
 bycache={str(audit.local_path(x['cache_manifest_path']).resolve()):x for x in entries}
 assert len(bycache)==20
 datasets={'source_test':1039,'target_test':1443,'external75':75,'supplement13':13}
 assert {e['dataset_id'] for e in entries}==set(datasets)
 methods=audit.METHODS
 assert {(e['dataset_id'],e['method_id']) for e in entries}=={(d,m) for d in datasets for m in methods}
 count=Counter();used=set();verified=[];folders={'GraphDTA-GIN':'graphdta-deepnc','DeepNC-GEN':'graphdta-deepnc','MGraphDTA':'mgraph-dgdta','DGDTA-CL':'mgraph-dgdta','GS-DTA':'gs-dta'}
 adapterhashes={folder:tree_hash(P/'methods'/folder) for folder in set(folders.values())}
 for item in side['verifications']:
  path=audit.local_path(item['spec_path']);check(path,item['spec_sha256']);spec=metadata(path)
  check(spec['cache_manifest'],spec['cache_manifest_sha256']);cache=metadata(spec['cache_manifest'])
  key=str(audit.local_path(spec['cache_manifest']).resolve());entry=bycache[key];used.add(key)
  ds=spec['dataset_id'];method=spec['method_id'];panel=spec['selection_split_id']
  assert ds==cache['dataset_id']==entry['dataset_id']==item['dataset_id_exact']==item['cache_dataset_id_exact']
  assert method==cache['method_id']==entry['method_id']==item['method_id_exact'] and method in methods
  assert panel==item['selection_split_id_exact'] and panel in audit.PANELS
  if ds=='source_test':assert panel=='source_peptide_dependency_cold'
  if ds=='target_test':assert panel=='target_reference_homology_cold'
  reg=registry['datasets'][ds]
  assert spec['input_rows']==reg['wsl_path']==item['input_rows']
  assert spec['input_rows_sha256']==reg['input_sha256']==cache['input_sha256']==entry['input_sha256']==item['input_sha256']
  assert cache['n']==entry['n']==reg['n']==datasets[ds]
  assert same_path(spec['cache_path'],entry['cache_path']) and same_path(spec['cache_manifest'],entry['cache_manifest_path'])
  assert cache['cache_sha256']==entry['cache_sha256']
  assert cache['adapter_tree_sha256']==entry['adapter_tree_sha256']==spec['adapter_tree_sha256']==adapterhashes[folders[method]]
  assert spec['cache_manifest_sha256']==entry['cache_manifest_sha256']==item['cache_manifest_sha256']
  expected_sig=hashlib.sha256(json.dumps(dict(schema='label-free-fixed-author-X-v1',method_id=method,input_sha256=spec['input_rows_sha256'],adapter_tree_sha256=spec['adapter_tree_sha256'],placeholder_pKd=0.0),sort_keys=True,separators=(',',':')).encode()).hexdigest()
  assert cache['signature']==entry['signature']==expected_sig and cache['placeholder_pKd']==0.0
  assert cache['all_cached_targets_zero'] is True
  authority=item['input_path_authority'];check(authority['path'],authority['sha256'])
  assert same_path(authority['path'],E/'authorized-manifest-v2.json')
  identity=(ds,method,panel);count[identity]+=1
  verified.append({'spec_path':str(path),'spec_sha256':audit.sha(path),'dataset_id':ds,'method_id':method,'panel':panel,'n':datasets[ds],'cache_manifest_sha256':spec['cache_manifest_sha256'],'cache_payload_sha256_declared':cache['cache_sha256'],'input_sha256_declared':spec['input_rows_sha256'],'no_payload_read':True})
 expected30={(ds,m,p) for m in methods for p in audit.PANELS for ds in [('source_test' if p=='source_peptide_dependency_cold' else 'target_test'),'external75','supplement13']}
 assert len(verified)==30 and set(count)==expected30 and all(v==1 for v in count.values()) and len(used)==20
 identities=set();tasks=Counter();rows=Counter();spec_by_path={str(audit.local_path(x['spec_path']).resolve()):x for x in verified}
 for uid,unit in plan['units'].items():
  method,panel,regime,seedstr=uid.split('__');seed=int(seedstr.removeprefix('seed'))
  identity=(method,panel,regime,seed)
  assert identity not in identities;identities.add(identity)
  assert unit['selection']['sha256'] is None and unit['checkpoint_sha256'] is None
  assert len(unit['score_specs'])==3
  expected_ds={'source_test' if panel=='source_peptide_dependency_cold' else 'target_test','external75','supplement13'}
  assert {s['dataset_id'] for s in unit['score_specs']}==expected_ds
  for s in unit['score_specs']:
   key=str(audit.local_path(s['path']).resolve());v=spec_by_path[key]
   assert s['sha256']==v['spec_sha256'] and s['method_id']==method==v['method_id']
   assert s['selection_split_id']==panel==v['panel'] and s['dataset_id']==v['dataset_id'] and s['n']==v['n']
   tasks[s['dataset_id']]+=1;rows[s['dataset_id']]+=s['n']
 expected200={(m,p,r,s) for m in methods for p in audit.PANELS for r in ('NC_only','standard_only') for s in range(10)}
 assert identities==expected200
 assert dict(tasks)=={'source_test':100,'target_test':100,'external75':200,'supplement13':200}
 assert dict(rows)=={'source_test':103900,'target_test':144300,'external75':15000,'supplement13':2600}
 assert sum(tasks.values())==600 and sum(rows.values())==265800
 out={'schema':'independent-score-spec-metadata-review.v1','status':'all30_specs_20_cache_metadata_600planned_score_identities_verified','utc':datetime.now(timezone.utc).isoformat(),
  'scope':'prebarrier metadata+source SHA only; not execution authorization or cache payload revalidation',
  'root_can_issue_postbarrier_authorization_preparation':True,'real_scoring_authorized_now':False,
  'shared_spec_count':30,'unique_X_cache_metadata_count':20,'selection_grid_metadata_count':200,'expected_score_receipts':600,'expected_prediction_rows':265800,
  'score_receipts_by_raw_dataset_id':dict(tasks),'prediction_rows_by_raw_dataset_id':dict(rows),
  'scorer_frozen_manifest_sha256':audit.sha(E/'FROZEN-SCORER-v1.json'),'scorer_code_hashes':frozen['evaluation_code_sha256'],
  'administrative_spec_identity_proof_sha256':audit.sha(sidepath),'administrative_prebarrier_plan_sha256':audit.sha(planpath),
  'X_cache_final_metadata_sha256':audit.sha(E/'X-cache-final-manifest-v2.json'),'input_registry_sha256':audit.sha(E/'authorized-manifest-v2.json'),
  'cache_payload_hash_claim':'Declared hashes matched across fixed X inventory and individual metadata; actual payloads not opened/rehash-tested by this independent metadata review. Runtime load_cache and prior consumer receipt own that check.',
  'gold_hash_claim':'Gold file paths/SHA remain authorized-spec metadata only; no numeric gold or bytes hashed here.',
  'raw_inputs_opened':False,'pickle_payloads_opened':False,'gold_opened':False,'actual_selection_or_checkpoint_opened':False,'model_predictions_read':False,
  'source_files_modified':False,'files_metadata_opened':sorted(set(OPENED)),'verified_specs':verified}
 audit.write_json(R/'score-spec-independent-review-v1.json',out)
 print(json.dumps({k:out[k] for k in ['status','shared_spec_count','unique_X_cache_metadata_count','selection_grid_metadata_count','expected_score_receipts','expected_prediction_rows','real_scoring_authorized_now']},ensure_ascii=False))

if __name__=='__main__':main()
