# Post-barrier scoring supervisor — prepared code only

This directory contains no authorization to perform real scoring. Preparation and
tests have not opened any real gold, prediction, trained checkpoint, or selection
file, and have not imported models or performed any model forward. All numerical
and process tests use temporary synthetic metadata and simple sleeping processes.

## Entrypoints and issuance

`score_pool.py --index ISSUED_INDEX --index-sha256 ACTUAL_SHA`

`score_unit.py --binding ISSUED_BINDING`

Use absolute WSL canonical paths and the existing interpreter
`/root/.venvs/peptide-omnipanel-v31-web311-20260723/bin/python`. Set
`CUDA_VISIBLE_DEVICES=GPU-e9419f8b-b24b-a22b-c8ec-8f5173f4b45a` and `PYTHONPATH` to
the task-owned `resources/local-gpu-route/vendor-dependencies` absolute WSL path.
No shared environment changes or package installations are needed.

The unit refuses direct invocation: it must be a private PGID/session leader
created by the scoring pool, whose real parent PID/start time/command line,
issued binding SHA and CPU2 affinity/thread environment are verified. This is
procedural provenance within the user's process account, not an OS security
boundary against another process controlled by that same user.

Examples are deliberately `issued:false`. Root/admin issue actual bindings only
after freezing the code, completing all 200 training selections / 400 candidate
fits, producing the independent full-grid barrier audit, and separately granting
post-barrier score authorization. Bindings contain references of exactly
`{path,sha256}`. `nc_run_contracts` owns central evaluation contracts; this code
does not create/sign them or fabricate selections.

Binding `entrypoint_sha256`, `pool_sha256` and `common_sha256` mean respectively
`score_unit.py`, `score_pool.py`, `score_common.py` in this directory. Actual SHA
values are filled after code freeze; they are not embedded in source, avoiding a
self-hash cycle. Code proofs must cover those three files, frozen
`launch/{common.py,pool_supervisor.py,run_unit.py}`, all four evaluation code files,
the frozen original runner, every Python file of the selected method's adapter
tree, and its vocabulary if present. No pickle/cache/checkpoint/gold file may be
used as a code proof. The original adapter Python tree hash is recomputed with
stdlib only, without importing the runner/model.

The pool index must contain exactly 200 bindings spanning five methods, two
panels, two training regimes and ten seeds, with 200 unique receipt directories
and 600 unique score output directories. Each unit binds one actual selection and
three distinct score specs: internal, external75, supplement13. The central
contract's `evaluation_stage` references must exactly equal the issued binding.

## Gates and resource limits

Both pool and unit check actual host `cihebi`, interpreter and virtual environment,
GPU UUID and dependency overlay. Before any scorer subprocess, checkpoint or gold
access, the unit verifies root score permission, the 200-selection/400-fit barrier,
independent audit, central contract and exact positive validation, original clock,
code SHA, three authorized score-spec SHA values, method tree, selected metadata
membership, and the experimental coordinate. The actual scorer then rechecks its
own gates, caches and model lineage and persists blind predictions before gold.

Only **one owned GPU worker** runs. Startup has three fresh compute-PID and
low-utilization probes, one second apart. Reported external/unknown compute PIDs
block new launches; they are never signalled or claimed as owned. A probe failure
also blocks new launches. Each subsequent launch rechecks GPU ownership and low
utilization and repeats metadata/code gates. NVIDIA WSL process visibility remains
imperfect; empty process output is not proof of perfect cross-OS visibility.

Each scoring unit has CPU2 affinity, process-tree RSS 4 GiB and Torch allocator at
most 3 GiB, as bound in its three score specs and central resources. The pool's
independent watchdog checks owned private-session RSS, per-unit monotonic deadline
and the original global wall-clock deadline every 0.2 seconds, with a progress
heartbeat every second. It only stops the private session it created. Its main
loop also checks reported GPU memory of owned PIDs; unknown owners only block new
launches. The shared frozen runner applies the actual Torch allocator budget.

The original global cutoff is **2026-10-22T01:45:00+00:00**. It cannot be extended.
Every new unit reserves the complete 1,200-second window for all three scores:
`actual_start + 1200 <= original_global_deadline`. A short remaining window does
not authorize shortening/resetting this timeout. Interrupted/failed outputs and
logs remain; no automatic retry or overwrite occurs.

## Output and resumption

Score outputs are always beneath `formal-runs-gpu-v4/scores`; the frozen scorer
creates `dataset/split/method/regime/seed-N` itself. Each unit keeps individual
stage start/end, actual child PID/PGID, exit code, stdout/stderr and SHA, and lists
three complete score receipts with dataset role and row count.

`unit-complete.json` records all result/log hashes, actual unit PID/PGID, binding,
selection, central contract, validation, specs and code SHA. It does not claim its
own future exit code. After the unit exits, the supervising pool waits/cleans the
whole owned session and writes `pool-exit-verification.json` plus SHA sidecar with
the real exit code, handles-absent evidence and pool-captured stdout/stderr hashes.
Only then is a unit counted complete. Root/admin archive both receipts together.

On resumption a completed unit is skipped only after SHA verification of its
completion receipt, all score artifacts, logs and actual pool exit proof. Prior
failed/incomplete receipts, outputs or log files prevent automatic rerun. Pool
attempts keep distinct terminal/startup receipts and progress; per-unit stdout and
stderr paths remain stable as declared by the central evaluation contract.

## Mechanical verification

WSL `unit-tests-wsl-v3.stderr.log` records **22 passing tests**, including:

- Unissued/unauthorized/incomplete 199-grid blocks before selection traversal.
- Exact contract validation, code SHA, three-score permission and selection audit.
- Original clock, full 1,200-second reservation, RSS/per-unit/global watchdog gates.
- No Torch/PyG/RDKit/runner/scorer imports by gate modules.
- No access to guarded synthetic gold/model/prediction files in valid preflight.
- Complete SHA resumption plus real pool-exit proof and mutation rejection.
- An actual temporary Linux parent/child private session is stopped and reaped;
  no GPU or model is involved.

The original failed Windows-only test attempt is preserved in
`unit-tests.stderr.log`; a mock for Linux-only `getpgrp` was corrected. The WSL v2
18-test pass and final v3 22-test pass are both retained. These are preparation
tests, not real scoring execution or evidence that any benchmark was scored.
