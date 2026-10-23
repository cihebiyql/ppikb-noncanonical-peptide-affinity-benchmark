"""Add frozen ESM heads to the existing precise-ID common cohorts without changing earlier scores."""
import csv
import json
import statistics
from pathlib import Path
from verify_results import metrics,read,sha

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
HEADS=ROOT/'runs/plm-simple-v1/heads'
OLD=ROOT/'runs/common-prediction-comparison-v2'
OUT=ROOT/'runs/plm-simple-v1/common-prediction-comparison'

def strata(rows):
    result={'all':rows,'NC_all_including_PTM':[r for r in rows if r['evaluation_stratum']!='standard20_control'],
        'PTM_any_including_mixed':[r for r in rows if r['evaluation_stratum'] in {'PTM','synthetic_and_PTM'}]}
    for value in ['synthetic_D_backbone','PTM','synthetic_and_PTM','other_NC','standard20_control']:
        result[value]=[r for r in rows if r['evaluation_stratum']==value]
    return result

def main():
    OUT.mkdir(parents=True,exist_ok=False)
    prior_path=OLD/'task-contract.json';prior=json.loads(prior_path.read_text(encoding='utf-8'))
    rows=[];inputs=[];evaluations=0;errors=[]
    for reference in prior['references']:
        reference_path=Path(reference['path']);assert sha(reference_path)==reference['input_sha256']
        all_reference={r['row_id']:r for r in read(reference_path)}
        gold={key:all_reference[key] for key in reference['test_ids']}
        panel=reference['panel'];view_id=f'ppikb_kd_{panel}_cold_scope_v2_esm2_raw20_len2048'
        for model in ['constant','linear','random_forest','extra_trees','hist_gradient_boosting']:
            for seed in range(10):
                path=HEADS/view_id/model/f'seed-{seed:02d}'/'test-predictions.csv'
                digest=sha(path);predictions={r['row_id']:r for r in read(path)}
                assert set(gold)<=set(predictions)
                selected=[]
                for key,ref in gold.items():
                    pred=predictions[key]
                    assert float(pred['label'])==float(ref['label']) and pred['endpoint']==ref['endpoint']=='pKd'
                    selected.append({**ref,'prediction':pred['prediction']})
                run=OUT/reference['id']/('esm2__'+model)/f'seed-{seed:02d}'
                run.mkdir(parents=True)
                with (run/'common-test-predictions.csv').open('w',encoding='utf-8',newline='') as f:
                    columns=['row_id','label','prediction','endpoint','group_id','evaluation_stratum']
                    writer=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');writer.writeheader();writer.writerows(selected)
                for stratum,subset in strata(selected).items():
                    values=metrics([float(r['label']) for r in subset],[float(r['prediction']) for r in subset],False) if subset else {k:None for k in ['mae','rmse','bias','r2','pearson','spearman']}
                    for metric,value in values.items():
                        rows.append({'cohort':reference['id'],'panel':panel,'method':'esm2__'+model,'seed':seed,
                                     'stratum':stratum,'metric':metric,'value':value,'n':len(subset)})
                assert digest==sha(path)
                inputs.append({'path':str(path),'sha256':digest,'reference_sha256':sha(reference_path)})
                evaluations+=1
    groups={}
    for row in rows:groups.setdefault((row['cohort'],row['panel'],row['method'],row['stratum'],row['metric']),[]).append(row)
    summary=[]
    for key,group in sorted(groups.items()):
        values=[r['value'] for r in group if r['value'] is not None]
        summary.append(dict(zip(['cohort','panel','method','stratum','metric'],key),
            mean=statistics.mean(values) if values else None,sd=statistics.stdev(values) if len(values)>1 else None,
            seed_count=10,valid_seed_count=len(values),n=group[0]['n']))
    for path,data in [(OUT/'esm2-per-seed-metrics.csv',rows),(OUT/'esm2-mean-sd-metrics.csv',summary)]:
        with path.open('w',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(data[0]));writer.writeheader();writer.writerows(data)
    old_summary=OLD/'mean-sd-metrics.csv';old_digest=sha(old_summary)
    combined=read(old_summary)+summary
    with (OUT/'combined-with-existing-frozen-mean-sd.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(combined[0]));writer.writeheader();writer.writerows(combined)
    assert old_digest==sha(old_summary)
    receipt={'new_fit_count':0,'new_forward_count':0,'fixed_prediction_evaluations':evaluations,
        'unique_new_prediction_source_files':len({row['path'] for row in inputs}),
        'four_cohort_test_denominators':{r['id']:r['test_n'] for r in prior['references']},
        'original_comparison_contract_sha256':sha(prior_path),'old_summary_sha256':old_digest,
        'old_summary_unchanged':True,'source_prediction_checks':inputs,'errors':errors,
        'canonical_labels':'Original frozen cohort CSV Python float64, exact row_id and endpoint match',
        'training_coverage_differs':True,'all_eight_paper_methods_common_subset_claimed':False,
        'esm2_training_counts_by_panel':{'source':{'train':5890,'validation':771,'own_test':758},
                                         'target':{'train':5203,'validation':1087,'own_test':1129}},
        'earlier_provider_training_counts_reference':str(prior_path),
        'generic_esm2_heads_not_additional_paper_reproductions':True,'code_sha256':sha(__file__)}
    (OUT/'comparison-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in receipt.items() if k!='source_prediction_checks'}))

if __name__=='__main__':main()
