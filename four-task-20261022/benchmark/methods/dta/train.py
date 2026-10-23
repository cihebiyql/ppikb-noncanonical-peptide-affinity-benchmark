"""New common-data retraining with frozen author architectures and explicit task adaptations.

Only the resource coordinator may launch CUDA jobs with a validated standard contract.
Candidate selection reads train/validation only. Test rows are opened after selection freezes.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import hashlib
import importlib.util
import inspect
import json
import math
import os
from pathlib import Path
import pickle
import random
import socket
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FOLDERS = {'GraphDTA-GIN': 'graphdta-deepnc', 'DeepNC-GEN': 'graphdta-deepnc',
           'MGraphDTA': 'mgraph-dgdta', 'DGDTA-CL': 'mgraph-dgdta', 'GS-DTA': 'gs-dta'}

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024**2), b''):
            h.update(block)
    return h.hexdigest()

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp-' + str(os.getpid()))
    temp.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2), encoding='utf-8')
    temp.replace(path)

def checked(reference):
    path = ROOT / reference['path']
    if sha(path) != reference['sha256']:
        raise ValueError('Frozen input hash differs: ' + str(path))
    return path

def load_rows(reference):
    with checked(reference).open(encoding='utf-8') as stream:
        rows = [json.loads(line) for line in stream if line.strip()]
    if len(rows) != reference['n']:
        raise ValueError('Frozen input count mismatch')
    if any(not math.isfinite(float(row['label'])) for row in rows):
        raise ValueError('Nonfinite label')
    return rows

def adapter(method):
    path = HERE / 'frozen' / FOLDERS[method] / 'adapter.py'
    spec = importlib.util.spec_from_file_location('fourtask_' + FOLDERS[method].replace('-', '_'), path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

@contextmanager
def cache_lock(path):
    """Serialize same-view seeds without stale PID locks; OS releases on exit."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as handle:
        if os.name == 'posix':
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == 'posix':
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

def encode_rows(module, method, rows, task, source_sha):
    signature = hashlib.sha256(json.dumps({'rows': rows, 'task': task, 'method': method,
                                          'source_manifest_sha256': source_sha},
                                         sort_keys=True).encode()).hexdigest()
    cache = HERE / 'cache' / (signature + '.pkl')
    receipt = cache.with_suffix('.json')
    with cache_lock(cache.with_suffix('.lock')):
        return encode_rows_locked(module, method, rows, task, signature, cache, receipt)

def encode_rows_locked(module, method, rows, task, signature, cache, receipt):
    if cache.exists() and receipt.exists():
        meta = json.loads(receipt.read_text())
        if sha(cache) != meta['sha256'] or meta['signature'] != signature:
            raise ValueError('Owned graph cache integrity failed')
        with cache.open('rb') as stream:
            return pickle.load(stream)
    parameters = inspect.signature(module.encode_record).parameters
    def one(row, smiles):
        value = {'record_id': row['record_id'], 'peptide_smiles': smiles,
                 'target_sequence': row['target_sequence'], 'pKd': 0.0}
        return module.encode_record(value, method_id=method) if 'method_id' in parameters else module.encode_record(value)
    # Label values are not used for graph construction; explicit 0 above is a dummy
    # graph.y tensor, never an observed binding/no-effect label.
    if task == 'effect':
        items = [(one(row, row['smiles_wt']), one(row, row['smiles_mut'])) for row in rows]
    else:
        items = [one(row, row['peptide_smiles']) for row in rows]
    cache.parent.mkdir(parents=True, exist_ok=True)
    temp = cache.with_name(cache.name + '.tmp-' + str(os.getpid()))
    with temp.open('wb') as stream:
        pickle.dump(items, stream, protocol=pickle.HIGHEST_PROTOCOL)
    temp.replace(cache)
    write(receipt, {'signature': signature, 'sha256': sha(cache), 'rows': len(rows),
                    'scope': 'owned feature cache; no training or prediction result reuse'})
    return items

def minibatches(order, size):
    chunks = [order[i:i+size] for i in range(0, len(order), size)]
    # Native GIN BatchNorm needs more than one example during training. Merge
    # the last singleton into its preceding batch instead of dropping/duplicating it.
    if len(chunks) > 1 and len(chunks[-1]) == 1:
        chunks[-2].extend(chunks.pop())
    return chunks

def raw_predict(module, model, items, indices, task, device):
    if task == 'effect':
        wt = module.collate([items[i][0] for i in indices])
        mt = module.collate([items[i][1] for i in indices])
        return module.predict(model, mt, device) - module.predict(model, wt, device)
    return module.predict(model, module.collate([items[i] for i in indices]), device)

