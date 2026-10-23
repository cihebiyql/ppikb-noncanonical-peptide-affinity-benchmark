"""Independent float64 CSV-label, metric, grouping, ten-seed and original-byte audit; no model load."""
import math
import statistics
from common import HERE,ROOT,DATA,RUN,sha,load,write,read

def corr(y,p):
    if len(y)<2:return None
    a=statistics.mean(y);b=statistics.mean(p)
    dy=[v-a for v in y];dp=[v-b for v in p]
    den=math.sqrt(math.fsum(v*v for v in dy)*math.fsum(v*v for v in dp))
    return math.fsum(v*w for v,w in zip(dy,dp))/den if den else None
def ranks(values):
    ordered=sorted(range(len(values)),key=values.__getitem__);result=[0.]*len(values);start=0
    while start<len(values):
        end=start+1
        while end<len(values) and values[ordered[end]]==values[ordered[start]]:end+=1
        for i in ordered[start:end]:result[i]=(start+1+end)/2
        start=end
    return result
def metrics(y,p):
    n=len(y);mean=statistics.mean(y);ss=math.fsum((v-mean)**2 for v in y)
    err=[b-a for a,b in zip(y,p)];sq=math.fsum(v*v for v in err)
    valid=len(y)>=2 and max(y)>min(y) and max(p)>min(p)
    return {'n':n,'mae':math.fsum(abs(v) for v in err)/n,'rmse':math.sqrt(sq/n),'bias':math.fsum(err)/n,
        'r2':1-sq/ss if n>=2 and ss else None,'pearson':corr(y,p) if valid else None,
        'spearman':corr(ranks(y),ranks(p)) if valid else None}

def main():
    contract=load(HERE/'execution-contract.json');original=read(contract['candidate_csv'])
    ref={r['row_id']:r for r in original};assert len(ref)==27
    process=load(RUN/'process-receipt.json');assert process['exit_code']==0 and process['worker_pid_absent'] and not process['termination_reason']
    errors=[];checks=0;applications=0;predrows=0;expected_summary=[]
    def check(actual,expected,context):
        nonlocal checks
        checks+=1
        if (actual is None)!=(expected is None) or (actual is not None and abs(actual-expected)>1e-9):errors.append({'context':context,'actual':actual,'expected':expected})
    stored_summary=read(RUN/'mean-sd-metrics.csv')
    for item in contract['models']:
        panel='source' if '_source_' in item['training_view'] else 'target'
        directory=RUN/panel/item['model']/f"s{item['seed']}";result=load(directory/'result.json');path=directory/'predictions.csv'
        assert sha(path)==result['prediction_sha256'] and sha(item['weight_path'])==item['sha256']
        rows=read(path);assert [r['row_id'] for r in rows]==list(ref)
        assert len(rows)==27;applications+=1;predrows+=len(rows)
        for row in rows:
            primary=ref[row['row_id']]
            assert float(row['label'])==float(primary['label'])
            assert float(row['label'])==-math.log10(float(primary['original_Kd_M']))
            assert all(row[key]==primary[key] for key in ['endpoint','target_id','study_id','binding_group','raw_source_row_ids'])
        values=metrics([float(r['label']) for r in rows],[float(r['prediction']) for r in rows])
        for key,value in values.items():check(value,result['micro'][key],str(path)+':'+key)
        for metric,value in values.items():
            if metric!='n':expected_summary.append({'panel':panel,'model':item['model'],'seed':item['seed'],'averaging':'micro','metric':metric,'value':value})
        for unit in contract['metric_groups']:
            grouped={}
            for row in rows:grouped.setdefault(row[unit],[]).append(row)
            expected_group_count={'target_id':13,'study_id':4,'binding_group':5}[unit]
            assert len(grouped)==expected_group_count
            groupvalues=[metrics([float(r['label']) for r in group],[float(r['prediction']) for r in group]) for group in grouped.values()]
            check(len(grouped),result['macro'][unit]['groups'],str(path)+':groups:'+unit)
            for metric in values:
                if metric=='n':continue
                finite=[r[metric] for r in groupvalues if r[metric] is not None];mean=statistics.mean(finite) if finite else None
                check(mean,result['macro'][unit]['metrics'][metric]['mean'],str(path)+':'+unit+':'+metric)
                check(len(finite),result['macro'][unit]['metrics'][metric]['valid_groups'],str(path)+':valid:'+unit+':'+metric)
                expected_summary.append({'panel':panel,'model':item['model'],'seed':item['seed'],'averaging':unit,'metric':metric,'value':mean})
    for row in stored_summary:
        values=[r['value'] for r in expected_summary if all(str(r[k])==row[k] for k in ['panel','model','averaging','metric'])]
        assert len(values)==10
        finite=[v for v in values if v is not None]
        check(float(row['mean']) if row['mean'] else None,statistics.mean(finite) if finite else None,'summary-mean:'+str(row))
        check(float(row['sd']) if row['sd'] else None,statistics.stdev(finite) if len(finite)>1 else None,'summary-sd:'+str(row))
    for item in contract['input_hashes']:assert sha(item['path'])==item['sha256'],item['path']
    report={'passed':applications==100 and predrows==2700 and not errors,'applications':applications,'candidate_rows':27,
        'prediction_calculation_rows':predrows,'numeric_checks':checks,'errors':errors,'all_input_weight_and_original_result_hashes_unchanged':True,
        'labels_verified_against_original_csv_float64_and_Kd_M':True,'original_prepare_manifest_unchanged':True,
        'certified_independent_external_rows':0,'new_fit_count':0,'new_model_forward_count':0,
        'no_test_or_external_tuning':True,'code_sha256':sha(__file__)}
    write(RUN/'independent-recalculation.json',report);print({k:v for k,v in report.items() if k!='errors'});assert report['passed']
if __name__=='__main__':main()
