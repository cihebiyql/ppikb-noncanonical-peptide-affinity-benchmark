"""Independent stdlib re-score and original-result comparison, never model/feature execution."""
from collections import defaultdict
import math
import statistics
from pathlib import Path
from prepare_catalog import HERE,ROOT,load,read,sha,dump

METRICS=['mae','rmse','bias','r2','pearson','spearman']
def num(value):return None if value is None or str(value)=='' else float(value)
def corr(y,p):
    a=statistics.mean(y);b=statistics.mean(p);dy=[v-a for v in y];dp=[v-b for v in p]
    d=math.sqrt(math.fsum(v*v for v in dy)*math.fsum(v*v for v in dp))
    return math.fsum(a*b for a,b in zip(dy,dp))/d if d else None
def ranks(values):
    order=sorted(range(len(values)),key=values.__getitem__);out=[0.]*len(values);start=0
    while start<len(order):
        end=start+1
        while end<len(order) and values[order[end]]==values[order[start]]:end+=1
        for index in order[start:end]:out[index]=(start+1+end)/2
        start=end
    return out
def metrics(y,p):
    if not y:return {'n':0,**{k:None for k in METRICS}}
    n=len(y);d=[b-a for a,b in zip(y,p)];squares=math.fsum(v*v for v in d);average=statistics.mean(y);den=math.fsum((v-average)**2 for v in y)
    varying=n>1 and max(y)>min(y) and max(p)>min(p)
    return {'n':n,'mae':math.fsum(abs(v) for v in d)/n,'rmse':math.sqrt(squares/n),'bias':math.fsum(d)/n,
        'r2':1-squares/den if n>1 and den else None,'pearson':corr(y,p) if varying else None,'spearman':corr(ranks(y),ranks(p)) if varying else None}
