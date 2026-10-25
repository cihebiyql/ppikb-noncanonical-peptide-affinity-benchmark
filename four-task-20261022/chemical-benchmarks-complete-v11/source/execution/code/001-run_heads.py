"""CPU-only, manifest-driven five-family ten-seed chemical-encoder regression heads."""
from __future__ import annotations

import os
for variable in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ.setdefault(variable, '1')
os.environ['CUDA_VISIBLE_DEVICES'] = ''

import argparse
import json
import math
import platform
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import scipy
from scipy.stats import spearmanr
import sklearn
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from chemical_features import ChemicalFeatures, json_read, resolve, sha

SEEDS = list(range(10))
GRID = {
    'constant': [{'strategy': 'mean'}, {'strategy': 'median'}],
    'ridge': [{'alpha': 0.1}, {'alpha': 10.0}],
    'random_forest': [{'n_estimators': 128, 'max_depth': 10, 'min_samples_leaf': 3},
                      {'n_estimators': 128, 'max_depth': None, 'min_samples_leaf': 2}],
    'extra_trees': [{'n_estimators': 128, 'max_depth': 10, 'min_samples_leaf': 3},
                    {'n_estimators': 128, 'max_depth': None, 'min_samples_leaf': 2}],
    'hist_gradient_boosting': [{'max_iter': 100, 'max_leaf_nodes': 15, 'learning_rate': 0.05},
                               {'max_iter': 150, 'max_leaf_nodes': 31, 'learning_rate': 0.05}],
}


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temp.replace(path)


def finite(value):
    return float(value) if value is not None and math.isfinite(float(value)) else None


def metrics(y, prediction, effect=False):
    y, prediction = np.asarray(y, dtype=np.float64), np.asarray(prediction, dtype=np.float64)
    if not len(y):
        return {'n': 0}
    if not np.isfinite(y).all() or not np.isfinite(prediction).all():
        raise ValueError('Nonfinite labels or predictions')
    residual = prediction - y
    varying = len(y) >= 2 and np.ptp(y) > 0 and np.ptp(prediction) > 0
    denominator = np.sum((y - np.mean(y)) ** 2)
    result = {'n': len(y), 'mae': finite(np.mean(np.abs(residual))),
              'rmse': finite(np.sqrt(np.mean(residual ** 2))), 'bias': finite(np.mean(residual)),
              'pearson': finite(np.corrcoef(y, prediction)[0, 1]) if varying else None,
              'spearman': finite(spearmanr(y, prediction).statistic) if varying else None,
              'r2': finite(1 - np.sum(residual ** 2) / denominator) if denominator > 0 else None}
    if effect:
        nonzero = y != 0
        result['direction_accuracy_nonzero'] = finite(np.mean(np.sign(y[nonzero]) == np.sign(prediction[nonzero]))) if nonzero.any() else None
        result['nonzero_effect_n'] = int(nonzero.sum())
    return result


def model(name, params, seed, threads):
    if name == 'constant':
        return DummyRegressor(**params)
    if name == 'ridge':
        return make_pipeline(StandardScaler(), Ridge(solver='lsqr', tol=1e-4, max_iter=2000, **params))
    if name in ('random_forest', 'extra_trees'):
        cls = RandomForestRegressor if name == 'random_forest' else ExtraTreesRegressor
        return cls(random_state=seed, n_jobs=threads, max_features='sqrt', **params)
    return HistGradientBoostingRegressor(random_state=seed, early_stopping=False, **params)


def prediction_file(path, frame, prediction):
    columns = [c for c in ('row_id', 'source', 'split', 'role', 'group_id', 'global_group_id', 'endpoint', 'evaluation_stratum', 'label') if c in frame]
    selected = frame[columns].copy()
    selected['prediction'] = prediction
    selected.to_csv(path, index=False, float_format='%.17g')


