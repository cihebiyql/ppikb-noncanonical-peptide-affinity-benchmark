"""Post-hoc metrics with exact constant detection; frozen trainer remains unchanged."""
import numpy as np
from scipy.stats import rankdata

def _finite(value):
    value=float(value)
    return value if np.isfinite(value) else None

def _unit_centered(values):
    scale=float(np.max(np.abs(values)))
    normalized=values/scale if scale else values.copy()
    centered=normalized-normalized[0]
    centered=centered-centered.mean()
    norm=float(np.linalg.norm(centered))
    return centered/norm if norm>0 and np.isfinite(norm) else None

def numeric_metrics(true,pred):
    y=np.asarray(true,dtype=np.float64).reshape(-1)
    p=np.asarray(pred,dtype=np.float64).reshape(-1)
    if y.shape!=p.shape or not np.isfinite(y).all() or not np.isfinite(p).all():
        raise ValueError('Mismatched or nonfinite metric inputs')
    result=dict(n=len(y),MAE=None,RMSE=None,Pearson=None,Spearman=None,R2=None)
    if not len(y):return result
    # Exact equality is decisive. np.var([0.1]*3) can be positive from rounding.
    y_constant=bool(np.all(y==y[0]));p_constant=bool(np.all(p==p[0]))
    with np.errstate(all='ignore'):
        error=p-y
        # Preserve the frozen trainer's MAE/RMSE formulas; only the independent
        # post-hoc undefined-correlation/R2 handling is corrected here.
        result['MAE']=_finite(np.mean(np.abs(error)))
        result['RMSE']=_finite(np.sqrt(np.mean(error*error)))
        if len(y)>1 and not y_constant:
            scale=float(np.max(np.abs(y)))
            yn=y/scale;pn=p/scale
            centered=yn-yn[0];centered=centered-centered.mean()
            denominator=float(np.sum(centered*centered))
            if denominator>0:result['R2']=_finite(1-np.sum((pn-yn)**2)/denominator)
        if len(y)>1 and not y_constant and not p_constant:
            yu=_unit_centered(y);pu=_unit_centered(p)
            if yu is not None and pu is not None:result['Pearson']=_finite(np.clip(np.dot(yu,pu),-1,1))
            yr=_unit_centered(rankdata(y));pr=_unit_centered(rankdata(p))
            if yr is not None and pr is not None:result['Spearman']=_finite(np.clip(np.dot(yr,pr),-1,1))
    return result

def grouped_metrics(rows,values):
    def compute(indices):return numeric_metrics([rows[i]['pKd'] for i in indices],[values[i] for i in indices])
    result={'all':compute(range(len(rows)))}
    strata=sorted({str(row.get('evaluation_stratum','unknown')) for row in rows})
    for stratum in strata:
        result[stratum]=compute([i for i,row in enumerate(rows) if str(row.get('evaluation_stratum','unknown'))==stratum])
    for name,desired in [('NC_core',True),('standard',False)]:
        result[name]=compute([i for i,row in enumerate(rows) if row.get('NC_core') is desired])
    clean=[i for i,row in enumerate(rows) if not any(value is True for key,value in row.items() if 'discord' in key.lower())]
    result['exclude_discordant_sensitivity']=compute(clean)
    for stratum in strata:
        result['exclude_discordant:'+stratum]=compute([i for i in clean if str(rows[i].get('evaluation_stratum','unknown'))==stratum])
    return result