def predict(module, model, items, task, device, batch_size, torch):
    model.eval()
    values = []
    with torch.no_grad():
        for start in range(0, len(items), batch_size):
            result = raw_predict(module, model, items,
                                 list(range(start, min(start+batch_size, len(items)))), task, device)
            if task == 'classification':
                result = torch.sigmoid(result)
            if not torch.isfinite(result).all():
                raise FloatingPointError('Nonfinite prediction')
            values.extend(result.detach().cpu().reshape(-1).tolist())
    return values

def metrics(y, prediction, task):
    import numpy as np
    from scipy.stats import rankdata
    from sklearn.metrics import (average_precision_score, balanced_accuracy_score,
                                 f1_score, log_loss, matthews_corrcoef, roc_auc_score)
    y, p = np.asarray(y, dtype=np.float64), np.asarray(prediction, dtype=np.float64)
    if y.shape != p.shape or not np.isfinite(y).all() or not np.isfinite(p).all():
        raise ValueError('Invalid metric input')
    out = {'n': len(y)}
    if task == 'classification':
        hard = p >= 0.5
        both = len(set(y.tolist())) == 2
        out.update(log_loss=float(log_loss(y, np.clip(p, 1e-12, 1-1e-12), labels=[0, 1])),
                   AUROC=float(roc_auc_score(y, p)) if both else None,
                   AUPRC=float(average_precision_score(y, p)) if both else None,
                   MCC=float(matthews_corrcoef(y, hard)) if both else None,
                   F1=float(f1_score(y, hard, zero_division=0)),
                   balanced_accuracy=float(balanced_accuracy_score(y, hard)) if both else None,
                   brier=float(np.mean((y-p)**2)), decision_threshold=0.5)
    else:
        varying = len(y) > 1 and np.var(y) > 0
        both = varying and np.var(p) > 0
        out.update(MAE=float(np.mean(np.abs(y-p))), RMSE=float(np.sqrt(np.mean((y-p)**2))),
                   R2=float(1-np.sum((y-p)**2)/np.sum((y-y.mean())**2)) if varying else None,
                   Pearson=float(np.corrcoef(y, p)[0, 1]) if both else None,
                   Spearman=float(np.corrcoef(rankdata(y), rankdata(p))[0, 1]) if both else None)
        if task == 'effect':
            eligible = np.abs(y) > 0
            out['direction_accuracy_nonzero'] = float(np.mean(np.sign(y[eligible]) == np.sign(p[eligible]))) if eligible.any() else None
            out['direction_n'] = int(eligible.sum())
    return out

def all_metrics(rows, values, task):
    out = {'all': metrics([row['label'] for row in rows], values, task), 'strata': {}}
    for name in sorted({row.get('evaluation_stratum') or row.get('stratum') or 'unknown' for row in rows}):
        indices = [i for i, row in enumerate(rows)
                   if (row.get('evaluation_stratum') or row.get('stratum') or 'unknown') == name]
        out['strata'][name] = metrics([rows[i]['label'] for i in indices], [values[i] for i in indices], task)
    groups = {}
    for i, row in enumerate(rows):
        groups.setdefault(row.get('group_id') or row.get('target_id') or 'unknown', []).append(i)
    out['groups'] = {name: metrics([rows[i]['label'] for i in indices], [values[i] for i in indices], task)
                     for name, indices in groups.items()}
    return out

def predictions(path, rows, values):
    with path.open('w', encoding='utf-8') as stream:
        for row, value in zip(rows, values):
            result = {k: row.get(k) for k in ['record_id', 'row_id', 'source', 'group_id', 'target_id',
                                              'stratum', 'evaluation_stratum', 'endpoint', 'split']}
            result.update(label=float(row['label']), prediction=float(value))
            stream.write(json.dumps(result, ensure_ascii=False, allow_nan=False) + '\n')

def seed_all(seed, torch, np):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

