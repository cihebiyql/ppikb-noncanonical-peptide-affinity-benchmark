"""Independent NumPy evaluator. Real holdouts require explicit post-freeze authorization.

Preparation/self-tests never read real predictions or affinity-label files. This
module does not import the execution runner, adapters, Torch or model checkpoints.
"""
from __future__ import annotations
import argparse
from collections import Counter,defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import numpy as np

METRICS=('MAE','RMSE','Pearson','Spearman','R2')
METHODS={'GraphDTA-GIN','MGraphDTA','DGDTA-CL','DeepNC-GEN','GS-DTA'}
PANELS={'source_peptide_dependency_cold','target_reference_homology_cold'}
STRATA={'synthetic_D_backbone','PTM','synthetic_and_PTM','other_NC','standard20_control'}
DATASETS={'internal-test':'PPIKB-internal',
          'external75-PTM-reference-view-v1':'PTM-external75',
          'postfreeze-supplement13-reference-view-v1':'IgG-supplement13',
          'source_test':'PPIKB-internal','target_test':'PPIKB-internal',
          'external75':'PTM-external75','supplement13':'IgG-supplement13'}
EXPECTED_PREDICTION_ROWS={'PPIKB-internal':248200,'PTM-external75':15000,'IgG-supplement13':2600}
SUPPLEMENT_ACCEPTED_SHA='eba3933184782b1eed6f178c30edbd4eeb6c9414758adb5584b2acc46beb3c92'

def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()

def local_path(path):
 s=str(path)
 if os.name=='nt' and s.startswith('/mnt/') and len(s)>7 and s[6]=='/':
  s=s[5].upper()+':'+s[6:]
 return Path(s)

def read_json(path):return json.loads(local_path(path).read_text(encoding='utf-8-sig'))
def read_jsonl(path):
 with local_path(path).open(encoding='utf-8-sig') as f:return [json.loads(s) for s in f if s.strip()]
def write_json(path,obj):Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def average_ranks(values):
 """One-based ranks; ties receive mean rank, independent of SciPy."""
 a=np.asarray(values,dtype=np.float64).reshape(-1)
 order=np.argsort(a,kind='mergesort');r=np.empty(a.size,dtype=np.float64)
 start=0
 while start<a.size:
  stop=start+1
  while stop<a.size and a[order[stop]]==a[order[start]]:stop+=1
  r[order[start:stop]]=(start+stop+1)/2.0
  start=stop
 return r

def correlation(a,b):
 if len(a)<2:return None
 if bool(np.all(a==a[0])) or bool(np.all(b==b[0])):return None
 def unit(x):
  with np.errstate(over='ignore'):
   delta=x-x[0]
  if not np.isfinite(delta).all():
   scaled=x/float(np.max(np.abs(x)));delta=scaled-scaled[0]
  scale=float(np.max(np.abs(delta)))
  if not scale:return None
  delta=delta/scale;centered=delta-delta.mean();norm=float(np.linalg.norm(centered))
  return centered/norm if norm else None
 ac=unit(a);bc=unit(b)
 if ac is None or bc is None:return None
 return float(np.clip(np.dot(ac,bc),-1,1))

def metrics(true,pred):
 y=np.asarray(true,dtype=np.float64).reshape(-1)
 p=np.asarray(pred,dtype=np.float64).reshape(-1)
 if y.shape!=p.shape or not np.isfinite(y).all() or not np.isfinite(p).all():
  raise ValueError('Mismatched/nonfinite truth or prediction')
 out=dict(n=len(y),MAE=None,RMSE=None,Pearson=None,Spearman=None,R2=None)
 if not len(y):return out
 residual=p-y;sse=float(np.dot(residual,residual))
 out['MAE']=float(np.abs(residual).sum()/len(y));out['RMSE']=math.sqrt(sse/len(y))
 if len(y)>1:
  delta=y-y[0];centered=delta-delta.mean();sst=float(np.dot(centered,centered))
  if not bool(np.all(y==y[0])) and sst>0:out['R2']=1.0-sse/sst
  out['Pearson']=correlation(y,p)
  out['Spearman']=correlation(average_ranks(y),average_ranks(p))
 return out

