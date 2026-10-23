"""Independent tie-aware binary metrics, validation thresholds, selection and group/complex audit."""
import argparse
import bisect
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024**2),b''):h.update(b)
    return h.hexdigest()
def read(path):
    with Path(path).open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
def scores(y,p,threshold):
    n=len(y);positive=sum(y);negative=n-positive;two=positive>0 and negative>0
    pred=[value>=threshold for value in p]
    tp=sum(v==1 and q for v,q in zip(y,pred));fp=sum(v==0 and q for v,q in zip(y,pred))
    fn=positive-tp;tn=negative-fp;denom=(tp+fp)*(tp+fn)*(tn+fp)*(tn+fn)
    auroc=ap=None
    if two:
        ordered=sorted(zip(p,y));ranksum=0.;start=0
        while start<n:
            end=start+1
            while end<n and ordered[end][0]==ordered[start][0]:end+=1
            ranksum+=((start+1+end)/2)*sum(v for _,v in ordered[start:end]);start=end
        auroc=(ranksum-positive*(positive+1)/2)/(positive*negative)
        ordered=list(reversed(ordered));start=0;tp_seen=0;seen=0;parts=[]
        while start<n:
            end=start+1
            while end<n and ordered[end][0]==ordered[start][0]:end+=1
            pos=sum(v for _,v in ordered[start:end]);tp_seen+=pos;seen+=end-start
            parts.append((pos/positive)*(tp_seen/seen));start=end
        ap=math.fsum(parts)
    return {'n':n,'positive_count':positive,'threshold':threshold,'auroc':auroc,'auprc':ap,
        'mcc':(tp*tn-fp*fn)/math.sqrt(denom) if denom and two else (0. if two else None),
        'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.,
        'balanced_accuracy':(tp/positive+tn/negative)/2 if two else None,
        'brier':math.fsum((v-q)**2 for v,q in zip(y,p))/n}
def threshold_check(y,p,chosen):
    ordered=sorted(zip(p,y));values=[v for v,_ in ordered];prefix=[0]
    for _,label in ordered:prefix.append(prefix[-1]+label)
    positive=sum(y);negative=len(y)-positive;candidates=[]
    for i in range(17):
        threshold=0.1+i*((0.9-0.1)/16)
        j=bisect.bisect_left(values,threshold);tp=positive-prefix[j];fp=len(y)-j-tp;fn=positive-tp;tn=negative-fp
        denominator=(tp+fp)*(tp+fn)*(tn+fp)*(tn+fn)
        mcc=(tp*tn-fp*fn)/math.sqrt(denominator) if denominator else 0.
        candidates.append((mcc,-abs(threshold-.5),threshold))
    best=max(candidates);actual=scores(y,p,chosen)['mcc']
    return {'max_mcc':best[0],'selected_mcc':actual,'independent_argmax':best[2],
            'mcc_optimal_to_1e12':abs(actual-best[0])<=1e-12,
            'selected_on_grid':any(abs(chosen-item[2])<1e-12 for item in candidates)}
