"""Deduplicate verified complete units across local mirrors and the shared remote filesystem."""
from pathlib import Path
import json,datetime as dt,statistics
H=Path(__file__).resolve().parent
views={'ppikb_kd_source_cold_scope_v2','ppikb_kd_target_cold_scope_v2','ppikb_effect_metadata_silver_source_cold'}
files=[max(H.glob('census-cihebi-*.json')),max(H.glob('census-node23-*.json'))];unique={};conflicts=[]
for f in files:
 for r in json.loads(f.read_text())['records']:
  if r['view'] not in views:continue
  key=(r['view'],r['method'],r['seed'])
  if key in unique:
   old=unique[key]
   if old['prediction_sha256']!=r['prediction_sha256']:conflicts.append({'key':key,'first':old,'other':r})
   else:old['mirror_paths'].append(r['path'])
  else:unique[key]={**r,'mirror_paths':[r['path']]}
groups=[]
for v in sorted(views):
 for method in ['GraphDTA-GIN','MGraphDTA','DGDTA-CL','DeepNC-GEN','GS-DTA']:
  rows=[r for k,r in unique.items() if k[:2]==(v,method)];seeds=sorted(r['seed'] for r in rows)
  groups.append({'view':v,'method':method,'seeds':seeds,'missing_seeds':sorted(set(range(10))-set(seeds)),'ten_seed_complete':seeds==list(range(10)),'metrics_available_seeds_only':{m:{'mean':statistics.mean(r['metrics'][m] for r in rows),'sd':statistics.stdev(r['metrics'][m] for r in rows) if len(rows)>1 else None} for m in ['MAE','RMSE','R2']} if rows else {},'sd_caveat':'Runtime/backends mixed; not pure random-seed variation'})
stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ');dest=H/('common-formal-census-continuation-'+stamp+'.json');dest.write_text(json.dumps({'at':stamp,'source_censuses':[str(p) for p in files],'complete_logical_units':len(unique),'expected_logical_units':150,'duplicate_conflicts':conflicts,'groups':groups,'records':list(unique.values()),'scope':'saved complete + prediction SHA census; independent per-cohort metric audits are separate'},indent=2));print(json.dumps({'path':str(dest),'complete':len(unique),'conflicts':len(conflicts),'ten_seed_groups':sum(g['ten_seed_complete'] for g in groups)}))
