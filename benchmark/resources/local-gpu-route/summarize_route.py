import hashlib
import json
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
OUT = HERE / 'gpu-canary-v1'
rows = []
for path in sorted(OUT.glob('*-result.json')):
    result = json.loads(path.read_text(encoding='utf-8'))
    method = result['method_id']
    watchdog = json.loads((OUT / f'{method}-watchdog-receipt.json').read_text(encoding='utf-8'))
    assert watchdog['success'] and watchdog['process_exited']
    assert not watchdog['post_exit_GPU_probe']['compute']
    assert result['unique_training_ids_visited'] == 32
    assert result['GPU_peak_reserved_bytes'] < 8 * 1024**3
    assert watchdog['max_process_tree_RSS_bytes'] < 8 * 1024**3
    assert hashlib.sha256(path.read_bytes()).hexdigest() == watchdog['outputs'][path.name]['sha256']
    cpu = json.loads((PROJECT / f'execution/canary-contracts-v1/{method}-receipt.json').read_text(encoding='utf-8'))
    effective_batch = result['batch_size'] * result['gradient_accumulation']
    cpu_batch = cpu['batch_size'] * cpu['gradient_accumulation']
    gpu_warm_rate = effective_batch / result['step_seconds'][1]
    cpu_warm_rate = cpu_batch / statistics.median(cpu['step_seconds'][1:])
    rows.append({'method_id': method,
                 'GPU_first_step_seconds': result['step_seconds'][0],
                 'GPU_second_step_seconds': result['step_seconds'][1],
                 'sample_visits_per_GPU_step': effective_batch,
                 'second_GPU_step_sample_visits_per_second': gpu_warm_rate,
                 'CPU_last_three_step_median_sample_visits_per_second': cpu_warm_rate,
                 'indicative_warm_step_speedup': gpu_warm_rate / cpu_warm_rate,
                 'GPU_peak_allocated_MiB': result['GPU_peak_allocated_bytes'] / 1024**2,
                 'GPU_peak_reserved_MiB': result['GPU_peak_reserved_bytes'] / 1024**2,
                 'process_tree_RSS_MiB': watchdog['max_process_tree_RSS_bytes'] / 1024**2,
                 'owned_process_exited': True, 'post_exit_GPU_compute_empty': True,
                 'compiled_torch_scatter': result['compiled_scatter_available'],
                 'compiled_torch_sparse': result['compiled_sparse_available']})
assert len(rows) == 5
manifest = json.loads((HERE / 'dependency-export-manifest.json').read_text(encoding='utf-8'))
summary = {'status': 'five_author_methods_GPU_component_verified', 'rows': rows,
           'environment': '/root/.venvs/peptide-omnipanel-v31-web311-20260723/bin/python',
           'PYTHONPATH': '/mnt/d/work/科研工作台/research-tasks/peptide-binding-nc-benchmark-20261021/resources/local-gpu-route/vendor-dependencies',
           'runtime': {'python': '3.11.15', 'torch': '2.12.1+cu130', 'PyG': '2.6.1', 'rdkit': '2026.03.4'},
           'dependency_packages_reused': len(manifest['packages']), 'dependency_files_hash_verified': len(manifest['files']),
           'dependency_bytes': sum(x['bytes'] for x in manifest['files']),
           'dependency_archive_sha256': manifest['archive_sha256'],
           'limitations': ['Two steps are a canary; second-step throughput is a single warm observation, not a completed epoch/fit or full-run ETA.',
                           'MGraphDTA CUDA adaptive_max_pool2d backward emits a nondeterminism warning under warn_only=True.',
                           'No compiled torch_scatter or torch_sparse; actual Torch fallback executed.',
                           'Local Torch and RDKit versions differ from Node23; retain runtime versions in all formal receipts.',
                           'No full fits launched, no benchmark metrics, no checkpoints retained.'],
           'shared_environment_modified': False, 'package_install_performed': False,
           'all_owned_children_exited_and_GPU_compute_empty': True}
