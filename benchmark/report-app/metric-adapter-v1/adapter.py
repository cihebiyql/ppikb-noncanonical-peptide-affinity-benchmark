"""Strict aggregate-only adapter; never imports the app or any model/scorer.

Preparation/test use pure convert_rows. Real file conversion requires root's
explicit review, SHA bindings and joint-barrier reference before summary access.
"""
from __future__ import annotations
import argparse,csv,datetime,hashlib,json,math,os
from pathlib import Path
from urllib.parse import quote

HERE=Path(__file__).resolve().parent
PANELS=('source_peptide_dependency_cold','target_reference_homology_cold')
REGIMES=('NC_only','standard_only')
DATASETS=('PPIKB-internal','PTM-external75','IgG-supplement13')
METRICS=('MAE','RMSE','Pearson','Spearman','R2')
CATEGORIES={'five_prior_paper_NN':{'GraphDTA-GIN','MGraphDTA','DGDTA-CL','DeepNC-GEN','GS-DTA'},'auxiliary_handcrafted_RF':{'RF-Morgan2-chiral-AAC-DP'},'three_deterministic_references':{'reference:train_mean','reference:train_median','reference:target_reference_train_median'}}
MICRO={'row_micro','matched_row_micro'}
MACRO={'equal_weight_target_id','equal_weight_target_reference_sequence_sha','equal_weight_study_id','matched_equal_target_reference','matched_equal_study_id'}
STRATA={'synthetic_D_backbone','PTM','synthetic_and_PTM','other_NC','standard20_control'}
COHORT_MAP={'all':'all','NC_core':'NC_all','standard':'standard20_control','standard20_control':'standard20_control',
 **{s:s for s in STRATA},'exclude_discordant_sensitivity':'all',
 'NC_core_exclude_discordant_sensitivity':'NC_all','standard_exclude_discordant_sensitivity':'standard20_control',
 'standard20_control_exclude_discordant_sensitivity':'standard20_control',
 **{'exclude_discordant:'+s:s for s in STRATA},
 'external_primary67':'PTM','external_conditional_sensitivity8':'PTM','external_reference_target_cold2':'PTM',
 'supplement_NC8':'synthetic_D_backbone','supplement_standard5':'standard20_control',
 'NC_matched':'NC_all','standard_matched':'standard20_control'}
FIELDS=('method_id','panel_id','regime_id','chemistry_id','evaluation_set_id','metric_id','mean','sd','n','seed_count')
IDENTITY=('category','dataset_id','panel','method_id','regime','cohort','aggregation','metric')
NEEDED=set(IDENTITY)|{'mean','sample_sd','completed_seed_count','defined_seed_count','n_by_seed','n_unit'}
FORBIDDEN={'record_id','pKd_true','pKd_pred','predictions','model_state','labels','gold','checkpoint'}

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for block in iter(lambda:f.read(1024**2),b''):h.update(block)
 return h.hexdigest()
def path(v):
 s=str(v).replace('\\','/')
 if os.name!='nt' and len(s)>2 and s[1:3]==':/':s='/mnt/'+s[0].lower()+s[2:]
 elif os.name=='nt' and s.startswith('/mnt/') and len(s)>7 and s[6]=='/':s=s[5].upper()+':'+s[6:]
 return Path(s)
def load(p):return json.loads(path(p).read_text(encoding='utf-8-sig'))
def dump(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def require_ref(ref):
 if not isinstance(ref,dict) or not {'path','sha256'}<=set(ref):raise ValueError('Missing explicit source reference')
 p=path(ref['path'])
 if p.suffix.lower()!='.json' or any(t in p.name.lower() for t in ['predictions','gold','labels','checkpoint']):raise ValueError('Only bound summary/review/barrier JSON metadata accepted')
 if p.stat().st_size>100*1024**2:raise ValueError('Bound reference exceeds100MiB')
 if sha(p)!=ref['sha256']:raise ValueError('Bound source SHA mismatch: '+p.name)
 return p
def integer(value,name,maximum=None):
 if type(value) is not int or value<0 or maximum is not None and value>maximum:raise ValueError('Invalid '+name+'; null is not replaced by zero')
 return value
def finite_or_null(value,name):
 if value is not None and (isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value)):raise ValueError('Nonfinite/nonnumeric '+name)
 return value
