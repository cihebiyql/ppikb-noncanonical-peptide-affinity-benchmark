"""Describe micro and component/complex macro metrics, preserving valid-denominator counts."""
import csv
import json
from pathlib import Path
import statistics

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];RUN=ROOT/'runs/plm-classification-contact-v1/heads'
rows=[];per_complex=[]
for path in sorted(RUN.glob('*/*/seed-*/result.json')):
    result=json.loads(path.read_text())
    for split,stored in result['splits'].items():
        for unit,key in [('component','macro'),('complex','per_complex_macro')]:
            data=stored.get(key)
            if data is None:continue
            for metric,item in data['metrics'].items():
                rows.append({'view_id':result['view_id'],'model':result['model'],'seed':result['seed'],'split':split,
                    'averaging_unit':unit,'metric':metric,'value':item['mean'],'valid_groups':item['valid_groups'],'all_groups':data['group_count']})
        complex_path=path.parent/f'{split}-complex-metrics.json'
        if complex_path.exists():
            for item in json.loads(complex_path.read_text()):
                per_complex.append({'view_id':result['view_id'],'model':result['model'],'seed':result['seed'],'split':split,**item})
def write(path,items):
    with path.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(items[0]));writer.writeheader();writer.writerows(items)
write(RUN/'macro-per-seed.csv',rows);write(RUN/'per-complex-per-seed.csv',per_complex)
grouped={}
for row in rows:grouped.setdefault(tuple(row[k] for k in ['view_id','model','split','averaging_unit','metric']),[]).append(row)
summary=[]
for key,values in grouped.items():
    finite=[r['value'] for r in values if r['value'] is not None]
    summary.append(dict(zip(['view_id','model','split','averaging_unit','metric'],key),
        mean=statistics.mean(finite) if finite else None,sd=statistics.stdev(finite) if len(finite)>1 else None,
        seed_count=len(values),valid_seed_count=len(finite),valid_groups=values[0]['valid_groups'],all_groups=values[0]['all_groups']))
write(RUN/'macro-mean-sd.csv',summary)
print(json.dumps({'macro_rows':len(rows),'per_complex_rows':len(per_complex),'new_fit_count':0,'new_forward_count':0}))
