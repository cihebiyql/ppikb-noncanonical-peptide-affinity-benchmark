"""Two optimizer steps on fixed training records; no holdout labels or fitting."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import sys
import time

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
sys.path.insert(0, str(HERE / 'vendor-dependencies'))
sys.path.insert(0, str(PROJECT / 'execution'))
import torch
import torch_geometric
import rdkit
import runner


def main():
    args = argparse.ArgumentParser()
    args.add_argument('--contract', required=True)
    contract_path = args.parse_args().contract
    contract = runner.read_json(contract_path)
    assert contract['stage'] == 'local-GPU-train-only-performance-canary'
    assert platform.node() == contract['host']
    assert os.environ['CUDA_VISIBLE_DEVICES'] == contract['GPU_UUID']
    assert torch.cuda.is_available()
    torch.cuda.set_per_process_memory_fraction(7 * 1024**3 / torch.cuda.get_device_properties(0).total_memory, 0)
    runner.require_hash(contract['train_sample'], contract['train_sample_sha256'])
    rows = runner.read_jsonl(contract['train_sample'])
    assert len(rows) == len({r['record_id'] for r in rows}) == 32
    assert {r['record_id'] for r in rows} <= set(contract['allowed_train_ids'])
    runner.seed_everything(contract['seed'], 2)
    method = contract['method_id']
    adapter = runner.load_adapter(method, contract['methods_root'])
    started = time.perf_counter()
    items = [runner.encode(adapter, method, row) for row in rows]
    encoding_seconds = time.perf_counter() - started
    model = runner.native_model(adapter, method).to('cuda:0')
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=0.)
    model.train()
    torch.cuda.reset_peak_memory_stats()
    timings = []
    losses = []
    batch_size = contract['batch_size']
    accumulation = contract['gradient_accumulation']
    visited_ids = []
    for step in range(2):
        torch.cuda.synchronize()
        begin_time = time.perf_counter()
        optimizer.zero_grad(set_to_none=True)
        total = 0.
        for micro in range(accumulation):
            begin = ((step * accumulation + micro) * batch_size) % len(items)
            indices = [(begin + j) % len(items) for j in range(batch_size)]
            visited_ids.extend(rows[i]['record_id'] for i in indices)
            batch = adapter.collate([items[i] for i in indices])
            pred = adapter.predict(model, batch, 'cuda:0')
            target = adapter.batch_targets(batch).to('cuda:0')
            loss = torch.nn.functional.mse_loss(pred, target) / accumulation
            if not torch.isfinite(loss):
                raise FloatingPointError('Nonfinite loss')
            loss.backward()
            total += float(loss.detach())
        if any(p.grad is not None and not torch.isfinite(p.grad).all() for p in model.parameters()):
            raise FloatingPointError('Nonfinite gradient')
        optimizer.step()
        torch.cuda.synchronize()
        timings.append(time.perf_counter() - begin_time)
        losses.append(total)
    assert set(visited_ids) == {r['record_id'] for r in rows}
    receipt = {'status': 'passed', 'stage': contract['stage'], 'method_id': method,
               'host': platform.node(), 'pid': os.getpid(), 'python': sys.version,
               'torch': torch.__version__, 'torch_geometric': torch_geometric.__version__,
               'rdkit': rdkit.__version__, 'cuda_runtime': torch.version.cuda,
               'device': torch.cuda.get_device_name(0), 'GPU_UUID': contract['GPU_UUID'],
               'parameter_count': sum(p.numel() for p in model.parameters()),
               'train_sample_n': len(rows), 'unique_training_ids_visited': len(set(visited_ids)),
               'optimizer_steps': 2, 'batch_size': batch_size, 'gradient_accumulation': accumulation,
               'encoding_seconds': encoding_seconds, 'step_seconds': timings,
               'sample_visits': len(visited_ids),
               'training_sample_visits_per_second': len(visited_ids) / sum(timings),
               'diagnostic_train_losses': losses,
               'GPU_peak_allocated_bytes': torch.cuda.max_memory_allocated(),
               'GPU_peak_reserved_bytes': torch.cuda.max_memory_reserved(),
               'GPU_allocator_budget_bytes': 7 * 1024**3,
               'max_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
               'cpu_affinity': sorted(os.sched_getaffinity(0)), 'cpu_threads': torch.get_num_threads(),
               'sample_sha256': contract['train_sample_sha256'],
               'contract_sha256': runner.sha_file(contract_path),
               'adapter_tree_sha256': runner.adapter_tree_hash(adapter),
               'compiled_scatter_available': torch_geometric.typing.WITH_TORCH_SCATTER,
               'compiled_sparse_available': torch_geometric.typing.WITH_TORCH_SPARSE,
               'test_label_reads': 0, 'holdout_label_reads': 0,
               'claim': 'real GPU train-only canary; no full fit, no checkpoint retained, no benchmark metric'}
    runner.write_json(contract['receipt_path'], receipt)
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