def summarize_seeds(rows):
 seeds=[r['seed'] for r in rows]
 if len(seeds)!=len(set(seeds)) or not set(seeds)<=set(range(10)):
  raise ValueError('Duplicate or out-of-plan seeds')
 out={'completed_seed_count':len(seeds),'seeds':sorted(seeds),'missing_seeds':sorted(set(range(10))-set(seeds)),
      'n_min':min((r['n'] for r in rows),default=None),'n_max':max((r['n'] for r in rows),default=None)}
 for metric in METRICS:
  x=[float(r[metric]) for r in rows if r[metric] is not None]
  if not all(math.isfinite(v) for v in x):raise ValueError('Nonfinite seed metric')
  out[metric+'_defined_seed_count']=len(x)
  out[metric+'_mean']=statistics.mean(x) if x else None
  out[metric+'_sd']=statistics.stdev(x) if len(x)>1 else None
 return out

def is_discordant(row):
 return any(v is True for k,v in row.items() if 'discord' in k.lower())

def group_metrics(rows,dataset_id=None):
 def at(ids):return metrics([rows[i]['pKd_true'] for i in ids],[rows[i]['pKd_pred'] for i in ids])
 result={'all':at(range(len(rows)))}
 strata=sorted({str(r.get('evaluation_stratum','unknown')) for r in rows})
 for s in strata:result[s]=at([i for i,r in enumerate(rows) if str(r.get('evaluation_stratum','unknown'))==s])
 for n,b in [('NC_core',True),('standard',False)]:result[n]=at([i for i,r in enumerate(rows) if r.get('NC_core') is b])
 clean=[i for i,r in enumerate(rows) if not is_discordant(r)]
 result['exclude_discordant_sensitivity']=at(clean)
 for s in strata:result['exclude_discordant:'+s]=at([i for i in clean if str(rows[i].get('evaluation_stratum','unknown'))==s])
 if dataset_id in (None,'PTM-external75'):
  for name,field in [('external_primary67','external_primary'),('external_conditional_sensitivity8','external_conditional_sensitivity'),('external_reference_target_cold2','external_reference_target_cold')]:
   if any(field in r for r in rows):result[name]=at([i for i,r in enumerate(rows) if r.get(field) is True])
 if dataset_id=='IgG-supplement13':
  for name,field in [('supplement_NC8','external_supplement_NC'),('supplement_standard5','external_supplement_standard')]:
   result[name]=at([i for i,r in enumerate(rows) if r.get(field) is True])
 return result

def macro_metrics(rows,field):
 groups=defaultdict(list)
 for row in rows:groups[str(row.get(field) or '__missing__')].append(row)
 each={key:metrics([r['pKd_true'] for r in rs],[r['pKd_pred'] for r in rs]) for key,rs in sorted(groups.items())}
 out={'group_field':field,'group_count':len(each),'missing_group_rows':len(groups.get('__missing__',[])),
      'per_group_metrics':each,'macro_mean':{},'defined_group_counts':{},
      'definition':'equal-weight group means; undefined group correlations/R2 excluded and counted'}
 for metric in METRICS:
  x=[r[metric] for r in each.values() if r[metric] is not None]
  out['macro_mean'][metric]=statistics.mean(x) if x else None;out['defined_group_counts'][metric]=len(x)
 total=sum(r['n'] for r in each.values())
 out['row_weighted_MAE']=sum(r['n']*r['MAE'] for r in each.values())/total if total else None
 out['row_weighted_RMSE']=math.sqrt(sum(r['n']*r['RMSE']**2 for r in each.values())/total) if total else None
 if field=='study_id':
  out['source_refs']=sorted(each)
  out['source_ref_scope']='machine study_id references, not independently certified papers or biological experiments'
 return out

def require_hash(path,digest):
 if sha(local_path(path))!=digest:raise ValueError('Frozen artifact hash mismatch: '+str(path))