def main():
    contract=load(HERE/'comparison-contract.json');computed=read(HERE/'per-seed-metrics.csv');summary=read(HERE/'ten-seed-mean-sampleSD.csv')
    index={(r['panel'],r['method'],int(r['seed']),r['stratum']):r for r in computed};assert len(index)==4320
    errors=[];checks=0;rows=0;maxdiff=0.;independent_all={}
    def check(actual,expected,context):
        nonlocal checks,maxdiff
        checks+=1;a=num(actual)
        if (a is None)!=(expected is None):errors.append({'context':context,'actual':a,'expected':expected})
        elif a is not None:
            delta=abs(a-expected);maxdiff=max(maxdiff,delta)
            if delta>1e-9:errors.append({'context':context,'actual':a,'expected':expected,'delta':delta})
    provenance=load(HERE/'prediction-provenance.json');assert len(provenance)==540
    for item in provenance:
        panel=item['panel'];canonical=contract['canonical'][panel];ref=canonical['label_float64_by_row_id'];strata=canonical['strata_by_row_id']
        source=next(r for r in contract['prediction_sources'] if (r['panel'],r['method'],r['seed'])==(panel,item['method'],item['seed']))
        path=Path(item['source_path']);assert sha(path)==item['source_SHA256']
        if source['format']=='jsonl':raw=[__import__('json').loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
        else:raw=read(path)
        byid={r.get('row_id',r.get('record_id')):r for r in raw}
        ids=canonical['row_ids'];assert set(ids)<=set(byid)
        for key in ids:
            assert float(byid[key]['label'])==ref[key] and byid[key]['endpoint']=='pKd';rows+=1
        for stratum in ['all','standard20_control','synthetic_D_backbone','PTM','synthetic_and_PTM','other_NC','NC_all','PTM_bearing']:
            chosen=ids if stratum=='all' else [k for k in ids if (strata[k]!='standard20_control' if stratum=='NC_all' else strata[k] in {'PTM','synthetic_and_PTM'} if stratum=='PTM_bearing' else strata[k]==stratum)]
            values=metrics([ref[k] for k in chosen],[float(byid[k]['prediction']) for k in chosen])
            record=index[panel,item['method'],item['seed'],stratum]
            for metric,value in values.items():check(record[metric],value,str((panel,item['method'],item['seed'],stratum,metric)))
            if stratum=='all':independent_all[panel,item['method'],item['seed']]=values
    for record in summary:
        local=[r for key,r in index.items() if (r['panel'],r['method'],r['stratum'])==(record['panel'],record['method'],record['stratum'])]
        assert len(local)==10 and {int(r['seed']) for r in local}==set(range(10))
        for metric in METRICS:
            finite=[num(r[metric]) for r in local if num(r[metric]) is not None]
            for field,value in [('mean',statistics.mean(finite) if finite else None),('sampleSD',statistics.stdev(finite) if len(finite)>1 else None),('valid_seeds',len(finite))]:
                check(record[metric+'_'+field],value,str((record['panel'],record['method'],record['stratum'],metric,field)))
    for record in read(HERE/'paired-seed-MAE-differences.csv'):
        panel=record['panel'];seed=int(record['seed']);expected=independent_all[panel,record['method_A'],seed]['mae']-independent_all[panel,record['method_B'],seed]['mae']
        check(record['MAE_A_minus_B'],expected,str(('paired',panel,record['method_A'],record['method_B'],seed)))
    paired=read(HERE/'paired-seed-MAE-differences.csv')
    for record in read(HERE/'paired-seed-MAE-summary.csv'):
        values=[float(r['MAE_A_minus_B']) for r in paired if (r['panel'],r['method_A'],r['method_B'])==(record['panel'],record['method_A'],record['method_B'])]
        assert len(values)==10
        check(record['MAE_A_minus_B_mean'],statistics.mean(values),'paired_mean');check(record['MAE_A_minus_B_sampleSD'],statistics.stdev(values),'paired_SD')
    # Cross-check the already published fixed-common scores, independent of new scoring.
    existing_checks=0
    old=read(ROOT/'runs/common-prediction-comparison-v2/per-seed-metrics.csv')
    for r in old:
        if not r['cohort'].startswith('backbone6336__') or r['stratum']!='all' or r['main_ranking_eligible']!='True':continue
        method=r['method'];mapped=None
        if method.startswith('sequence__'):mapped=method.replace('sequence__','manual_sequence__',1)
        elif method.startswith('morgan__'):mapped=method.replace('morgan__','chiral_Morgan__',1)
        elif method=='PepInter_backbone_ablation_native_head':mapped='PepInter_backbone_native_head'
        if mapped is None:continue
        current=independent_all[r['panel'],mapped,int(r['seed'])]
        for metric in ['n',*METRICS]:check(r[metric],current[metric],'existing_old_common:'+str((r['panel'],method,r['seed'],metric)));existing_checks+=1
    for r in read(ROOT/'runs/plm-simple-v1/common-prediction-comparison/esm2-per-seed-metrics.csv'):
        if not r['cohort'].startswith('backbone6336__') or r['stratum']!='all':continue
        current=independent_all[r['panel'],r['method'].replace('esm2__','frozen_ESM2_8M__',1),int(r['seed'])]
        check(r['value'],current[r['metric']],'existing_ESM_common');existing_checks+=1
    for r in read(ROOT/'reports/dta-pepinter-common-fixed-v1/per-seed-metrics.csv'):
        if r['chemical_group']!='all':continue
        current=independent_all[r['panel'],'DTA__'+r['method'],int(r['seed'])]
        for original,metric in [('n','n'),('MAE','mae'),('RMSE','rmse'),('R2','r2'),('Pearson','pearson'),('Spearman','spearman')]:check(r[original],current[metric],'existing_DTA_common');existing_checks+=1
    for r in read(ROOT/'methods/interaction/continuation-20261023/swing-affinity/affinity-all-per-seed.csv'):
        if r['cohort']!='common_PepInter_native6336_test':continue
        current=independent_all[r['panel'],'SWING_Doc2Vec_XGBRegressor',int(r['seed'])]
        for metric in ['n',*METRICS]:check(r[metric],current[metric],'existing_SWING_common');existing_checks+=1
    for item in contract['prediction_sources']:assert sha(item['path'])==item['sha256']
    for item in contract['source_locks']:assert sha(item['path'])==item['sha256']
    audit={'passed':not errors,'fixed_applications':540,'methods_per_panel':27,'per_seed_stratum_rows':4320,
        'exact_rowID_label_endpoint_checks':rows,'numeric_checks':checks,'existing_fixed_score_numeric_checks':existing_checks,
        'maximum_absolute_numeric_difference':maxdiff,'absolute_tolerance':1e-9,'errors':errors,
        'all_original_input_and_prediction_SHA_unchanged':True,'generic1050_and_SHA_unchanged':True,
        'no_dynamic_intersection':True,'no_new_fit_or_forward':True,'model_objects_loaded':0,'gpu_jobs':0,
        'p_values_reported_or_used':0,'code_sha256':sha(__file__)}
    dump(HERE/'independent-audit.json',audit);print({k:v for k,v in audit.items() if k!='errors'});assert audit['passed']
if __name__=='__main__':main()