def exclusion_reason(row,rules):
 for rule in rules:
  required={'category','dataset_id','cohort','aggregation','reason'}
  if not isinstance(rule,dict) or not required<=set(rule) or not str(rule['reason']).strip():raise ValueError('Explicit exclusion requires full scope and reason')
  selectors={k:v for k,v in rule.items() if k!='reason'}
  if not set(selectors)<=set(IDENTITY):raise ValueError('Unknown explicit exclusion selector')
  if all(row.get(k)==v for k,v in selectors.items()):return rule['reason']
 return None
def chemistry(row):
 cohort=row['cohort'];dataset=row['dataset_id']
 if cohort not in COHORT_MAP:raise ValueError('Unknown cohort (requires explicit exclusion or schema revision): '+str(cohort))
 if cohort.startswith('external_') and dataset!='PTM-external75':raise ValueError('External75 cohort on wrong dataset')
 if cohort.startswith('supplement_') and dataset!='IgG-supplement13':raise ValueError('Supplement cohort on wrong dataset')
 if cohort in {'NC_matched','standard_matched'}:
  if dataset!='PPIKB-internal' or row['aggregation']!='matched_row_micro':raise ValueError('Matched cohort/dataset/aggregation mismatch')
 elif row['aggregation']=='matched_row_micro':raise ValueError('Matched aggregation requires an explicit matched cohort')
 return COHORT_MAP[cohort]
def expected_n(row):
 c=row['cohort'];d=row['dataset_id'];i=PANELS.index(row['panel'])
 if d=='PPIKB-internal':
  return {'all':(1039,1443),'NC_core':(303,332),'standard':(736,1111),'standard20_control':(736,1111),
   'synthetic_D_backbone':(100,93),'PTM':(158,190),'synthetic_and_PTM':(39,37),'other_NC':(6,12),
   'exclude_discordant_sensitivity':(998,1328),'NC_core_exclude_discordant_sensitivity':(274,261),
   'standard_exclude_discordant_sensitivity':(724,1067),'standard20_control_exclude_discordant_sensitivity':(724,1067),
   'NC_matched':(90,174),'standard_matched':(124,203)}.get(c,(None,None))[i]
 if d=='PTM-external75':return {'all':75,'NC_core':75,'PTM':75,'standard':0,'standard20_control':0,'synthetic_D_backbone':0,'synthetic_and_PTM':0,'other_NC':0,'external_primary67':67,'external_conditional_sensitivity8':8,'external_reference_target_cold2':2}.get(c)
 return {'all':13,'NC_core':8,'synthetic_D_backbone':8,'standard':5,'standard20_control':5,'PTM':0,'synthetic_and_PTM':0,'other_NC':0,'supplement_NC8':8,'supplement_standard5':5}.get(c)
def row_values(row):
 completed=integer(row['completed_seed_count'],'completed_seed_count',10);defined=integer(row['defined_seed_count'],'defined_seed_count',10)
 if defined>completed:raise ValueError('Defined seeds exceed completed seeds')
 ns=row['n_by_seed']
 if not isinstance(ns,dict) or not ns or len(ns)!=completed or any(type(k) is not str or k not in {str(i) for i in range(10)} for k in ns):raise ValueError('n_by_seed must enumerate exactly completed seeds0-9')
 for n in ns.values():integer(n,'observation denominator')
 if len(set(ns.values()))!=1:raise ValueError('Different n_by_seed cannot become a single sample n')
 if row['n_unit']!='observation_rows':raise ValueError('Micro n must be observation_rows, never macro group counts')
 n=next(iter(ns.values()));expected=expected_n(row)
 if expected is not None and n!=expected:raise ValueError('Frozen cohort denominator mismatch')
 mean=finite_or_null(row['mean'],'mean');sd=finite_or_null(row['sample_sd'],'sample_sd')
 if n==0 and defined>0:raise ValueError('No defined metric seeds with zero observations')
 if (defined==0)!=(mean is None):raise ValueError('Null mean and defined_seed_count disagree')
 if sd is not None and sd<0:raise ValueError('Negative SD')
 if defined<2 and sd is not None:raise ValueError('SD must remain null with fewer than two defined seeds')
 if defined>=2 and sd is None:raise ValueError('Missing source SD despite two defined seeds; no SD invented')
 if 'values_by_seed' in row:
  values=row['values_by_seed']
  if not isinstance(values,dict) or set(values)!=set(ns):raise ValueError('values_by_seed differs from n_by_seed')
  for value in values.values():finite_or_null(value,'per-seed aggregate metric')
  if sum(v is not None for v in values.values())!=defined:raise ValueError('Defined-seed count differs from actual aggregate nulls')
 if 'missing_seeds' in row and row['missing_seeds']!=sorted(set(range(10))-{int(k) for k in ns}):raise ValueError('Missing seed list inconsistent')
 return mean,sd,n,defined
