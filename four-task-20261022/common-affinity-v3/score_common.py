"""Score frozen saved predictions on exact683/946 IDs; no model or feature imports."""
from collections import defaultdict
import itertools
import math
import statistics
import numpy as np
from scipy.stats import spearmanr
from prepare_catalog import HERE,ROOT,load,read,dump,sha

FIELDS=['mae','rmse','bias','r2','pearson','spearman']
STRATA=['all','standard20_control','synthetic_D_backbone','PTM','synthetic_and_PTM','other_NC','NC_all','PTM_bearing']
def metrics(y,p):
    if not y:return {'n':0,**{k:None for k in FIELDS}}
    a=np.asarray(y,dtype=np.float64);b=np.asarray(p,dtype=np.float64);delta=b-a
    varying=len(a)>1 and np.ptp(a)>0 and np.ptp(b)>0
    return {'n':len(a),'mae':float(np.mean(np.abs(delta))),'rmse':float(np.sqrt(np.mean(delta**2))),
        'bias':float(np.mean(delta)),'r2':float(1-np.sum(delta**2)/np.sum((a-a.mean())**2)) if len(a)>1 and np.ptp(a)>0 else None,
        'pearson':float(np.corrcoef(a,b)[0,1]) if varying else None,'spearman':float(spearmanr(a,b).statistic) if varying else None}
