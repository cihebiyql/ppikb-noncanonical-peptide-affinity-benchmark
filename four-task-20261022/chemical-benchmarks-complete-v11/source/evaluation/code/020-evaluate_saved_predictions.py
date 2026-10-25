"""Recompute saved-prediction metrics without loading or training a model.

Use the disclosed PPIKB prediction files and optional disclosed split annotation
table. Labels/predictions are read as float64-equivalent Python floats. Undefined
correlations/R2 remain JSON null. Seeds are repetitions on a fixed split, not ten
independent biological cohorts.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics


def ranks(values):
    ordered = sorted(range(len(values)), key=lambda i: values[i])
    result = [0.0] * len(values)
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and values[ordered[end]] == values[ordered[start]]:
            end += 1
        rank = (start + end - 1) / 2.0 + 1.0
        for offset in range(start, end):
            result[ordered[offset]] = rank
        start = end
    return result


def pearson(left, right):
    if len(left) < 2 or max(left)==min(left) or max(right)==min(right):
        return None
    lm, rm = statistics.fmean(left), statistics.fmean(right)
    ll = [x - lm for x in left]
    rr = [x - rm for x in right]
    denominator = math.sqrt(math.fsum(x*x for x in ll) * math.fsum(x*x for x in rr))
    return max(-1.0, min(1.0, math.fsum(x*y for x,y in zip(ll,rr)) / denominator)) if denominator else None


def metrics(rows):
    if not rows:
        return {'n': 0, **{key: None for key in ('mae','rmse','bias','r2','pearson','spearman')}}
    labels = [float(row['label']) for row in rows]
    predictions = [float(row['prediction']) for row in rows]
    if not all(math.isfinite(x) for x in labels + predictions):
        raise ValueError('Non-finite labels/predictions')
    differences = [pred-label for label,pred in zip(labels,predictions)]
    mean_label = statistics.fmean(labels)
    ssr = math.fsum(x*x for x in differences)
    sst = math.fsum((x-mean_label)**2 for x in labels)
    return {'n': len(rows), 'mae': statistics.fmean(abs(x) for x in differences), 'rmse': math.sqrt(ssr/len(rows)), 'bias': statistics.fmean(differences), 'r2': 1.0-ssr/sst if len(rows)>1 and sst else None, 'pearson': pearson(labels,predictions), 'spearman': pearson(ranks(labels),ranks(predictions))}


def evaluate(path, annotations=None):
    with Path(path).open(encoding='utf-8-sig',newline='') as stream:
        rows = list(csv.DictReader(stream))
    ids = [row['row_id'] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate prediction IDs')
    strata = {'overall': rows}
    for row in rows:
        strata.setdefault(row['evaluation_stratum'],[]).append(row)
    if annotations is not None:
        for row in rows:
            expected = annotations[row['row_id']]
            if float(row['label']) != float(expected['label']) or row['evaluation_stratum'] != expected['evaluation_stratum']:
                raise ValueError('Annotation/label mismatch')
        strata['exclude_class_graph_discordance'] = [row for row in rows if annotations[row['row_id']]['residue_class_graph_discordance'].strip().lower() not in ('true','1','yes')]
    groups = {}
    for row in rows:
        groups.setdefault(row['global_group_id'],[]).append(row)
    group_metrics = [dict(group_id=key,**metrics(value)) for key,value in sorted(groups.items())]
    group_macro = {}
    for key in ('mae','rmse','bias','r2','pearson','spearman'):
        defined = [row[key] for row in group_metrics if row[key] is not None]
        group_macro[key] = {'defined_groups':len(defined),'mean':statistics.fmean(defined) if defined else None}
    return {'source_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest(),'strata':{key:metrics(value) for key,value in strata.items()},'group_metrics':group_metrics,'group_macro':group_macro,'new_fits':0,'new_predictions':0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--predictions',type=Path,required=True)
    parser.add_argument('--annotations',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    annotations = None
    if args.annotations:
        with args.annotations.open(encoding='utf-8-sig',newline='') as stream:
            rows=list(csv.DictReader(stream))
        annotations={row['row_id']:row for row in rows}
        if len(annotations)!=len(rows):raise ValueError('Duplicate annotation IDs')
    result=evaluate(args.predictions,annotations)
    with args.output.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')


if __name__=='__main__':main()