def convert_rows(rows,explicit_exclusions=()):
 if not isinstance(rows,list) or len(rows)>100000:raise ValueError('Bounded aggregate list required')
 output=[];trace=[];macro=[];explicit=[];seen_source=set();seen_output=set()
 for index,row in enumerate(rows):
  if not isinstance(row,dict) or not NEEDED<=set(row) or FORBIDDEN&set(row):raise ValueError('Not an aggregate summary row')
  if row['category'] not in CATEGORIES or row['method_id'] not in CATEGORIES[row['category']]:raise ValueError('Method/category mismatch')
  if row['dataset_id'] not in DATASETS or row['panel'] not in PANELS or row['regime'] not in REGIMES or row['metric'] not in METRICS:raise ValueError('Unknown dataset/panel/regime/metric')
  identity=tuple(row[k] for k in IDENTITY)
  if identity in seen_source:raise ValueError('Duplicate original summary coordinate')
  seen_source.add(identity)
  reason=exclusion_reason(row,explicit_exclusions)
  if reason:explicit.append({'source_index':index,'reason':reason,'original_row':row});continue
  if row['cohort'] not in COHORT_MAP and not (row['cohort']=='all_diagnostic' and row['aggregation'] in MACRO):raise ValueError('Unknown cohort requires explicit exclusion or schema revision')
  if row['aggregation'] in MACRO:macro.append({'source_index':index,'reason':'macro_not_compatible_with_observation_n_app_schema','original_row':row});continue
  if row['aggregation'] not in MICRO:raise ValueError('Unknown aggregation; not silently dropped')
  chem=chemistry(row);mean,sd,n,defined=row_values(row)
  evaluation='|'.join(quote(str(row[k]),safe='-_') for k in ['category','dataset_id','cohort','aggregation'])
  out=dict(method_id=row['method_id'],panel_id=row['panel'],regime_id=row['regime'],chemistry_id=chem,evaluation_set_id=evaluation,metric_id=row['metric'],mean=mean,sd=sd,n=n,seed_count=defined)
  key=tuple(out[k] for k in FIELDS[:6])
  if key in seen_output:raise ValueError('Output coordinate collision')
  seen_output.add(key);output.append(out)
  trace.append({'source_index':index,'original_identity':dict(zip(IDENTITY,identity)),'evaluation_set_id':evaluation,'chemistry_id':chem,'completed_seed_count':row['completed_seed_count'],'defined_seed_count':defined,'source_n_unit':row['n_unit'],'n_by_seed':row['n_by_seed'],'source_missing_seeds':row.get('missing_seeds'),'mean_and_SD_recomputed':False})
 return {'rows':output,'mapping_trace':trace,'excluded_macros':macro,'explicitly_excluded':explicit,'source_row_count':len(rows),'converted_row_count':len(output)}