def validate_frame(frame, view):
    for original, canonical in ((view.get('label_column', 'label'), 'label'),
                                (view.get('split_column', 'split'), 'split'),
                                (view.get('group_column', 'group_id'), 'group_id')):
        if original not in frame:
            raise ValueError(f'Missing declared column {original}')
        frame[canonical] = frame[original]
    frame['split'] = frame['split'].replace({'fine_train': 'train', 'finetune_train': 'train',
                                           'val': 'validation', 'valid': 'validation', 'external_test': 'external'})
    if frame.row_id.duplicated().any():
        raise ValueError('Duplicate observation ID inside frozen task view')
    allowed = {'train', 'validation', 'test', 'external', 'pretrain', 'quarantine', 'excluded'}
    if not set(frame.split).issubset(allowed):
        raise ValueError('Unknown split/role in new frozen view')
    frame = frame[frame.split.isin(['train', 'validation', 'test', 'external'])].copy().reset_index(drop=True)
    frame['label'] = pd.to_numeric(frame.label, errors='raise').astype(np.float64)
    if not np.isfinite(frame.label).all():
        raise ValueError('Point regression labels must be finite')
    if any((frame.split == p).sum() == 0 for p in ('train', 'validation', 'test')):
        raise ValueError('Nonempty train/validation/test required; do not invent missing partitions')
    if (frame.groupby('group_id').split.nunique() > 1).any():
        raise ValueError('Declared dependency group crosses model partitions')
    if 'endpoint' in frame and set(frame.endpoint) != {view['endpoint']}:
        raise ValueError('Different affinity endpoints cannot share this single-endpoint run')
    if view['endpoint'] not in ('pKd', 'pKi', 'pIC50', 'delta_pKd', 'delta_pKd_silver'):
        raise ValueError('Undeclared/unverified endpoint is not accepted by this regression benchmark')
    return frame


def verify_existing_result(result_path, expected_contract_sha):
    prior = json_read(result_path)
    if prior.get('status') != 'succeeded' or prior.get('contract_sha256') != expected_contract_sha:
        raise ValueError('Existing run is partial or belongs to a different frozen contract; preserve it and choose a new output')
    for item in prior['candidates']:
        if sha(item['model_path']) != item['model_sha256']:
            raise ValueError('Existing candidate checkpoint changed')
    for split in prior['splits'].values():
        if sha(split['prediction_path']) != split['prediction_sha256']:
            raise ValueError('Existing selected prediction changed')
    return prior


def evaluate_partition(run, split, frame, predictions, effect):
    path = run / f'{split}-predictions.csv'
    prediction_file(path, frame, predictions)
    group_rows = []
    for group, indices in frame.groupby('group_id', sort=True).groups.items():
        group_rows.append({'group_id': str(group), **metrics(frame.loc[indices, 'label'], predictions[np.asarray(indices)], effect)})
    subgroup_rows = []
    for column in ('evaluation_stratum', 'source'):
        if column not in frame:
            continue
        for value, indices in frame.groupby(column, sort=True).groups.items():
            subgroup_rows.append({'column': column, 'value': str(value),
                                  **metrics(frame.loc[indices, 'label'], predictions[np.asarray(indices)], effect)})
    write_json(run / f'{split}-groups.json', group_rows)
    write_json(run / f'{split}-strata.json', subgroup_rows)
    macro = {}
    for key in ('mae','rmse','bias','pearson','spearman','r2','direction_accuracy_nonzero'):
        valid = [item[key] for item in group_rows if item.get(key) is not None]
        if any(key in item for item in group_rows):
            macro[key] = {'mean': finite(np.mean(valid)) if valid else None,
                          'valid_groups': len(valid), 'all_groups': len(group_rows)}
    return {'metrics': metrics(frame.label, predictions, effect), 'group_metrics': group_rows,
            'group_macro_metrics': macro, 'subgroups': subgroup_rows,
            'prediction_path': str(path), 'prediction_sha256': sha(path)}


def read_views(manifest):
    views = manifest.get('views')
    if not isinstance(views, list):
        raise ValueError('Frozen manifest views must be an explicit list; use a reviewed adapter for another schema')
    if manifest.get('schema') != 'peptide.cross-task-firewall.v1' or manifest.get('status') != 'frozen' or manifest.get('frozen') is not True:
        raise ValueError('The frozen cross-task-firewall manifest is required; legacy task views are not accepted')
    return views


