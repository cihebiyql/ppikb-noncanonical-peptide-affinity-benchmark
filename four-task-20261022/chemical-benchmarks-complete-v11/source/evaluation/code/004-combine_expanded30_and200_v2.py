"""Combine completed expanded685 raw-prediction audits with independently accepted200 heads; no NN."""
import argparse,csv,hashlib,json,math,pathlib,runpy,statistics,sys,datetime,collections
METRICS=['mae','rmse','pearson','spearman','r2','bias'];COHORT='93cdc000433e3c0babd7a5b7e183acd2fbe25649f4d2e7d5d95f5f0ad5aacae4';CSV='c3d8f4e42600f0c762bb9d2d24595a32c8f13de7a1f5018d59047d241dd8525a'
STRATA={'all':685,'standard20_control':572,'synthetic_D_backbone':45,'PTM':41,'synthetic_and_PTM':20,'other_NC':7,'NC_all':113,'PTM_bearing':61,'flagged':21,'unflagged':664}
FULL=['fullfine_hybrid','fullfine_mlm','fullfine_peptideclm2025'];REPS=['hybrid','mlm','morgan','peptideclm2025'];FAMS=['constant','ridge','random_forest','extra_trees','hist_gradient_boosting']
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(pathlib.Path(p).read_text(encoding='utf-8-sig'))
def rows(p):
 with pathlib.Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def num(s):return float(s) if s not in ['',None] else None
def dumpcsv(p,rr):
 with p.open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=list(rr[0]));w.writeheader();w.writerows(rr)