def run(authorization,summary,output):
 auth=load(authorization)
 if auth.get('schema')!='metric-adapter-authorization-v1' or any(auth.get(k) is not True for k in ['root_metric_adapter_authorized','reviewed','independently_recomputed','all_required_selections_frozen']):raise PermissionError('Await explicit root reviewed-source and joint-barrier authorization')
 if auth.get('adapter_sha256')!=sha(__file__):raise ValueError('Adapter source SHA mismatch')
 if 'expires_at' in auth:
  expires=datetime.datetime.fromisoformat(auth['expires_at'].replace('Z','+00:00'))
  if expires.tzinfo is None or datetime.datetime.now(datetime.timezone.utc)>=expires:raise TimeoutError('Format-conversion authorization expired')
 approved=path(auth['source_summary']['path'])
 if approved.resolve()!=path(summary).resolve():raise ValueError('CLI summary differs from approved source')
 if approved.suffix.lower()!='.json' or not 'summary' in approved.name.lower() or any(x in approved.name.lower() for x in ['gold','prediction','label','checkpoint']):raise ValueError('Only explicitly bound aggregate summary JSON allowed')
 for key in ['source_review','joint_barrier']:require_ref(auth[key])
 if approved.stat().st_size>100*1024**2:raise ValueError('Bounded summary input exceeds100MiB')
 require_ref(auth['source_summary'])
 loaded=load(approved)
 if isinstance(loaded,dict):
  keys=[k for k in ['rows','summary'] if k in loaded]
  if len(keys)!=1:raise ValueError('Aggregate wrapper must expose exactly rows or summary')
  loaded=loaded[keys[0]]
 result=convert_rows(loaded,auth.get('explicit_exclusions',[]))
 out=path(output).resolve()
 if not out.is_relative_to(HERE) or out==HERE or out.exists():raise ValueError('New output directory must stay inside metric-adapter-v1; no overwrite')
 out.mkdir(parents=True)
 dump(out/'app-metrics.json',result['rows'])
 with (out/'app-metrics.csv').open('w',encoding='utf-8-sig',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader()
  for row in result['rows']:writer.writerow({k:'null' if v is None else v for k,v in row.items()})
 dump(out/'mapping-trace.json',result['mapping_trace']);dump(out/'excluded-macros.json',result['excluded_macros']);dump(out/'explicit-exclusions.json',result['explicitly_excluded'])
 provenance={'source_summary_path':str(approved),'source_summary_sha256':auth['source_summary']['sha256'],'source_review':auth['source_review'],'joint_barrier':auth['joint_barrier'],'authorization_path':str(path(authorization)),'authorization_sha256':sha(path(authorization)),'adapter_sha256':sha(__file__),'source_row_count':result['source_row_count'],'converted_row_count':result['converted_row_count'],'excluded_macro_rows':len(result['excluded_macros']),'explicit_excluded_rows':len(result['explicitly_excluded']),'macro_preservation':'full original aggregate summary stays authoritative; excluded macro original rows retained here, never discarded from full report','statistics_recomputed':False,'app_modified':False,'import_or_build_called':False,'raw_predictions_labels_models_opened':False}
 dump(out/'conversion-provenance.json',provenance)
 for suffix in ['json','csv']:
  dump(out/('import-review-'+suffix+'.template.json'),{'kind':'reviewed_aggregate_performance','reviewed':False,'independently_recomputed':True,'all_required_selections_frozen':True,'summary_sha256':sha(out/('app-metrics.'+suffix)),'requires_root_conversion_review':True,'source_summary_sha256':auth['source_summary']['sha256'],'source_review':auth['source_review'],'joint_barrier':auth['joint_barrier'],'conversion_provenance_sha256':sha(out/'conversion-provenance.json'),'app_schema_warning':'seed_count is defined metric seeds, not completed model seeds; keep completion/null details in mapping-trace and full report'})
 dump(out/'artifact-manifest.json',{'files':{p.name:sha(p) for p in out.iterdir() if p.is_file()},'source_summary_sha256':auth['source_summary']['sha256']})
 return provenance
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--authorization',required=True);ap.add_argument('--summary',required=True);ap.add_argument('--output',required=True);a=ap.parse_args();r=run(a.authorization,a.summary,a.output);print(json.dumps({k:r[k] for k in ['source_row_count','converted_row_count','excluded_macro_rows','explicit_excluded_rows','source_summary_sha256','app_modified','import_or_build_called']}))
if __name__=='__main__':main()
