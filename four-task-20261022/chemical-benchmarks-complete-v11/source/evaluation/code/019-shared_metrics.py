"""Frozen pure helpers copied from the head benchmark; no CUDA/environment side effects.
Source provenance and exact function hashes are in METRICS-ORIGIN.json.
"""
import json,math,hashlib
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

def sha(path):
    digest=hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda:handle.read(1024*1024),b""):digest.update(block)
    return digest.hexdigest()

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