def selected(path,fmt):
    if fmt=='jsonl':return [__import__('json').loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    return read(path)
def csvwrite(path,rows):
    import csv
    with path.open('w',encoding='utf-8',newline='') as f:
        out=csv.DictWriter(f,fieldnames=list(rows[0]));out.writeheader();out.writerows(rows)
def main():
    assert not (HERE/'score-receipt.json').exists()
    contract=load(HERE/'comparison-contract.json');coverage=[];values=[];provenance=[];method_sources=defaultdict(list)
    for item in contract['prediction_sources']:method_sources[item['panel'],item['method']].append(item)
    for (panel,method),items in method_sources.items():
        canonical=contract['canonical'][panel];ref=canonical['label_float64_by_row_id'];strata=canonical['strata_by_row_id']
        outcomes=[]
        for item in sorted(items,key=lambda r:r['seed']):
            path=__import__('pathlib').Path(item['path']);assert sha(path)==item['sha256']
            rows=selected(path,item['format']);byid={r.get('row_id',r.get('record_id')):r for r in rows};assert len(byid)==len(rows)
            common=set(ref)&set(byid);mismatch=[]
            for key in common:
                row=byid[key]
                if float(row['label'])!=ref[key] or row.get('endpoint')!='pKd':mismatch.append(key)
                assert math.isfinite(float(row['prediction']))
                if 'evaluation_stratum' in row:assert row['evaluation_stratum']==strata[key]
                if 'split' in row:assert row['split']=='test'
            assert not mismatch
            outcomes.append((item,byid,len(common)))
        eligible=len(outcomes)==10 and {r[0]['seed'] for r in outcomes}==set(range(10)) and all(r[2]==canonical['n'] for r in outcomes)
        if items[0]['family']=='coverage_only':assert not eligible
        coverage.append({'panel':panel,'method':method,'family':items[0]['family'],'available_seeds':len(outcomes),'canonical_test_n':canonical['n'],
            'minimum_ID_coverage':min(r[2] for r in outcomes),'maximum_ID_coverage':max(r[2] for r in outcomes),'eligible_full_fixed_cohort':eligible,
            'reason':'complete10seeds/exactIDs/float64labels/pKd' if eligible else 'incomplete_fixedIDcoverage; no new intersection or metrics on smaller set'})
        if not eligible:continue
        for item,byid,_ in outcomes:
            ordered=canonical['row_ids'];y=[ref[k] for k in ordered];p=[float(byid[k]['prediction']) for k in ordered]
            subset_fingerprint=__import__('hashlib').sha256(__import__('json').dumps(list(zip(ordered,y,p)),separators=(',',':'),allow_nan=False).encode()).hexdigest()
            provenance.append({'panel':panel,'method':method,'family':item['family'],'seed':item['seed'],'source_path':item['path'],
                'source_SHA256':item['sha256'],'canonical_SHA256':canonical['sha256'],'fixed_test_n':canonical['n'],
                'selected_original_prediction_rows_sha256':subset_fingerprint,'endpoint':'pKd','raw_labels_exact_canonical_float64':True,
                'training_scope':item['training_scope'],'protocol_note':item.get('protocol_note')})
            for stratum in STRATA:
                if stratum=='all':indices=list(range(len(ordered)))
                elif stratum=='NC_all':indices=[i for i,k in enumerate(ordered) if strata[k]!='standard20_control']
                elif stratum=='PTM_bearing':indices=[i for i,k in enumerate(ordered) if strata[k] in {'PTM','synthetic_and_PTM'}]
                else:indices=[i for i,k in enumerate(ordered) if strata[k]==stratum]
                current=metrics([y[i] for i in indices],[p[i] for i in indices])
                values.append({'panel':panel,'method':method,'family':item['family'],'seed':item['seed'],'stratum':stratum,'endpoint':'pKd',**current})
    assert len(provenance)==540 and sum(r['eligible_full_fixed_cohort'] for r in coverage)==54
    groups=defaultdict(list)
    for row in values:groups[row['panel'],row['method'],row['family'],row['stratum']].append(row)
    summary=[]
    for (panel,method,family,stratum),rows in sorted(groups.items()):
        assert len(rows)==10 and {r['seed'] for r in rows}==set(range(10)) and len({r['n'] for r in rows})==1
        result={'panel':panel,'method':method,'family':family,'stratum':stratum,'endpoint':'pKd','n':rows[0]['n'],'seeds':10}
        for metric in FIELDS:
            finite=[r[metric] for r in rows if r[metric] is not None]
            result.update({metric+'_mean':statistics.mean(finite) if finite else None,metric+'_sampleSD':statistics.stdev(finite) if len(finite)>1 else None,metric+'_valid_seeds':len(finite)})
        summary.append(result)
    paired=[];paired_summary=[]
    index={(r['panel'],r['method'],r['seed']):r['mae'] for r in values if r['stratum']=='all'}
    for panel in ['source','target']:
        methods=sorted({r['method'] for r in coverage if r['panel']==panel and r['eligible_full_fixed_cohort']})
        assert len(methods)==27
        for a,b in itertools.combinations(methods,2):
            differences=[]
            for seed in range(10):
                d=index[panel,a,seed]-index[panel,b,seed];differences.append(d)
                paired.append({'panel':panel,'method_A':a,'method_B':b,'seed':seed,'MAE_A_minus_B':d,'fixed_test_n':contract['canonical'][panel]['n']})
            paired_summary.append({'panel':panel,'method_A':a,'method_B':b,'seeds':10,'MAE_A_minus_B_mean':statistics.mean(differences),
                'MAE_A_minus_B_sampleSD':statistics.stdev(differences),'interpretation':'same-fixed-test computational seed comparison; no significance/biological CI'})
    csvwrite(HERE/'per-seed-metrics.csv',values);csvwrite(HERE/'ten-seed-mean-sampleSD.csv',summary)
    csvwrite(HERE/'paired-seed-MAE-differences.csv',paired);csvwrite(HERE/'paired-seed-MAE-summary.csv',paired_summary)
    csvwrite(HERE/'coverage.csv',coverage);dump(HERE/'prediction-provenance.json',provenance)
    for item in contract['prediction_sources']:assert sha(item['path'])==item['sha256']
    for item in contract['source_locks']:assert sha(item['path'])==item['sha256']
    dump(HERE/'score-receipt.json',{'status':'completed_saved_prediction_scoring_only','method_panel_conditions':54,'eligible_fixed_applications':540,
        'source_methods':27,'target_methods':27,'canonical_test_n':{'source':683,'target':946},'per_seed_stratum_rows':len(values),
        'ten_seed_summary_rows':len(summary),'paired_computational_seed_rows':len(paired),'paired_method_summary_rows':len(paired_summary),
        'incomplete_coverage_conditions':sum(not r['eligible_full_fixed_cohort'] for r in coverage),'no_new_intersection':True,
        'input_and_original_prediction_SHA_unchanged':True,'training_not_equalized':True,'original_generic1050_unchanged':True,
        'comparison_contract_sha256':sha(HERE/'comparison-contract.json'),'new_fit_count':0,'new_forward_count':0,'model_objects_loaded':0,
        'gpu_jobs':0,'p_values_computed':0,'code_sha256':sha(__file__)})
    print({'eligible_applications':540,'methods_per_panel':27,'metric_rows':len(values),'paired_rows':len(paired),'new_fit_or_forward':0})
if __name__=='__main__':main()