def authorize_barrier(path,digest,explicit_authorization):
 """No prediction/gold file is opened before this check succeeds."""
 if not explicit_authorization:raise PermissionError('Await root explicit post-freeze real-holdout audit authorization')
 require_hash(path,digest);barrier=read_json(path)
 if barrier.get('status')!='all_selections_frozen' or barrier.get('selection_count')!=200 or barrier.get('candidate_fit_count')!=400:
  raise ValueError('Global 200-selection/400-fit barrier missing')
 entries=barrier.get('selections',[])
 if len(entries)!=200:raise ValueError('Incomplete global barrier entries')
 identities=set();hashes=set()
 for e in entries:
  require_hash(e['path'],e['sha256']);s=read_json(e['path'])
  if s.get('status')!='frozen' or s.get('holdout_metrics_consulted') is not False:
   raise ValueError('Unfrozen or holdout-informed selection')
  identity=tuple(s[k] for k in ['method_id','split_id','regime','seed'])
  if identity in identities:raise ValueError('Duplicate barrier selection')
  identities.add(identity);hashes.add(e['sha256'])
 expected={(m,p,r,s) for m in METHODS for p in PANELS for r in ('NC_only','standard_only') for s in range(10)}
 if identities!=expected:raise ValueError('Barrier lacks exact preregistered full grid')
 return barrier,hashes

def unique_by_id(rows,where):
 out={}
 for r in rows:
  rid=r['record_id']
  if rid in out:raise ValueError('Duplicate '+where+' record_id')
  out[rid]=r
 return out

def normalize_score_spec(raw,selection_panel):
 """Read-only compatibility with legacy and new cached-blind-first schemas."""
 spec=dict(raw);raw_dataset=raw.get('dataset_id',raw.get('holdout_id'))
 dataset=DATASETS.get(raw_dataset,raw_dataset)
 panel=raw.get('split_id') or raw.get('selection_split_id') or selection_panel
 if panel!=selection_panel:raise ValueError('Score input belongs to different selection panel')
 if raw_dataset=='source_test' and panel!='source_peptide_dependency_cold':raise ValueError('source_test cache paired to wrong panel')
 if raw_dataset=='target_test' and panel!='target_reference_homology_cold':raise ValueError('target_test cache paired to wrong panel')
 canonical={'PPIKB-internal':'internal-test','PTM-external75':'external75-PTM-reference-view-v1','IgG-supplement13':'postfreeze-supplement13-reference-view-v1'}
 spec.update(split_id=panel,holdout_id=canonical.get(dataset,raw_dataset),normalized_dataset_id=dataset,raw_scoring_dataset_id=raw_dataset)
 if 'gold_rows' in raw:spec.update(label_rows=raw['gold_rows'],label_rows_sha256=raw['gold_rows_sha256'])
 project=Path(__file__).resolve().parent.parent
 if dataset=='PTM-external75':
  base=project/'external-validation/scoring-views-v1'
  for key,name in [('external_primary_ids','ids-primary67.json'),('external_conditional_sensitivity_ids','ids-conditional-sensitivity8.json'),('external_reference_target_cold_ids','ids-reference-target-cold2.json')]:spec.setdefault(key,str(base/name))
 if dataset=='IgG-supplement13':
  base=project/'external-validation/scoring-supplement13-v1'
  for key,name in [('root_accepted_manifest_path','root-accepted-manifest.json'),('nc_ids','ids-nc8.json'),('standard_control_ids','ids-standard5.json')]:spec.setdefault(key,str(base/name))
 return spec

def load_matched_manifest(path,digest):
 require_hash(path,digest);m=read_json(path)
 if m.get('status')!='frozen_metadata_only_not_scored' or m.get('gold_reads')!=0 or m.get('prediction_reads')!=0:
  raise ValueError('Matched-target subsets were not frozen label-free')
 for e in m['artifacts']+m['source_files']:require_hash(e['path'],e['sha256'])
 if {r['panel'] for r in m['panels']}!=PANELS:raise ValueError('Matched-target panel mismatch')
 return m

