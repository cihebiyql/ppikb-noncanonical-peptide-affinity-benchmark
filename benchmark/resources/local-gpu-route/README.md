# Local RTX 5080 author-model route

All five author methods passed **real GPU forward, backward and two Adam steps**
on the existing frozen 32-training-record canary. All 32 training IDs were visited
for every method. No validation/test/external labels were read, no full fitting
was launched, and no model checkpoints were retained.

| Method | First GPU step (s) | Second GPU step (s) | Sample visits/step | Peak GPU reserved (MiB) | Peak process-tree RSS (MiB) |
|---|---:|---:|---:|---:|---:|
| DeepNC-GEN | 0.981 | 0.0313 | 32 | 370 | 2227 |
| DGDTA-CL | 1.492 | 0.0250 | 32 | 908 | 2362 |
| GraphDTA-GIN | 1.372 | 0.0269 | 32 | 154 | 2260 |
| MGraphDTA | 1.079 | 0.1398 | 32 | 638 | 2203 |
| MRBDTA | 0.983 | 0.2092 | 16 | 386 | 1822 |

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
