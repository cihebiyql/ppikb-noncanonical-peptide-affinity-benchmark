# GraphDTA-GIN / DeepNC-GEN author-code adapters

This directory implements the common benchmark interface for two distinct prior
papers. It does not train a benchmark, report benchmark accuracy, modify source
records, or replace the shared partition protocol.

## Interface

`adapter.py` provides:

- `METHOD_IDS = ['GraphDTA-GIN', 'DeepNC-GEN']`
- `encode_record(row) -> CPU pickleable dict`: fields `record_id`,
  `canonical_isomeric_smiles` (preferred) or `peptide_smiles`, `target_sequence`,
  and numeric `pKd` are required. No label conversion is performed.
- `collate(items) -> torch_geometric.data.Batch`
- `build_model(method_id, config) -> nn.Module`: keeps all original architecture
  defaults; runner learning rate, batch size, epochs and selection rules are
  controlled externally. The constructor does not silently change dimensions.
- `predict(model, batch, device) -> tensor[B]`
- `batch_targets(batch) -> tensor[B]`
- `method_metadata(method_id) -> dict`

The common runner should persist every encoded item's `audit` field as its input
view manifest. In particular, preserve the original/effective protein lengths,
coverage, sequence hashes, encoded prefix hash, graph hash and molecule atom
counts. The model's target view is the author's **first 1,000 residues**, including
the author's unusual Conv1d channel interpretation; this is not a site-centered
crop or a complete protein representation for longer targets. Padding token is 0;
the original 25-character protein vocabulary maps to integers 1–25. Unsupported
characters raise an error rather than being silently replaced.

## Frozen source and disclosed changes

`vendor-manifest.json` records full source paths and SHA-256 values.
`prepare_vendor.py` can recreate only the owned vendor files from the immutable
`model-audit/author-source` copies.

- GraphDTA-GIN: original `models/ginconv.py`, unchanged; 1,297,505 parameters.
- DeepNC-GEN: original `models/gen.py`, 4,933,417 parameters. A one-line typo
  repair changes undefined `super(GEN_Conv, self)` to `super(GEN, self)`.
  The exact diff is `deepnc_gen.py.patch`.
- Feature functions are extracted as AST functions from author preprocessing
  files. This removes dataset-loading side effects at import time without changing
  the functions. Both extracted pipelines agree exactly in the smoke checks.
- PyG 2.6.1 already maps `aggr='softmax_sg'` to `SoftmaxAggregation` with
  `semi_grad=True`, `t=1.0`, `learn_t=False`. All three DeepNC layers were inspected
  at runtime. No aggregation compatibility patch was necessary.

The 78 original atom features and per-atom normalization are retained. The graph
has all atoms and both bond directions, with no atom cap. **Neither model encodes
atom chirality, bond order, or bond stereochemistry.** D/L stereoisomers can
therefore have identical effective features: the smoke explicitly confirms this
limitation. Do not describe these methods as chirality-aware noncanonical peptide
models. The DeepNC source comment says max pooling, but its executable operation
is `global_add_pool`; the executable operation is preserved.

## Actual verification

Executed under the frozen `smoke-contract.json` on **node23**, using the existing
Python environment:

`/data/qlyu/projects/peptide-binding-benchmark-20261020/common-prior-methods-20261021/.venv/bin/python`

Torch 2.6.0+cu124 / PyG 2.6.1 / RDKit 2024.03.2. One CPU core, no GPU, process-tree
RSS watchdog at 4 GiB and timeout 180 seconds. Observed maximum process-tree RSS
750,579,712 bytes, wrapper wall time 8.22 seconds, exit code 0. The watchdog polls
RSS every 0.1 seconds; it is not a kernel cgroup allocation reservation.

Both methods passed real module import, forward and backward at batch sizes 1 and
2, finite nonzero gradients, and evaluation invariance under batch permutation
and splitting into singleton batches (largest absolute difference 1.12e-8).
CPU pickle roundtrip, explicit 1,260-to-1,000 target truncation, empty-edge
encoding, and preservation of a 600-atom synthetic molecule were also checked.
Synthetic smoke MSE values are diagnostic values, not biological performance.

`smoke-results.json`, `smoke-receipt.json` and stdout/stderr are copied back from
the remote unique run directory:

`/data/qlyu/projects/peptide-binding-nc-benchmark-20261021/methods/graphdta-deepnc/smoke-20261022-v1`

No full fitting, GPU computation, or benchmark test evaluation was performed in
this component task. Real-data preprocessing, training resource sizing,
validation-only tuning, seeds 0–9 and external evaluation belong to the shared
frozen training contract.
