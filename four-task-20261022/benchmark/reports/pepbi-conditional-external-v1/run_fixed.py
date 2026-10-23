"""Apply only the 100 frozen selected sklearn1.9 models, preserving all 27 labels in float64."""
import os
import psutil
if os.environ.get('PEPBI_CPU_AFFINITY'):
    psutil.Process().cpu_affinity([int(x) for x in os.environ['PEPBI_CPU_AFFINITY'].split(',')])
    psutil.Process().nice(psutil.IDLE_PRIORITY_CLASS)
for key in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[key]='2'
os.environ['CUDA_VISIBLE_DEVICES']=''
import ast
from collections import Counter
import gc
import math
import time
import joblib
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
import sklearn
from threadpoolctl import threadpool_limits
from common import HERE,ROOT,DATA,RUN,sha,load,write,read,csvwrite

def metrics(y,p):
    y=np.asarray(y,dtype=np.float64);p=np.asarray(p,dtype=np.float64)
    corr=len(y)>=2 and np.ptp(y)>0 and np.ptp(p)>0
    result={'n':len(y),'mae':float(np.mean(np.abs(p-y))),'rmse':float(np.sqrt(np.mean((p-y)**2))),
        'bias':float(np.mean(p-y)),'r2':float(1-np.sum((y-p)**2)/np.sum((y-y.mean())**2)) if len(y)>=2 and np.ptp(y)>0 else None,
        'pearson':float(np.corrcoef(y,p)[0,1]) if corr else None,'spearman':float(spearmanr(y,p).statistic) if corr else None}
    assert all(v is None or math.isfinite(v) for v in result.values());return result

def main():
    started=time.monotonic();contract=load(HERE/'execution-contract.json')
    assert sklearn.__version__=='1.9.0'
    for item in contract['input_hashes']:assert sha(item['path'])==item['sha256'],item['path']
    frame=pd.read_csv(contract['candidate_csv'],keep_default_na=False,float_precision='round_trip')
    x=np.load(contract['feature_array'],allow_pickle=False);assert x.shape==(27,174) and np.isfinite(x).all()
    tree=ast.parse(open(contract['feature_code_path'],encoding='utf-8').read())
    names={'text_value','seq_features','is_contact','is_effect','build_features'}
    ns={'np':np,'math':math,'Counter':Counter,'AA':'ACDEFGHIKLMNPQRSTVWY','FEATURE_VERSION':'manual-aa20-raw-unknown-loglength-hashed-dipeptide64-v1'}
    ns['AA_INDEX']={a:i for i,a in enumerate(ns['AA'])}
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names];assert len(nodes)==5
    exec(compile(ast.Module(body=nodes,type_ignores=[]),contract['feature_code_path'],'exec'),ns)
    reference,audit=ns['build_features'](frame,'affinity');np.testing.assert_array_equal(reference,x)
    write(RUN/'feature-equality-receipt.json',{'passed':True,'shape':list(x.shape),'exact_prepared_feature_equality':True,
        'source_feature_sha256':contract['feature_code_sha256'],'new_fit_count':0,'model_prediction_count':0})
    allmetrics=[];groupmetrics=[];records=[]
    for item in contract['models']:
        if time.monotonic()-started>contract['timeout_seconds']-30:raise TimeoutError('bounded inference budget')
        assert sha(item['weight_path'])==item['sha256']
        estimator=joblib.load(item['weight_path'])
        with threadpool_limits(limits=2):pred=np.asarray(estimator.predict(x),dtype=np.float64)
        del estimator;gc.collect()
        assert pred.shape==(27,) and np.isfinite(pred).all()
        panel='source' if '_source_' in item['training_view'] else 'target'
        dest=RUN/panel/item['model']/f"s{item['seed']}";assert not dest.exists();dest.mkdir(parents=True)
        saved=frame.copy();saved['prediction']=pred
        saved.to_csv(dest/'predictions.csv',index=False,float_format='%.17g')
        y=frame.label.to_numpy(dtype=np.float64);micro=metrics(y,pred)
        macros={}
        for unit in contract['metric_groups']:
            values=[]
            for value,indices in frame.groupby(unit,sort=False).groups.items():
                indexes=np.asarray(indices);scores=metrics(y[indexes],pred[indexes]);values.append(scores)
                groupmetrics.append({'panel':panel,'model':item['model'],'seed':item['seed'],'unit':unit,'group':value,**scores})
            macros[unit]={'groups':len(values),'metrics':{key:{'mean':float(np.mean([r[key] for r in values if r[key] is not None])) if any(r[key] is not None for r in values) else None,
                'valid_groups':sum(r[key] is not None for r in values)} for key in micro if key!='n'}}
        result={'status':'succeeded','panel':panel,'model':item['model'],'seed':item['seed'],'rows':27,
            'weight_sha256':item['sha256'],'training_view':item['training_view'],'training_result_sha256':item['training_result_sha256'],
            'prediction_sha256':sha(dest/'predictions.csv'),'contract_sha256':sha(HERE/'execution-contract.json'),
            'micro':micro,'macro':macros,'new_fit_count':0,'tuning_count':0,'certified_independent_external_rows':0}
        write(dest/'result.json',result);records.append(result)
        for metric,value in micro.items():
            if metric!='n':allmetrics.append({'panel':panel,'model':item['model'],'seed':item['seed'],'averaging':'micro','metric':metric,'value':value,'n':27,'valid_groups':1})
        for unit,values in macros.items():
            for metric,value in values['metrics'].items():allmetrics.append({'panel':panel,'model':item['model'],'seed':item['seed'],'averaging':unit,'metric':metric,'value':value['mean'],'n':27,'valid_groups':value['valid_groups']})
        print(f"{panel} {item['model']} seed{item['seed']} completed",flush=True)
    csvwrite(RUN/'per-seed-metrics.csv',allmetrics);csvwrite(RUN/'per-group-per-seed.csv',groupmetrics)
    table=pd.DataFrame(allmetrics);summary=table.groupby(['panel','model','averaging','metric'],dropna=False).agg(mean=('value','mean'),sd=('value','std'),valid_seed_count=('value','count'),seed_count=('seed','nunique'),n=('n','first'),valid_groups=('valid_groups','first')).reset_index()
    summary.to_csv(RUN/'mean-sd-metrics.csv',index=False,float_format='%.17g')
    write(RUN/'execution-result.json',{'status':'succeeded','applications':len(records),'calculation_rows':len(records)*27,'unique_candidate_rows':27,
        'new_fit_count':0,'tuning_count':0,'gpu':False,'certified_independent_external_rows':0,
        'elapsed_seconds':time.monotonic()-started,'code_sha256':sha(__file__)})
if __name__=='__main__':main()
