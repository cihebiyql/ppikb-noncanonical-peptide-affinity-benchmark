"""Frozen-author affinity benchmark execution. Fit never opens holdout label files."""
from __future__ import annotations
import argparse
import csv
import hashlib
import importlib.util
import inspect
import json
import math
import os
from pathlib import Path
import pickle
import random
import sys
import time
from typing import Any

import numpy as np
import torch
from scipy.stats import rankdata

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
METHOD_FOLDERS = {'GraphDTA-GIN': 'graphdta-deepnc', 'DeepNC-GEN': 'graphdta-deepnc',
                  'MGraphDTA': 'mgraph-dgdta', 'DGDTA-CL': 'mgraph-dgdta', 'MRBDTA': 'mrbdta',
                  'GS-DTA': 'gs-dta'}
FORMAL_METHOD_IDS = ['GraphDTA-GIN', 'MGraphDTA', 'DGDTA-CL', 'DeepNC-GEN', 'GS-DTA']
HYPERPARAMETERS = [dict(learning_rate=1e-3, weight_decay=0.0),
                   dict(learning_rate=3e-4, weight_decay=0.0)]
METADATA = ('record_id', 'source_record_id', 'chemical_entity_id', 'achiral_entity_id',
            'evaluation_stratum', 'NC_core', 'noncanonical_subtypes', 'target_id', 'study_id',
            'discordant_label', 'discordant_flag', 'label_discordance_flag', 'target_cluster_id',
            'study_component_id', 'chemistry_flags', 'annotation_unresolved_components')

def sha_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024**2), b''):
            digest.update(chunk)
    return digest.hexdigest()

def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding='utf-8')
    temporary.replace(path)

def read_jsonl(path):
    with Path(path).open(encoding='utf-8-sig') as handle:
        return [json.loads(line) for line in handle if line.strip()]

def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8', newline='\n') as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')

def seed_everything(seed, threads=2):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.set_num_threads(threads)
    if hasattr(torch.backends, 'cuda'):
        torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.use_deterministic_algorithms(True, warn_only=True)

def configure_device(spec):
    """Fail before model construction if CUDA authorization or runtime is missing.

    The optional fraction constrains PyTorch's allocator, not CUDA context memory
    or the whole process RSS. The launch controller owns concurrency/RSS limits.
    """
    device=spec.get('device','cpu')
    if device=='cpu':
        return dict(device='cpu',gpu_allocator_budget_bytes=None)
    if device!='cuda:0':raise ValueError('Only explicit cpu or cuda:0 devices supported')
    if spec.get('gpu_explicitly_authorized') is not True:
        raise ValueError('GPU execution requires explicit launch contract authorization')
    if not torch.cuda.is_available() or torch.cuda.device_count()<1:
        raise RuntimeError('Authorized CUDA device is unavailable; no automatic CPU fallback')
    total=int(torch.cuda.get_device_properties(0).total_memory)
    budget=spec.get('gpu_allocator_budget_bytes')
    if budget is not None:
        budget=int(budget)
        if budget<=0 or budget>min(total,3*1024**3):
            raise ValueError('GPU allocator budget must be positive and <=3 GiB and physical total')
        torch.cuda.set_per_process_memory_fraction(budget/total,device=0)
    return dict(device=device,device_name=torch.cuda.get_device_name(0),total_memory_bytes=total,
                gpu_allocator_budget_bytes=budget,allocator_budget_excludes_cuda_context_and_RSS=True,
                determinism='seeded; deterministic_algorithms warn_only; GPU bitwise reproducibility not guaranteed')

def load_adapter(method_id, methods_root=None):
    folder = Path(methods_root) if methods_root else PROJECT / 'methods'
    path = folder / METHOD_FOLDERS[method_id] / 'adapter.py'
    name = 'benchmark_adapter_' + METHOD_FOLDERS[method_id].replace('-', '_')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def adapter_tree_hash(adapter):
    root = Path(adapter.__file__).parent
    entries = [(str(path.relative_to(root)).replace('\\', '/'), sha_file(path))
               for path in sorted(root.rglob('*.py')) if '__pycache__' not in path.parts]
    return hashlib.sha256(json.dumps(entries, separators=(',', ':')).encode()).hexdigest()