def run_view(view, manifest_path, features, output, deadline, threads, seeds, requested):
    view_id = view['id']
    if view.get('status') not in ('ready', 'frozen', 'model_ready'):
        raise ValueError(f'View not execution-ready: {view_id}')
    source = resolve(view.get('path') or view['csv_path'], manifest_path.parent)
    if not view.get('sha256') or sha(source) != view['sha256']:
        raise ValueError('Input CSV differs from frozen global manifest')
    frame = validate_frame(pd.read_csv(source, keep_default_na=False, float_precision='round_trip'), view)
    x, feature_audit = features.build(frame, view.get('task', 'affinity'))
    if x.nbytes > 1024**3:
        raise MemoryError('Per-view feature matrix exceeds 1 GiB')
    parts = {p: np.flatnonzero(frame.split.to_numpy() == p) for p in ('train', 'validation', 'test', 'external')}
    y = frame.label.to_numpy()
    dest = output / view_id
    dest.mkdir(parents=True, exist_ok=True)
    contract_path = dest / 'frozen-head-contract.json'
    contract = {'schema': 'chemical-encoder.head-contract.v1', 'view_id': view_id,
                'endpoint': view['endpoint'], 'task': view.get('task', 'affinity'),
                'global_manifest_path': str(manifest_path), 'global_manifest_sha256': sha(manifest_path),
                'input_path': str(source), 'input_sha256': sha(source), 'code_sha256': sha(__file__),
                'feature_code_sha256': sha(Path(__file__).with_name('chemical_features.py')),
                'column_binding': {'label': view.get('label_column','label'),
                                   'split': view.get('split_column','split'),
                                   'group': view.get('group_column','group_id')},
                'feature_audit': feature_audit, 'seeds': seeds, 'models': {k: v for k, v in GRID.items() if k in requested},
                'selection': 'minimum validation MAE; tie lower candidate index; freeze before TEST/external',
                'training_only_scaler': True, 'threads': threads, 'encoder_frozen': True,
                'split_counts': {k: len(v) for k, v in parts.items()},
                'environment': {'python': sys.version, 'platform': platform.platform(), 'numpy': np.__version__,
                                'sklearn': sklearn.__version__, 'scipy': scipy.__version__}}
    if contract_path.exists():
        if json_read(contract_path) != contract:
            raise ValueError('Existing output contract differs; use a new immutable output directory')
    else:
        write_json(contract_path, contract)
    contract_sha = sha(contract_path)
    feature_file = dest / 'features.npz'
    if feature_file.exists():
        with np.load(feature_file,allow_pickle=False) as prior_features:
            if not np.array_equal(prior_features['embeddings'],x) or not np.array_equal(prior_features['row_ids'],frame.row_id.to_numpy(dtype=str)):
                raise ValueError('Existing saved feature matrix differs; preserve it and choose a new output')
    else:
        np.savez_compressed(feature_file, embeddings=x, row_ids=frame.row_id.to_numpy(dtype=str))
    for name in requested:
        for seed in seeds:
            run = dest / name / f'seed-{seed:02d}'
            result_path = run / 'result.json'
            if result_path.exists():
                verify_existing_result(result_path, contract_sha)
                continue
            if run.exists() and any(run.iterdir()):
                raise ValueError(f'Partial run preserved; do not overwrite {run}')
            run.mkdir(parents=True, exist_ok=True)
            started = now()
            candidates = []
            best = None
            for index, params in enumerate(GRID[name]):
                if time.monotonic() >= deadline:
                    raise TimeoutError('Wall clock reached before next candidate; partial assets retained')
                print(f'[{now()}] START {view_id} {name} seed={seed} candidate={index}', flush=True)
                estimator = model(name, params, seed, threads)
                fit_start = time.monotonic()
                with threadpool_limits(limits=threads):
                    estimator.fit(x[parts['train']], y[parts['train']])
                    vp = np.asarray(estimator.predict(x[parts['validation']]), dtype=np.float64)
                vm = metrics(y[parts['validation']], vp, view.get('task') == 'effect')
                weights = run / f'candidate-{index:02d}.joblib'
                joblib.dump(estimator, weights, compress=3)
                validation_path = run / f'candidate-{index:02d}-validation.csv'
                prediction_file(validation_path, frame.iloc[parts['validation']], vp)
                item = {'candidate': index, 'parameters': params, 'validation_metrics': vm,
                        'fit_seconds': time.monotonic() - fit_start, 'model_path': str(weights),
                        'model_sha256': sha(weights), 'validation_path': str(validation_path),
                        'validation_sha256': sha(validation_path)}
                if name == 'ridge':
                    scaler = estimator.named_steps['standardscaler']
                    expected = np.mean(x[parts['train']].astype(np.float64), axis=0)
                    difference = float(np.max(np.abs(scaler.mean_ - expected)))
                    if int(scaler.n_samples_seen_) != len(parts['train']) or difference > 1e-8:
                        raise ValueError('Ridge scaler was not fitted exclusively on frozen training inputs')
                    item['scaler_audit'] = {'training_rows': int(scaler.n_samples_seen_),
                                            'mean_matches_training': True,
                                            'max_abs_mean_difference': difference,
                                            'mean_sha256': __import__('hashlib').sha256(scaler.mean_.astype(np.float64).tobytes()).hexdigest()}
                candidates.append(item)
                write_json(run / 'candidates.json', candidates)
                if best is None or vm['mae'] < best[0]:
                    best = (vm['mae'], index, estimator)
            winner = best[1]
            selection = {'selected_candidate': winner, 'validation_mae': best[0],
                         'contract_sha256': contract_sha, 'frozen_before_test_at': now(),
                         'test_used_for_selection': False, 'external_used_for_selection': False}
            write_json(run / 'selection.json', selection)
            result = {'status': 'succeeded', 'view_id': view_id, 'model': name, 'seed': seed,
                      'task': view.get('task', 'affinity'), 'endpoint': view['endpoint'],
                      'contract_sha256': contract_sha, 'selected_candidate': winner,
                      'candidates': candidates, 'started_at': started, 'splits': {}}
            for split, indices in parts.items():
                if split == 'train' or not len(indices):
                    continue
                with threadpool_limits(limits=threads):
                    pred = np.asarray(best[2].predict(x[indices]), dtype=np.float64)
                part = frame.iloc[indices].reset_index(drop=True)
                result['splits'][split] = evaluate_partition(run, split, part, pred, view.get('task') == 'effect')
            result['completed_at'] = now()
            write_json(result_path, result)
            print(f'[{now()}] DONE {view_id} {name} seed={seed} selected={winner}', flush=True)
            aggregate(output)