def run(spec_path, device):
    # Third-party imports happen only at the real resource-coordinated entrypoint.
    import numpy as np
    import torch
    spec = json.loads(spec_path.read_text(encoding='utf-8-sig'))
    if spec['seed'] not in range(10) or spec['method_id'] not in FOLDERS:
        raise ValueError('Unregistered method/seed')
    source_path = checked(spec['source_manifest'])
    source = json.loads(source_path.read_text(encoding='utf-8'))
    for reference in source['files']:
        if sha(HERE / reference['path']) != reference['sha256']:
            raise ValueError('Frozen author source changed')
    output = ROOT / spec['run_root']
    output.mkdir(parents=True, exist_ok=False)
    started = time.time()
    write(output/'started.json', {'status': 'running', 'pid': os.getpid(),
          'pgid': os.getpgrp() if hasattr(os, 'getpgrp') else None, 'hostname': socket.gethostname(),
          'spec_sha256': sha(spec_path), 'started_unix': started, 'device': device,
          'source_manifest_sha256': spec['source_manifest']['sha256'],
          'new_training': True, 'prior_run_resumed': False})
    try:
        torch.set_num_threads(int(spec['cpu_threads']))
        torch.set_num_interop_threads(1)
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        torch.backends.cudnn.benchmark = False
        torch.backends.cudnn.deterministic = True
        torch.use_deterministic_algorithms(True, warn_only=True)
        if hasattr(torch, 'set_float32_matmul_precision'):
            torch.set_float32_matmul_precision('highest')
        if device == 'cuda:0':
            if not torch.cuda.is_available() or not os.environ.get('CUDA_VISIBLE_DEVICES'):
                raise RuntimeError('Explicit resource-controlled CUDA visibility required')
            budget = min(int(spec['gpu_allocator_budget_bytes']),
                         int(os.environ.get('GPU_MEMORY_CAP_MIB', 2048))*1024**2)
            torch.cuda.set_per_process_memory_fraction(budget/torch.cuda.get_device_properties(0).total_memory, 0)
        write(output/'runtime.json', {'python': sys.version, 'python_path': sys.executable,
              'torch': torch.__version__, 'numpy': np.__version__,
              'CUDA_VISIBLE_DEVICES': os.environ.get('CUDA_VISIBLE_DEVICES'),
              'dtype': 'float32', 'autocast': False, 'tf32': False,
              'deterministic_algorithms': 'warn_only; GPU bitwise identity not guaranteed',
              'allocator_budget_bytes': spec['gpu_allocator_budget_bytes'],
              'shared_environment_modified': False})
        train = load_rows(spec['paths']['train'])
        val = load_rows(spec['paths']['validation'])
        if {r['record_id'] for r in train} & {r['record_id'] for r in val}:
            raise ValueError('train/validation row leakage')
        module = adapter(spec['method_id'])
        train_items = encode_rows(module, spec['method_id'], train, spec['task'], spec['source_manifest']['sha256'])
        val_items = encode_rows(module, spec['method_id'], val, spec['task'], spec['source_manifest']['sha256'])
        candidates = []
        for ci, config in enumerate(spec['candidates']):
            seed_all(spec['seed'], torch, np)
            folder = output / ('candidate-' + str(ci))
            folder.mkdir()
            model = module.build_model(spec['method_id'], {}).to(device=device, dtype=torch.float32)
            optimizer = torch.optim.Adam(model.parameters(), lr=config['learning_rate'])
            target = np.asarray([row['label'] for row in train], dtype=np.float32)
            rng = np.random.default_rng(spec['seed'])
            best, best_epoch, stale = float('inf'), None, 0
            with (folder/'epochs.jsonl').open('w', encoding='utf-8') as log:
                for epoch in range(spec['max_epochs']):
                    if time.time()-started >= spec['timeout_seconds']:
                        raise TimeoutError('Original job timeout elapsed')
                    model.train()
                    loss_sum, visited = 0.0, 0
                    for indices in minibatches(rng.permutation(len(train)).tolist(), spec['batch_size']):
                        optimizer.zero_grad(set_to_none=True)
                        pred = raw_predict(module, model, train_items, indices, spec['task'], device)
                        y = torch.tensor(target[indices], device=device)
                        if spec['task'] == 'classification':
                            loss = torch.nn.functional.binary_cross_entropy_with_logits(pred, y)
                        else:
                            loss = torch.nn.functional.mse_loss(pred, y)
                        if not torch.isfinite(loss):
                            raise FloatingPointError('Nonfinite training loss')
                        loss.backward()
                        for parameter in model.parameters():
                            if parameter.grad is not None and not torch.isfinite(parameter.grad).all():
                                raise FloatingPointError('Nonfinite gradient')
                        optimizer.step()
                        loss_sum += float(loss.detach().cpu())*len(indices)
                        visited += len(indices)
                    val_pred = predict(module, model, val_items, spec['task'], device, spec['batch_size'], torch)
                    vm = metrics([row['label'] for row in val], val_pred, spec['task'])
                    score = vm['log_loss' if spec['task'] == 'classification' else 'MAE']
                    improved = score < best
                    if improved:
                        best, best_epoch, stale = score, epoch, 0
                        torch.save({'model_state': model.state_dict(), 'method_id': spec['method_id'],
                                    'spec_sha256': sha(spec_path), 'candidate_index': ci,
                                    'best_epoch': epoch, 'seed': spec['seed']}, folder/'best.pt')
                        predictions(folder/'validation-predictions.jsonl', val, val_pred)
                        write(folder/'validation-metrics.json', all_metrics(val, val_pred, spec['task']))
                    else:
                        stale += 1
                    row = {'epoch': epoch, 'train_n': visited, 'train_loss': loss_sum/visited,
                           'validation': vm, 'improved': improved, 'elapsed_seconds': time.time()-started}
                    log.write(json.dumps(row, allow_nan=False)+'\n')
                    log.flush()
                    print(json.dumps({'job': spec['job_id'], 'candidate': ci, **row}), flush=True)
                    if stale >= spec['patience']:
                        break
            record = {'candidate_index': ci, 'hyperparameters': config, 'best_validation_score': best,
                      'best_epoch': best_epoch, 'checkpoint_sha256': sha(folder/'best.pt'),
                      'validation_predictions_sha256': sha(folder/'validation-predictions.jsonl')}
            write(folder/'complete.json', record)
            candidates.append(record)
            del optimizer, model
            if device.startswith('cuda'):
                torch.cuda.empty_cache()
        winner = min(candidates, key=lambda c: (c['best_validation_score'], c['candidate_index']))
        selection = {'status': 'frozen', 'spec_sha256': sha(spec_path), 'candidates': candidates,
                     'winner': winner['candidate_index'], 'metric': 'validation logloss' if spec['task'] == 'classification' else 'validation MAE',
                     'test_used_for_selection': False, 'frozen_unix': time.time()}
        write(output/'selection.json', selection)
        # First access to held-out labels occurs after the immutable winner record.
        test = load_rows(spec['paths']['test'])
        if {r['record_id'] for r in test} & {r['record_id'] for r in train+val}:
            raise ValueError('test observation overlap')
        test_items = encode_rows(module, spec['method_id'], test, spec['task'], spec['source_manifest']['sha256'])
        seed_all(spec['seed'], torch, np)
        model = module.build_model(spec['method_id'], {}).to(device=device, dtype=torch.float32)
        checkpoint = output / ('candidate-' + str(winner['candidate_index'])) / 'best.pt'
        if sha(checkpoint) != winner['checkpoint_sha256']:
            raise ValueError('Selected checkpoint changed')
        payload = torch.load(checkpoint, map_location='cpu', weights_only=True)
        model.load_state_dict(payload['model_state'], strict=True)
        values = predict(module, model, test_items, spec['task'], device, spec['batch_size'], torch)
        predictions(output/'test-predictions.jsonl', test, values)
        result = all_metrics(test, values, spec['task'])
        write(output/'test-metrics.json', result)
        receipt = {'status': 'complete', 'job_id': spec['job_id'], 'stage': spec['stage'],
                   'method_id': spec['method_id'], 'view_id': spec['view_id'], 'task': spec['task'],
                   'endpoint': spec['endpoint'], 'seed': spec['seed'], 'new_training': True,
                   'reproduction_type': spec['reproduction_type'], 'scope': 'smoke_subset' if spec['stage'] == 'smoke' else 'full_frozen_view',
                   'spec_sha256': sha(spec_path), 'selection_sha256': sha(output/'selection.json'),
                   'prediction_sha256': sha(output/'test-predictions.jsonl'),
                   'elapsed_seconds': time.time()-started, 'metrics': result['all'],
                   'sample_counts': {'train': len(train), 'validation': len(val), 'test': len(test)}}
        write(output/'complete.json', receipt)
        return receipt
    except BaseException as exc:
        write(output/'failed.json', {'status': 'failed', 'error': repr(exc), 'traceback': traceback.format_exc(),
                                     'elapsed_seconds': time.time()-started, 'spec_sha256': sha(spec_path)})
        raise

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--spec', required=True)
    parser.add_argument('--device', choices=('cpu', 'cuda:0'), default='cuda:0')
    args = parser.parse_args()
    path = Path(args.spec)
    if not path.is_absolute():
        path = ROOT / path
    print(json.dumps(run(path, args.device), ensure_ascii=False, allow_nan=False), flush=True)

if __name__ == '__main__':
    main()