def encode(adapter, method_id, row):
    parameters = inspect.signature(adapter.encode_record).parameters
    return adapter.encode_record(row, method_id=method_id) if 'method_id' in parameters else adapter.encode_record(row)

def native_model(adapter, method_id):
    return adapter.build_model(method_id, {})

def numeric_metrics(true, pred):
    y = np.asarray(true, dtype=np.float64).reshape(-1)
    p = np.asarray(pred, dtype=np.float64).reshape(-1)
    if y.shape != p.shape or not np.isfinite(y).all() or not np.isfinite(p).all():
        raise ValueError('Mismatched or nonfinite labels/predictions')
    result = dict(n=len(y), MAE=None, RMSE=None, Pearson=None, Spearman=None, R2=None)
    if not len(y):
        return result
    result['MAE'] = float(np.mean(np.abs(y-p)))
    result['RMSE'] = float(np.sqrt(np.mean((y-p)**2)))
    if len(y) > 1 and float(np.var(y)) > 0:
        result['R2'] = float(1 - np.sum((y-p)**2) / np.sum((y-y.mean())**2))
    if len(y) > 1 and float(np.var(y)) > 0 and float(np.var(p)) > 0:
        result['Pearson'] = float(np.corrcoef(y, p)[0, 1])
        result['Spearman'] = float(np.corrcoef(rankdata(y), rankdata(p))[0, 1])
    return result

def is_nc(row):
    value = row.get('NC_core')
    if not isinstance(value, bool):
        raise ValueError('NC_core must be explicit boolean: ' + row['record_id'])
    return value

def filter_scope(rows, scope):
    if scope == 'all':
        return list(rows)
    if scope not in ('NC_only', 'standard_only'):
        raise ValueError('Unknown scope ' + scope)
    desired = scope == 'NC_only'
    return [row for row in rows if is_nc(row) == desired]

def grouped_metrics(rows, values):
    result = {'all': numeric_metrics([r['pKd'] for r in rows], values)}
    strata = sorted({str(row.get('evaluation_stratum', 'unknown')) for row in rows})
    for stratum in strata:
        indices = [i for i, row in enumerate(rows) if str(row.get('evaluation_stratum', 'unknown')) == stratum]
        result[stratum] = numeric_metrics([rows[i]['pKd'] for i in indices], [values[i] for i in indices])
    for name, desired in [('NC_core', True), ('standard', False)]:
        indices = [i for i, row in enumerate(rows) if row.get('NC_core') is desired]
        result[name] = numeric_metrics([rows[i]['pKd'] for i in indices], [values[i] for i in indices])
    clean = [i for i, row in enumerate(rows) if not any(value is True for key, value in row.items()
                                                       if 'discord' in key.lower())]
    result['exclude_discordant_sensitivity'] = numeric_metrics([rows[i]['pKd'] for i in clean], [values[i] for i in clean])
    for stratum in strata:
        indices=[i for i in clean if str(rows[i].get('evaluation_stratum','unknown'))==stratum]
        result['exclude_discordant:'+stratum]=numeric_metrics([rows[i]['pKd'] for i in indices],[values[i] for i in indices])
    return result

