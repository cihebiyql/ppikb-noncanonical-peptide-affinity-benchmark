"""Independent NumPy/SciPy/sklearn recalculation of all descriptive paired outputs."""
import csv
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import rankdata
from sklearn.metrics import r2_score
from verify_manual_controls import sha

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
OUT=ROOT/'runs/plm-cohort-manual-controls-v1/paired-with-esm'

def metric_values(y,p,effect):
    if not len(y):
        return {k:None for k in ['mae','rmse','bias','r2','pearson','spearman']+(['direction_accuracy_nonzero'] if effect else [])}
    variable=len(y)>1 and np.ptp(y)>0 and np.ptp(p)>0
    result={'mae':float(np.mean(np.abs(p-y))),'rmse':float(np.sqrt(np.mean((p-y)**2))),
            'bias':float(np.mean(p-y)),
            'r2':float(r2_score(y,p)) if len(y)>1 and np.ptp(y)>0 else None,
            'pearson':float(np.corrcoef(y,p)[0,1]) if variable else None,
            'spearman':float(np.corrcoef(rankdata(y),rankdata(p))[0,1]) if variable else None}
    if effect:
        nonzero=y!=0;result['direction_accuracy_nonzero']=float(np.mean(np.sign(y[nonzero])==np.sign(p[nonzero]))) if nonzero.any() else None
    return result
def subsets(frame):
    values=frame.evaluation_stratum
    out={'all':frame,'NC_any_including_PTM':frame[values!='standard20_control'],
        'PTM_any_including_mixed':frame[values.isin(['PTM','synthetic_and_PTM'])],
        'synthetic_D_any_including_mixed':frame[values.isin(['synthetic_D_backbone','synthetic_and_PTM'])]}
    for value in ['standard20_control','PTM','synthetic_D_backbone','synthetic_and_PTM','other_NC']:
        out[value]=frame[values==value]
    return out
def numeric(value):
    if value is None or value=='':return None
    return float(value)
def main():
    receipt=json.loads((OUT/'comparison-receipt.json').read_text())
    with (OUT/'per-seed-paired-metrics.csv').open(encoding='utf-8') as stream:
        rows=list(csv.DictReader(stream))
    indexed={(r['view_id'],r['model'],int(r['seed']),r['stratum'],r['metric']):r for r in rows}
    assert len(indexed)==len(rows)
    errors=[];cells=0
    def check(actual,wanted,context):
        nonlocal cells
        cells+=1;wanted=numeric(wanted)
        if (actual is None)!=(wanted is None) or (actual is not None and abs(actual-wanted)>1e-9):
            errors.append({'context':context,'actual':actual,'wanted':wanted})
    for pair in receipt['pairs']:
        path=OUT/pair['view_id']/pair['model']/f'seed-{pair["seed"]:02d}'/'paired-test-predictions.csv'
        assert sha(path)==pair['paired_prediction_sha256']
        frame=pd.read_csv(path,float_precision='round_trip')
        assert len(frame)==pair['n'] and frame.row_id.is_unique
        np.testing.assert_allclose(frame.manual_abs_error,np.abs(frame.manual_prediction-frame.label),rtol=0,atol=1e-12)
        np.testing.assert_allclose(frame.esm_abs_error,np.abs(frame.esm_prediction-frame.label),rtol=0,atol=1e-12)
        np.testing.assert_allclose(frame.delta_abs_error_manual_minus_ESM,frame.manual_abs_error-frame.esm_abs_error,rtol=0,atol=1e-12)
        for stratum,group in subsets(frame).items():
            y=group.label.to_numpy();effect='effect' in pair['view_id']
            manual=metric_values(y,group.manual_prediction.to_numpy(),effect)
            esm=metric_values(y,group.esm_prediction.to_numpy(),effect)
            for metric,mvalue in manual.items():
                key=(pair['view_id'],pair['model'],pair['seed'],stratum,metric);expected=indexed[key]
                check(len(group),expected['n'],str(key)+':n')
                check(mvalue,expected['manual'],str(key)+':manual');check(esm[metric],expected['esm'],str(key)+':esm')
                delta=mvalue-esm[metric] if mvalue is not None and esm[metric] is not None else None
                check(delta,expected['delta_manual_minus_ESM'],str(key)+':delta')
    with (OUT/'paired-mean-sd.csv').open(encoding='utf-8') as stream:
        summary=list(csv.DictReader(stream))
    for row in summary:
        members=[r for r in rows if all(r[k]==row[k] for k in ['view_id','model','stratum','metric'])]
        assert len(members)==10
        for source in ['manual','esm','delta_manual_minus_ESM']:
            values=[numeric(r[source]) for r in members if numeric(r[source]) is not None]
            check(float(np.mean(values)) if values else None,row[source+'_mean'],str(row)+':mean:'+source)
            check(float(np.std(values,ddof=1)) if len(values)>1 else None,row[source+'_sd'],str(row)+':sd:'+source)
            check(len(values),row[source+'_valid_seed_count'],str(row)+':valid:'+source)
    report={'passed':len(receipt['pairs'])==150 and not errors,'paired_runs':len(receipt['pairs']),
        'numeric_checks':cells,'errors':errors,'new_fit_count':0,'new_forward_count':0,'p_values_computed':0,'code_sha256':sha(__file__)}
    (OUT/'independent-recalculation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report));assert report['passed']
if __name__=='__main__':main()