(HERE / 'route-summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
table = '\n'.join('| {method_id} | {GPU_first_step_seconds:.3f} | {GPU_second_step_seconds:.4f} | {sample_visits_per_GPU_step} | {GPU_peak_reserved_MiB:.0f} | {process_tree_RSS_MiB:.0f} |'.format(**r) for r in rows)
text = '''# Local RTX 5080 author-model route

All five author methods passed **real GPU forward, backward and two Adam steps**
on the existing frozen 32-training-record canary. All 32 training IDs were visited
for every method. No validation/test/external labels were read, no full fitting
was launched, and no model checkpoints were retained.

| Method | First GPU step (s) | Second GPU step (s) | Sample visits/step | Peak GPU reserved (MiB) | Peak process-tree RSS (MiB) |
|---|---:|---:|---:|---:|---:|
''' + table + '''

The first step includes CUDA initialization. The second is one warm observation;
it does not establish a full-run ETA or guarantee memory for every corpus row.
MRBDTA uses batch 1 with 16 gradient-accumulation microbatches; the four GNNs use
batch 32 with no accumulation. Every ligand SMILES/graph remains complete;
the already disclosed author protein-prefix caps remain unchanged.

## Verified runtime

- Host `cihebi`, WSL Ubuntu-22.04, CPython 3.11.15 x86_64 Linux, ABI
  `cpython-311-x86_64-linux-gnu`.
- Existing general runtime (no PLM runtime/helpers):
  `/root/.venvs/peptide-omnipanel-v31-web311-20260723/bin/python`.
- Torch 2.12.1+cu130, RDKit 2026.03.4, PyG 2.6.1; NVIDIA RTX 5080 UUID
  `GPU-e9419f8b-b24b-a22b-c8ec-8f5173f4b45a`.
- No `torch_scatter`/`torch_sparse` compiled extensions: Torch fallback actually
  executed successfully. MGraphDTA logs a CUDA adaptive_max_pool2d backward
  nondeterminism warning with `warn_only=True`; do not claim bitwise deterministic
  CUDA training.

## Dependencies without installation

`export_dependencies.py` resolved mandatory requirements with importlib.metadata
and packaging markers. Eleven already installed Node23 distributions were copied:
PyG, aiohttp, psutil, pyparsing, xxhash, aiohappyeyeballs, aiosignal, frozenlist,
multidict, propcache and yarl. Only files inside their installed site-packages
were copied. Existing compatible WSL dependencies are reused, without copying
Torch/RDKit/NumPy or generic whole environments. There was no pip command,
downloaded version, shared environment modification, or credential access.

The task-owned `vendor-dependencies` contains 846 copied files / 16,506,223 bytes.
All per-file SHA-256 values, source locations, requirement decisions and archive
hash are retained in `dependency-export-manifest.json`; actual target imports and
ABI checks passed in `dependency-import-verification.json`.

Formal commands must set `PYTHONPATH` to this task's `vendor-dependencies`, with
the existing runtime interpreter above. Keep this overlay task-local. The shared
runner still needs its authorized GPU execution contract before full training.

## Resource and completion evidence

Each launch froze its own contract before execution and repeated three live GPU
checks (two-second spacing). No compute process was present; desktop graphics used
about 5 GB. Each child inherited two CPU cores. The watchdog limited owned
process-tree RSS to 8 GiB, observed GPU-memory delta to 8 GiB and wall time to 180
seconds. Torch's caching allocator was separately capped at 7 GiB, leaving room
for driver/context memory. The RSS monitor polls every 0.1 seconds, GPU every one
second; observed global GPU delta also includes desktop fluctuations.

`gpu-canary-v1` preserves five contracts, results, watchdog receipts and stdout/
stderr logs. Every owned child exited; after each exit, the live GPU compute
query was empty. Node1 and other users' workloads were not touched.
'''
(HERE / 'README.md').write_text(text, encoding='utf-8')
print(json.dumps({'status':summary['status'], 'rows':rows}, ensure_ascii=False))