def aggregate(output):
    entries = []
    for path in output.glob('*/*/seed-*/result.json'):
        result = json_read(path)
        if result.get('status') != 'succeeded':
            continue
        for split, part in result['splits'].items():
            groups = [('all', part['metrics'])] + [(f"{x['column']}:{x['value']}", x) for x in part['subgroups']]
            for stratum, mm in groups:
                for metric, value in mm.items():
                    if metric in ('n', 'column', 'value', 'nonzero_effect_n'):
                        continue
                    entries.append({'view_id': result['view_id'], 'endpoint': result['endpoint'],
                                    'model': result['model'], 'seed': result['seed'], 'split': split,
                                    'stratum': stratum, 'metric': metric, 'value': value, 'n': mm['n']})
    if entries:
        table = pd.DataFrame(entries)
        table.to_csv(output / 'per-seed-metrics.csv', index=False)
        summary = table.groupby(['view_id', 'endpoint', 'model', 'split', 'stratum', 'metric'], dropna=False).agg(
            mean=('value', 'mean'), sd=('value', 'std'), valid_seeds=('value', 'count'), seeds=('seed', 'nunique'),
            n=('n', 'first')).reset_index()
        summary.to_csv(output / 'ten-seed-mean-sd.csv', index=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--feature-spec', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--view', action='append')
    parser.add_argument('--model', action='append', choices=list(GRID))
    parser.add_argument('--seeds', default='0,1,2,3,4,5,6,7,8,9')
    parser.add_argument('--threads', type=int, choices=(1, 2), default=1)
    parser.add_argument('--max-seconds', type=int, default=7200)
    args = parser.parse_args()
    seeds = [int(x) for x in args.seeds.split(',')]
    if len(set(seeds)) != len(seeds) or not set(seeds).issubset(SEEDS):
        parser.error('Unique seeds must be drawn from 0..9')
    if args.max_seconds <= 0:
        parser.error('Positive bounded wall clock required')
    args.output.mkdir(parents=True, exist_ok=True)
    manifest_path = args.manifest.resolve()
    views = read_views(json_read(manifest_path))
    features = ChemicalFeatures(args.feature_spec)
    deadline = time.monotonic() + args.max_seconds
    records = []
    try:
        for view in views:
            if args.view and view['id'] not in args.view:
                continue
            if view.get('status') not in ('ready', 'frozen', 'model_ready'):
                records.append({'view_id': view['id'], 'status': 'not_run',
                                'reason': view.get('reason', view.get('qualification', 'Global freeze view is blocked'))})
                continue
            run_view(view, manifest_path, features, args.output.resolve(), deadline, args.threads, seeds, args.model or list(GRID))
            records.append({'view_id': view['id'], 'status': 'succeeded'})
    except Exception as exc:
        records.append({'status': 'failed', 'error': str(exc), 'traceback': traceback.format_exc()})
        print(traceback.format_exc(), flush=True)
    aggregate(args.output)
    write_json(args.output / 'execution-status.json', {'updated_at': now(), 'pid': os.getpid(),
               'requested_seeds': seeds,
               'formal_ten_seed_request_complete': seeds == SEEDS and any(x['status'] == 'succeeded' for x in records) and all(x['status'] in ('succeeded','not_run') for x in records),
               'all_manifest_views_completed': bool(records) and all(x['status'] == 'succeeded' for x in records),
               'records': records, 'new_encoder_training': False, 'gpu_used': False})
    return 0 if any(x['status'] == 'succeeded' for x in records) and all(x['status'] in ('succeeded','not_run') for x in records) else 1


if __name__ == '__main__':
    raise SystemExit(main())
