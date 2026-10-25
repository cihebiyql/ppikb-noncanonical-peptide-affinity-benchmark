"""Expanded-data PeptideCLM2025-SPEfix + unchanged ordinary MLP pKd adaptation; resource owner launches jobs.

All learnable chemical parameters are trained; original sinusoidal constants and ESM vectors stay fixed.
Candidate training and validation-only selection/TEST are separate entry modes.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import importlib
import importlib.util
import json
import os
import random
import sys
import time
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_adapter import PairRegressor, load_pair_model, prepare_tokenizer, tokenize_safely, chemical_canary, COUNTS
from dataset_binding import validate_frozen_files, validate_target_view

os.environ.setdefault('CUBLAS_WORKSPACE_CONFIG', ':4096:8')
os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')
os.environ.setdefault('HF_HUB_OFFLINE', '1')
os.environ.setdefault('TRANSFORMERS_OFFLINE', '1')

import numpy as np
import pandas as pd
import torch
from torch import nn
from shared_metrics import evaluate_partition, metrics, now, prediction_file, read_views, sha, validate_frame, write_json

ROOT = Path(__file__).resolve().parents[2]
HEAD_SOURCE = ROOT / 'baselines/chemical-encoder-benchmark-20261024-v1'
sys.path.insert(0, str(HEAD_SOURCE))
from chemical_features import ChemicalFeatures

LRS = (1e-5, 3e-5)
SETTINGS = {'batch_size': 8, 'max_epochs': 30, 'patience': 5, 'weight_decay': 0.01,
            'gradient_clip_norm': 1.0, 'pooling': 'adapted_masked_mean_including_cls_sep', 'dtype': 'float32',
            'tf32': False, 'max_tokens_including_special': 768, 'head': [1088, 256, 1], 'dropout': 0.1,
            'pretraining_token_prediction_head_removed': True, 'parameter_counts': COUNTS,
            'fixed_native_position_parameter': 'encoder.embed_positions.weight',
            'common_reference_manifest_sha256': '93cdc000433e3c0babd7a5b7e183acd2fbe25649f4d2e7d5d95f5f0ad5aacae4'}


def import_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def seed_all(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def configure(threads):
    torch.set_num_threads(threads)
    torch.set_num_interop_threads(1)
    torch.set_float32_matmul_precision('highest')
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True


def rng_state(device):
    state = np.random.get_state()
    return {'python': random.getstate(), 'numpy': [state[0], state[1].tolist(), state[2], state[3], state[4]],
            'torch_cpu': torch.get_rng_state(),
            'torch_cuda': torch.cuda.get_rng_state_all() if device.type == 'cuda' else []}


def restore_rng(state, device):
    random.setstate(state['python'])
    n = state['numpy']
    np.random.set_state((n[0], np.asarray(n[1], dtype=np.uint32), n[2], n[3], n[4]))
    torch.set_rng_state(state['torch_cpu'])
    if device.type == 'cuda':
        torch.cuda.set_rng_state_all(state['torch_cuda'])


def parameter_hash(model):
    digest = hashlib.sha256()
    for name, value in sorted(model.state_dict().items()):
        digest.update(name.encode())
        digest.update(value.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def load_model(model_dir, identity, seed, device):
    seed_all(seed)
    return load_pair_model(model_dir, identity, device)


def prepare(args):
    validate_frozen_files(args.manifest, args.feature_spec)
    manifest = json.loads(args.manifest.read_text(encoding='utf-8-sig'))
    views = read_views(manifest)
    if manifest.get('model_cohort', {}).get('schema') != 'chemical-encoder.common-input-cohort.v1':
        raise ValueError('A newly frozen common chemical/Morgan input cohort is required')
    selected = [v for v in views if v['id'] == args.view]
    if len(selected) != 1 or '_target_' not in args.view:
        raise ValueError('Only the declared strict target-global view is accepted')
    view = selected[0]
    if view.get('endpoint') != 'pKd' or view.get('task') != 'affinity' or view.get('status') not in ('frozen', 'ready', 'model_ready'):
        raise ValueError('Full fine-tuning is restricted to ready point-pKd affinity')
    source = Path(view.get('path') or view['csv_path'])
    if not source.is_absolute():
        source = args.manifest.parent / source
    if sha(source) != view['sha256']:
        raise ValueError('Frozen cohort CSV changed')
    validate_target_view(view, sha(source))
    frame = validate_frame(pd.read_csv(source, keep_default_na=False, float_precision='round_trip'), view)
    if 'label_kind' in frame and set(frame.label_kind) != {'experimental_Kd_point'}:
        raise ValueError('Only measured point Kd labels are permitted')
    features = ChemicalFeatures(args.feature_spec)
    if features.chemistry_mode != 'cached_encoder' or features.protein_mode != 'frozen_esm2' or features.protein_dimension != 320:
        raise ValueError('Frozen ESM320 target and actual chemical encoder specification required')
    cohort_specs = manifest['model_cohort']['feature_specifications']
    if sha(args.feature_spec) not in {x['sha256'] for x in cohort_specs}:
        raise ValueError('Feature specification is outside common-cohort freeze')
    extractor = ROOT / 'methods/chemical-encoders-20261025-v3-peptideclm2025-spefix/load_peptideclm2025_spefix.py'
    tokenizer, identity = prepare_tokenizer(args.model_dir, args.asset_receipt, features.audit.get('model_identity'))
    if manifest['model_cohort'].get('source_global_manifest_sha256') != '971a1feaafeae45e0e4f29092b80405419d8d47100b0a3e5e936c82ecc0e44c0':
        raise ValueError('Use the frozen v3 homology source, not the earlier leaking split')
    if view['sha256'] != 'c3d8f4e42600f0c762bb9d2d24595a32c8f13de7a1f5018d59047d241dd8525a':
        raise ValueError('Use the approved93cdc expanded common-cohort CSV; do not resplit or refilter')
    tokenized, protein = {}, []
    for row in frame.to_dict('records'):
        if features.coverage_reason(row, 'affinity') is not None:
            raise ValueError('Common cohort includes an unsupported input; do not silently filter')
        smiles = row.get('smiles') or row.get('peptide_smiles')
        key = hashlib.sha256(smiles.encode()).hexdigest()
        if key not in tokenized:
            encoded = tokenize_safely(tokenizer, smiles)
            ids = encoded['input_ids']
            tokenized[key] = ids
        protein.append(features.target(row['target_sequence']))
    tokens = [tokenized[hashlib.sha256((r.get('smiles') or r.get('peptide_smiles')).encode()).hexdigest()]
              for r in frame.to_dict('records')]
    protein = np.stack(protein).astype(np.float32)
    parts = {p: np.flatnonzero(frame.split.to_numpy() == p) for p in ('train', 'validation', 'test', 'external')}
    if {k: len(v) for k, v in parts.items()} != {'train': 531, 'validation': 570, 'test': 685, 'external': 0}:
        raise ValueError('This expanded preparation is restricted to approved531/570/685 cohort, without external evaluation')
    base = {'schema': 'chemical-encoder.fullfinetune-contract.v1', 'task_adaptation': True,
            'view_id': args.view, 'endpoint': 'pKd', 'manifest_sha256': sha(args.manifest),
            'input_csv_sha256': sha(source), 'feature_spec_sha256': sha(args.feature_spec),
            'feature_source_sha256': sha(HEAD_SOURCE / 'chemical_features.py'),
            'runner_sha256': sha(__file__), 'metrics_source_sha256': sha(Path(__file__).with_name('shared_metrics.py')),
            'asset_verifier_sha256': sha(extractor), 'model_identity': identity, 'settings': SETTINGS,
            'model_adapter_sha256': sha(Path(__file__).with_name('model_adapter.py')),
            'dataset_binding_sha256': sha(Path(__file__).with_name('dataset_binding.py')),
            'protein_encoder_frozen': True, 'chemical_encoder_frozen': False, 'seed': args.seed,
            'split_counts': {k: len(v) for k, v in parts.items()}, 'torch': str(torch.__version__),
            'numpy': np.__version__, 'device_type': args.device, 'threads': args.threads,
            'python': sys.version,
            'selection': 'validation MAE only; TEST after both candidate results and selection are frozen'}
    return frame, tokens, protein, parts, identity, base


def batch_values(indices, tokens, protein, device):
    length = max(len(tokens[i]) for i in indices)
    ids = torch.zeros((len(indices), length), dtype=torch.long, device=device)
    mask = torch.zeros_like(ids)
    for j, i in enumerate(indices):
        value = tokens[i]
        ids[j, :len(value)] = torch.tensor(value, device=device)
        mask[j, :len(value)] = 1
    return ids, mask, torch.as_tensor(protein[indices], dtype=torch.float32, device=device)


def predict(model, indices, tokens, protein, device, deadline=None):
    model.eval()
    out = []
    with torch.inference_mode():
        for start in range(0, len(indices), 8):
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError('Prediction budget reached before next batch')
            values = model(*batch_values(indices[start:start+8], tokens, protein, device))
            out.extend(values.cpu().numpy().astype(np.float64).tolist())
    result = np.asarray(out, dtype=np.float64)
    if not np.isfinite(result).all():
        raise ValueError('Nonfinite prediction')
    return result


def atomic_checkpoint(path, state, events, kind):
    temporary = path.with_suffix('.pt.tmp')
    torch.save(state, temporary)
    temporary.replace(path)
    digest = sha(path)
    with events.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps({'at': now(), 'kind': kind, 'path': str(path), 'sha256': digest,
                                 'global_steps': state.get('cursor', {}).get('global_steps')}) + '\n')
    return digest


def train_candidate(args, context, started):
    frame, tokens, protein, parts, identity, base = context
    device = torch.device(args.device)
    model = load_model(args.model_dir, identity, args.seed, device)
    initial_hash = parameter_hash(model)
    optimizer = torch.optim.AdamW(model.parameters(), lr=LRS[args.candidate], weight_decay=0.01)
    contract = dict(base, candidate=args.candidate, learning_rate=LRS[args.candidate])
    fingerprint = hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()
    write_json(args.output / 'contract.json', contract)
    cursor = {'epoch': 0, 'next_offset': 0, 'global_steps': 0, 'epoch_loss_sum': 0., 'epoch_rows': 0,
              'best_val_mae': None, 'best_epoch': None, 'stale_epochs': 0, 'history': []}
    best_path, best_sha, validation_path = None, None, None
    if args.resume_checkpoint:
        if not args.resume_sha256 or sha(args.resume_checkpoint) != args.resume_sha256:
            raise ValueError('Resume checkpoint requires exact SHA')
        prior = torch.load(args.resume_checkpoint, map_location='cpu', weights_only=True)
        if prior['fingerprint'] != fingerprint or prior['initial_parameter_sha256'] != initial_hash:
            raise ValueError('Resume science configuration, runtime or initialization differs')
        model.load_state_dict(prior['model'], strict=True)
        optimizer.load_state_dict(prior['optimizer'])
        cursor = prior['cursor']
        best_path, best_sha, validation_path = prior['best_path'], prior['best_sha256'], prior['validation_path']
        if best_path and sha(best_path) != best_sha:
            raise ValueError('Prior best checkpoint changed')
        if validation_path and sha(validation_path) != prior.get('validation_sha256'):
            raise ValueError('Prior best validation predictions changed')
        restore_rng(prior['rng'], device)
        write_json(args.output / 'resume-source.json', {'path': str(args.resume_checkpoint), 'sha256': args.resume_sha256,
                   'cursor': cursor, 'original_files_modified': False})
    events = args.output / 'checkpoint-events.jsonl'
    loss_fn = nn.MSELoss()

    def save_last(status):
        payload = {'schema': 'chemical-encoder.fullfinetune-state.v1', 'fingerprint': fingerprint,
                   'model': model.state_dict(), 'optimizer': optimizer.state_dict(), 'rng': rng_state(device),
                   'cursor': cursor, 'initial_parameter_sha256': initial_hash,
                   'best_path': str(best_path) if best_path else None, 'best_sha256': best_sha,
                   'validation_path': str(validation_path) if validation_path else None,
                   'validation_sha256': sha(validation_path) if validation_path else None, 'status': status}
        last = args.output / 'last.pt'
        digest = atomic_checkpoint(last, payload, events, 'last_' + status)
        return {'path': str(last.resolve()), 'sha256': digest}

    while cursor['epoch'] < 30 and cursor['stale_epochs'] < 5:
        epoch = cursor['epoch']
        generator = torch.Generator().manual_seed(args.seed * 100000 + epoch)
        order = parts['train'][torch.randperm(len(parts['train']), generator=generator).numpy()]
        for offset in range(cursor['next_offset'], len(order), 8):
            if time.monotonic() - started >= args.max_seconds - args.checkpoint_reserve_seconds:
                last = save_last('paused_checkpointed')
                write_json(args.output / 'result.json', {'status': 'paused_checkpointed', 'complete_candidate': False,
                           'contract': contract, 'fingerprint': fingerprint, 'cursor': cursor, 'last_checkpoint': last})
                return 0
            indices = order[offset:offset+8]
            model.train()
            optimizer.zero_grad(set_to_none=True)
            values = model(*batch_values(indices, tokens, protein, device))
            labels = torch.as_tensor(frame.label.to_numpy()[indices], dtype=torch.float32, device=device)
            loss = loss_fn(values, labels)
            if not torch.isfinite(loss):
                raise ValueError('Nonfinite training loss')
            loss.backward()
            if any(p.requires_grad and p.grad is None for p in model.parameters()):
                raise ValueError('A declared trainable parameter did not receive a gradient')
            norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.)
            if not torch.isfinite(norm):
                raise ValueError('Nonfinite gradient norm')
            optimizer.step()
            cursor['next_offset'] = offset + len(indices)
            cursor['global_steps'] += 1
            cursor['epoch_loss_sum'] += float(loss.detach()) * len(indices)
            cursor['epoch_rows'] += len(indices)
        try:
            vp = predict(model, parts['validation'], tokens, protein, device,
                         started + args.max_seconds - args.checkpoint_reserve_seconds)
        except TimeoutError:
            last = save_last('paused_checkpointed')
            write_json(args.output / 'result.json', {'status': 'paused_checkpointed', 'complete_candidate': False,
                       'contract': contract, 'fingerprint': fingerprint, 'cursor': cursor, 'last_checkpoint': last})
            return 0
        vm = metrics(frame.label.to_numpy()[parts['validation']], vp)
        history = {'epoch': epoch+1, 'global_steps': cursor['global_steps'], 'training_rows': cursor['epoch_rows'],
                   'train_mse': cursor['epoch_loss_sum']/cursor['epoch_rows'], 'validation': vm, 'at': now()}
        cursor['history'].append(history)
        with (args.output / 'epochs.jsonl').open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(history, allow_nan=False) + '\n')
        if cursor['best_val_mae'] is None or vm['mae'] < cursor['best_val_mae']:
            cursor.update(best_val_mae=vm['mae'], best_epoch=epoch+1, stale_epochs=0)
            best_path = args.output / 'best.pt'
            best_sha = atomic_checkpoint(best_path, {'model': model.state_dict(), 'fingerprint': fingerprint,
                     'epoch': epoch+1, 'validation_metrics': vm}, events, 'best')
            validation_path = args.output / 'best-validation.csv'
            prediction_file(validation_path, frame.iloc[parts['validation']], vp)
        else:
            cursor['stale_epochs'] += 1
        cursor.update(epoch=epoch+1, next_offset=0, epoch_loss_sum=0., epoch_rows=0)
        last = save_last('epoch_completed')
    last = save_last('completed')
    write_json(args.output / 'result.json', {'status': 'succeeded', 'complete_candidate': True,
               'contract': contract, 'fingerprint': fingerprint, 'initial_parameter_sha256': initial_hash,
               'cursor': cursor, 'best_model_path': str(best_path.resolve()), 'best_model_sha256': best_sha,
               'validation_path': str(Path(validation_path).resolve()), 'validation_sha256': sha(validation_path),
               'last_checkpoint': last, 'test_evaluated': False, 'elapsed_seconds': time.monotonic()-started,
               'trainable_parameters': sum(p.numel() for p in model.parameters() if p.requires_grad)})
    return 0


def select_test(args, context, started):
    frame, tokens, protein, parts, identity, base = context
    candidates = []
    for directory in args.candidate_dir:
        path = directory / 'result.json'
        result = json.loads(path.read_text())
        if result.get('status') != 'succeeded' or result.get('complete_candidate') is not True:
            raise ValueError('Both candidates must finish before selection/TEST')
        contract = dict(result['contract'])
        index, lr = contract.pop('candidate'), contract.pop('learning_rate')
        if contract != base or lr != LRS[index]:
            raise ValueError('Candidate inputs/runtime/configuration differ from frozen selection')
        if sha(result['best_model_path']) != result['best_model_sha256'] or sha(result['validation_path']) != result['validation_sha256']:
            raise ValueError('Candidate artifact changed')
        vp = pd.read_csv(result['validation_path'], float_precision='round_trip')
        reference = frame.iloc[parts['validation']]
        if vp.row_id.tolist() != reference.row_id.tolist() or not np.array_equal(vp.label.to_numpy(), reference.label.to_numpy()):
            raise ValueError('Candidate validation IDs/labels changed')
        score = metrics(vp.label.to_numpy(), vp.prediction.to_numpy())['mae']
        if abs(score-result['cursor']['best_val_mae']) > 1e-12:
            raise ValueError('Saved validation score does not recompute')
        candidates.append((score, index, result, str(path), sha(path)))
    if len(candidates) != 2 or {x[1] for x in candidates} != {0, 1}:
        raise ValueError('Exactly the two fixed learning-rate candidates required')
    if len({x[2]['initial_parameter_sha256'] for x in candidates}) != 1:
        raise ValueError('Same-seed LR candidates did not start identically')
    winner = min(candidates, key=lambda x: (x[0], x[1]))
    selection = {'schema': 'chemical-encoder.fullfinetune-selection.v1', 'frozen_before_test_at': now(),
                 'selected_candidate': winner[1], 'validation_mae': winner[0], 'test_used_for_selection': False,
                 'candidates': [{'path': x[3], 'sha256': x[4], 'candidate': x[1], 'mae': x[0]} for x in candidates]}
    write_json(args.output / 'selection.json', selection)
    model = load_model(args.model_dir, identity, args.seed, torch.device(args.device))
    best = torch.load(winner[2]['best_model_path'], map_location='cpu', weights_only=True)
    model.load_state_dict(best['model'], strict=True)
    result = {'schema': 'chemical-encoder.fullfinetune-result.v1', 'status': 'succeeded', 'contract': base,
              'selected_candidate': winner[1], 'selection_sha256': sha(args.output / 'selection.json'), 'splits': {}}
    for split in ('validation', 'test', 'external'):
        if len(parts[split]):
            prediction = predict(model, parts[split], tokens, protein, torch.device(args.device), started + args.max_seconds)
            local = frame.iloc[parts[split]].reset_index(drop=True)
            result['splits'][split] = evaluate_partition(args.output, split, local, prediction, False)
    write_json(args.output / 'result.json', result)
    return 0


def cost_gate(args, context, started):
    frame, tokens, protein, parts, identity, base = context
    device = torch.device(args.device)
    model = load_model(args.model_dir, identity, args.seed, device)
    tokenizer, _ = prepare_tokenizer(args.model_dir, args.asset_receipt, identity)
    write_json(args.output / 'chemical-canary.json', chemical_canary(model, tokenizer, device))
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-5, weight_decay=0.01)
    if device.type == 'cuda':
        torch.cuda.reset_peak_memory_stats()
    chosen = sorted(parts['train'], key=lambda i: (-len(tokens[i]), frame.iloc[i].row_id))[:8]
    records = []
    for step in range(2):
        if time.monotonic()-started >= args.max_seconds:
            raise TimeoutError('Cost gate budget exhausted')
        model.train()
        optimizer.zero_grad(set_to_none=True)
        prediction = model(*batch_values(chosen, tokens, protein, device))
        loss = nn.functional.mse_loss(prediction, torch.as_tensor(frame.label.to_numpy()[chosen], dtype=torch.float32, device=device))
        loss.backward()
        count = sum(p.numel() for p in model.parameters() if p.grad is not None)
        if count != sum(p.numel() for p in model.parameters() if p.requires_grad):
            raise ValueError('Cost gate did not exercise every declared trainable parameter')
        norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.)
        if not torch.isfinite(loss) or not torch.isfinite(norm):
            raise ValueError('Cost gate nonfinite loss/gradient')
        optimizer.step()
        if device.type == 'cuda':
            torch.cuda.synchronize()
        records.append({'step': step+1, 'loss': float(loss.detach()), 'parameters_with_gradient': count,
                        'batch_rows': len(chosen), 'longest_tokens': max(len(tokens[i]) for i in chosen)})
    write_json(args.output / 'cost.json', {'status': 'succeeded', 'scope': 'two_steps_not_formal_fit',
               'contract': base, 'steps': records, 'elapsed_seconds': time.monotonic()-started,
               'max_cuda_allocated_bytes': torch.cuda.max_memory_allocated() if device.type == 'cuda' else 0,
               'max_cuda_reserved_bytes': torch.cuda.max_memory_reserved() if device.type == 'cuda' else 0,
               'test_rows_evaluated': 0, 'formal_candidates_completed': 0})
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['train', 'select-test', 'cost'], required=True)
    for name in ('manifest', 'feature-spec', 'model-dir', 'asset-receipt', 'output'):
        parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--view', required=True)
    parser.add_argument('--seed', type=int, choices=range(10), required=True)
    parser.add_argument('--candidate', type=int, choices=(0, 1))
    parser.add_argument('--candidate-dir', type=Path, action='append', default=[])
    parser.add_argument('--resume-checkpoint', type=Path)
    parser.add_argument('--resume-sha256')
    parser.add_argument('--device', choices=['cpu', 'cuda'], default='cpu')
    parser.add_argument('--threads', type=int, choices=(1, 2), default=2)
    parser.add_argument('--max-seconds', type=int, required=True)
    parser.add_argument('--checkpoint-reserve-seconds', type=int, default=60)
    args = parser.parse_args()
    if args.mode == 'train' and args.candidate is None:
        parser.error('Train requires candidate index')
    if args.max_seconds <= 0 or args.checkpoint_reserve_seconds < 0 or args.checkpoint_reserve_seconds >= args.max_seconds:
        parser.error('Positive finite budget with checkpoint reserve required')
    if args.output.exists():
        parser.error('Use a new run/segment directory; old partial outputs are immutable')
    args.output.mkdir(parents=True)
    started = time.monotonic()
    configure(args.threads)
    write_json(args.output / 'started.json', {'at': now(), 'mode': args.mode, 'seed': args.seed,
               'max_seconds': args.max_seconds, 'args': {k: str(v) if isinstance(v, Path) else
                 [str(x) for x in v] if isinstance(v, list) else v for k, v in vars(args).items()}})
    context = prepare(args)
    if args.mode == 'cost':
        return cost_gate(args, context, started)
    if args.mode == 'select-test':
        return select_test(args, context, started)
    return train_candidate(args, context, started)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'status': 'failed', 'error': type(error).__name__ + ': ' + str(error)}), file=sys.stderr)
        raise
