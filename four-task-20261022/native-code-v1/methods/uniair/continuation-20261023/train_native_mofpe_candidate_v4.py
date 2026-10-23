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
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('method-root', 'source-manifest', 'input', 'cache', 'asset-manifest', 'protocol', 'output', 'native-canary-proof'):
        p.add_argument('--' + name, type=Path, required=True)
    for name in ('input-sha', 'cache-sha', 'protocol-sha', 'native-canary-proof-sha'):
        p.add_argument('--' + name, required=True)
    p.add_argument('--seed', type=int, choices=range(10), required=True)
    p.add_argument('--phase', choices=['candidate_train', 'selected_test'], required=True)
    p.add_argument('--candidate', type=int, choices=(0, 1))
    for key in ('execution-protocol', 'epoch-proof'):
        p.add_argument('--' + key, type=Path, required=True)
        p.add_argument('--' + key + '-sha', required=True)
    for key in ('resume-checkpoint', 'selection', 'selected-checkpoint'):
        p.add_argument('--' + key, type=Path)
        p.add_argument('--' + key + '-sha')
    p.add_argument('--gpu-memory-gib', type=float, required=True)
    a = p.parse_args()
    c = a.method_root / 'continuation-20261023'
    sys.path.insert(0, str(c))
    from owned_dispatch_admission import current_validation
    admission = current_validation(argparse.Namespace(method_root=a.method_root, validation=Path('owner-current-dispatch')))
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
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch.set_float32_matmul_precision('high')
    torch.hub.set_dir('<REMOTE_USER_DATA_ROOT>/.cache/torch/hub')
    assert os.environ.get('CUDA_VISIBLE_DEVICES') and torch.cuda.device_count() == 1
    torch.cuda.set_per_process_memory_fraction(a.gpu_memory_gib * 1024 ** 3 / torch.cuda.get_device_properties(0).total_memory, 0)
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
            return value.cuda()
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
        model = UniAIR(model_dirs=paths, encoder=EasyDict(node_feat_dim=128, pair_feat_dim=64, num_layers=3, num_heads=12), fold=0, fix_backbone=True).cuda()
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
    from mofpe_candidate_checkpoint_v1 import capture_epoch, restore_epoch
    assert sha(a.execution_protocol) == a.execution_protocol_sha
    execution_protocol = json.loads(a.execution_protocol.read_text())
    assert execution_protocol['mathematical_parent_protocol_sha256'] == a.protocol_sha
    assert execution_protocol['worker_sha256'] == sha(Path(__file__))
    assert execution_protocol['checkpoint_helper_sha256'] == sha(c / 'mofpe_candidate_checkpoint_v1.py')
    assert a.gpu_memory_gib == 13.25
    assert sha(a.epoch_proof) == a.epoch_proof_sha
    epoch_proof = json.loads(a.epoch_proof.read_text())
    assert epoch_proof['complete_training_epoch_verified'] and epoch_proof['actual_Adam_steps_verified'] == 37
    assert epoch_proof['test_rows'] == 0 and epoch_proof['independent_saved_artifact_audit_passed']
    provenance = {'seed': a.seed, 'protocol_sha256': a.protocol_sha, 'input_sha256': a.input_sha, 'cache_sha256': a.cache_sha, 'source_manifest_sha256': sha(a.source_manifest), 'official_expert_assets_manifest_sha256': sha(a.asset_manifest), 'execution_protocol_sha256': a.execution_protocol_sha, 'worker_sha256': sha(Path(__file__)), 'checkpoint_helper_sha256': sha(c / 'mofpe_candidate_checkpoint_v1.py')}
    if a.phase == 'selected_test':
        assert a.selection is not None and a.selection_sha and (a.selected_checkpoint is not None) and a.selected_checkpoint_sha
        assert a.resume_checkpoint is None
        assert sha(a.selection) == a.selection_sha and sha(a.selected_checkpoint) == a.selected_checkpoint_sha
        selection = json.loads(a.selection.read_text())
        assert selection['seed'] == a.seed and selection['test_used_for_selection'] is False
        assert selection['winner'] in (0, 1) and len(selection['candidates']) == 2
        assert selection['selected_checkpoint_sha256'] == a.selected_checkpoint_sha
        checkpoint = torch.load(a.selected_checkpoint, map_location='cpu', weights_only=False)
        assert checkpoint['candidate'] == selection['winner'] and checkpoint['seed'] == a.seed
        assert checkpoint['mathematical_parent_protocol_sha256'] == a.protocol_sha
        for key in provenance:
            assert checkpoint['provenance'][key] == provenance[key], key
        model = construct()
        restore(model, checkpoint['best'])
        _, _, records = evaluate(model, test)
        save_csv(a.output / 'test-predictions.csv', records)
        y = np.array([record['label'] for record in records])
        prediction = np.array([record['prediction'] for record in records])
        result = {'schema': 'fourtask.uniair.MoFPE.selected-test.v3', 'phase': a.phase, **provenance, 'selection_sha256': a.selection_sha, 'selected_checkpoint_sha256': a.selected_checkpoint_sha, 'selected_candidate': selection['winner'], 'selected_epoch': checkpoint['best']['epoch'], 'test_rows': 63, 'actual_Adam_steps_in_this_job': 0, 'test_ids': [record['row_id'] for record in records], 'test_predictions_sha256': sha(a.output / 'test-predictions.csv'), 'metrics': {'MAE': float(np.mean(abs(y - prediction))), 'RMSE': float(np.sqrt(np.mean((y - prediction) ** 2))), 'Pearson': float(pearsonr(y, prediction).statistic) if np.std(prediction) > 0 else None, 'Spearman': float(spearmanr(y, prediction).statistic) if np.std(prediction) > 0 else None, 'R2': float(1 - np.sum((y - prediction) ** 2) / np.sum((y - y.mean()) ** 2)), 'direction_accuracy_author_sign': float(np.mean(np.sign(y) == np.sign(prediction)))}, 'physical_DDG_unit_certified': False, 'main_article_pdf_status': 'missing', 'claim_scope': 'One selected native MoFPE gate test within a known human HER2 background;not full-paper reproduction'}
    else:
        assert a.candidate in (0, 1) and a.selection is None and (a.selected_checkpoint is None)
        candidate = a.candidate
        lr = protocol['optimizer']['lr_candidates'][candidate]
        model = construct()
        params = [parameter for parameter in model.parameters() if parameter.requires_grad]
        initial = state_sha(gate_state(model))
        initial_buffers = state_sha(buffer_state(model))
        optimizer = torch.optim.Adam(params, lr=lr, betas=(0.9, 0.999), weight_decay=0)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.8, patience=5, min_lr=1e-06)
        rng = np.random.default_rng(a.seed)
        history = []
        best = math.inf
        stale = 0
        steps = 0
        first_gradient = None
        best_state = None
        first_epoch = 1
        resume = None
        checkpoint_path = None
        if a.resume_checkpoint is not None:
            assert a.resume_checkpoint_sha and sha(a.resume_checkpoint) == a.resume_checkpoint_sha
            assert a.resume_checkpoint.resolve().is_relative_to((a.method_root.parents[1] / 'runs').resolve())
            previous = torch.load(a.resume_checkpoint, map_location='cpu', weights_only=False)
            assert previous['seed'] == a.seed and previous['candidate'] == candidate
            for key in provenance:
                assert previous['provenance'][key] == provenance[key], key
            assert previous['initial_trainable_state_sha256'] == initial
            assert previous['initial_buffers_sha256'] == initial_buffers
            current = previous['current']
            assert current['epoch'] >= 1 and current['initial_lr'] == lr
            restore_epoch(current, model, optimizer, scheduler, rng, np, torch)
            history = previous['history']
            best = previous['best_validation_MSE']
            stale = previous['stale_epochs']
            steps = current['optimizer_steps']
            first_gradient = previous['first_gradient_l2']
            best_state = previous['best']
            first_epoch = current['epoch'] + 1
            assert len(history) == current['epoch'] and steps == 37 * current['epoch']
            resume = {'checkpoint_path': str(a.resume_checkpoint), 'sha256': a.resume_checkpoint_sha, 'last_completed_epoch': current['epoch'], 'last_completed_Adamsteps': steps, 'uncommitted_partial_epoch_replayed_from_full_saved_state': True}
            checkpoint_path = a.resume_checkpoint
            del previous
        assert 1 <= first_epoch <= 31 and 0 <= stale <= 5
        epochs_to_run = range(first_epoch, 31) if stale < 5 else []
        for epoch in epochs_to_run:
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
            val_loss, val_mae, val_records = evaluate(model, val)
            scheduler.step(val_loss)
            info = {'epoch': epoch, 'train_native_MSE': total / len(train), 'validation_native_MSE': val_loss, 'validation_forward_MAE': val_mae, 'lr': optimizer.param_groups[0]['lr'], 'optimizer_steps': steps}
            history.append(info)
            improved = val_loss < best
            if improved:
                best = val_loss
                stale = 0
            else:
                stale += 1
            current = capture_epoch(model, optimizer, scheduler, rng, np, torch, seed=a.seed, candidate=candidate, epoch=epoch, optimizer_steps=steps, initial_lr=lr)
            if improved:
                best_state = current
            checkpoint = {'schema': 'fourtask.uniair.MoFPE.epoch-complete-checkpoint.v3', 'seed': a.seed, 'candidate': candidate, 'current': current, 'best': best_state, 'history': history.copy(), 'best_validation_MSE': best, 'stale_epochs': stale, 'first_gradient_l2': first_gradient, 'initial_trainable_state_sha256': initial, 'initial_buffers_sha256': initial_buffers, 'provenance': provenance, 'mathematical_parent_protocol_sha256': a.protocol_sha, 'resumed_from': resume}
            checkpoint_path = a.output / f'epoch-{epoch:02d}.pt'
            assert not checkpoint_path.exists()
            temporary = a.output / f'epoch-{epoch:02d}.pt.incomplete'
            torch.save(checkpoint, temporary)
            temporary.replace(checkpoint_path)
            save_csv(a.output / f'epoch-{epoch:02d}-validation-predictions.csv', val_records)
            (a.output / 'history.json').write_text(json.dumps(history, indent=2) + '\n')
            (a.output / 'last-complete-epoch.json').write_text(json.dumps({'epoch': epoch, 'optimizer_steps': steps, 'checkpoint': str(checkpoint_path), 'sha256': sha(checkpoint_path)}, indent=2) + '\n')
            print(json.dumps({'candidate': candidate, 'seed': a.seed, **info}), flush=True)
            if stale >= 5:
                break
        (a.output / 'history.json').write_text(json.dumps(history, indent=2) + '\n')
        restore(model, best_state)
        val_loss, val_mae, val_records = evaluate(model, val)
        save_csv(a.output / 'validation-predictions.csv', val_records)
        trained = state_sha(gate_state(model))
        assert trained != initial
        receipt = {'candidate': candidate, 'seed': a.seed, 'initial_lr': lr, 'epochs_ran': len(history), 'optimizer_steps': steps, 'best_epoch': best_state['epoch'], 'checkpoint_Adamsteps': best_state['optimizer_steps'], 'initial_trainable_state_sha256': initial, 'selected_trainable_state_sha256': trained, 'initial_buffers_sha256': initial_buffers, 'selected_all_buffers_sha256': state_sha(buffer_state(model)), 'all_native_buffers_saved': True, 'original_expert_train_modes_preserved': True, 'released_expert_parameters_modified': False, 'first_gradient_l2': first_gradient, 'validation_native_MSE': val_loss, 'validation_forward_MAE': val_mae, 'checkpoint_sha256': sha(checkpoint_path), 'checkpoint_path': str(checkpoint_path), 'trainable_parameters': 2046380, 'total_parameters': 684421861, 'resumed_from': resume, 'test_evaluated': False, **provenance}
        (a.output / 'fit-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
        result = {'schema': 'fourtask.uniair.MoFPE.candidate-train.v3', 'phase': a.phase, 'candidate': candidate, 'seed': a.seed, 'initial_lr': lr, 'epochs_ran': len(history), 'actual_Adam_steps_total': steps, 'actual_Adam_steps_in_this_job': 37 * (len(history) - first_epoch + 1), 'test_evaluated': False, 'test_rows': 0, 'validation_rows': 63, 'training_rows': 293, 'real_candidate_fits_completed': 1, 'selected_models_tested': 0, 'fit_receipt': receipt, 'physical_DDG_unit_certified': False, 'main_article_pdf_status': 'missing', **provenance, 'claim_scope': 'One native MoFPE candidate, TRAIN/VAL only. Seed-level HPO/test require separate frozen selection.'}
    result.update(elapsed_seconds=time.monotonic() - started, peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated(), peak_cuda_reserved_bytes=torch.cuda.max_memory_reserved())
    (a.output / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'phase': a.phase, 'seed': a.seed, 'completed': True, 'elapsed_seconds': result['elapsed_seconds']}), flush=True)
if __name__ == '__main__':
    main()
