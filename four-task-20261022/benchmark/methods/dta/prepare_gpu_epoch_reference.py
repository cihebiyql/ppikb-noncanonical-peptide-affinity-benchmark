"""Metadata-only empirical GPU full-fit/epoch timing references for possible later CPU resource handoff."""
from pathlib import Path
import datetime as dt,json,statistics
from export_complete_dta_report import local
H=Path(__file__).resolve().parent
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
pointer=load(H/'accepted-details-current.json');details=load(local(pointer['path']));rows=[]
for r in details['records']:
 env=r.get('runtime') or {}
 if not env.get('CUDA_VISIBLE_DEVICES'):continue
 unit=local(r['path']).parent;rates=[];first_elapsed=None
 for i in range(2):
  p=unit/('candidate-'+str(i))/'epochs.jsonl'
  if not p.exists():continue
  logs=[json.loads(x) for x in p.read_text(encoding='utf-8-sig').splitlines() if x.strip()]
  if i==0 and logs:first_elapsed=logs[0]['elapsed_seconds']
  rates += [b['elapsed_seconds']-a['elapsed_seconds'] for a,b in zip(logs,logs[1:]) if b['elapsed_seconds']>a['elapsed_seconds']]
 if not rates:continue
 row={k:r[k] for k in ['view','method','seed','elapsed_seconds','runtime']};row.update(complete_unit_path=str(unit),completed_epoch_seconds_min=min(rates),completed_epoch_seconds_median=statistics.median(rates),completed_epoch_seconds_max=max(rates),epoch_interval_count=len(rates),first_epoch_elapsed_including_setup=first_elapsed,full40_epoch_scenario_seconds=40*max(rates)+max(0,(first_elapsed or 0)-statistics.median(rates)),scenario_scope='Full fixed upper40epochs across2LR at observed slowest completed inter-epoch interval plus observed first-epoch setup excess; future scheduling/cache/runtime can differ, not a guaranteed ETA')
 rows.append(row)
out=H/'criticalpath-GPU-comparison-input.json';out.write_text(json.dumps({'at':dt.datetime.now(dt.timezone.utc).isoformat(),'accepted_details_sha256':pointer['sha256'],'records':rows,'scope':'Read-only observed epoch logs; no model load/forward/fit or automatic live migration'},indent=2),encoding='utf-8')
print(json.dumps({'records':len(rows),'source_GS':[{k:x[k] for k in ['seed','elapsed_seconds','completed_epoch_seconds_max','full40_epoch_scenario_seconds']} for x in rows if x['view']=='ppikb_kd_source_cold_scope_v2' and x['method']=='GS-DTA']}))
