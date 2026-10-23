"""Transport complete candidate state without constructing or changing a model."""
import copy
import random


def cpu_clone_tree(values, torch):
    if torch.is_tensor(values):
        return values.detach().cpu().clone()
    if isinstance(values, dict):
        return {key: cpu_clone_tree(value, torch) for key, value in values.items()}
    if isinstance(values, list):
        return [cpu_clone_tree(value, torch) for value in values]
    if isinstance(values, tuple):
        return tuple(cpu_clone_tree(value, torch) for value in values)
    return copy.deepcopy(values)


def capture_rng(np, torch, loader_rng):
    return {'python': random.getstate(), 'numpy_legacy': np.random.get_state(),
            'torch_CPU': torch.get_rng_state().clone(),
            'torch_CUDA_all': [value.clone() for value in torch.cuda.get_rng_state_all()],
            'loader_generator': copy.deepcopy(loader_rng.bit_generator.state)}


def restore_rng(values, np, torch, loader_rng):
    random.setstate(values['python'])
    np.random.set_state(values['numpy_legacy'])
    torch.set_rng_state(values['torch_CPU'])
    torch.cuda.set_rng_state_all(values['torch_CUDA_all'])
    loader_rng.bit_generator.state = copy.deepcopy(values['loader_generator'])


def capture_epoch(model, optimizer, scheduler, loader_rng, np, torch,
                  *, seed, candidate, epoch, optimizer_steps, initial_lr):
    return {
        'gate_state_dict': {key: value.detach().cpu().clone()
                            for key, value in model.named_parameters() if value.requires_grad},
        'all_native_buffers': {key: value.detach().cpu().clone()
                               for key, value in model.named_buffers()},
        'optimizer_state_dict': cpu_clone_tree(optimizer.state_dict(), torch),
        'scheduler_state_dict': copy.deepcopy(scheduler.state_dict()),
        'RNG_state': capture_rng(np, torch, loader_rng),
        'seed': seed, 'candidate': candidate, 'epoch': epoch,
        'optimizer_steps': optimizer_steps, 'initial_lr': initial_lr,
    }


def restore_epoch(checkpoint, model, optimizer, scheduler, loader_rng, np, torch):
    destinations = {**dict(model.named_parameters()), **dict(model.named_buffers())}
    required = {key for key, value in model.named_parameters() if value.requires_grad}
    required.update(key for key, _ in model.named_buffers())
    values = {**checkpoint['gate_state_dict'], **checkpoint['all_native_buffers']}
    assert set(values) == required
    with torch.no_grad():
        for key, value in values.items():
            assert tuple(destinations[key].shape) == tuple(value.shape)
            destinations[key].copy_(value)
    optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
    scheduler.load_state_dict(checkpoint['scheduler_state_dict'])
    # Construction/load precede this final restoration; no later random seeding.
    restore_rng(checkpoint['RNG_state'], np, torch, loader_rng)