def matched_target_metrics(rows,panel,manifest):
 spec=next(x for x in manifest['panels'] if x['panel']==panel)
 byid=unique_by_id(rows,'matched target scoring input')
 target_refs=set(read_json(spec['target_reference_shas']))
 result={'panel':panel,'same_fixed_reference_target_count':len(target_refs),'target_key':'exact full database reference sequence SHA256',
         'selection_uses_numeric_labels_or_performance':False,'original_test_unchanged':True,'cohorts':{}}
 for scope,key,wanted_nc in [('NC_matched','NC_ids',True),('standard_matched','standard_ids',False)]:
  ids=read_json(spec[key])
  if len(ids)!=len(set(ids)) or not set(ids)<=set(byid):raise ValueError('Matched-target ID mismatch')
  selected=[byid[rid] for rid in ids]
  if any(r['NC_core'] is not wanted_nc for r in selected):raise ValueError('Matched-target NC/control class changed')
  if {r['target_reference_sequence_sha'] for r in selected}!=target_refs:raise ValueError('Matched-target reference set differs')
  result['cohorts'][scope]={'n':len(selected),'target_count':len(target_refs),
   'row_micro_metrics':metrics([r['pKd_true'] for r in selected],[r['pKd_pred'] for r in selected]),
   'target_reference_equal_weight_macro':macro_metrics(selected,'target_reference_sequence_sha'),
   'study_id_equal_weight_macro':macro_metrics(selected,'study_id'),
   'source_refs':sorted({str(r.get('study_id') or '__missing__') for r in selected}),
   'source_ref_scope':'machine study_id references, not independently certified paper/experiment counts'}
 return result

