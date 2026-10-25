"""Read-only checks of frozen IDs, raw-label preservation, roles, stage groups and hashes."""
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime,timezone
import csv,json,hashlib

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def rows(p):
 with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
 failures=[];checks=0
 def check(x,msg):
  nonlocal checks
  checks+=1
  if not x:failures.append(msg)
 manifest=json.loads((HERE/'frozen-manifest.json').read_text(encoding='utf8'))
 check(manifest.get('frozen') is True and manifest.get('revision')==3,'final manifest identity')
 check(manifest['numeric_labels_used_to_assign_roles'] is False,'numeric labels used in split')
 check(sha(HERE/manifest['producer_path'])==manifest['producer_sha256'],'producer SHA')
 check(sha(HERE/manifest['input_manifest_path'])==manifest['input_manifest_sha256'],'input manifest SHA')
 inputs=json.loads((HERE/'input-manifest.json').read_text(encoding='utf8'))
 for x in inputs['inputs']:check(sha(x['path'])==x['sha256'],'input changed '+x['path'])
 for x in manifest['outputs']:check(sha(HERE/x['path'])==x['sha256'],'output changed '+x['path'])
 detail={}
 for panel in ('source','target'):
  assigned=rows(HERE/panel/'role_assignments.csv');groups=defaultdict(set)
  keys=set();finekeys=set()
  for a in assigned:
   key=(a['dataset'],a['row_id']);check(key not in keys,'duplicate assignment '+str(key));keys.add(key)
   groups[a['global_group_id']].add(a['role'])
   if a['role'] in ('fine_train','pretrain'):check(a['source_known']=='True','unknown-source development '+str(key))
  for group,roles in groups.items():
   development=bool(roles&{'fine_train','pretrain'})
   protected=bool(roles&{'validation','test','external','external_background'})
   check(not(development and protected),'development/protected group collision '+group)
   check(not({'validation','test'}<=roles),'validation/test collision '+group)
   check(not({'fine_train','pretrain'}<=roles),'stage collision '+group)
  original={r['row_id']:r for r in rows(ROOT/f'data/ppikb_kd_{panel}_cold_scope_v2.csv')}
  fine=rows(HERE/panel/'fine_affinity.csv')
  for r in fine:
   check(r['row_id'] not in finekeys,'duplicate fine ID');finekeys.add(r['row_id']);o=original[r['row_id']]
   for key,value in o.items():
    if key!='split':check(r[key]==value,f'original data changed {panel}/{r["row_id"]}/{key}')
   check(r['legacy_split']==o['split'],'legacy split mismatch')
   check(r['split']==o['split'] or (o['split']=='train' and r['split']=='fine_train'),'legacy heldout promoted')
  v=next(x for x in manifest['views'] if x['id']==f'ppikb_kd_{panel}_global_firewall_v1')
  counts=dict(Counter(r['split'] for r in fine))
  check(v['training_ready']==all(counts.get(s,0)>0 for s in ('fine_train','validation','test')),'ready mismatch')
  for external in manifest['external_views']:
   if not external['id'].startswith(panel+'_'):continue
   er=rows(HERE/external['path']);check(len(er)==external['rows'],'external count mismatch')
   if external['dataset']=='pepbi_candidate':check(len(er)==24,'PEPBI formal must24')
   if external['dataset']=='pepbi_ptpa4':check(len(er)==4,'PTPA must4')
  detail[panel]={'fine_split_counts':counts,'role_counts':dict(Counter(x['role'] for x in assigned)),'groups':len(groups)}
 print(json.dumps({'valid':not failures,'checks':checks,'failures':failures,'manifest_sha256':sha(HERE/'frozen-manifest.json'),'checked_at_utc':datetime.now(timezone.utc).isoformat(),'panels':detail,'model_calls':0},ensure_ascii=False,indent=2))
 return 0 if not failures else 1
if __name__=='__main__':raise SystemExit(main())
