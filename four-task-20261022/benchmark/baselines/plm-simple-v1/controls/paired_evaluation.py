"""Predeclared descriptive paired summaries: same view/model/seed/exact row_id, no significance selection."""
import csv
import json
import statistics
from pathlib import Path
from verify_manual_controls import metrics,read,sha

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
MANUAL=ROOT/'runs/plm-cohort-manual-controls-v1'
ESM=ROOT/'runs/plm-simple-v1/heads'
OUT=MANUAL/'paired-with-esm'

def write_csv(path,rows):
    with Path(path).open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))

def masks():
    out={'all':lambda s:True,'NC_any_including_PTM':lambda s:s!='standard20_control',
        'PTM_any_including_mixed':lambda s:s in {'PTM','synthetic_and_PTM'},
        'synthetic_D_any_including_mixed':lambda s:s in {'synthetic_D_backbone','synthetic_and_PTM'}}
    for value in ['standard20_control','PTM','synthetic_D_backbone','synthetic_and_PTM','other_NC']:
        out[value]=lambda s,value=value:s==value
    return out

def main():
    OUT.mkdir(parents=True,exist_ok=False)
    manifest=load(HERE/'coverage-manifest.json');metrics_rows=[];pairs=[];constant_rows=0
    for view in manifest['views']:
        path=Path(view['path']);assert sha(path)==view['sha256']
        reference={r['row_id']:r for r in read(path) if r['split']=='test'}
        mcontract=load(MANUAL/view['id']/'task-contract.json')
        econtract=load(ESM/view['id']/'task-contract.json')
        assert mcontract['input_sha256']==econtract['input_sha256']==view['sha256']
        assert mcontract['data_audit']['split_counts']==econtract['data_audit']['split_counts']
        assert mcontract['sklearn']==econtract['sklearn'] and mcontract['numpy']==econtract['numpy']
        for model in ['constant','linear','random_forest','extra_trees','hist_gradient_boosting']:
            for seed in range(10):
                mr=MANUAL/view['id']/model/f'seed-{seed:02d}'
                er=ESM/view['id']/model/f'seed-{seed:02d}'
                mout,eout=load(mr/'result.json'),load(er/'result.json')
                mp,ep=mr/'test-predictions.csv',er/'test-predictions.csv'
                mh,eh=sha(mp),sha(ep)
                assert mh==mout['splits']['test']['prediction_sha256']
                assert eh==eout['splits']['test']['prediction_sha256']
                manual={r['row_id']:r for r in read(mp)};esm={r['row_id']:r for r in read(ep)}
                assert set(manual)==set(esm)==set(reference)
                records=[]
                for key,ref in reference.items():
                    m,e=manual[key],esm[key];y=float(ref['label'])
                    assert float(m['label'])==float(e['label'])==y
                    assert m['endpoint']==e['endpoint']==ref['endpoint']
                    assert m['group_id']==e['group_id']==ref['group_id']
                    assert m['evaluation_stratum']==e['evaluation_stratum']==ref['evaluation_stratum']
                    a,b=float(m['prediction']),float(e['prediction'])
                    records.append({'row_id':key,'endpoint':ref['endpoint'],'group_id':ref['group_id'],
                        'evaluation_stratum':ref['evaluation_stratum'],'label':y,
                        'manual_prediction':a,'esm_prediction':b,'manual_abs_error':abs(a-y),'esm_abs_error':abs(b-y),
                        'delta_abs_error_manual_minus_ESM':abs(a-y)-abs(b-y)})
                    if model=='constant':assert a==b;constant_rows+=1
                target=OUT/view['id']/model/f'seed-{seed:02d}';target.mkdir(parents=True)
                output=target/'paired-test-predictions.csv';write_csv(output,records)
                for stratum,mask in masks().items():
                    subset=[r for r in records if mask(r['evaluation_stratum'])]
                    empty_metrics=['mae','rmse','bias','r2','pearson','spearman']+(['direction_accuracy_nonzero'] if view['task']=='effect' else [])
                    mvalues=metrics([r['label'] for r in subset],[r['manual_prediction'] for r in subset],view['task']=='effect') if subset else {k:None for k in empty_metrics}
                    evalues=metrics([r['label'] for r in subset],[r['esm_prediction'] for r in subset],view['task']=='effect') if subset else mvalues
                    for metric,mvalue in mvalues.items():
                        evalue=evalues[metric]
                        if metric in {'nonzero_effect_n'}:continue
                        metrics_rows.append({'view_id':view['id'],'model':model,'seed':seed,'stratum':stratum,
                            'metric':metric,'n':len(subset),'manual':mvalue,'esm':evalue,
                            'delta_manual_minus_ESM':mvalue-evalue if mvalue is not None and evalue is not None else None})
                entry={'view_id':view['id'],'model':model,'seed':seed,'n':len(records),
                    'manual_prediction_path':str(mp),'manual_prediction_sha256':mh,
                    'esm_prediction_path':str(ep),'esm_prediction_sha256':eh,
                    'manual_selected_candidate':mout['selected_candidate'],'esm_selected_candidate':eout['selected_candidate'],
                    'paired_prediction_sha256':sha(output),'input_sha256':view['sha256'],
                    'training_and_validation_identical_by_byte_frozen_view':True,'labels_exact_CSV64':True,
                    'no_test_intersection_shrink':True}
                (target/'receipt.json').write_text(json.dumps(entry,indent=2),encoding='utf-8');pairs.append(entry)
                assert mh==sha(mp) and eh==sha(ep)
    write_csv(OUT/'per-seed-paired-metrics.csv',metrics_rows)
    groups={}
    for row in metrics_rows:groups.setdefault(tuple(row[k] for k in ['view_id','model','stratum','metric']),[]).append(row)
    summary=[]
    for key,rows in sorted(groups.items()):
        result=dict(zip(['view_id','model','stratum','metric'],key),n=rows[0]['n'],seed_count=len(rows))
        assert len(rows)==10 and len({r['n'] for r in rows})==1
        for source in ['manual','esm','delta_manual_minus_ESM']:
            values=[r[source] for r in rows if r[source] is not None]
            result[source+'_mean']=statistics.mean(values) if values else None
            result[source+'_sd']=statistics.stdev(values) if len(values)>1 else None
            result[source+'_valid_seed_count']=len(values)
        summary.append(result)
    write_csv(OUT/'paired-mean-sd.csv',summary)
    receipt={'schema':'plm.matched-cohort.paired-comparison.v1','paired_runs':len(pairs),
        'paired_prediction_calculation_rows':sum(r['n'] for r in pairs),'source_files_unchanged':True,
        'constant_prediction_rows_exactly_identical':constant_rows,'new_fit_count':0,'new_forward_count':0,
        'p_values_computed':0,'no_selective_significance_tests':True,'test_rows_removed_to_match':0,
        'canonical_labels':'original byte-identical CSV float64','same_train_validation_test_ids':True,
        'models_are_method_recipes_not_pure_encoder_causal_effect':True,
        'known_implementation_differences':['Manual Ridgeauto vs ESM RidgeLSQR1e-4/1000','Manual435D effect layout vs ESM960D WT/delta/target layout'],
        'pairs':pairs,'code_sha256':sha(__file__)}
    (OUT/'comparison-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in receipt.items() if k!='pairs'}))
if __name__=='__main__':main()
