"""Independent CSV64 metric and candidate-selection checks; no fitting or forward."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def ranks(values):
    order=sorted(range(len(values)),key=values.__getitem__);out=[0.]*len(values);i=0
    while i<len(order):
        j=i+1
        while j<len(order) and values[order[j]]==values[order[i]]:j+=1
        rank=(i+1+j)/2
        for k in range(i,j):out[order[k]]=rank
        i=j
    return out
def corr(y,p):
    if len(y)<2 or max(y)==min(y) or max(p)==min(p):return None
    a,b=statistics.mean(y),statistics.mean(p)
    return math.fsum((v-a)*(w-b) for v,w in zip(y,p))/math.sqrt(math.fsum((v-a)**2 for v in y)*math.fsum((w-b)**2 for w in p))
def metrics(y,p,effect):
    n=len(y);sse=math.fsum((a-b)**2 for a,b in zip(y,p));mean=statistics.mean(y)
    out={'mae':math.fsum(abs(a-b) for a,b in zip(y,p))/n,'rmse':math.sqrt(sse/n),
         'bias':math.fsum(b-a for a,b in zip(y,p))/n,'pearson':corr(y,p),'spearman':corr(ranks(y),ranks(p)),
         'r2':1-sse/math.fsum((a-mean)**2 for a in y) if n>1 and max(y)>min(y) else None}
    if effect:
        nonzero=[i for i,v in enumerate(y) if v!=0]
        sign=lambda x:(x>0)-(x<0)
        out['direction_accuracy_nonzero']=sum(sign(y[i])==sign(p[i]) for i in nonzero)/len(nonzero) if nonzero else None
        out['nonzero_effect_n']=len(nonzero)
    return out
def read(path):
    with path.open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
def main():
    parser=argparse.ArgumentParser();parser.add_argument('root',type=Path);args=parser.parse_args()
    errors=[];count=0;files=[];selected=0;candidate_count=0
    here=Path(__file__).resolve().parent
    manifest=json.loads((here/'coverage-manifest.json').read_text(encoding='utf-8'))
    references={}
    for view in manifest['views']:
        path=Path(view['path'])
        if not path.exists():path=here/'inputs'/(view['id']+'.csv')
        if sha(path)!=view['sha256']:errors.append({'frozen_view_hash':str(path)})
        references[view['id']]={row['row_id']:row for row in read(path)}
    def check(got,wanted,context):
        nonlocal count
        count+=1
        if (got is None)!=(wanted is None) or (got is not None and abs(got-wanted)>1e-9):errors.append({'context':context,'actual':got,'expected':wanted})
    for result_path in sorted(args.root.glob('*/*/seed-*/result.json')):
        obj=json.loads(result_path.read_text());selected+=1;run=result_path.parent
        choices=json.loads((run/'candidates.json').read_text());candidate_count+=len(choices)
        for candidate in choices:
            index=candidate['candidate'];path=run/f'candidate-{index}-validation.csv'
            records=read(path);values=metrics([float(r['label']) for r in records],[float(r['prediction']) for r in records],obj['task']=='effect')
            for metric,value in values.items():check(value,candidate['validation_metrics'][metric],f'{path}:{metric}')
            check(-values['mae'],candidate['selection_objective'],f'{path}:selection')
            if sha(run/f'candidate-{index}.joblib')!=candidate['model_sha256']:errors.append({'model_hash':str(path)})
        winner=max(choices,key=lambda c:c['selection_objective'])['candidate']
        check(winner,obj['selected_candidate'],f'{result_path}:winner')
        for split,stored in obj['splits'].items():
            path=run/f'{split}-predictions.csv'
            if sha(path)!=stored['prediction_sha256']:errors.append({'prediction_hash':str(path)})
            records=read(path);y=[float(r['label']) for r in records];p=[float(r['prediction']) for r in records]
            reference=references[obj['view_id']]
            expected_ids={key for key,row in reference.items() if row['split']==split}
            if {row['row_id'] for row in records}!=expected_ids:errors.append({'test_coverage':str(path)})
            for row in records:
                ref=reference[row['row_id']]
                if float(row['label'])!=float(ref['label']) or row['split']!=ref['split']:
                    errors.append({'label_or_split_changed':row['row_id'],'path':str(path)})
            actual=metrics(y,p,obj['task']=='effect')
            check(len(records),stored['metrics']['n'],str(path)+':n')
            for metric,value in actual.items():check(value,stored['metrics'][metric],f'{path}:{metric}')
            # Validate grouped and chemistry metrics using independent stdlib math.
            groups={}
            for row in records:groups.setdefault(row['group_id'],[]).append(row)
            stored_groups={str(row['group_id']):row for row in json.loads((run/f'{split}-group-metrics.json').read_text())}
            grouped_values=[]
            for key,group_rows in groups.items():
                gm=metrics([float(r['label']) for r in group_rows],[float(r['prediction']) for r in group_rows],obj['task']=='effect')
                grouped_values.append(gm)
                for metric,value in gm.items():check(value,stored_groups[key][metric],f'{path}:group:{key}:{metric}')
            for metric,value in stored['macro']['metrics'].items():
                valid=[row[metric] for row in grouped_values if row.get(metric) is not None]
                check(statistics.mean(valid) if valid else None,value['mean'],f'{path}:macro:{metric}')
                check(len(valid),value['valid_groups'],f'{path}:macro:{metric}:n')
            for column,subgroups in stored.get('subgroups',{}).items():
                for subgroup in subgroups:
                    subset=[r for r in records if r.get(column)==str(subgroup['value'])]
                    sm=metrics([float(r['label']) for r in subset],[float(r['prediction']) for r in subset],obj['task']=='effect')
                    for metric,value in sm.items():check(value,subgroup[metric],f'{path}:{column}:{subgroup["value"]}:{metric}')
            files.append({'path':str(path),'sha256':sha(path),'rows':len(records)})
    report={'schema':'frozen-esm2.independent-scoring.v1','selected_runs':selected,'candidate_fits':candidate_count,
            'prediction_files':len(files),'metric_cells':count,'errors':errors,'passed':selected==150 and candidate_count==300 and not errors,
            'new_fit_count':0,'new_forward_count':0,'code_sha256':sha(__file__),'files':files}
    (args.root/'independent-recalculation.local-v1.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='files'}));return 0 if report['passed'] else 2
if __name__=='__main__':raise SystemExit(main())
