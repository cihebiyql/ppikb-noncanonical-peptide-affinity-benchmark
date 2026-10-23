"""Fixed prediction strata only; overlapping PTM/D strata are explicitly labelled."""
import argparse
import csv
import json
import statistics
from pathlib import Path
from verify_results import metrics,read,sha

def main():
    parser=argparse.ArgumentParser();parser.add_argument('root',type=Path);args=parser.parse_args()
    rows=[];hashes=[]
    masks={'all':lambda s:True,'standard20':lambda s:s=='standard20_control',
           'annotated_NC':lambda s:s!='standard20_control',
           'PTM_any_including_mixed':lambda s:s in {'PTM','synthetic_and_PTM'},
           'synthetic_D_any_including_mixed':lambda s:s in {'synthetic_D_backbone','synthetic_and_PTM'}}
    for result_path in sorted(args.root.glob('*/*/seed-*/result.json')):
        result=json.loads(result_path.read_text());path=result_path.parent/'test-predictions.csv'
        before=sha(path);predictions=read(path)
        for name,mask in masks.items():
            part=[r for r in predictions if mask(r['evaluation_stratum'])]
            values=metrics([float(r['label']) for r in part],[float(r['prediction']) for r in part],result['task']=='effect') if part else {}
            for metric,value in values.items():
                rows.append({'view_id':result['view_id'],'model':result['model'],'seed':result['seed'],
                             'stratum':name,'n':len(part),'metric':metric,'value':value})
        assert before==sha(path);hashes.append({'path':str(path),'sha256':before})
    output=args.root/'strata-per-seed.csv'
    with output.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    grouped={}
    for row in rows:grouped.setdefault((row['view_id'],row['model'],row['stratum'],row['metric']),[]).append(row)
    summary=[]
    for key,group in sorted(grouped.items()):
        values=[r['value'] for r in group if r['value'] is not None]
        summary.append(dict(zip(['view_id','model','stratum','metric'],key),n=group[0]['n'],seed_count=len(group),
            valid_seed_count=len(values),mean=statistics.mean(values) if values else None,
            sd=statistics.stdev(values) if len(values)>1 else None))
    with (args.root/'strata-mean-sd.csv').open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(summary[0]));writer.writeheader();writer.writerows(summary)
    (args.root/'strata-receipt.json').write_text(json.dumps({'new_fit_count':0,'new_forward_count':0,
        'original_prediction_files':hashes,'PTM_and_D_aggregate_masks_overlap_at_mixed':True,
        'chemical_identity_encoded':False,'code_sha256':sha(__file__)},indent=2),encoding='utf-8')
    print(json.dumps({'files':len(hashes),'per_seed_rows':len(rows),'summary_rows':len(summary)}))
if __name__=='__main__':main()
