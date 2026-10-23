"""Original four-expert UniAIR gate training on the frozen benign HER2 view.

Released expert parameters remain frozen. Original train-mode expert buffers and
dropout remain active, and all buffers are retained in every gate checkpoint.
This is a conditional single-context benchmark, not the original paper table.
"""
import argparse
import copy
import csv
import datetime as dt
import gc
import hashlib
import json
import math
import os
from pathlib import Path
import random
import sys
import time

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def state_sha(state):
    h = hashlib.sha256()
    for key, value in sorted(state.items()):
        h.update(key.encode())
        h.update(str(value.dtype).encode())
        h.update(str(tuple(value.shape)).encode())
        h.update(value.detach().cpu().contiguous().numpy().tobytes())
    return h.hexdigest()

def batch_groups(indices, size):
    """Keep original tensor ranks: merge a singleton tail with its prior batch."""
    groups = [indices[i:i + size] for i in range(0, len(indices), size)]
    if len(groups) > 1 and len(groups[-1]) == 1:
        groups[-2].extend(groups.pop())
    assert all((len(group) >= 2 for group in groups))
    assert [i for group in groups for i in group] == indices
    return groups

def main():
    CPU_epoch_main_entry = time.monotonic()
    CPU_epoch_phases = []

    def CPU_epoch_phase(name, steps=0):
        row = {'CPU_epoch_phase': name, 'Adam_steps': steps, 'wall_epoch': time.time(), 'elapsed_main_seconds': time.monotonic() - CPU_epoch_main_entry}
        CPU_epoch_phases.append(row)
        print(json.dumps(row), flush=True)
    CPU_epoch_phase('worker_entry')
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('method-root', 'source-manifest', 'input', 'cache', 'asset-manifest', 'protocol', 'output', 'native-canary-proof'):
        p.add_argument('--' + name, type=Path, required=True)
    for name in ('input-sha', 'cache-sha', 'protocol-sha', 'native-canary-proof-sha'):
        p.add_argument('--' + name, required=True)
    p.add_argument('--seed', type=int, choices=range(10), required=True)
    p.add_argument('--phase', choices=['epoch_canary', 'formal'], required=True)
    p.add_argument('--gpu-memory-gib', type=float, required=True)
    p.add_argument('--validation', type=Path, required=True)
    a = p.parse_args()
    assert a.phase == 'epoch_canary'
    c = a.method_root / 'continuation-20261023'
    sys.path.insert(0, str(c))
    admission = json.loads(a.validation.read_text(encoding='utf-8'))
    assert admission['valid_for_execution'] is True
    for path, expected in ((a.input, a.input_sha), (a.cache, a.cache_sha), (a.protocol, a.protocol_sha), (a.native_canary_proof, a.native_canary_proof_sha)):
        assert sha(path) == expected, 'Frozen asset changed: ' + str(path)
    canary = json.loads(a.native_canary_proof.read_text())
    assert canary['original_UniAIR_MoFPE_forward'] and canary['all_four_original_experts']
    assert canary['optimizer_steps'] == 1 and canary['gate_parameters_changed']
    assert canary['expert_buffers_retained'] and canary['test_rows_accessed_for_prediction'] == 0
    source = c / 'native-full-source-v7'
    for item in json.loads(a.source_manifest.read_text())['files']:
        assert sha(source / item['relative_path']) == item['sha256']
    assert canary['source_manifest_sha256'] == sha(a.source_manifest)
    for item in json.loads(a.asset_manifest.read_text())['files']:
        assert sha(item['path']) == item['sha256']
    protocol = json.loads(a.protocol.read_text())
    assert protocol['seeds'] == list(range(10)) and protocol['max_epochs'] == 30
    assert protocol['batch_size'] == 8 and protocol['fix_backbone'] is True
    sys.path.insert(0, str(a.method_root / 'rde-vendor'))
    sys.path.insert(0, str(source))
    import numpy as np
    import pandas as pd
    import torch
    from easydict import EasyDict
    from scipy.stats import pearsonr, spearmanr
    from data.pdbredo_dataset import PaddingCollate
    from models.encoders.RDE.rde_ddg import DDG_RDE_Network
    from models.encoders.PPIformer.ppiformer import PPIformer
    from models.encoders.ESSM.model import ESSM
    from models.encoders.Gearbind.gearbind import BindModel
    from models.encoders.UniAIR.model import UniAIR
    from utils.metrics import cal_weighted_loss
    torch.set_num_threads(16)
    torch.set_num_interop_threads(1)
    torch.set_float32_matmul_precision('high')
    torch.hub.set_dir('<REMOTE_USER_DATA_ROOT>/.cache/torch/hub')
    assert os.environ.get('CUDA_VISIBLE_DEVICES') == '' and torch.cuda.device_count() == 0
    assert a.gpu_memory_gib == 0
    frame = pd.read_csv(a.input)
    assert len(frame) == 419 and frame['split'].value_counts().to_dict() == {'train': 293, 'validation': 63, 'test': 63}
    assert set(frame['Protein']) == {'1n8z'}
    cache = torch.load(a.cache, map_location='cpu', weights_only=False)
    assert cache['row_ids'] == frame['row_id'].tolist() and cache['input_sha256'] == a.input_sha
    assert cache['learned_models_loaded'] == 0 and (not cache['learned_representation_cache'])
    train = frame.index[frame['split'] == 'train'].tolist()
    val = frame.index[frame['split'] == 'validation'].tolist()
    test = frame.index[frame['split'] == 'test'].tolist()
    a.output.mkdir(parents=True, exist_ok=False)
    (a.output / 'own-current-contract-admission.json').write_text(json.dumps(admission, indent=2) + '\n')
    paths = {'gearbind': [str(c / 'official-native-assets-small-v1/expert_ckpts/gearbind/gearbind_fold0.ckpt')], 'rde': [str(a.method_root / 'checkpoints/expert_ckpts/rde/rde_fold0.ckpt')], 'ppiformer': [str(c / 'official-native-assets-small-v1/expert_ckpts/ppiformer/ppiformer_fold0.ckpt')], 'essm': [str(c / 'official-native-assets-essm0-v1/expert_ckpts/essm/essm_fold0.ckpt')]}
    collate = PaddingCollate()
    started = time.monotonic()

    def move(value):
        if isinstance(value, torch.Tensor):
            return value.to('cpu')
        if isinstance(value, dict):
            return {k: move(v) for k, v in value.items()}
        if isinstance(value, list):
            return [move(v) for v in value]
        if isinstance(value, tuple):
            return tuple((move(v) for v in value))
        return value

    def batches(indices):
        for subset in batch_groups(indices, protocol['batch_size']):
            yield (subset, move(collate([copy.deepcopy(cache['items'][i]) for i in subset])))

    def construct():
        random.seed(a.seed)
        np.random.seed(a.seed)
        torch.manual_seed(a.seed)
        torch.cuda.manual_seed_all(a.seed)
        model = UniAIR(model_dirs=paths, encoder=EasyDict(node_feat_dim=128, pair_feat_dim=64, num_layers=3, num_heads=12), fold=0, fix_backbone=True).to('cpu')
        assert sum((p.numel() for p in model.parameters())) == 684421861
        assert sum((p.numel() for p in model.parameters() if p.requires_grad)) == 2046380
        assert all((not p.requires_grad for p in model.pretrained_models.parameters()))
        return model

    def gate_state(model):
        return {k: v.detach().cpu().clone() for k, v in model.named_parameters() if v.requires_grad}

    def buffer_state(model):
        return {k: v.detach().cpu().clone() for k, v in model.named_buffers()}

    def restore(model, checkpoint):
        expected = {k for k, p in model.named_parameters() if p.requires_grad} | {k for k, _ in model.named_buffers()}
        values = {**checkpoint['gate_state_dict'], **checkpoint['all_native_buffers']}
        assert set(values) == expected
        destinations = {**dict(model.named_parameters()), **dict(model.named_buffers())}
        with torch.no_grad():
            for key, value in values.items():
                assert tuple(destinations[key].shape) == tuple(value.shape)
                destinations[key].copy_(value)

    def evaluate(model, indices):
        model.eval()
        records = []
        loss_sum = 0.0
        with torch.no_grad():
            for subset, batch in batches(indices):
                pred = model.inference(batch)
                loss = cal_weighted_loss(pred, batch['labels'], batch['label_mask'], ['regression'], [1.0])
                loss_sum += float(loss) * len(subset)
                for index, prediction in zip(subset, pred['y_pred'].reshape(-1).cpu().tolist()):
                    assert math.isfinite(prediction)
                    row = frame.iloc[index]
                    records.append({'row_id': row['row_id'], 'component_id': row['variant_component_id'], 'label': float(row['DDG']), 'prediction': prediction, 'split': row['split'], 'seed': a.seed, 'endpoint': 'uncalibrated_author_DDG'})
        return (loss_sum / len(indices), sum((abs(r['label'] - r['prediction']) for r in records)) / len(records), records)

    def save_csv(path, rows):
        with path.open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n')
            writer.writeheader()
            writer.writerows(rows)
    CPU_epoch_phase('inputs_ready_before_constructor')
    candidates = []
    for candidate, lr in enumerate(protocol['optimizer']['lr_candidates'] if a.phase == 'formal' else [0.0003]):
        model = construct()
        CPU_epoch_phase('constructor_ready')
        params = [p for p in model.parameters() if p.requires_grad]
        initial = state_sha(gate_state(model))
        initial_buffers = state_sha(buffer_state(model))
        optimizer = torch.optim.Adam(params, lr=lr, betas=(0.9, 0.999), weight_decay=0)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.8, patience=5, min_lr=1e-06)
        folder = a.output / f'candidate-{candidate:02d}'
        folder.mkdir()
        checkpoint_path = folder / 'best-checkpoint.pt'
        rng = np.random.default_rng(a.seed)
        history = []
        best = math.inf
        stale = 0
        steps = 0
        first_gradient = None
        for epoch in range(1, (30 if a.phase == 'formal' else 1) + 1):
            model.train()
            order = rng.permutation(train).tolist()
            total = 0.0
            for subset, batch in batches(order):
                optimizer.zero_grad(set_to_none=True)
                pred = model.inference(batch)
                loss = cal_weighted_loss(pred, batch['labels'], batch['label_mask'], ['regression'], [1.0])
                assert torch.isfinite(loss)
                if steps == 0:
                    expected = ((pred['y_pred'].reshape(-1) - batch['labels'].reshape(-1)) ** 2).mean()
                    torch.testing.assert_close(loss, expected, atol=1e-06, rtol=1e-06)
                loss.backward()
                assert all((p.grad is None or torch.isfinite(p.grad).all() for p in params))
                if first_gradient is None:
                    first_gradient = float(sum((p.grad.detach().square().sum() for p in params if p.grad is not None)).sqrt())
                    assert first_gradient > 0
                optimizer.step()
                steps += 1
                total += float(loss.detach()) * len(subset)
                CPU_epoch_phase('Adam_step_completed', steps)
            CPU_epoch_phase('validation_start', steps)
            val_loss, val_mae, _ = evaluate(model, val)
            scheduler.step(val_loss)
            CPU_epoch_phase('validation_completed', steps)
            info = {'epoch': epoch, 'train_native_MSE': total / len(train), 'validation_native_MSE': val_loss, 'validation_forward_MAE': val_mae, 'lr': optimizer.param_groups[0]['lr'], 'optimizer_steps': steps}
            history.append(info)
            if val_loss < best:
                best = val_loss
                stale = 0
                torch.save({'gate_state_dict': gate_state(model), 'all_native_buffers': buffer_state(model), 'optimizer_state_dict': optimizer.state_dict(), 'scheduler_state_dict': scheduler.state_dict(), 'seed': a.seed, 'initial_lr': lr, 'epoch': epoch, 'optimizer_steps': steps, 'protocol_sha256': a.protocol_sha, 'source_manifest_sha256': sha(a.source_manifest), 'official_expert_assets_manifest_sha256': sha(a.asset_manifest), 'released_expert_parameters_modified': False, 'original_expert_train_modes_preserved': True}, checkpoint_path)
            else:
                stale += 1
            (folder / 'history.json').write_text(json.dumps(history, indent=2) + '\n')
            print(json.dumps({'candidate': candidate, 'seed': a.seed, **info}), flush=True)
            if stale >= 5:
                break
        checkpoint = torch.load(checkpoint_path, map_location='cpu', weights_only=False)
        restore(model, checkpoint)
        val_loss, val_mae, val_records = evaluate(model, val)
        save_csv(folder / 'validation-predictions.csv', val_records)
        trained = state_sha(gate_state(model))
        assert trained != initial
        receipt = {'candidate': candidate, 'seed': a.seed, 'initial_lr': lr, 'epochs_ran': len(history), 'optimizer_steps': steps, 'best_epoch': checkpoint['epoch'], 'checkpoint_Adamsteps': checkpoint['optimizer_steps'], 'initial_trainable_state_sha256': initial, 'selected_trainable_state_sha256': trained, 'initial_buffers_sha256': initial_buffers, 'selected_all_buffers_sha256': state_sha(buffer_state(model)), 'all_native_buffers_saved': True, 'original_expert_train_modes_preserved': True, 'released_expert_parameters_modified': False, 'first_gradient_l2': first_gradient, 'validation_native_MSE': val_loss, 'validation_forward_MAE': val_mae, 'checkpoint_sha256': sha(checkpoint_path), 'trainable_parameters': 2046380, 'total_parameters': 684421861}
        (folder / 'fit-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
        candidates.append(receipt)
        del model, optimizer, scheduler, checkpoint, params
        gc.collect()
        torch.cuda.empty_cache()
    winner = min(candidates, key=lambda r: (r['validation_forward_MAE'], r['candidate']))
    selection = {'winner': winner['candidate'], 'candidates': candidates, 'test_used_for_selection': False, 'rule': protocol['HPO_selection'], 'frozen_at_utc': dt.datetime.now(dt.timezone.utc).isoformat()}
    (a.output / 'selection.json').write_text(json.dumps(selection, indent=2) + '\n')
    result = {'schema': 'fourtask.uniair.original-MoFPE-local-training.v1', 'phase': a.phase, 'seed': a.seed, 'original_UniAIR_MoFPE': True, 'all_four_original_experts': True, 'published_gate_weights_available': False, 'new_gate_training': True, 'real_candidate_fits': len(candidates), 'selected_trained_models': 1, 'split_counts': {'train': 293, 'validation': 63, 'test': 63}, 'test_evaluated': False, 'selection': selection, 'protocol_sha256': a.protocol_sha, 'input_sha256': a.input_sha, 'cache_sha256': a.cache_sha, 'source_manifest_sha256': sha(a.source_manifest), 'official_expert_assets_manifest_sha256': sha(a.asset_manifest), 'physical_DDG_unit_certified': False, 'main_article_pdf_status': 'missing', 'claim_scope': 'Original four-expert MoFPE gate adapted within one human HER2 context. Supervised released expert HER2 background exposure partly known; not strict unseen-complex external evaluation or published table reproduction.'}
    if a.phase == 'formal':
        model = construct()
        checkpoint_path = a.output / f"candidate-{winner['candidate']:02d}" / 'best-checkpoint.pt'
        checkpoint = torch.load(checkpoint_path, map_location='cpu', weights_only=False)
        restore(model, checkpoint)
        _, _, records = evaluate(model, test)
        save_csv(a.output / 'test-predictions.csv', records)
        y = np.array([r['label'] for r in records])
        prediction = np.array([r['prediction'] for r in records])
        result.update(test_evaluated=True, test_predictions_sha256=sha(a.output / 'test-predictions.csv'), metrics={'MAE': float(np.mean(abs(y - prediction))), 'RMSE': float(np.sqrt(np.mean((y - prediction) ** 2))), 'Pearson': float(pearsonr(y, prediction).statistic) if np.std(prediction) > 0 else None, 'Spearman': float(spearmanr(y, prediction).statistic) if np.std(prediction) > 0 else None, 'R2': float(1 - np.sum((y - prediction) ** 2) / np.sum((y - y.mean()) ** 2)), 'direction_accuracy_author_sign': float(np.mean(np.sign(y) == np.sign(prediction)))}, test_ids=[r['row_id'] for r in records])
    result.update(elapsed_seconds=time.monotonic() - started, peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated(), peak_cuda_reserved_bytes=torch.cuda.max_memory_reserved())
    result.update(CPU_threads=torch.get_num_threads(), GPU_devices_visible=0, device='cpu', CPU_FP32_not_GPU_precision_equivalence=True, CPU_epoch_phase_records=CPU_epoch_phases, benchmark_formal_fits=0)
    (a.output / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'original_MoFPE_training_completed': True, 'phase': a.phase, 'seed': a.seed, 'real_candidate_fits': len(candidates), 'test_evaluated': result['test_evaluated'], 'elapsed_seconds': result['elapsed_seconds']}), flush=True)
if __name__ == '__main__':
    main()
