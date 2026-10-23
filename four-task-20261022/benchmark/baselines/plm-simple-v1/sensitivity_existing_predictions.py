"""Score fixed test predictions with/without existing annotation-discordance flags; no refit."""
import csv
import json
import statistics
from pathlib import Path
from verify_results import metrics,read,sha

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
RUN=ROOT/'runs/plm-simple-v1/heads'
OUT=ROOT/'runs/plm-simple-v1/residue-flag-sensitivity-v1'

def main():
    OUT.mkdir(parents=True,exist_ok=False)
    coverage=json.loads((HERE/'coverage-manifest.json').read_text(encoding='utf-8'))
    metadata=ROOT/'data/ppikb_preserved_input_metadata.jsonl'
    assert sha(metadata)==coverage['views'][0]['metadata_sidecar_sha256']
    flags={}
    for line in metadata.read_text(encoding='utf-8').splitlines():
        row=json.loads(line);key=row.get('record_id') or row.get('row_id')
        assert key and isinstance(row['residue_class_graph_discordance'],bool)
        assert key not in flags;flags[key]=row['residue_class_graph_discordance']
    assert len(flags)==9116 and sum(flags.values())==568
    masks={'all':lambda s:True,'standard20':lambda s:s=='standard20_control',
        'NC_all_including_PTM':lambda s:s!='standard20_control',
        'PTM_any_including_mixed':lambda s:s in {'PTM','synthetic_and_PTM'},
        'synthetic_D_any_including_mixed':lambda s:s in {'synthetic_D_backbone','synthetic_and_PTM'}}
    all_rows=[];hashes=[];counts=[]
    for view in coverage['views']:
        frozen=read(Path(view['path']))
        flagged={r['row_id']:(flags[r['reference_row_id']] or flags[r['variant_row_id']])
                 if view['task']=='effect' else flags[r['row_id']] for r in frozen}
        counts.append({'view_id':view['id'],'train_n':view['split_counts']['train'],
            'train_flagged_still_used':sum(flagged[r['row_id']] for r in frozen if r['split']=='train'),
            'test_n':view['split_counts']['test'],
            'test_flagged':sum(flagged[r['row_id']] for r in frozen if r['split']=='test')})
        for path in sorted((RUN/view['id']).glob('*/seed-*/result.json')):
            result=json.loads(path.read_text());prediction=path.parent/'test-predictions.csv'
            before=sha(prediction);assert before==result['splits']['test']['prediction_sha256']
            rows=read(prediction)
            for policy in ['all_fixed_predictions','exclude_flagged_at_scoring_only']:
                selected=rows if policy=='all_fixed_predictions' else [r for r in rows if not flagged[r['row_id']]]
                for stratum,mask in masks.items():
                    group=[r for r in selected if mask(r['evaluation_stratum'])]
                    values=metrics([float(r['label']) for r in group],[float(r['prediction']) for r in group],view['task']=='effect') if group else {k:None for k in ['mae','rmse','r2','bias','pearson','spearman']}
                    for metric,value in values.items():
                        all_rows.append({'view_id':view['id'],'model':result['model'],'seed':result['seed'],
                            'policy':policy,'stratum':stratum,'metric':metric,'value':value,'n':len(group)})
            assert before==sha(prediction);hashes.append({'path':str(prediction),'sha256':before})
    groups={}
    for row in all_rows:
        key=tuple(row[k] for k in ['view_id','model','policy','stratum','metric'])
        groups.setdefault(key,[]).append(row)
    summary=[]
    for key,rows in sorted(groups.items()):
        values=[r['value'] for r in rows if r['value'] is not None]
        summary.append(dict(zip(['view_id','model','policy','stratum','metric'],key),
            n=rows[0]['n'],mean=statistics.mean(values) if values else None,
            sd=statistics.stdev(values) if len(values)>1 else None,seed_count=len(rows),valid_seed_count=len(values)))
    for path,rows in [(OUT/'per-seed-metrics.csv',all_rows),(OUT/'mean-sd-metrics.csv',summary)]:
        with path.open('w',encoding='utf-8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    receipt={'new_fit_count':0,'new_forward_count':0,'training_still_contains_flagged_observations':True,
        'metadata_path':str(metadata),'metadata_sha256':sha(metadata),'original_metadata_flags':568,
        'derived_view_counts':counts,'unchanged_prediction_files':hashes,'code_sha256':sha(__file__),
        'exclusion_is_sensitivity_not_retraining':True,'paired_effect_flags':'either parent observation flagged'}
    (OUT/'receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in receipt.items() if k!='unchanged_prediction_files'}))
if __name__=='__main__':main()
