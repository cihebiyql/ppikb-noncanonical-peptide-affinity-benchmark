"""Bounded CPU regression checks, no training dataset or GPU use."""
import json
import os
from pathlib import Path
import resource
import time

# Set before importing torch and numerical libraries.
assert not os.environ.get('CUDA_VISIBLE_DEVICES'), 'CPU-only contract'
os.environ['OMP_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
resource.setrlimit(resource.RLIMIT_AS, (6 * 1024**3, 6 * 1024**3))
import torch
import adapter
torch.set_num_threads(1)
torch.set_num_interop_threads(1)
torch.manual_seed(11)
start = time.time()
rows = [
    dict(record_id='synthetic-amide-1', canonical_isomeric_smiles='CC(=O)NCC(=O)O', target_sequence='ACDEFGHIKLMNPQRSTVWY' * 70, pKd=1.),
    dict(record_id='synthetic-amide-2', canonical_isomeric_smiles='CCNC(=O)CC(=O)O', target_sequence='WVTSPNMLKIHGFEDCAYRQ' * 10, pKd=2.),
]
receipts = []
for name in adapter.METHOD_IDS:
    model = adapter.build_model(name, {})
    encoded = [adapter.encode_record(row, name) for row in rows]
    batch = adapter.collate(encoded)
    original_x = batch['graph'].x.clone()
    model.eval()
    with torch.no_grad():
        together = adapter.predict(model, batch, 'cpu')
        repeat = adapter.predict(model, batch, 'cpu')
        reversed_pred = adapter.predict(model, adapter.collate(encoded[::-1]), 'cpu').flip(0)
        single = torch.cat([adapter.predict(model, adapter.collate([item]), 'cpu') for item in encoded])
    assert together.shape == (2,)
    assert torch.isfinite(together).all()
    assert torch.equal(original_x, batch['graph'].x), 'Batch x mutated'
    torch.testing.assert_close(together, repeat, rtol=1e-5, atol=1e-6)
    torch.testing.assert_close(together, reversed_pred, rtol=1e-4, atol=1e-5)
    torch.testing.assert_close(together, single, rtol=1e-4, atol=1e-5)
    model.train()
    predictions = adapter.predict(model, batch, 'cpu')
    loss = torch.nn.functional.mse_loss(predictions, adapter.batch_targets(batch))
    loss.backward()
    grads = [p.grad for p in model.parameters() if p.grad is not None]
    assert grads and all(torch.isfinite(g).all() for g in grads)
    assert batch['graph'].x.shape[1] == (22 if name == 'MGraphDTA' else 78)
    assert encoded[0]['target_truncated'] and not encoded[1]['target_truncated']
    # Native atom features do not distinguish stereochemistry: expose rather than hide it.
    stereo_rows = [dict(rows[0], canonical_isomeric_smiles=s) for s in ['N[C@@H](C)C(=O)O', 'N[C@H](C)C(=O)O']]
    stereo = [adapter.encode_record(row, name) for row in stereo_rows]
    assert torch.equal(stereo[0]['graph'].x, stereo[1]['graph'].x)
    receipts.append(dict(method_id=name, eval_single_batch_permutation_pass=True,
                         repeated_batch_cache_unchanged=True, backward_finite=True,
                         max_single_batch_difference=float((together - single).abs().max()),
                         parameter_count=sum(p.numel() for p in model.parameters()),
                         atom_feature_dim=batch['graph'].x.shape[1],
                         protein_cap=encoded[0]['protein_cap'], atom_truncation=False,
                         chirality_collision_explicitly_verified=True,
                         batch_targets=adapter.batch_targets(batch).tolist()))
result = dict(status='passed', host=os.uname().nodename, pid=os.getpid(),
              torch_version=torch.__version__, cpu_threads=torch.get_num_threads(),
              elapsed_seconds=time.time()-start, max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              claim='component CPU import/forward/backward regression only; no benchmark results', methods=receipts)
Path('smoke-receipt.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
