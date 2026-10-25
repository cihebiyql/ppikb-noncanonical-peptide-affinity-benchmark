"""Independent v3 selected20 CSV audit; no NN, fitting or checkpoint loading."""
from __future__ import annotations
import argparse,csv,hashlib,json,math,runpy,statistics,time
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path

UTIL=runpy.run_path(str(Path(__file__).with_name('audit_training60_expanded_local_v4.py')))
sha,load,rows,metrics,guard=(UTIL[x] for x in ['sha','load','rows','metrics','guard'])
COHORT=UTIL['COHORT'];LABELS=UTIL['LABELS'];WORKERS=UTIL['WORKERS'];SETTINGS_BY_MODEL=UTIL['SETTINGS_BY_MODEL'];MODEL_NAMES={'hybrid':'fullfine_hybrid','mlm':'fullfine_mlm','2025':'fullfine_peptideclm2025'}

def writecsv(p,items):
 with p.open('w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(items[0]));w.writeheader();w.writerows(items)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--mapping',type=Path,required=True);ap.add_argument('--training-audit',type=Path,required=True);ap.add_argument('--training-audit-sha',required=True);ap.add_argument('--cohort-csv',type=Path,required=True);ap.add_argument('--selected-root',required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
 job,proc=guard();started=time.monotonic();checks=0;errors=[];paths={};output=[];selected={};group_output=[];macro_output=[]
 if a.output.exists():raise ValueError('Unique audit attempt required')
 a.output.mkdir(parents=True)
 def check(ok,msg):
  nonlocal checks
  checks+=1
  if not ok:errors.append(msg)
  if time.monotonic()-started>180:raise TimeoutError('Audit180s wall budget exceeded')
 def compare(fresh,saved,msg):
  for k,v in fresh.items():
   z=saved.get(k);check(v is None and z is None or v is not None and z is not None and abs(v-z)<=5e-12,msg+'/'+k)
 mapping=load(a.mapping)
 for q in mapping['files']:
  p=Path(q.get('local_mirror') or q['local']);check(p.stat().st_size==q['bytes'] and sha(p)==q['sha256'],q['remote']+': independent bytes/SHA');paths[q['remote']]=p
 for remote,p in list(paths.items()):
  if remote.endswith('/SOURCE-TO-NFS-MIRROR.json'):
   proof=load(p);check(proof['all_bytes_verified'] and proof['scientific_manifests_unmodified'],remote+': original mirror proof')
   for q in proof['files']:
    if q['mirror'] in paths:check(sha(paths[q['mirror']])==q['sha256'],q['mirror']+': source SHA receipt');paths[q['source']]=paths[q['mirror']]
 check(sha(a.training_audit)==a.training_audit_sha,'Previously accepted completed40 audit bytes')
 training=load(a.training_audit);check(training['status']=='passed' and training['exact_candidate_count']==60 and training['exact_encoder_seed_pairs']==30,'Training60 audit scope')
 candidates={q['key']:q for q in training['candidates']};candidate_sha={(q['candidate'],q['file']):q['sha256'] for q in training['small_files']}
 check(sha(a.cohort_csv)==LABELS,'Actual new raw labels CSV bytes')
 raw=rows(a.cohort_csv);refs={s:[q for q in raw if q['split']==s] for s in ['validation','test']}
 check(len(refs['validation'])==570 and len(refs['test'])==685,'VAL570/TEST685')
 strata=Counter(q['evaluation_stratum'] for q in refs['test']);check(strata=={'standard20_control':572,'synthetic_D_backbone':45,'PTM':41,'synthetic_and_PTM':20,'other_NC':7},'Test chemical layers')
 flag=lambda q:q['residue_class_graph_discordance'].lower() in ['true','1','yes']
 check(sum(map(flag,refs['test']))==21,'Flagged21/unflagged664')
 root=a.selected_root.rstrip('/')+'/'
 for remote,p in sorted(paths.items()):
  if not remote.startswith(root) or not remote.endswith('/result.json'):continue
  result=load(p);contract=result['contract'];model=('2025' if contract['model_identity'].get('model')=='aaronfeller/PeptideCLM-23M-all' else 'hybrid' if contract['model_identity'].get('repository','').endswith('hybrid-small') else 'mlm');seed=contract['seed'];key=(model,seed);base=remote.removesuffix('result.json')
  check(key not in selected,'Duplicate encoder-seed selection');selected[key]=result
  check(result['schema']=='chemical-encoder.fullfinetune-result.v1' and result['status']=='succeeded','Selected schema/status')
  proof=load(paths[base+'SOURCE-TO-NFS-MIRROR.json']);dispatch=load(paths[proof['dispatch_path']])
  check(dispatch['status']=='succeeded' and dispatch['exit_code']==0 and dispatch['remaining_owned_pids']==[] and not dispatch.get('stop_reason'),'Actual selected worker terminal')
  check(dispatch['contract_sha256']==proof['contract_sha256'] and sha(paths[dispatch['job_path']])==dispatch['job_sha256'],'Selected issued job/contract binding')
  rjob=load(paths[dispatch['job_path']]);rc=load(paths[rjob['contract_path']]);rav=rc['argv'];cap=8192 if model=='2025' else 4096
  check(sha(paths[rjob['contract_path']])==dispatch['contract_sha256']==rjob['contract_sha256'] and rav==rjob['argv']==rc['execution']['command'],'Exact actual selected resource contract/argv bytes')
  check(rc['allocator_cap_mib']==cap and rc['context_mib']==512 and rc['reserve_mib']==6144 and rc['resources']['cpu_threads']==1 and rc['resources']['memory_limit_bytes']==4*1024**3,'Actual selected allocator/CPU/RSS budget')
  check(rc['training_fits']==0 and rc['expected_TEST_rows']==685 and rc['model_name']==model and rc['seed']==seed and rc['worker_sha256']==WORKERS[model] and rc['native_fixed_position_parameters']==(49152 if model=='2025' else 0),'Selected fixed scope/source/no new fits')
  check(rav[rav.index('--mode')+1]=='select-test' and rav[rav.index('--seed')+1]==str(seed) and rav[rav.index('--threads')+1]=='1' and rav[rav.index('--device')+1]=='cuda' and '--candidate' not in rav and not any(x.startswith('--resume') for x in rav),'Actual selection-only command no fit/resume')
  expected_dirs=[q['directory'] for q in [candidates[f'{model}-seed{seed:02d}-candidate{i}'] for i in [0,1]]];check([rav[i+1] for i,v in enumerate(rav) if v=='--candidate-dir']==expected_dirs,'Exactly two independently audited candidate directories')
  check(rc['source_admission']['sha256']=='6093faea30b997ab1a4f6ba4eeedebdb7dd339f81c38d69a6e72c9f90330ae09' and rc['cost_review']['sha256']=='5e7ee6ee6418779e125be50c7b55fef305a081f7bcc38a89310eb7f8bc034058','Actual source admission and fresh expandedcost GO')
  assets={(x['path'],x['sha256']) for x in rc['assets']};check(any(p.endswith('/SOURCE-MANIFEST.json') and h=='d09955e1fe47bd27e72cf0d5d9e670901cb7ced8fbc3f0476c1adf64c36decdd' for p,h in assets) and any(h=='7684788554e23e475726a0219d098849cedf6c989caf7a446d442b05f0800712' for p,h in assets) and any(h=='d68f9b6169a84c32eacefc753af5941701225a5c0e583e4f2a67da4a10e84a35' for p,h in assets),'Actual resource assets bind selected source, training60 review and frozen registry')
  for q in [candidates[f'{model}-seed{seed:02d}-candidate{i}'] for i in [0,1]]:check((q['best_model_nfs_path'],q['best_model_production_sha256']) in assets and (q['best_model_original_path'],q['best_model_production_sha256']) in assets,'Registered original/NFS best model assets agree with accepted trainingSHA')
  allocator=load(paths[rav[rav.index('--proof')+1]]);check(allocator['pid']==dispatch['pid'] and allocator['worker_sha256']==WORKERS[model] and allocator['allocator_cap_bytes']==cap*1024**2 and allocator['CUDA_VISIBLE_DEVICES']==rc['gpu_uuid']==dispatch['gpu_uuid'] and allocator['applied_before_worker_model_import'] is True and allocator['no_allocator_configuration_override'] is True,'Actual selected allocator before encoder import')
  traces=[json.loads(t) for t in paths[rc['run_dir']+'/exec-identity-trace.jsonl'].read_text().splitlines() if t.strip()];execs=[t for t in traces if t['event']=='launch_guard_exact_exec_proven'];check(len(execs)==1 and execs[0]['spawned_pid']==dispatch['pid'] and execs[0]['identity']['uid']==1030 and execs[0]['identity']['argv']==rav and execs[0]['identity']['starttime_ticks']==dispatch['process_starttime_ticks'],'Exact selected scientific kernel PID/birth/argv')
  check(contract['manifest_sha256']==COHORT and contract['input_csv_sha256']==LABELS and contract['runner_sha256']==WORKERS[model],'v3 data/source identity')
  check(contract['model_identity']==UTIL['IDENTITIES'][model] and contract['feature_spec_sha256']==UTIL['SPECS'][model],'Exact selected chemical model and expanded spec identity')
  check(contract['device_type']=='cuda' and contract['threads']==1 and contract['settings']==SETTINGS_BY_MODEL[model] and contract['split_counts']=={'train':531,'validation':570,'test':685,'external':0},'Actual numerical policy and counts')
  select=load(paths[base+'selection.json']);check(sha(paths[base+'selection.json'])==result['selection_sha256'],'Frozen selection bytes')
  pair=[candidates[f'{model}-seed{seed:02d}-candidate{ci}'] for ci in [0,1]];winner=min(range(2),key=lambda ci:(pair[ci]['validation_metrics']['mae'],ci))
  check(result['selected_candidate']==select['selected_candidate']==winner,'VAL-only winner')
  check(select['test_used_for_selection'] is False and abs(select['validation_mae']-pair[winner]['validation_metrics']['mae'])<=5e-12,'VAL selection score')
  check(pair[0]['initial_sha']==pair[1]['initial_sha'],'Same initialization for LR candidates')
  check(len(select['candidates'])==2 and {q['candidate'] for q in select['candidates']}=={0,1},'Exactly both candidates considered')
  for q in select['candidates']:check(q['sha256']==candidate_sha[(f'{model}-seed{seed:02d}-candidate{q["candidate"]}','result.json')],'Selection bound to independently audited candidate bytes')
  for split in ['validation','test']:
   part=result['splits'][split];predpath=paths[part['prediction_path']];check(sha(predpath)==part['prediction_sha256'],'Prediction bytes')
   pred=rows(predpath);ref=refs[split]
   check([q['row_id'] for q in pred]==[q['row_id'] for q in ref],'Exact ordered IDs')
   check([float(q['label']) for q in pred]==[float(q['label']) for q in ref],'Exact float64 labels')
   for q,z in zip(pred,ref):check(q['group_id']==z['global_group_id'] and q['endpoint']=='pKd','Global dependency group/endpoint')
   y=[float(q['label']) for q in pred];pr=[float(q['prediction']) for q in pred];compare(metrics(y,pr),part['metrics'],'Overall')
   grouped=defaultdict(list)
   for i,q in enumerate(pred):grouped[q['group_id']].append(i)
   gm={g:metrics([y[i] for i in ii],[pr[i] for i in ii]) for g,ii in grouped.items()};saved={q['group_id']:q for q in part['group_metrics']}
   check(set(gm)==set(saved),'Exact group inventory')
   for g,mm in gm.items():compare(mm,saved[g],'Group')
   for name,value in part['group_macro_metrics'].items():
    valid=[q[name] for q in gm.values() if q[name] is not None];compare({'mean':sum(valid)/len(valid) if valid else None},value,'Group macro')
    check(value['valid_groups']==len(valid) and value['all_groups']==len(gm),'Defined/total group counts')
   for sub in part['subgroups']:
    ii=[i for i,q in enumerate(ref) if q[sub['column']]==sub['value']];compare(metrics([y[i] for i in ii],[pr[i] for i in ii]),sub,'Source/chemical subgroup')
   if split=='validation':compare(metrics(y,pr),pair[winner]['validation_metrics'],'Selected VAL matches training proof')
   if split=='test':
    for group_id,group_m in sorted(gm.items()):group_output.append({'kind':'full_encoder','method':MODEL_NAMES[model],'seed':seed,'group_id':group_id,**group_m})
    for metric in ['mae','rmse','bias','pearson','spearman','r2']:
     valid_group_values=[q[metric] for q in gm.values() if q[metric] is not None];macro_output.append({'kind':'full_encoder','method':MODEL_NAMES[model],'seed':seed,'metric':metric,'mean':sum(valid_group_values)/len(valid_group_values) if valid_group_values else None,'valid_groups':len(valid_group_values),'all_groups':len(gm)})
    check(len(grouped)==155,'TEST155 dependency groups')
    masks={'all':list(range(len(ref))),'NC_all':[i for i,q in enumerate(ref) if q['evaluation_stratum']!='standard20_control'],'PTM_bearing':[i for i,q in enumerate(ref) if q['evaluation_stratum'] in ['PTM','synthetic_and_PTM']],'flagged':[i for i,q in enumerate(ref) if flag(q)],'unflagged':[i for i,q in enumerate(ref) if not flag(q)]}
    for name in strata:masks[name]=[i for i,q in enumerate(ref) if q['evaluation_stratum']==name]
    for name,ii in masks.items():output.append({'kind':'full_encoder','method':MODEL_NAMES[model],'seed':seed,'stratum':name,**metrics([y[i] for i in ii],[pr[i] for i in ii])})
 check(set(selected)=={(m,s) for m in ['hybrid','mlm','2025'] for s in range(10)},'Exactly30 selected encoder-seed groups')
 summary=[]
 for method,stratum in sorted({(q['method'],q['stratum']) for q in output}):
  group=[q for q in output if (q['method'],q['stratum'])==(method,stratum)]
  check(len(group)==10 and {q['seed'] for q in group}==set(range(10)),'Exact10seeds per summary')
  item={'kind':'full_encoder','method':method,'stratum':stratum,'n':group[0]['n'],'seeds':10}
  for name in ['mae','rmse','bias','pearson','spearman','r2']:
   values=[q[name] for q in group if q[name] is not None];item[name+'_mean']=statistics.mean(values) if values else None;item[name+'_sampleSD']=statistics.stdev(values) if len(values)>1 else None;item[name+'_valid_seeds']=len(values)
  summary.append(item)
 writecsv(a.output/'INDEPENDENT-per-seed-chemical-metrics.csv',output);writecsv(a.output/'INDEPENDENT-ten-seed-chemical-summary.csv',summary)
 writecsv(a.output/'INDEPENDENT-TEST-group-metrics.private.csv',group_output);writecsv(a.output/'INDEPENDENT-TEST-group-macro-per-seed.csv',macro_output)
 report={'schema':'chemical-expanded-v3.independent-selected30.v1','at_utc':datetime.now(timezone.utc).isoformat(),'status':'passed' if not errors else 'failed','checks':checks,'errors':errors,'exact_selected_groups':len(selected),'raw_selected_models_recomputed':30,'test_n':685,'validation_n':570,'test_dependency_groups':155,'test_strata':dict(strata),'flagged_n':21,'cohort_manifest_sha256':COHORT,'cohort_csv_sha256':LABELS,'training60_proof_sha256':sha(a.training_audit),'local_mirror_files_independently_hashed':len(mapping['files']),'derived_per_seed_rows':len(output),'ten_seed_summaries':len(summary),'head_models_reused':0,'NN':0,'fits':0,'weights_loaded':0,'large_weight_hash_boundary':'No checkpoint or large neural-weight bytes read; completed60 proof and exact selection resultSHA bind model selection.','process':proc,'seconds':time.monotonic()-started}
 report.update(test_group_metrics_private_sha256=sha(a.output/'INDEPENDENT-TEST-group-metrics.private.csv'),test_group_macro_per_seed_sha256=sha(a.output/'INDEPENDENT-TEST-group-macro-per-seed.csv'),per_seed_metrics_sha256=sha(a.output/'INDEPENDENT-per-seed-chemical-metrics.csv'),ten_seed_summary_sha256=sha(a.output/'INDEPENDENT-ten-seed-chemical-summary.csv'),auditor_source_sha256=sha(__file__),utility_source_sha256=sha(Path(__file__).with_name('audit_training60_expanded_local_v4.py')))
 p=a.output/'SELECTED30-INDEPENDENT-AUDIT.actual.json';p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'status':report['status'],'checks':checks,'errors':errors,'report':str(p),'sha256':sha(p),'seconds':report['seconds']}));return bool(errors)

if __name__=='__main__':raise SystemExit(main())
