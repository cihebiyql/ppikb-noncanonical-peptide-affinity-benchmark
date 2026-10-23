"""Fixed-prediction common-ID evaluation, no retraining or threshold changes."""
import csv
import json
from pathlib import Path
import statistics
from verify_heads import scores,read,sha
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];RUN=ROOT/'runs/plm-classification-contact-v1'
def main():
    plan=json.loads((HERE/'common-classification-cohorts.json').read_text(encoding='utf-8'))
    coverage=json.loads((HERE/'coverage-manifest.json').read_text(encoding='utf-8'))
    view=next(v for v in coverage['views'] if v['task']=='classification')
    reference={r['row_id']:r for r in read(view['path']) if r['split']=='test'}
    output=RUN/'common-classification-fixed-predictions';output.mkdir(parents=True,exist_ok=False)
    rows=[];files=[]
    for cohort in plan['cohorts']:
        assert sha(cohort['path'])==cohort['sha256']
        ids=cohort['row_ids'];assert len(ids)==cohort['rows']
        for model in ['constant','linear','random_forest','extra_trees','hist_gradient_boosting']:
            for seed in range(10):
                run=RUN/'heads'/view['id']/model/f'seed-{seed:02d}'
                result=json.loads((run/'result.json').read_text());threshold=result['threshold']
                path=run/'test-predictions.csv';before=sha(path);assert before==result['splits']['test']['prediction_sha256']
                predictions={r['row_id']:r for r in read(path)};assert set(ids)<=set(predictions)
                selected=[]
                for key in ids:
                    r=predictions[key];ref=reference[key]
                    assert float(r['label'])==float(ref['label']) and r['endpoint']==ref['endpoint']
                    assert float(r['threshold'])==threshold;selected.append(r)
                dest=output/cohort['name']/model/f'seed-{seed:02d}';dest.mkdir(parents=True)
                with (dest/'test-predictions.csv').open('w',encoding='utf-8',newline='') as f:
                    writer=csv.DictWriter(f,fieldnames=list(selected[0]));writer.writeheader();writer.writerows(selected)
                values=scores([int(float(r['label'])) for r in selected],[float(r['prediction']) for r in selected],threshold)
                for metric,value in values.items():
                    if metric not in {'n','positive_count','threshold'}:
                        rows.append({'cohort':cohort['name'],'model':model,'seed':seed,'n':len(selected),'positive_count':values['positive_count'],
                            'metric':metric,'value':value,'threshold_from_full_validation':threshold})
                assert before==sha(path)
                files.append({'cohort':cohort['name'],'model':model,'seed':seed,'source':str(path),'source_sha256':before,
                    'subset_prediction_sha256':sha(dest/'test-predictions.csv'),'threshold_unchanged':True})
    def write(path,data):
        with path.open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
    write(output/'per-seed-metrics.csv',rows);groups={}
    for row in rows:groups.setdefault((row['cohort'],row['model'],row['metric']),[]).append(row)
    summary=[]
    for key,group in sorted(groups.items()):
        finite=[r['value'] for r in group if r['value'] is not None]
        summary.append(dict(zip(['cohort','model','metric'],key),n=group[0]['n'],seed_count=len(group),valid_seed_count=len(finite),
            mean=statistics.mean(finite) if finite else None,sd=statistics.stdev(finite) if len(finite)>1 else None))
    write(output/'mean-sd-metrics.csv',summary)
    (output/'receipt.json').write_text(json.dumps({'fixed_prediction_applications':len(files),'files':files,'new_fit_count':0,'new_forward_count':0,
        'thresholds_never_tuned_on_common_test':True,'primary_test_rows_unchanged':2362,
        'cohorts_not_independent_external_datasets':True,'training_and_pretraining_coverage_still_differ':True,
        'code_sha256':sha(__file__)},indent=2),encoding='utf-8')
    print(json.dumps({'applications':len(files),'new_fit_count':0,'new_forward_count':0}))
if __name__=='__main__':main()