def main():
    parser=argparse.ArgumentParser();parser.add_argument('root',type=Path);args=parser.parse_args()
    here=Path(__file__).resolve().parent;manifest=json.loads((here/'coverage-manifest.json').read_text(encoding='utf-8'))
    refs={}
    for view in manifest['views']:
        path=Path(view['path'])
        if not path.exists():path=here/'inputs'/(view['id']+'.csv')
        assert sha(path)==view['sha256'];refs[view['id']]={r['row_id']:r for r in read(path)}
    errors=[];checks=0;selected=0;fit_count=0;thresholds=[];files=[]
    def check(actual,expected,context):
        nonlocal checks
        checks+=1
        if (actual is None)!=(expected is None) or (actual is not None and abs(actual-expected)>1e-9):
            errors.append({'context':context,'actual':actual,'expected':expected})
    for path in sorted(args.root.glob('*/*/seed-*/result.json')):
        record=json.loads(path.read_text());run=path.parent;selected+=1
        candidates=json.loads((run/'candidates.json').read_text());fit_count+=len(candidates)
        for candidate in candidates:
            index=candidate['candidate'];pred_path=run/f'candidate-{index}-validation.csv';rows=read(pred_path)
            y=[int(float(r['label'])) for r in rows];p=[float(r['prediction']) for r in rows];threshold=float(rows[0]['threshold'])
            values=scores(y,p,threshold)
            for metric,value in values.items():check(value,candidate['validation_metrics'][metric],str(pred_path)+':'+metric)
            optimal=threshold_check(y,p,threshold);thresholds.append({'path':str(pred_path),**optimal})
            if not optimal['mcc_optimal_to_1e12'] or not optimal['selected_on_grid']:errors.append({'threshold':str(pred_path),**optimal})
            objective=values['auprc'] if values['auprc'] is not None else -values['brier']
            check(objective,candidate['selection_objective'],str(pred_path)+':objective')
            if sha(run/f'candidate-{index}.joblib')!=candidate['model_sha256']:errors.append({'model_hash':str(path),'candidate':index})
        winner=max(candidates,key=lambda c:c['selection_objective'])['candidate']
        check(winner,record['selected_candidate'],str(path)+':selection')
        for split,stored in record['splits'].items():
            pred_path=run/f'{split}-predictions.csv';digest=sha(pred_path)
            if digest!=stored['prediction_sha256']:errors.append({'prediction_hash':str(pred_path)})
            rows=read(pred_path);reference=refs[record['view_id']]
            if {r['row_id'] for r in rows}!={key for key,v in reference.items() if v['split']==split}:errors.append({'coverage':str(pred_path)})
            for row in rows:
                original=reference[row['row_id']]
                if float(row['label'])!=float(original['label']) or row['endpoint']!=original['endpoint']:errors.append({'label_endpoint':row['row_id']})
                if int(row['predicted_class'])!=int(float(row['prediction'])>=float(row['threshold'])):errors.append({'threshold_class':row['row_id']})
            threshold=float(record['threshold']);y=[int(float(r['label'])) for r in rows];p=[float(r['prediction']) for r in rows]
            actual=scores(y,p,threshold)
            for metric,value in actual.items():check(value,stored['metrics'][metric],str(pred_path)+':'+metric)
            for column,macro_key,file_tag in [('group_id','macro','group'),('structure_id','per_complex_macro','complex')]:
                if column not in rows[0]:continue
                groups={}
                for row in rows:groups.setdefault(row[column],[]).append(row)
                saved={str(r['group_id']):r for r in json.loads((run/f'{split}-{file_tag}-metrics.json').read_text())}
                values=[]
                for key,group in groups.items():
                    current=scores([int(float(r['label'])) for r in group],[float(r['prediction']) for r in group],threshold);values.append(current)
                    for metric,value in current.items():check(value,saved[key][metric],str(pred_path)+':'+column+':'+key+':'+metric)
                check(len(groups),stored[macro_key]['group_count'],str(pred_path)+':macro_n:'+column)
                for metric,expected in stored[macro_key]['metrics'].items():
                    valid=[r[metric] for r in values if r[metric] is not None]
                    check(statistics.mean(valid) if valid else None,expected['mean'],str(pred_path)+':macro:'+column+':'+metric)
                    check(len(valid),expected['valid_groups'],str(pred_path)+':macro_valid:'+column+':'+metric)
            for column,groups in stored['subgroups'].items():
                for group in groups:
                    local=[r for r in rows if r[column]==str(group['value'])]
                    current=scores([int(float(r['label'])) for r in local],[float(r['prediction']) for r in local],threshold)
                    for metric,value in current.items():check(value,group[metric],str(pred_path)+':subgroup:'+column+':'+metric)
            files.append({'path':str(pred_path),'sha256':digest,'n':len(rows)})
    report={'schema':'frozen-esm2.binary-heads.independent-audit.v1','passed':selected==100 and fit_count==200 and not errors,
        'selected_runs':selected,'candidate_fits':fit_count,'numeric_checks':checks,'errors':errors,
        'candidate_validation_threshold_checks':thresholds,'prediction_files':files,'new_fit_count':0,'new_forward_count':0,
        'p_values_computed':0,'code_sha256':sha(__file__)}
    (args.root/'independent-recalculation.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ['candidate_validation_threshold_checks','prediction_files']}))
    return 0 if report['passed'] else 2
if __name__=='__main__':raise SystemExit(main())
