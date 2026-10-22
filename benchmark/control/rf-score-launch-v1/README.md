# RF40 post-joint CPU scoring launcher — preparation only

This directory adds the supervisor for **40 RF selections × three datasets =120
scores /53,160 prediction rows**. It does not replace NN200, add a paper count,
refit models or change any frozen RF/NN source or specification. Preparation and
tests invoke zero real scores and open no real selection, trained model, gold or
prediction file. Current real training in other processes is outside this claim.

## Interface

- Pool: `rf_score_pool.py --index ISSUED_INDEX --index-sha256 ACTUAL_SHA`
- Unit: `rf_score_unit.py --binding ISSUED_BINDING`
- Delegated frozen scorer, after all gates:
  `rf_score.py --authorization A --joint-barrier J --selection S --spec ONE`

There is **no `score` subcommand** in the frozen RF worker. Each unit invokes it
three times in sequence for one unchanged selected model: `source_test` or
`target_test`, `external75`, `supplement13`. It keeps the six original RF score
specification files unchanged. Their actual output root is
`auxiliary-rf-baseline/rf-scores-v1`, with layout
`dataset_id/panel/regime/seed-N` (the RF layout has no method path component).

Use absolute WSL canonical paths and the existing generic runtime
`/root/.venvs/peptide-omnipanel-v31-web311-20260723/bin/python`; set the existing
task dependency overlay as `PYTHONPATH` and explicitly empty
`CUDA_VISIBLE_DEVICES`. Root/admin fill the unissued examples with actual SHA
values only after joint freeze, explicit RF scoring authorization and positive
central validation. Source does not embed its own SHA.

`entrypoint_sha256`, `pool_sha256`, `common_sha256` refer to this directory's
`rf_score_unit.py`, `rf_score_pool.py`, `rfs_common.py`. References contain exactly
`{path,sha256}`. Central `rf_score_execution_stage` exactly binds `selection`,
`score_specs`, `authorization`, `joint_barrier`, `NN_barrier`, `RF_barrier`,
`live_cpu_proof`, `worker`, `code_files`, `receipt_root`, `score_root`. Unit ID is
the actual RF training spec's unit ID plus `__evaluation_v1`. The central
`RF-Classic` alias maps explicitly to scorer method `RF-Morgan2-chiral-AAC-DP`
without a prior-paper contribution.

## Gate order before model/gold access

The stdlib-only gates verify real host/interpreter/prefix/overlay/empty CUDA and a
root-issued private parent pool, then enforce the original clock. **RF fit
authorization does not authorize scoring.** Root must explicitly grant
`root_RF_holdout_score_authorized`, the exact three score-spec SHA values, frozen
RF source SHA, stable metrics SHA, joint barrier SHA and the original deadline.

The joint barrier must retain all **NN200+RF40 selections and400+80 candidate
fits**, linked NN200/RF40 barrier SHA values and the complete RF40 coordinates.
RF joint entries must exactly equal linked RF barrier entries. The approved
recovery-aware NN index constants are parsed as literals from frozen `rf_runner`
source without importing NumPy or the model; actual metadata index SHA and both
barriers must match. No other selected model or checkpoint is opened by the gate.

The unit then checks the exact frozen central contract/positive validation,
resource proof, complete code proofs, selected metadata membership/SHA/model-SHA
string, three correct dataset/panel specs and their label-free input/feature
manifest SHA, and exact central stage bindings. Code proofs cover these three
launcher files, reused frozen `control/rf-launch-v1/rf_common.py`, frozen
`launch/common.py`, `evaluation/metrics_stable.py` and the eight RF source/metadata
files. A model, gold file or binary cache cannot be a code proof.

Only after all these checks may the frozen scorer access trained weights. The
scorer itself verifies actual model SHA/type/parameters, saves blind predictions
and a blind receipt, and only then first hashes/opens gold. The launcher does not
alter or reproduce that scientific implementation.

## Resources, clocks, persistence

The index requires exactly40 unique RF coordinates and120 unique output paths.
Up to four owned scoring units run on logical CPU4–7, one distinct core each,
nice10, BLAS/OpenMP threads one, `n_jobs=1`, CUDA empty. These slots avoid the
planned NN GPU scorer's CPU0–1 assignment; this is not a claim of exclusive OS
CPU ownership. Each private session has RSS2GiB; this pool and all owned sessions
have RSS8GiB total. Fresh memory/load/affinity proofs gate startup and new launch.

Each unit reserves **1800 seconds for all three datasets**. Original global
deadline **2026-10-22T01:45:00+00:00** is never reset or extended, and new launch
requires `actual_start+1800 <= original_global_deadline`. The private-group
resource watchdog checks RSS/per-unit/global clocks every0.2 seconds and emits
heartbeat requests every second. It signals only private sessions this pool owns.

The frozen RF train helper supplies unique PID/thread/UUID JSON temporary files
and at most seven PermissionError replacement attempts. A separate bounded-queue
writer thread means Windows live-file locking cannot pause the resource watchdog.
Persistent I/O failure safely stops owned sessions. There is no unknown-process
kill, WSL restart, package installation or shared-environment modification.

Per-stage receipts keep actual scorer PID/PGID/start/end/exit/stdout/stderr SHA.
Three original RF score receipt paths/SHA and row counts, selected-model SHA and
blind/joined prediction SHA are retained in `unit-complete.json`. Each new score
must declare zero parameter updates and blind-before-gold. The unit does not
claim its own future exit: supervising pool separately records true wrapper exit,
whole-session cleanup and stdout/stderr SHA in `pool-exit-verification.json` with
SHA sidecar. Only then is a unit counted complete. Root/admin archive both.

Existing incomplete/failed outputs or logs prevent automatic rerun. Completed
units are skipped only after all result/log/exit-proof SHA checks. Failed attempts
are never overwritten. NN200 training/score and RF40 training files remain frozen.

## Mechanical evidence

Tests use temporary synthetic metadata and sleeping private parent/child
processes. They cover authorization separation, NN199/RF39/missing RF coordinate
rejection, source/spec/selection/validator SHA, original1800-second window,
2/8GiB and clock gates, true private-PGID cleanup, no model-runtime import,
completed-result SHA/exit proof, bounded persistent/transient sharing failures,
and continuing independent budget ticks during writer retries. No real scorer or
model is run. The pool structure is an owned adapted copy of the frozen RF train
pool; `copy-provenance.json` identifies the unchanged source and hash.