def cache_items(adapter, method_id, rows, cache_path):
    signature = hashlib.sha256(json.dumps([(r['record_id'], r.get('canonical_isomeric_smiles') or r.get('peptide_smiles'),
                                           r['target_sequence'], r['pKd']) for r in rows],
                                          ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    source_hash = hashlib.sha256((adapter_tree_hash(adapter) + method_id).encode()).hexdigest()
    cache_path = Path(cache_path)
    if cache_path.exists():
        with cache_path.open('rb') as handle:
            payload = pickle.load(handle)
        if payload['signature'] != signature or payload['adapter_hash'] != source_hash:
            raise ValueError('Encoded cache does not match input/source: ' + str(cache_path))
        return payload['items']
    items = [encode(adapter, method_id, row) for row in rows]
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = cache_path.with_name(cache_path.name + '.' + str(os.getpid()) + '.tmp')
    with temporary.open('wb') as handle:
        pickle.dump(dict(signature=signature, adapter_hash=source_hash, items=items), handle,
                    protocol=pickle.HIGHEST_PROTOCOL)
    temporary.replace(cache_path)
    audits=[]
    for row,item in zip(rows,items):
        meta=item.get('audit') or item.get('metadata')
        if meta is None:
            meta={key:val for key,val in item.items() if key not in ('graph','x','edge_index','target','y')}
        audits.append(dict(record_id=row['record_id'],method_id=method_id,input_audit=meta))
    write_jsonl(cache_path.with_suffix('.input-audit.jsonl'),audits)
    return items

def predict_rows(adapter, model, items, device, batch_size):
    model.eval()
    values = []
    with torch.no_grad():
        for offset in range(0, len(items), batch_size):
            batch = adapter.collate(items[offset:offset+batch_size])
            pred = adapter.predict(model, batch, device).detach().cpu().reshape(-1)
            if not torch.isfinite(pred).all():
                raise FloatingPointError('Nonfinite evaluation prediction')
            values.extend(pred.tolist())
    if len(values) != len(items):
        raise AssertionError('Prediction cardinality mismatch')
    return values

def prediction_rows(rows, values):
    output = []
    for row, value in zip(rows, values):
        record = {key: row.get(key) for key in METADATA}
        record.update({key: val for key, val in row.items() if 'discord' in key.lower()})
        record.update(pKd_true=float(row['pKd']), pKd_pred=float(value),
                      residual=float(value-row['pKd']))
        output.append(record)
    return output

def require_hash(path, expected):
    actual = sha_file(path)
    if actual != expected:
        raise ValueError('Frozen input hash mismatch: ' + str(path))
    return actual

def validate_fit_spec(spec):
    forbidden = [key for key in spec if 'test' in key.lower() or 'external' in key.lower() or 'holdout' in key.lower()]
    if forbidden:
        raise ValueError('Fit spec must not name holdout paths: ' + ','.join(forbidden))
    if spec['method_id'] not in METHOD_FOLDERS:
        raise ValueError('Unknown method')
    if spec['regime'] not in ('NC_only', 'standard_only'):
        raise ValueError('No pooled training regime')
    if spec['seed'] not in range(10):
        raise ValueError('Frozen seeds are 0..9')
    if spec['validation_scope'] not in ('all', 'NC_only', 'standard_only', 'same_as_regime'):
        raise ValueError('Explicit validation_scope required')
    if not 1 <= int(spec['max_epochs']) <= 20 or not 1 <= int(spec['patience']) <= 5:
        raise ValueError('Current preregistration is bounded by 20 epochs / patience 5; CPU30 drafts are historical')
    if spec.get('device','cpu') not in ('cpu','cuda:0'):
        raise ValueError('Explicit cpu or cuda:0 required')
    if spec.get('device','cpu')!='cpu' and spec.get('gpu_explicitly_authorized') is not True:
        raise ValueError('GPU spec lacks explicit authorization')
    budget=spec.get('gpu_allocator_budget_bytes')
    if budget is not None and (int(budget)<=0 or int(budget)>3*1024**3):
        raise ValueError('GPU allocator budget must be <=3 GiB')
    if spec['method_id'] == 'MRBDTA' and (spec['batch_size'] != 1 or spec['gradient_accumulation'] != 8):
        raise ValueError('MRBDTA must use one graph and gradient accumulation 8')
    if spec.get('y_standardize', False):
        raise ValueError('Current frozen benchmark uses direct pKd MSE; normalization needs a revised explicit contract')
    if spec.get('candidates', HYPERPARAMETERS) != HYPERPARAMETERS:
        raise ValueError('Hyperparameters differ from frozen two-candidate plan')

def prepare_cache(spec_path):
    spec=read_json(spec_path)
    validate_fit_spec(spec)
    seed_everything(spec['seed'],int(spec.get('cpu_threads',2)))
    require_hash(spec['train_rows'],spec['train_rows_sha256'])
    require_hash(spec['validation_rows'],spec['validation_rows_sha256'])
    val_scope=spec['regime'] if spec['validation_scope']=='same_as_regime' else spec['validation_scope']
    rows_train=filter_scope(read_jsonl(spec['train_rows']),spec['regime'])
    rows_val=filter_scope(read_jsonl(spec['validation_rows']),val_scope)
    adapter=load_adapter(spec['method_id'],spec.get('methods_root'))
    key=str(spec['split_id'])+'-'+spec['regime']+'-'+spec['method_id']
    start=time.time()
    root=Path(spec['cache_root'])
    train=cache_items(adapter,spec['method_id'],rows_train,root/(key+'-train.pkl'))
    validation=cache_items(adapter,spec['method_id'],rows_val,root/(key+'-validation-'+spec['validation_scope']+'.pkl'))
    return dict(status='ready',train_n=len(train),validation_n=len(validation),seconds=time.time()-start,
                method_id=spec['method_id'],split_id=spec['split_id'],regime=spec['regime'],
                adapter_tree_sha256=adapter_tree_hash(adapter),label_scope='train_and_validation_only')

def train_candidate(spec_path, candidate_index):
    spec = read_json(spec_path)
    validate_fit_spec(spec)
    if candidate_index not in (0, 1):
        raise ValueError('Candidate must be 0 or 1')
    candidate = HYPERPARAMETERS[candidate_index]
    output = Path(spec['run_root']) / ('candidate-' + str(candidate_index))
    output.mkdir(parents=True, exist_ok=False)
    started = time.time()
    write_json(output/'started.json', dict(pid=os.getpid(), unix_time=started, spec=spec,
                                         spec_sha256=sha_file(spec_path), candidate=candidate,
                                         stage='fit_train_and_validation_only'))
    try:
        device_receipt=configure_device(spec)
        seed_everything(spec['seed'], int(spec.get('cpu_threads', 2)))
        device = device_receipt['device']
        require_hash(spec['train_rows'], spec['train_rows_sha256'])
        require_hash(spec['validation_rows'], spec['validation_rows_sha256'])
        train_rows = filter_scope(read_jsonl(spec['train_rows']), spec['regime'])
        effective_val_scope = spec['regime'] if spec['validation_scope']=='same_as_regime' else spec['validation_scope']
        val_rows = filter_scope(read_jsonl(spec['validation_rows']), effective_val_scope)
        if not train_rows or not val_rows:
            raise ValueError('Empty training or validation after explicit scope filtering')
        if {r['record_id'] for r in train_rows} & {r['record_id'] for r in val_rows}:
            raise ValueError('Record ID leakage train/validation')
        adapter = load_adapter(spec['method_id'], spec.get('methods_root'))
        cache_root = Path(spec['cache_root'])
        cache_key = str(spec['split_id']) + '-' + spec['regime'] + '-' + spec['method_id']
        train_items = cache_items(adapter, spec['method_id'], train_rows, cache_root/(cache_key+'-train.pkl'))
        val_items = cache_items(adapter, spec['method_id'], val_rows,
                                cache_root/(cache_key+'-validation-'+spec['validation_scope']+'.pkl'))
        model = native_model(adapter, spec['method_id']).to(device=device, dtype=torch.float32)
        optimizer = torch.optim.Adam(model.parameters(), lr=candidate['learning_rate'], weight_decay=candidate['weight_decay'])
        best_mae = float('inf')
        best_epoch = None
        stale = 0
        rng = np.random.default_rng(spec['seed'])
        batch_size = int(spec['batch_size'])
        accumulation = int(spec['gradient_accumulation'])
        with (output/'epochs.jsonl').open('w', encoding='utf-8') as epoch_log:
            for epoch in range(int(spec['max_epochs'])):
                epoch_started = time.time()
                model.train()
                optimizer.zero_grad(set_to_none=True)
                order = rng.permutation(len(train_items)).tolist()
                minibatches = [order[i:i+batch_size] for i in range(0, len(order), batch_size)]
                loss_sum = 0.0
                count = 0
                for group_start in range(0, len(minibatches), accumulation):
                    group = minibatches[group_start:group_start+accumulation]
                    denominator = sum(len(indices) for indices in group)
                    for indices in group:
                        batch = adapter.collate([train_items[i] for i in indices])
                        targets = adapter.batch_targets(batch).to(device=device, dtype=torch.float32)
                        pred = adapter.predict(model, batch, device)
                        loss = torch.nn.functional.mse_loss(pred, targets, reduction='sum')
                        if not torch.isfinite(loss):
                            raise FloatingPointError('Nonfinite train loss')
                        (loss/denominator).backward()
                        loss_sum += float(loss.detach().cpu())
                        count += len(indices)
                    for parameter in model.parameters():
                        if parameter.grad is not None and not torch.isfinite(parameter.grad).all():
                            raise FloatingPointError('Nonfinite gradient')
                    optimizer.step()
                    optimizer.zero_grad(set_to_none=True)
                values = predict_rows(adapter, model, val_items, device, 1 if spec['method_id']=='MRBDTA' else batch_size)
                metrics = grouped_metrics(val_rows, values)
                mae = metrics['all']['MAE']
                improved = mae < best_mae
                if improved:
                    best_mae, best_epoch, stale = mae, epoch, 0
                    checkpoint = dict(model_state=model.state_dict(), method_id=spec['method_id'], seed=spec['seed'],
                                      candidate_index=candidate_index, candidate=candidate, best_epoch=epoch,
                                      best_validation_MAE=mae, fit_spec_sha256=sha_file(spec_path),
                                      adapter_tree_sha256=adapter_tree_hash(adapter),
                                      model_architecture='frozen_author_default', y_standardization=None)
                    torch.save(checkpoint, output/'best.pt')
                    write_jsonl(output/'best-validation-predictions.jsonl', prediction_rows(val_rows, values))
                    write_json(output/'best-validation-metrics.json', metrics)
                else:
                    stale += 1
                entry = dict(epoch=epoch, train_MSE=loss_sum/count, train_n=count, validation=metrics,
                             improved=improved, best_epoch=best_epoch, seconds=time.time()-epoch_started)
                epoch_log.write(json.dumps(entry, allow_nan=False)+'\n')
                epoch_log.flush()
                if stale >= int(spec['patience']):
                    break
        complete = dict(status='complete', method_id=spec['method_id'], split_id=spec['split_id'],
                        regime=spec['regime'], seed=spec['seed'], candidate_index=candidate_index,
                        hyperparameters=candidate, best_validation_MAE=best_mae, best_epoch=best_epoch,
                        train_n=len(train_rows), validation_n=len(val_rows), validation_scope=spec['validation_scope'],
                        effective_validation_scope=effective_val_scope,
                        checkpoint_sha256=sha_file(output/'best.pt'), fit_spec_sha256=sha_file(spec_path),
                        validation_predictions_sha256=sha_file(output/'best-validation-predictions.jsonl'),
                        adapter_tree_sha256=adapter_tree_hash(adapter),
                        runner_sha256=sha_file(__file__),
                        device_receipt=device_receipt,
                        elapsed_seconds=time.time()-started, test_label_reads=0, external_label_reads=0,
                        procedural_holdout_boundary='separate files and fit entrypoint; not an OS security guarantee')
        write_json(output/'complete.json', complete)
        return complete
    except BaseException as error:
        write_json(output/'failed.json', dict(status='failed', error=repr(error), elapsed_seconds=time.time()-started))
        raise

def select_candidate(spec_path):
    spec = read_json(spec_path)
    validate_fit_spec(spec)
    output = Path(spec['run_root'])
    target = output/'selection.json'
    if target.exists():
        raise FileExistsError('Frozen selection already exists: '+str(target))
    candidates = []
    for index in (0, 1):
        folder = output/('candidate-'+str(index))
        complete = read_json(folder/'complete.json')
        if complete['status'] != 'complete' or complete['fit_spec_sha256'] != sha_file(spec_path):
            raise ValueError('Candidate incomplete or wrong frozen spec')
        require_hash(folder/'best.pt', complete['checkpoint_sha256'])
        require_hash(folder/'best-validation-predictions.jsonl', complete['validation_predictions_sha256'])
        candidates.append(complete)
    best = min(candidates, key=lambda row: (row['best_validation_MAE'], row['candidate_index']))
    if len({row['adapter_tree_sha256'] for row in candidates})!=1:
        raise ValueError('Candidate adapters changed between the two fits')
    selection = dict(status='frozen', method_id=spec['method_id'], split_id=spec['split_id'], regime=spec['regime'],
                     seed=spec['seed'], candidate_index=best['candidate_index'],
                     checkpoint=str(output/('candidate-'+str(best['candidate_index']))/'best.pt'),
                     checkpoint_sha256=best['checkpoint_sha256'], fit_spec_sha256=sha_file(spec_path),
                     candidates=candidates, selection_metric='validation_MAE', tie_break='lower_candidate_index',
                     frozen_unix_time=time.time(), holdout_metrics_consulted=False)
    write_json(target, selection)
    return selection

def score_holdout(selection_path, holdout_spec_path):
    selection = read_json(selection_path)
    if selection['status'] != 'frozen':
        raise ValueError('Select and freeze before opening holdout labels')
    require_hash(selection['checkpoint'], selection['checkpoint_sha256'])
    holdout = read_json(holdout_spec_path)
    if holdout.get('selection_barrier_path'):
        barrier=read_json(holdout['selection_barrier_path'])
        if barrier['status']!='all_selections_frozen':raise ValueError('Global selection barrier incomplete')
        selected_hash=sha_file(selection_path)
        if not any(entry['sha256']==selected_hash for entry in barrier['selections']):
            raise ValueError('Selection not in global pre-holdout freeze')
    device_receipt=configure_device(holdout)
    if holdout['split_id'] != selection['split_id']:
        raise ValueError('Wrong holdout split')
    require_hash(holdout['input_rows'], holdout['input_rows_sha256'])
    require_hash(holdout['label_rows'], holdout['label_rows_sha256'])
    output = Path(holdout['output_root'])/selection['method_id']/selection['regime']/('seed-'+str(selection['seed']))
    output.mkdir(parents=True, exist_ok=False)
    seed_everything(selection['seed'], int(holdout.get('cpu_threads', 2)))
    input_rows = read_jsonl(holdout['input_rows'])
    if any('pKd' in row for row in input_rows):
        raise ValueError('Holdout input rows must not contain labels')
    desired_ids={row['record_id'] for row in input_rows}
    labels = {row['record_id']: row['pKd'] for row in read_jsonl(holdout['label_rows']) if row['record_id'] in desired_ids}
    if len(labels) != len(input_rows) or set(labels) != {r['record_id'] for r in input_rows}:
        raise ValueError('Holdout label/input identity mismatch')
    # First and only holdout-label access entrypoint. No optimizer or selection runs here.
    rows = [dict(row, pKd=float(labels[row['record_id']])) for row in input_rows]
    adapter = load_adapter(selection['method_id'], holdout.get('methods_root'))
    model = native_model(adapter, selection['method_id'])
    checkpoint = torch.load(selection['checkpoint'], map_location='cpu', weights_only=True)
    if checkpoint['adapter_tree_sha256']!=adapter_tree_hash(adapter):
        raise ValueError('Scoring adapter differs from trained adapter')
    model.load_state_dict(checkpoint['model_state'], strict=True)
    device = device_receipt['device']
    model.to(device=device, dtype=torch.float32)
    items = [encode(adapter, selection['method_id'], row) for row in rows]
    batch_size = 1 if selection['method_id'] == 'MRBDTA' else int(holdout.get('batch_size', 32))
    values = predict_rows(adapter, model, items, device, batch_size)
    write_jsonl(output/'predictions.jsonl', prediction_rows(rows, values))
    metrics = grouped_metrics(rows, values)
    write_json(output/'metrics.json', metrics)
    receipt = dict(status='complete', stage='post-selection-score-only', method_id=selection['method_id'],
                   regime=selection['regime'], seed=selection['seed'], split_id=selection['split_id'],
                   holdout_id=holdout['holdout_id'], n=len(rows), metrics=metrics,
                   selection_sha256=sha_file(selection_path), checkpoint_sha256=selection['checkpoint_sha256'],
                   holdout_spec_sha256=sha_file(holdout_spec_path),
                   predictions_sha256=sha_file(output/'predictions.jsonl'),
                   no_parameter_updates=True, scientific_external_status=holdout.get('scientific_external_status'))
    receipt['device_receipt']=device_receipt
    write_json(output/'complete.json', receipt)
    return receipt

def freeze_barrier(index_path,output_path):
    index=read_json(index_path)
    entries=index['per_seed_selections']
    if len(entries)!=200 or index['total_fits']!=400:raise ValueError('Expected complete 400-fit/200-selection plan')
    if Path(output_path).exists():raise FileExistsError('Selection barrier already frozen')
    selections=[]
    identities=set()
    for entry in entries:
        selection=read_json(entry['selection_path'])
        identity=tuple(selection[key] for key in ('method_id','split_id','regime','seed'))
        if identity in identities:raise ValueError('Repeated selection identity in barrier')
        identities.add(identity)
        if selection['status']!='frozen' or selection['holdout_metrics_consulted']:
            raise ValueError('Invalid candidate selection')
        require_hash(selection['checkpoint'],selection['checkpoint_sha256'])
        if selection['fit_spec_sha256']!=sha_file(entry['spec_path']):raise ValueError('Selection/spec mismatch')
        selections.append(dict(path=entry['selection_path'],sha256=sha_file(entry['selection_path'])))
    methods={identity[0] for identity in identities}
    panels={identity[1] for identity in identities}
    expected={(method,panel,regime,seed) for method in FORMAL_METHOD_IDS for panel in panels
              for regime in ('NC_only','standard_only') for seed in range(10)}
    if methods!=set(FORMAL_METHOD_IDS) or len(panels)!=2 or identities!=expected:
        raise ValueError('Barrier is not the complete five-method/two-panel/two-regime/ten-seed grid')
    barrier=dict(status='all_selections_frozen',selection_count=200,candidate_fit_count=400,
                 execution_index_sha256=sha_file(index_path),selections=selections,
                 frozen_unix_time=time.time(),holdout_label_reads=0)
    write_json(output_path,barrier)
    return barrier

def prepare_panel(observations_path, split_path, output_root):
    """Split file must map train/validation/test to explicit lists of record IDs."""
    split = read_json(split_path)
    mapping = {row['record_id']: row for row in read_jsonl(observations_path)}
    partitions = {part: split[part] for part in ('train', 'validation', 'test')}
    if any(len(ids) != len(set(ids)) for ids in partitions.values()):
        raise ValueError('Duplicate partition IDs')
    sets = [set(partitions[key]) for key in ('train', 'validation', 'test')]
    if sets[0]&sets[1] or sets[0]&sets[2] or sets[1]&sets[2]:
        raise ValueError('Partition record identity overlap')
    if not set.union(*sets) <= set(mapping):
        raise ValueError('Unknown split IDs')
    output = Path(output_root)
    output.mkdir(parents=True, exist_ok=False)
    for part in ('train', 'validation'):
        write_jsonl(output/(part+'.jsonl'), [mapping[rid] for rid in partitions[part]])
    held = [mapping[rid] for rid in partitions['test']]
    write_jsonl(output/'test-inputs.jsonl', [{k:v for k,v in row.items() if k!='pKd'} for row in held])
    write_jsonl(output/'sealed-test-labels.jsonl', [dict(record_id=row['record_id'], pKd=row['pKd']) for row in held])
    manifest = dict(split_id=split['split_id'], observations_sha256=sha_file(observations_path),
                    split_sha256=sha_file(split_path), counts={key:len(value) for key,value in partitions.items()},
                    files={name:sha_file(output/name) for name in ('train.jsonl','validation.jsonl','test-inputs.jsonl','sealed-test-labels.jsonl')},
                    boundary='procedural separation, not OS sandboxing')
    write_json(output/'panel-manifest.json', manifest)
    return manifest

def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('prepare')
    prepare.add_argument('--observations', required=True)
    prepare.add_argument('--split', required=True)
    prepare.add_argument('--output', required=True)
    fit = commands.add_parser('fit')
    fit.add_argument('--spec', required=True)
    fit.add_argument('--candidate-index', type=int, required=True)
    cache = commands.add_parser('cache')
    cache.add_argument('--spec',required=True)
    select = commands.add_parser('select')
    select.add_argument('--spec', required=True)
    score = commands.add_parser('score')
    score.add_argument('--selection', required=True)
    score.add_argument('--holdout-spec', required=True)
    barrier=commands.add_parser('freeze-barrier')
    barrier.add_argument('--index',required=True)
    barrier.add_argument('--output',required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        result = prepare_panel(args.observations, args.split, args.output)
    elif args.command == 'fit':
        result = train_candidate(args.spec, args.candidate_index)
    elif args.command == 'select':
        result = select_candidate(args.spec)
    elif args.command == 'cache':
        result = prepare_cache(args.spec)
    elif args.command == 'freeze-barrier':
        result=freeze_barrier(args.index,args.output)
    else:
        result = score_holdout(args.selection, args.holdout_spec)
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))

if __name__ == '__main__':
    main()
