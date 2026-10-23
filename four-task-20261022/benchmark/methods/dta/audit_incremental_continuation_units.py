"""Read-only audit of newly completed continuation logical units against the old59 snapshot."""
from pathlib import Path,PureWindowsPath
import json,hashlib,datetime as dt
from audit_runs import independent_metrics
H=Path(__file__).resolve().parent;R=H.parents[1]
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
old=load(H/'common-formal-census-20261023T013530Z.json');current=load(max(H.glob('common-formal-census-continuation-*.json')));keys={(x['view'],x['method'],x['seed']) for x in old['records']};records=[];errors=[];metric_checks=0
prior=list(H.glob('accepted-common-census-continuation-*.json'))
if prior:keys.update(tuple(x['logical_key']) for x in load(max(prior))['records'])
for r in current['records']:
 if (r['view'],r['method'],r['seed']) in keys:continue
 raw=r['path']
 if len(raw)>2 and raw[1]==':':
  parts=PureWindowsPath(raw).parts;ix=parts.index('peptide-four-task-benchmark-20261022');path=R/Path(*parts[ix+1:])
 elif raw.startswith('/data/qlyu/projects/peptide-four-task-benchmark-20261022/'):
  path=R/Path(raw.removeprefix('/data/qlyu/projects/peptide-four-task-benchmark-20261022/'))
 else:path=Path(raw)
 if not path.exists():continue
 unit=path.parent;c=load(path);s=load(unit/'selection.json');assert sha(unit/'test-predictions.jsonl')==c['prediction_sha256'] and sha(unit/'selection.json')==c['selection_sha256']
 for q in s['candidates']:
  p=unit/('candidate-'+str(q['candidate_index']));assert sha(p/'best.pt')==q['checkpoint_sha256'] and sha(p/'validation-predictions.jsonl')==q['validation_predictions_sha256']
 rows=[json.loads(x) for x in (unit/'test-predictions.jsonl').read_text().splitlines()];m=load(unit/'test-metrics.json');buckets={'all':{'all':rows},'strata':{},'groups':{}}
 for row in rows:
  buckets['strata'].setdefault(row.get('evaluation_stratum') or row.get('stratum') or 'unknown',[]).append(row);buckets['groups'].setdefault(row.get('group_id') or row.get('target_id') or 'unknown',[]).append(row)
 for kind,groups in buckets.items():
  for group,data in groups.items():
   actual=independent_metrics(data,c['task']);expected=m['all'] if kind=='all' else m[kind][group]
   for k,value in actual.items():
    e=expected.get(k);metric_checks+=1
    if (value is None)!=(e is None) or (value is not None and abs(value-e)>1e-10):errors.append({'key':[r['view'],r['method'],r['seed']],'kind':kind,'group':group,'metric':k,'actual':value,'saved':e})
 records.append({'logical_key':[r['view'],r['method'],r['seed']],'path':str(path),'test_n':len(rows),'two_candidate_weights_and_valpred_SHA':True,'test_and_selection_SHA':True})
stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ');out=H/('continuation-new-unit-audit-'+stamp+'.json');out.write_text(json.dumps({'at':stamp,'units':records,'unit_count':len(records),'metric_checks':metric_checks,'errors':errors,'all_available_new_units_valid':not errors,'scope':'Numerical and saved scientific artifact audit; GPU/CPU exit-state receipts are maintained by their resource owners. Remote-only new units need separate readback, never silently claimed audited.'},indent=2));print(json.dumps({'path':str(out),'new_units':len(records),'metric_checks':metric_checks,'errors':len(errors)}))
if errors:raise SystemExit(2)