def summary(rr,groupcols):
 result=[]
 for key in sorted({tuple(r[k] for k in groupcols) for r in rr}):
  gg=[r for r in rr if tuple(r[k] for k in groupcols)==key];assert len(gg)==10 and {int(r['seed']) for r in gg}==set(range(10));q=dict(zip(groupcols,key));q.update(n=gg[0].get('n'),seeds=10)
  if 'all_groups' in gg[0]:q.update(all_groups=155)
  for m in METRICS:
   vv=[num(r[m]) for r in gg if num(r[m]) is not None];q[m+'_mean']=statistics.mean(vv) if vv else None;q[m+'_sampleSD']=statistics.stdev(vv) if len(vv)>1 else None;q[m+'_valid_seeds']=len(vv)
   if m+'_valid_groups' in gg[0]:q[m+'_valid_groups_min']=min(int(r[m+'_valid_groups']) for r in gg);q[m+'_valid_groups_max']=max(int(r[m+'_valid_groups']) for r in gg)
  result.append(q)
 return result

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--utility',required=True);ap.add_argument('--clm-audit',type=pathlib.Path);ap.add_argument('--2025-audit',dest='a2025',type=pathlib.Path);ap.add_argument('--full-audit',type=pathlib.Path);ap.add_argument('--head-audit',type=pathlib.Path,required=True);ap.add_argument('--protocol',type=pathlib.Path,required=True);ap.add_argument('--output',type=pathlib.Path,required=True);a=ap.parse_args();u=runpy.run_path(a.utility);job,proc=u['guard']();checks=[]
 def check(ok,msg):
  checks.append({'name':msg,'ok':bool(ok)})
  if not ok:raise ValueError(msg)
 check(not a.output.exists(),'new unique output only');a.output.mkdir()
 check(sha(a.protocol)=='6f8ab0b2ab614dedee66b069bd98b35d436deb8b2a7b55bebb0f26255c6dbb11','frozen comparison protocol')
 head=load(a.head_audit);check(sha(a.head_audit)=='5a37b96fc53dc823331a195fb7bd8a9cee3e5767a9580889d467ebaedb061efc' and head['valid'] is True,'accepted expanded200 only');check(head['model_cohort_manifest_sha256']==COHORT and head['cohort_csv_sha256']==CSV and head['test_dependency_groups']==155,'head cohort/groups')
 source_pins={str(a.head_audit):sha(a.head_audit),str(a.protocol):sha(a.protocol)};allrows=[];macrows=[]
 full_proofs=[(a.full_audit,30)] if a.full_audit else [(a.clm_audit,20),(a.a2025,10)]
 check(all(pp is not None for pp,count in full_proofs),'explicit accepted30 or20+10 raw-audit inputs')
 for pp,count in full_proofs:
  proof=load(pp);check(proof['status']=='passed' and proof['raw_selected_models_recomputed']==count and proof['test_n']==685 and proof['validation_n']==570 and proof['test_dependency_groups']==155 and proof['cohort_manifest_sha256']==COHORT and proof['cohort_csv_sha256']==CSV,'new fullfine raw predictions audited'+str(count));source_pins[str(pp)]=sha(pp)
  f=pp.parent/'INDEPENDENT-per-seed-chemical-metrics.csv';check(sha(f)==proof['per_seed_metrics_sha256'],'full raw derived metrics binding');source_pins[str(f)]=sha(f);allrows+=rows(f)
  f=pp.parent/'INDEPENDENT-TEST-group-macro-per-seed.csv';check(sha(f)==proof['test_group_macro_per_seed_sha256'],'full independent macro binding');source_pins[str(f)]=sha(f);long=rows(f)
  for meth,seed in sorted({(x['method'],int(x['seed'])) for x in long}):
   gm=[x for x in long if x['method']==meth and int(x['seed'])==seed];check(len(gm)==6 and {x['metric'] for x in gm}==set(METRICS),'all six full group macros');q={'kind':'full_encoder','method':meth,'seed':seed,'all_groups':155}
   for x in gm:check(int(x['all_groups'])==155,'all155 groups');q[x['metric']]=num(x['mean']);q[x['metric']+'_valid_groups']=int(x['valid_groups'])
   macrows.append(q)
 f=a.head_audit.parent/'HEAD-CHEMICAL-2000.actual.csv';check(sha(f)==head['metric_file_hashes'][f.name],'head2000 independent proof binding');source_pins[str(f)]=sha(f)
 for q in rows(f):allrows.append({'kind':'frozen_head','method':q['representation']+'__'+q['model'],'seed':int(q['seed']),'stratum':q['stratum'],'n':int(q['n']),**{m:num(q[m]) for m in METRICS}})
 f=a.head_audit.parent/'group-macro-per-seed.actual.csv';check(sha(f)==head['metric_file_hashes'][f.name],'head200 macro proof binding');source_pins[str(f)]=sha(f)
 for q in rows(f):check(int(q['groups'])==155,'head155 groups');macrows.append({'kind':'frozen_head','method':q['representation']+'__'+q['model'],'seed':int(q['seed']),'all_groups':155,**{m:num(q['group_macro_'+m]) for m in METRICS},**{m+'_valid_groups':int(q['group_valid_'+m]) for m in METRICS}})
 for r in allrows:
  r['seed']=int(r['seed']);r['n']=int(r['n'])
  for m in METRICS:r[m]=num(r[m])
 expectedmethods=set(FULL+[r+'__'+f for r in REPS for f in FAMS]);expectedkeys={(m,s,t) for m in expectedmethods for s in range(10) for t in STRATA};check(len(allrows)==2300 and {(r['method'],r['seed'],r['stratum']) for r in allrows}==expectedkeys,'exact23configs x10seeds x10strata')
 for r in allrows:check(r['n']==STRATA[r['stratum']] and all(r[m] is None or math.isfinite(r[m]) for m in METRICS),'correct chemistry denominator and finite defined metrics')
 check(len(macrows)==230 and {(r['method'],int(r['seed'])) for r in macrows}=={(m,s) for m in expectedmethods for s in range(10)},'exact230 per-seed group macros')
 allrows.sort(key=lambda r:(r['kind'],r['method'],r['stratum'],int(r['seed'])));macrows.sort(key=lambda r:(r['kind'],r['method'],int(r['seed'])));summ=summary(allrows,['kind','method','stratum']);ms=summary(macrows,['kind','method'])
 paired=[];idx={(r['method'],r['seed'],r['stratum']):r for r in allrows}
 for full in FULL:
  for family in FAMS:
   for t in STRATA:
    for seed in range(10):
     x=idx[(full,seed,t)];b=idx[('morgan__'+family,seed,t)];paired.append({'full_method':full,'Morgan_family':family,'seed':seed,'stratum':t,'n':STRATA[t],**{m:(x[m]-b[m]) if x[m] is not None and b[m] is not None else None for m in METRICS}})
 ps=summary(paired,['full_method','Morgan_family','stratum'])
 outputs={'COMBINED-2300-per-seed-metrics.actual.csv':allrows,'COMBINED-230-ten-seed-summary.actual.csv':summ,'COMBINED-GROUP-MACRO-230-per-seed.actual.csv':macrows,'COMBINED-GROUP-MACRO-23-ten-seed-summary.actual.csv':ms,'FULL-vs-ALL5-MORGAN-1500-paired-seed-differences.actual.csv':paired,'FULL-vs-ALL5-MORGAN-150-ten-seed-summary.actual.csv':ps}
 for name,rr in outputs.items():dumpcsv(a.output/name,rr)
 report={'schema':'expanded-v3.combined230.independent-audit.v1','at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'passed','checks':len(checks),'check_details':checks,'errors':[],'manifest_sha256':COHORT,'csv_sha256':CSV,'splits':{'train':531,'validation':570,'test':685,'external':0},'groups':155,'model_configurations':23,'model_seed_units':230,'fullfine30_models_fresh_raw_audited':30,'head200_models_prior_independent_proof_reused':200,'metric_counts':{k:len(v) for k,v in outputs.items()},'source_pins':source_pins,'metric_file_hashes':{name:sha(a.output/name) for name in outputs},'audit_source_sha256':sha(__file__),'process':proc,'reviewer_NN_forward_model_load_fit':0,'limitations':['No TEST-driven model selection; all five Morgan families reported, including matching ET comparisons.','Seed-paired differences represent computational repetition, not biological significance or independence.','2025 SPE/pooling adapted; two CLM2 variants represent one paper, three chemical models from two papers.','Fullfine parameter capacity, LR selection grid, feature dimensions and4/4/8GiB caps differ from frozen-head models.','Unknown foundation pretraining entity exposure and zero independent external-gold rows remain.','The expanded685 TEST retains the original656 TEST records and adds29; it is not an independent external validation of the prior benchmark.','Comparison protocol was frozen after expanded-head results were known; no preregistration before all TEST access is claimed.']}
 p=a.output/'COMPARISON-230-INDEPENDENT-AUDIT.actual.json';p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'status':'passed','checks':len(checks),'report':str(p),'sha256':sha(p),'outputs':report['metric_counts']}))
if __name__=='__main__':main()
