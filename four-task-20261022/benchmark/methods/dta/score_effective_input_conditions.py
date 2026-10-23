"""Diagnostic condition scores from saved predictions only; no split changes, model reads or new fit."""
from pathlib import Path
import argparse,collections,datetime as dt,gzip,hashlib,json,statistics,csv
from audit_runs import independent_metrics
from export_complete_dta_report import local
H=Path(__file__).resolve().parent
P=argparse.ArgumentParser();P.add_argument('--native-report',required=True);P.add_argument('--manifest24-report',required=True);A=P.parse_args()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
MAP={'standard20_control':'standard','standard':'standard','PTM':'PTM','synthetic_D_backbone':'NC','other_NC':'NC','synthetic_and_PTM':'NC+PTM'}
reports={};evidence=[]
for kind,path in [('native',A.native_report),('manifest24',A.manifest24_report)]:
 p=Path(path);r=load(p);assert r['schema']=='fourtask.actual-cached-effective-input-audit.v3';assert r['runtime']['auditor_source_sha256']=='5c77fdbe679f1213e04d38109db40d45b6a0d9f32408f7078290997a32b25916'
 evidence.append({'kind':kind,'path':str(p),'sha256':sha(p),'runtime':r['runtime']})
 for entry in r['results']:
  if not entry['complete_partitions']:continue
  mp=p.parent/entry['test_masks_file'];dp=p.parent/entry['duplicate_groups_file'];assert sha(mp)==entry['test_masks_sha256'] and sha(dp)==entry['duplicate_groups_sha256']
  masks={x['record_id']:x for x in load(mp)};ambiguous={rid for g in load(dp) if len(g['strata'])>1 for rid in g['records']}
  for rid,m in masks.items():m['input_annotation_heterogeneous']=rid in ambiguous
  reports[kind,entry['view'],entry['method']]=masks
pointer=load(H/'accepted-details-current.json');assert sha(local(pointer['path']))==pointer['sha256'];accepted=load(local(pointer['path']));records=[];missing=[];metric_checks=0
for row in accepted['records']:
 env=row.get('runtime') or {};torch_version=env.get('torch','');kind='native' if torch_version.startswith('2.12') else 'manifest24' if torch_version.startswith('2.6') else None
 if kind is None:missing.append({'key':[row['view'],row['method'],row['seed']],'reason':'actual runtime not mapped to a verified feature producer; no default assumed','runtime':env});continue
 masks=reports.get((kind,row['view'],row['method']))
 if masks is None:missing.append({'key':[row['view'],row['method'],row['seed']],'reason':'actual runtime/view/method has incomplete cached-input proof'});continue
 unit=local(row['path']).parent;assert sha(unit/'test-predictions.jsonl')==row['prediction_sha256'];pred=[json.loads(x) for x in (unit/'test-predictions.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()];assert len(pred)==len(masks) and {x['record_id'] for x in pred}==set(masks)
 conditions={'all_original_test':lambda m:True,'no_exact_effective_pair_seen_train_or_validation':lambda m:not m['effective_pair_seen_train_or_validation'],'untruncated_target':lambda m:not m['target_truncated'],'input_annotation_homogeneous':lambda m:not m['input_annotation_heterogeneous'],'untruncated_unseen_and_annotation_homogeneous':lambda m:not(m['target_truncated'] or m['effective_pair_seen_train_or_validation'] or m['input_annotation_heterogeneous'])}
 if row['task']=='effect':conditions['WT_mutant_consumed_inputs_distinguishable']=lambda m:not m['effect_WT_mutant_consumed_inputs_identical']
 for name,condition in conditions.items():
  selected=[x for x in pred if condition(masks[x['record_id']])]
  groups=collections.defaultdict(list);groups['all']=selected
  for x in selected:groups[MAP.get(x.get('evaluation_stratum') or x.get('stratum') or 'unknown','unknown')].append(x)
  for chemical,data in groups.items():
   ids=sorted(x['record_id'] for x in data);idhash=hashlib.sha256(json.dumps(ids).encode()).hexdigest();scores=independent_metrics(data,row['task']) if data else {'n':0};metric_checks+=len(scores)
   records.append({'view':row['view'],'method':row['method'],'seed':row['seed'],'runtime_kind':kind,'torch':torch_version,'condition':name,'chemical_group':chemical,'eligible_test_n':len(data),'original_test_n':len(pred),'eligible_record_ids_sha256':idhash,'metrics':scores})
buckets=collections.defaultdict(list)
for x in records:buckets[x['view'],x['method'],x['condition'],x['chemical_group']].append(x)
summary=[]
for key,rows in buckets.items():
 hashes={x['eligible_record_ids_sha256'] for x in rows};metrics={}
 if len(hashes)==1:
  for metric in rows[0]['metrics']:
   if metric=='n':continue
   values=[x['metrics'][metric] for x in rows if x['metrics'][metric] is not None]
   if values:metrics[metric]={'mean':statistics.mean(values),'sd':statistics.stdev(values) if len(values)>1 else None,'n_defined_seeds':len(values)}
 summary.append({'view':key[0],'method':key[1],'condition':key[2],'chemical_group':key[3],'seeds':sorted(x['seed'] for x in rows),'ten_seeds':sorted(x['seed'] for x in rows)==list(range(10)),'same_eligible_test_ids_across_seeds':len(hashes)==1,'eligible_test_n_values':sorted({x['eligible_test_n'] for x in rows}),'metrics':metrics,'aggregation_scope':'same test subset only; seed+runtime differences remain mixed'})
stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ');out=H/('conditional-input-scores-'+stamp);out.mkdir();(out/'scores.json').write_text(json.dumps({'at':stamp,'source_accepted_details_sha256':pointer['sha256'],'accepted_units':len(accepted['records']),'scored_units':len({(x['view'],x['method'],x['seed']) for x in records}),'input_proofs':evidence,'records':records,'summary':summary,'missing':missing,'metric_units_evaluated':metric_checks,'scope':'Read-only input-conditioned diagnostics; frozen primary test scores, samples, splits, HPO and models unchanged. Exact ordered tensor equivalence is a lower bound; graph isomorphism equivalence not asserted. Heterogeneous raw annotations on the same recorded input are not proof of distinct chemical species.'},indent=2),encoding='utf-8')
cp=H/'conditional-input-scores-current.json';temp=cp.with_suffix('.tmp');temp.write_text(json.dumps({'at':stamp,'path':str(out/'scores.json'),'sha256':sha(out/'scores.json'),'source_accepted_details_sha256':pointer['sha256'],'accepted_units':len(accepted['records']),'scored_units':len({(x['view'],x['method'],x['seed']) for x in records}),'missing':missing},indent=2),encoding='utf-8');temp.replace(cp)
print(json.dumps({'directory':str(out),'accepted_units':len(accepted['records']),'scored_units':len({(x['view'],x['method'],x['seed']) for x in records}),'missing':missing,'metric_units_evaluated':metric_checks}))