def audit_task(task,selection_hashes,matched_manifest=None):
 """Root authorizes this only after all selections freeze.

 task: {score_receipt, holdout_spec}. Paths are supplied; no blind rglob of
 private result directories and no guesses about which run is final.
 """
 rp=local_path(task['score_receipt']);receipt=read_json(rp)
 if receipt.get('status')!='complete' or receipt.get('stage')!='post-selection-score-only':raise ValueError('Not final score receipt')
 if receipt['selection_sha256'] not in selection_hashes:raise ValueError('Receipt selection not in global barrier')
 specpath=local_path(task['holdout_spec']);expected_spec_sha=receipt.get('score_spec_sha256') or receipt['holdout_spec_sha256']
 require_hash(specpath,expected_spec_sha);raw_spec=read_json(specpath)
 if raw_spec.get('dataset_id',raw_spec.get('holdout_id'))!=receipt['holdout_id']:raise ValueError('Raw score receipt/spec dataset mismatch')
 spec=normalize_score_spec(raw_spec,receipt['split_id'])
 predpath=rp.parent/'predictions.jsonl';require_hash(predpath,receipt['predictions_sha256'])
 # Only now may real numeric predictions and sealed labels be opened.
 pred=unique_by_id(read_jsonl(predpath),'prediction')
 blind_proof_verified=None
 if receipt.get('prediction_protocol')=='label-free cached X; blind first, gold later':
  bp=rp.parent/'blind-predictions.jsonl';require_hash(bp,receipt['blind_predictions_sha256'])
  proof=read_json(rp.parent/'blind-complete.json')
  if proof.get('stage')!='blind_predictions_persisted_before_gold_open' or proof.get('gold_reads')!=0 or proof['blind_predictions_sha256']!=receipt['blind_predictions_sha256'] or proof['selection_sha256']!=receipt['selection_sha256']:raise ValueError('Blind-first proof mismatch')
  blind=unique_by_id(read_jsonl(bp),'blind prediction')
  if set(blind)!=set(pred) or proof['n']!=len(pred) or any(float(blind[rid]['pKd_pred'])!=float(pred[rid]['pKd_pred']) for rid in pred):raise ValueError('Predictions changed when joining gold')
  blind_proof_verified=True
 require_hash(spec['input_rows'],spec['input_rows_sha256']);inputs=unique_by_id(read_jsonl(spec['input_rows']),'input')
 if set(pred)!=set(inputs) or len(pred)!=receipt['n']:raise ValueError('Prediction/input cardinality or identity mismatch')
 require_hash(spec['label_rows'],spec['label_rows_sha256']);gold=unique_by_id(read_jsonl(spec['label_rows']),'gold')
 if not set(inputs)<=set(gold):raise ValueError('Missing frozen gold records')
 dataset_id=spec['normalized_dataset_id']
 rows=[]
 for rid,inp in inputs.items():
  pr=pred[rid];truth=float(gold[rid]['pKd'])
  if blind_proof_verified:
   expected_input_sha=hashlib.sha256(json.dumps(inp,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
   if pr.get('input_record_sha256')!=expected_input_sha or blind[rid].get('input_record_sha256')!=expected_input_sha:raise ValueError('Retained blind input metadata changed')
  if not math.isclose(float(pr['pKd_true']),truth,rel_tol=1e-12,abs_tol=1e-12):raise ValueError('Saved prediction truth differs from frozen gold')
  if inp.get('NC_core') not in (True,False) or not isinstance(inp.get('NC_core'),bool):raise ValueError('Missing explicit NC status')
  if inp.get('evaluation_stratum') not in STRATA:raise ValueError('Unknown chemistry stratum')
  for key in ('NC_core','evaluation_stratum','chemical_entity_id','target_id','study_id'):
   if pr.get(key) is not None and pr[key]!=inp.get(key):raise ValueError('Prediction metadata conflict: '+key)
  rows.append(dict(inp,pKd_true=truth,pKd_pred=float(pr['pKd_pred']),dataset_id=dataset_id,
                   target_reference_sequence_sha=hashlib.sha256(inp['target_sequence'].encode('utf-8')).hexdigest() if inp.get('target_sequence') else None))
 for spec_key,flag in [('external_primary_ids','external_primary'),('external_conditional_sensitivity_ids','external_conditional_sensitivity'),('external_reference_target_cold_ids','external_reference_target_cold'),('nc_ids','external_supplement_NC'),('standard_control_ids','external_supplement_standard')]:
  if spec_key in spec:
   ids=set(read_json(spec[spec_key]))
   if not ids<=set(inputs):raise ValueError('External subgroup contains unmatched record')
   for row in rows:
    if flag in row and row[flag]!=(row['record_id'] in ids):raise ValueError('Frozen external group flag/ID conflict')
    row[flag]=row['record_id'] in ids
 grouped=group_metrics(rows,dataset_id)
 if dataset_id=='PTM-external75':
  if [grouped[k]['n'] for k in ['external_primary67','external_conditional_sensitivity8','external_reference_target_cold2']]!=[67,8,2]:raise ValueError('External67/8/2 cohort counts changed')
  if {r['record_id'] for r in rows if r['external_primary']} & {r['record_id'] for r in rows if r['external_conditional_sensitivity']}:raise ValueError('Primary/sensitivity overlap')
  if any(r['external_reference_target_cold'] and not r['external_primary'] for r in rows):raise ValueError('Target-cold subset must be primary')
 if dataset_id=='IgG-supplement13':
  if not spec.get('root_accepted_manifest_path'):raise ValueError('Supplement lacks root accepted metadata binding')
  require_hash(spec['root_accepted_manifest_path'],SUPPLEMENT_ACCEPTED_SHA)
  if len(rows)!=13 or [grouped[k]['n'] for k in ['supplement_NC8','supplement_standard5']]!=[8,5]:raise ValueError('Supplement13 NC8/control5 counts changed')
  nc={r['record_id'] for r in rows if r['external_supplement_NC']};std={r['record_id'] for r in rows if r['external_supplement_standard']}
  if nc&std or nc|std!=set(inputs):raise ValueError('Supplement NC/control sets do not partition13')
  if any(r['NC_core'] is not r['external_supplement_NC'] for r in rows):raise ValueError('Supplement frozen NC IDs disagree with residue class')
  if Counter(r['evaluation_stratum'] for r in rows)!={'synthetic_D_backbone':8,'standard20_control':5}:raise ValueError('Supplement chemistry strata changed')
 differences=[]
 for group,actual in receipt['metrics'].items():
  if group not in grouped:raise ValueError('Runner group unsupported independently: '+group)
  expected=grouped[group]
  for metric in ('n',)+METRICS:
   a=actual[metric];b=expected[metric]
   same=(a is None and b is None) or (a is not None and b is not None and math.isclose(float(a),float(b),rel_tol=1e-9,abs_tol=1e-10))
   if not same:differences.append({'group':group,'metric':metric,'runner':a,'independent':b})
 identity={k:receipt[k] for k in ('split_id','method_id','regime','seed')};identity.update(holdout_id=spec['holdout_id'],dataset_id=dataset_id)
 result={'identity':identity,'score_receipt':str(rp),'score_receipt_sha256':sha(rp),'metrics':grouped,
         'macro_by_target':macro_metrics(rows,'target_id'),'macro_by_source':macro_metrics(rows,'study_id'),
         'macro_by_full_target_reference':macro_metrics(rows,'target_reference_sequence_sha'),
         'source_refs':sorted({str(r.get('study_id') or '__missing__') for r in rows}),
         'source_ref_scope':'machine study_id references; not independently certified paper or experiment counts',
         'runner_metric_differences':differences,'all_truths_match_frozen_gold':True,
         'raw_scoring_dataset_id':spec['raw_scoring_dataset_id'],'cached_blind_first_proof_verified':blind_proof_verified,
         'scientific_limits':['seed SD measures training variability, not independent experiments',
          'external75 is retrospective PTM reference-view data; target-cold2 is not family-cold',
          'IgG-supplement13 is separate retrospective8nonPTM+5standard source/declared-chemical-cold diagnostic;449aaheavy reference only, target-related, not whole2H2L/lot/glycoform/family-certified',
          'standard20_control denotes residue annotation, not confirmed uncapped/unmodified chemistry']}
 if dataset_id=='PPIKB-internal' and matched_manifest is not None:
  result['matched_target_diagnostics']=matched_target_metrics(rows,receipt['split_id'],matched_manifest)
 return result

def summarize_matched_targets(audited):
 """Seed summaries of fixed-target diagnostics; no pooling across datasets/scopes."""
 groups=defaultdict(list)
 for score in audited:
  if 'matched_target_diagnostics' not in score:continue
  ident=score['identity']
  for cohort,data in score['matched_target_diagnostics']['cohorts'].items():
   choices=[('row_micro',data['row_micro_metrics'],data['n'],{},'observation rows'),
     ('target_reference_equal_weight_macro',data['target_reference_equal_weight_macro']['macro_mean'],data['target_count'],data['target_reference_equal_weight_macro']['defined_group_counts'],'same fixed full-reference targets'),
     ('study_id_equal_weight_macro',data['study_id_equal_weight_macro']['macro_mean'],data['study_id_equal_weight_macro']['group_count'],data['study_id_equal_weight_macro']['defined_group_counts'],'machine study_id references')]
   for aggregation,met,n,defined,unit in choices:
    key=tuple(ident[k] for k in ['dataset_id','split_id','method_id','regime'])+(cohort,aggregation)
    groups[key].append({'seed':ident['seed'],'n':n,**{m:met[m] for m in METRICS},'observation_rows':data['n'],'target_reference_count':data['target_count'],'defined_groups':defined,'n_unit':unit})
 out=[]
 for key,rs in sorted(groups.items()):
  record={'identity':key,**summarize_seeds(rs),'n_field_unit':rs[0]['n_unit'],
          'observation_rows_min':min(r['observation_rows'] for r in rs),'observation_rows_max':max(r['observation_rows'] for r in rs),
          'target_reference_count_min':min(r['target_reference_count'] for r in rs),'target_reference_count_max':max(r['target_reference_count'] for r in rs),
          'defined_group_counts_by_seed':{str(r['seed']):r['defined_groups'] for r in rs},
          'source_scope':'study_id macro uses machine source_refs; seed SD is not biological CI'}
  out.append(record)
 return out

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--selection-barrier',required=True);p.add_argument('--barrier-sha256',required=True)
 p.add_argument('--task-map',required=True,help='Explicit list of {score_receipt,holdout_spec}; no directory scan')
 p.add_argument('--matched-target-manifest',required=True);p.add_argument('--matched-target-manifest-sha256',required=True)
 p.add_argument('--output',required=True);p.add_argument('--audit-authorized-after-freeze',action='store_true')
 a=p.parse_args()
 barrier,hashes=authorize_barrier(a.selection_barrier,a.barrier_sha256,a.audit_authorized_after_freeze)
 matched=load_matched_manifest(a.matched_target_manifest,a.matched_target_manifest_sha256)
 tasks=read_json(a.task_map);outpath=Path(a.output);outpath.mkdir(parents=True,exist_ok=False)
 audited=[audit_task(t,hashes,matched) for t in tasks]
 if any(x['identity']['dataset_id'] not in EXPECTED_PREDICTION_ROWS for x in audited):raise ValueError('Dataset outside frozen600-score plan')
 identities=[tuple(x['identity'].values()) for x in audited]
 if len(identities)!=len(set(identities)):raise ValueError('Duplicate final score tasks')
 write_json(outpath/'per-score-audit.json',audited)
 grouped=defaultdict(list)
 for x in audited:
  ident=x['identity']
  for group,m in x['metrics'].items():grouped[tuple(ident[k] for k in ['dataset_id','split_id','holdout_id','method_id','regime'])+(group,)].append(dict(seed=ident['seed'],**m))
 summaries=[{'identity':key,**summarize_seeds(rs)} for key,rs in sorted(grouped.items())]
 write_json(outpath/'independent-ten-seed-summary.json',summaries)
 write_json(outpath/'independent-matched-target-ten-seed-summary.json',summarize_matched_targets(audited))
 expected_internal={(m,p,r,s) for m in METHODS for p in PANELS for r in ('NC_only','standard_only') for s in range(10)}
 actual_internal={(x['identity']['method_id'],x['identity']['split_id'],x['identity']['regime'],x['identity']['seed']) for x in audited if x['identity']['holdout_id']=='internal-test'}
 expected_scores={(d,m,p,r,s) for d in EXPECTED_PREDICTION_ROWS for m in METHODS for p in PANELS for r in ('NC_only','standard_only') for s in range(10)}
 actual_scores={(x['identity']['dataset_id'],x['identity']['method_id'],x['identity']['split_id'],x['identity']['regime'],x['identity']['seed']) for x in audited}
 score_counts=Counter(x['identity']['dataset_id'] for x in audited)
 prediction_counts=Counter()
 for x in audited:prediction_counts[x['identity']['dataset_id']]+=x['metrics']['all']['n']
 report={'scope':'root-authorized post-global-freeze independent metrics recomputation','barrier_sha256':a.barrier_sha256,
         'real_score_tasks_audited':len(audited),'all_predictions_true_labels_match':all(x['all_truths_match_frozen_gold'] for x in audited),
         'metric_difference_count':sum(len(x['runner_metric_differences']) for x in audited),
         'internal_expected_units':200,'internal_actual_units':len(actual_internal),'missing_internal_units':sorted(expected_internal-actual_internal),
         'all_expected_score_units':600,'all_actual_score_units':len(actual_scores),'missing_score_units':sorted(expected_scores-actual_scores),
         'extra_score_units':sorted(actual_scores-expected_scores),'expected_score_units_by_dataset':{d:200 for d in EXPECTED_PREDICTION_ROWS},
         'actual_score_units_by_dataset':dict(score_counts),'expected_prediction_rows_by_dataset':EXPECTED_PREDICTION_ROWS,
         'actual_prediction_rows_by_dataset':dict(prediction_counts),'expected_total_prediction_rows':265800,
         'actual_total_prediction_rows':sum(prediction_counts.values()),
         'complete600_scores_265800_rows':actual_scores==expected_scores and dict(prediction_counts)==EXPECTED_PREDICTION_ROWS,
         'all_observed_groups_ten_seeds':bool(summaries) and all(x['completed_seed_count']==10 for x in summaries),
         'no_training_or_model_selection':True,'author_code_loaded':False,'evaluator_sha256':sha(__file__)}
 write_json(outpath/'independent-audit-manifest.json',report)
 print(json.dumps({k:v for k,v in report.items() if k not in ('missing_internal_units','missing_score_units','extra_score_units')},ensure_ascii=False))

if __name__=='__main__':main()
