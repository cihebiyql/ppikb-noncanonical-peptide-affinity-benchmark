"""Independent per-chemical-stratum and per-group validation for completed current-data units."""
from pathlib import Path
import json,sys,statistics,datetime as dt
from audit_runs import independent_metrics
R=Path(__file__).resolve().parents[2];views={'ppikb_kd_source_cold_scope_v2','ppikb_kd_target_cold_scope_v2','ppikb_effect_metadata_silver_source_cold'};checks=[];fail=[];strata_records=[];dedup=set()
for home in ['dta_local_gpu','dta_node23_cpu','dta_node23_cpu_recovery_v2']:
 for cp in (R/'runs'/home).rglob('complete.json'):
  c=json.loads(cp.read_text());view=c.get('view_id')
  if view not in views or c.get('stage')!='formal':continue
  key=(view,c['method_id'],c['seed'])
  if key in dedup:raise ValueError('Unexpected duplicate local completed key')
  dedup.add(key);pred=[json.loads(x) for x in (cp.parent/'test-predictions.jsonl').read_text().splitlines()];saved=json.loads((cp.parent/'test-metrics.json').read_text())
  for kind,field in [('strata','evaluation_stratum'),('groups','group_id')]:
   buckets={}
   for r in pred:
    k=(r.get(field) or r.get('stratum') or 'unknown') if kind=='strata' else (r.get('group_id') or r.get('target_id') or 'unknown');buckets.setdefault(k,[]).append(r)
   assert set(buckets)==set(saved[kind])
   for k,rows in buckets.items():
    actual=independent_metrics(rows,c['task']);expected=saved[kind][k];errors={}
    for metric,val in actual.items():
     e=expected.get(metric)
     if (val is None)!=(e is None) or (val is not None and abs(val-e)>1e-10):errors[metric]={'saved':e,'actual':val}
    check={'view':view,'method':c['method_id'],'seed':c['seed'],'kind':kind,'group':k,'valid':not errors,'errors':errors};checks.append(check)
    if errors:fail.append(check)
    if kind=='strata':strata_records.append({'view':view,'method':c['method_id'],'seed':c['seed'],'stratum':k,**actual})
H=R/'methods/dta';stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ');out=H/('strata-audit-'+stamp);out.mkdir()
(out/'audit.json').write_text(json.dumps({'units':len(dedup),'checks':len(checks),'failed':fail,'all_passed':not fail,'check_records':checks},indent=2));(out/'stratum-results.json').write_text(json.dumps(strata_records,indent=2))
print(json.dumps({'path':str(out),'units':len(dedup),'checks':len(checks),'failures':len(fail)}))
if fail:raise SystemExit(2)
