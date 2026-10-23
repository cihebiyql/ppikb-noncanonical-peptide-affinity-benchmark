"""Independently check all fixed common rows and sklearn scores; no fitting or inference."""
import csv
import json
import math
from pathlib import Path
import statistics
import numpy as np
from sklearn.metrics import roc_auc_score,average_precision_score,matthews_corrcoef,f1_score,brier_score_loss,balanced_accuracy_score
from mirror_artifacts import HERE,ROOT,RUN,sha,write

def read(path):
    with Path(path).open(encoding='utf-8',newline='') as stream:return list(csv.DictReader(stream))
output=RUN/'common-classification-v2';receipt=json.loads((output/'receipt.json').read_text(encoding='utf-8'))
plan=json.loads((HERE/'common-classification-cohorts.json').read_text(encoding='utf-8'))
coverage=json.loads((HERE/'coverage-manifest.json').read_text(encoding='utf-8'))
view=next(v for v in coverage['views'] if v['task']=='classification')
reference={r['row_id']:r for r in read(view['path']) if r['split']=='test'}
stored=read(output/'per-seed-metrics.csv');summaries=read(output/'mean-sd-metrics.csv')
errors=[];checks=0;rows_checked=0
for item in receipt['files']:
    source=Path(item['source']);assert sha(source)==item['source_sha256']
    cohort=next(c for c in plan['cohorts'] if c['name']==item['cohort'])
    path=output/item['cohort']/item['model']/f"seed-{item['seed']:02d}"/'test-predictions.csv'
    assert sha(path)==item['subset_prediction_sha256'];selected=read(path)
    assert [r['row_id'] for r in selected]==cohort['row_ids']
    original={r['row_id']:r for r in read(source)}
    for row in selected:
        key=row['row_id'];assert row==original[key]
        assert float(row['label'])==float(reference[key]['label']) and row['endpoint']==reference[key]['endpoint']
        rows_checked+=1
    threshold=float(selected[0]['threshold']);y=np.array([int(float(r['label'])) for r in selected]);p=np.array([float(r['prediction']) for r in selected])
    hard=p>=threshold
    expected={'auroc':roc_auc_score(y,p),'auprc':average_precision_score(y,p),'mcc':matthews_corrcoef(y,hard),
        'f1':f1_score(y,hard,zero_division=0),'brier':brier_score_loss(y,p),'balanced_accuracy':balanced_accuracy_score(y,hard)}
    for metric,value in expected.items():
        row=next(r for r in stored if r['cohort']==item['cohort'] and r['model']==item['model'] and int(r['seed'])==item['seed'] and r['metric']==metric)
        checks+=1
        if abs(float(row['value'])-value)>1e-10:errors.append({'context':str(path)+':'+metric,'actual':float(row['value']),'expected':float(value)})
for row in summaries:
    values=[float(r['value']) for r in stored if all(r[k]==row[k] for k in ['cohort','model','metric'])]
    assert len(values)==10
    for key,expected in [('mean',statistics.mean(values)),('sd',statistics.stdev(values))]:
        checks+=1
        if abs(float(row[key])-expected)>1e-10:errors.append({'summary':row,'key':key,'expected':expected})
prior=json.loads((HERE/'common-windows-path-revision2.json').read_text(encoding='utf-8'))
for item in prior['partial_file_hashes']:
    old=Path(item['path']);assert sha(old)==item['sha256']
    new=Path(str(old).replace('common-classification-fixed-predictions','common-classification-v2'))
    assert sha(new)==item['sha256']
report={'passed':not errors and len(receipt['files'])==100 and rows_checked==231950,
    'fixed_applications':len(receipt['files']),'row_label_endpoint_and_prediction_checks':rows_checked,
    'sklearn_and_summary_numeric_checks':checks,'errors':errors,'original_prediction_hashes_unchanged':True,
    'preserved_partial_attempt_files_identical_to_revision2':len(prior['partial_file_hashes']),
    'diagnostic_partial_applications_excluded_from_formal_count':len(prior['partial_file_hashes']),
    'new_fit_count':0,'new_forward_count':0,'code_sha256':sha(__file__)}
write(output/'independent-audit.json',report);print(json.dumps(report));assert report['passed']
