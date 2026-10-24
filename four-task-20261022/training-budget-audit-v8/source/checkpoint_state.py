"""Completed-epoch checkpoint producer. Imports no numerical library.

Only objects passed by the reviewed training entry are serialized. This is not a
resume consumer; loading a prior best.pt is deliberately unsupported.
"""
import hashlib
import json
import os
import random
from pathlib import Path


def file_sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def save_last_state(folder, model, optimizer, rng, torch, np, *, spec, spec_path,
                    candidate_index, epoch, best, best_epoch, stale, history_path):
    """Synchronous atomic state at the next-epoch boundary, before early stop.

    Failure aborts this attempt. The prior committed last-state file stays intact.
    Model tensors are not moved, cast, changed or deserialized. Saving transient
    current-batch gradients is redundant for next zero_grad but makes the stored
    boundary explicit. Device RNG is captured only when CUDA is available.
    """
    folder = Path(folder)
    # Windows fsync requires a writable descriptor. This is this attempt's own
    # already-flushed history; append mode plus no write preserves its bytes.
    with Path(history_path).open('ab') as history:
        os.fsync(history.fileno())
    payload = {
        'schema': 'fourtask.dta.completed-epoch-state.v2',
        'model_state': model.state_dict(),
        'named_buffers': dict(model.named_buffers()),
        'module_training_modes': {n: m.training for n, m in model.named_modules()},
        'parameter_gradients': {n: p.grad for n, p in model.named_parameters()},
        'optimizer_state': optimizer.state_dict(),
        'python_rng': random.getstate(),
        'numpy_global_rng': np.random.get_state(),
        'torch_cpu_rng': torch.get_rng_state(),
        'torch_cuda_rng_all': torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None,
        'shuffle_bit_generator_state': rng.bit_generator.state,
        'completed_epoch_0based': epoch,
        'next_epoch_0based': epoch + 1,
        'best_validation_score': best,
        'best_epoch_0based': best_epoch,
        'stale': stale,
        'candidate_index': candidate_index,
        'seed': spec['seed'],
        'method_id': spec['method_id'],
        'spec_sha256': file_sha(spec_path),
        'inputs': spec['paths'],
        'source_manifest': spec['source_manifest'],
        'history_sha256': file_sha(history_path),
        'history_epochs': epoch + 1,
        'runtime_sha256': file_sha(folder.parent / 'runtime.json'),
        'best_checkpoint_sha256': file_sha(folder / 'best.pt'),
        'fresh_from_seed': True,
        'old_checkpoint_loaded': False,
        'automatic_resume_supported': False,
    }
    temp = folder / ('last-state.pt.partial-' + str(os.getpid()))
    with temp.open('xb') as stream:
        torch.save(payload, stream)
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(folder / 'last-state.pt')
    receipt = {
        'schema': payload['schema'], 'completed_epoch_0based': epoch,
        'next_epoch_0based': epoch + 1, 'history_sha256': payload['history_sha256'],
        'checkpoint_sha256': file_sha(folder / 'last-state.pt'),
        'spec_sha256': payload['spec_sha256'], 'automatic_resume_supported': False,
    }
    tmp_json = folder / ('last-state.json.partial-' + str(os.getpid()))
    with tmp_json.open('x', encoding='utf-8') as stream:
        json.dump(receipt, stream, allow_nan=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    tmp_json.replace(folder / 'last-state.json')
