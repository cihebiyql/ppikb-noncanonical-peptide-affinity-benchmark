"""Summarize retained per-seed scoring receipts; missing seeds remain explicit."""
import argparse
from collections import defaultdict
import csv
from pathlib import Path
import numpy as np
import runner

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--scoring-root',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    output=Path(args.output)
    output.mkdir(parents=True,exist_ok=False)
    per_seed=[]
    sources=[]
    seen=set()
    for path in sorted(Path(args.scoring_root).rglob('complete.json')):
        receipt=runner.read_json(path)
        if receipt.get('stage')!='post-selection-score-only':continue
        runner.require_hash(path.parent/'predictions.jsonl',receipt['predictions_sha256'])
        identity=tuple(receipt[k] for k in ('split_id','holdout_id','method_id','regime','seed'))
        if identity in seen:raise ValueError('Duplicate score receipt '+str(identity))
        seen.add(identity)
        sources.append(dict(path=str(path),sha256=runner.sha_file(path)))
        for group,metrics in receipt['metrics'].items():
            per_seed.append(dict(split_id=receipt['split_id'],holdout_id=receipt['holdout_id'],
                                 method_id=receipt['method_id'],regime=receipt['regime'],seed=receipt['seed'],
                                 group=group,**metrics))
    grouped=defaultdict(list)
    for row in per_seed:
        grouped[tuple(row[k] for k in ('split_id','holdout_id','method_id','regime','group'))].append(row)
    aggregate=[]
    for identity,rows in sorted(grouped.items()):
        record=dict(zip(('split_id','holdout_id','method_id','regime','group'),identity))
        seeds=sorted(row['seed'] for row in rows)
        record.update(completed_seed_count=len(seeds),seeds=','.join(map(str,seeds)),
                      missing_seeds=','.join(map(str,sorted(set(range(10))-set(seeds)))),
                      n_min=min(row['n'] for row in rows),n_max=max(row['n'] for row in rows))
        for metric in ('MAE','RMSE','Pearson','Spearman','R2'):
            values=[row[metric] for row in rows if row[metric] is not None]
            record[metric+'_defined_seed_count']=len(values)
            record[metric+'_mean']=float(np.mean(values)) if values else None
            record[metric+'_sd']=float(np.std(values,ddof=1)) if len(values)>1 else None
        aggregate.append(record)
    for name,rows in [('per-seed-metrics.csv',per_seed),('ten-seed-summary.csv',aggregate)]:
        with (output/name).open('w',encoding='utf-8-sig',newline='') as handle:
            if rows:
                writer=csv.DictWriter(handle,fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
    runner.write_json(output/'summary-manifest.json',dict(source_receipts=sources,score_receipt_count=len(sources),
                      per_seed_metric_rows=len(per_seed),summary_rows=len(aggregate),
                      all_observed_groups_have_ten_seeds=bool(aggregate) and all(row['completed_seed_count']==10 for row in aggregate),
                      SD='sample SD ddof=1; undefined metrics excluded with defined-seed count explicitly reported',
                      missing_run_policy='never fill missing seeds or undefined metrics with zero'))
    print('Summarized '+str(len(sources))+' verified score receipts.')

if __name__=='__main__':main()
