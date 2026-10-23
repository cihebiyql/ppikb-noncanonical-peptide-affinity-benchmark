"""Independently recompute saved predictions; do not load a model or retrain."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def independent_metrics(rows, task):
    import numpy as np
    from scipy.stats import spearmanr, pearsonr
    from sklearn.metrics import (mean_absolute_error, mean_squared_error, r2_score,
                                  roc_auc_score, average_precision_score, matthews_corrcoef,
                                  f1_score, balanced_accuracy_score, log_loss, brier_score_loss)
    y = np.asarray([r['label'] for r in rows], dtype=float)
    p = np.asarray([r['prediction'] for r in rows], dtype=float)
    result = {'n': len(rows)}
    both = len(set(y.tolist())) > 1
    if task == 'classification':
        hard = p >= .5
        result.update(log_loss=float(log_loss(y, np.clip(p, 1e-12, 1-1e-12), labels=[0, 1])),
                      AUROC=float(roc_auc_score(y, p)) if both else None,
                      AUPRC=float(average_precision_score(y, p)) if both else None,
                      MCC=float(matthews_corrcoef(y, hard)) if both else None,
                      F1=float(f1_score(y, hard, zero_division=0)),
                      balanced_accuracy=float(balanced_accuracy_score(y, hard)) if both else None,
                      brier=float(brier_score_loss(y, p)), decision_threshold=.5)
    else:
        variable = both and len(set(p.tolist())) > 1
        result.update(MAE=float(mean_absolute_error(y, p)), RMSE=float(mean_squared_error(y, p)**.5),
                      R2=float(r2_score(y, p)) if both else None,
                      Pearson=float(pearsonr(y, p).statistic) if variable else None,
                      Spearman=float(spearmanr(y, p).statistic) if variable else None)
        if task == 'effect':
            eligible = y != 0
            result['direction_n'] = int(eligible.sum())
            result['direction_accuracy_nonzero'] = float(np.mean(np.sign(y[eligible]) == np.sign(p[eligible]))) if eligible.any() else None
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runs', default='runs/dta')
    parser.add_argument('--output', default='methods/dta/audit')
    args = parser.parse_args()
    records, checks, failures = [], [], []
    for file in sorted((ROOT/args.runs).rglob('complete.json')):
        record = json.loads(file.read_text(encoding='utf-8'))
        if not record.get('job_id'):
            continue  # per-candidate receipts have a different statistical unit
        prediction = file.parent/'test-predictions.jsonl'
        rows = [json.loads(line) for line in prediction.read_text(encoding='utf-8').splitlines() if line]
        actual = independent_metrics(rows, record['task'])
        errors = {}
        for key, value in actual.items():
            expected = record['metrics'].get(key)
            if value is None or expected is None:
                if value is not expected:
                    errors[key] = {'expected': expected, 'actual': value}
            elif abs(value-expected) > 1e-10:
                errors[key] = {'expected': expected, 'actual': value}
        valid = not errors and sha(prediction) == record['prediction_sha256']
        check = {'job_id': record['job_id'], 'valid': valid, 'differences': errors,
                 'prediction_sha256': sha(prediction), 'recomputed': actual}
        checks.append(check)
        if not valid:
            failures.append(check)
        records.append({k: record[k] for k in ('job_id', 'stage', 'method_id', 'view_id', 'task', 'seed')}
                       | record['metrics'])
    groups = {}
    for row in records:
        key = (row['stage'], row['method_id'], row['view_id'], row['task'])
        groups.setdefault(key, []).append(row)
    summaries = []
    for key, members in groups.items():
        numeric = {}
        for metric in members[0]:
            if metric in ('job_id', 'stage', 'method_id', 'view_id', 'task', 'seed'):
                continue
            values = [r[metric] for r in members if isinstance(r.get(metric), (int, float))]
            numeric[metric] = {'mean': statistics.mean(values) if values else None,
                               'sd': statistics.stdev(values) if len(values)>1 else None,
                               'valid_seeds': len(values)}
        seeds = sorted(m['seed'] for m in members)
        summaries.append({'stage': key[0], 'method_id': key[1], 'view_id': key[2], 'task': key[3],
                          'seeds': seeds, 'ten_seed_complete': key[0] == 'formal' and seeds == list(range(10)),
                          'metrics': numeric})
    output = ROOT/args.output
    output.mkdir(parents=True, exist_ok=True)
    (output/'prediction-audit.json').write_text(json.dumps({'checks': checks, 'failed': failures,
        'all_valid': bool(checks) and not failures, 'check_count': len(checks)}, indent=2, allow_nan=False), encoding='utf-8')
    (output/'seed-summary.json').write_text(json.dumps(summaries, indent=2, allow_nan=False), encoding='utf-8')
    if records:
        keys = sorted({k for row in records for k in row})
        with (output/'per-seed-metrics.csv').open('w', encoding='utf-8', newline='') as stream:
            writer = csv.DictWriter(stream, keys)
            writer.writeheader()
            writer.writerows(records)
    print(json.dumps({'runs': len(records), 'failed_audits': len(failures),
                      'formal_complete_groups': sum(x['ten_seed_complete'] for x in summaries)}))
    if failures:
        raise SystemExit(2)

if __name__ == '__main__':
    main()
