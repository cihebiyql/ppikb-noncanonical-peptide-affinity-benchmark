# Auxiliary CPU RF launcher — prepared, not authorized

This is an extra traditional Random Forest baseline. It contributes zero papers
to the five-model NN reproduction count and does not alter the frozen NN200
training or scoring code. Preparation has launched **zero real RF fits** and read
no real holdout gold, trained model, prediction or selected-model file.

## Interface and bindings

- Pool: `rf_pool.py --index ROOT_ISSUED_INDEX --index-sha256 ACTUAL_SHA`
- Unit: `rf_unit.py --binding ROOT_ISSUED_BINDING`
- Actual delegated worker, only after every gate:
  `rf_runner.py fit --spec EXACT_SPEC --authorization ROOT_RF_FIT_AUTH`

Use absolute WSL canonical paths, the existing generic runtime
`/root/.venvs/peptide-omnipanel-v31-web311-20260723/bin/python`, the task's reused
dependency overlay as `PYTHONPATH`, and **explicitly empty**
`CUDA_VISIBLE_DEVICES`. No new dependency, shared installation, Torch/GPU helper
or GPU query is needed by this launcher.

`binding.example.json` and `index.example.json` are unissued examples. Root/admin
fill actual SHA values after code freeze; source does not embed its own SHA.
The three binding code hashes refer to this directory's `rf_unit.py`,
`rf_pool.py`, `rf_common.py` respectively. Every reference is exactly
`{path,sha256}`. Code proofs cover those three files, frozen `launch/common.py`,
and the eight RF worker source/metadata assets listed by `rf_runner.source_hashes`.
No trained binary model, holdout file or feature cache can be a code proof.

Central `rf_execution_stage` must exactly bind `spec`, `authorization`,
`live_cpu_proof`, `worker`, `code_files`, `receipt_root`. The central command is
the actual interpreter plus this unit's absolute path and `--binding` path.
Central metadata preserves `method_id=RF-Classic`; the actual worker's explicit
method ID is `RF-Morgan2-chiral-AAC-DP`. These are an intentional conventional
baseline alias, not an additional prior-paper reproduction.

The root authorization must explicitly permit real RF fitting and the exact spec
SHA, bind the complete frozen RF source map, and retain the exact original
deadline. Positive central validation is SHA-bound to the actual frozen central
contract. Root's actual CPU resource proof is also bound and retained. Before
launch, the pool separately records **fresh** host memory/load/affinity evidence;
an older source proof is never relabelled as a fresh observation.

## Fixed execution scope and resource gates

Exactly **40 units = two panels × two training regimes × ten seeds** are required.
Each unit delegates two profiles (`min_samples_leaf=2,5`, 200 trees, `n_jobs=1`)
and validation-MAE selection with lower-index tie break. The wrapper verifies two
complete candidates and the frozen validation-only winner. No score CLI exists
in this launcher. Future scoring requires the separately authorized combined
NN200 plus RF40 selection barrier.

Actual host/interpreter/prefix/`PYTHONPATH`/empty CUDA are checked at pool and unit.
The unit can run only as its pool's actual child, private PGID/session leader,
with matching parent PID/start tick/command and bound index/binding SHA. This is
auditable process provenance, not an OS security boundary against the same user.

At most four owned RF workers run, each pinned to **one distinct logical CPU in
4–7**, threads one and nice 10, avoiding the NN pool's assigned 0–3 slots. This
does not claim exclusive ownership against all other OS scheduling. CPU slots
must actually be available in the pool affinity. Each worker's whole private
session has RSS cap **2 GiB**; all RF sessions plus this pool process have a total
**8 GiB** cap. Other processes are excluded from owned-RSS accounting and never
signalled. Startup requires at least 8 GiB currently available host memory;
subsequent launches require 2 GiB available and one-minute load at most the signed
index threshold (default 12). The pool lowers its actual active count when gates
do not permit another launch.

Every unit has **1,800 seconds**, including both candidates/selection and their
artifact writes. New launch requires `now + 1800 <= original cutoff`, fixed at
**2026-10-22T01:45:00+00:00**. No shortened timeout or retry can reset/extend it.
The independent resource watchdog checks RSS and per-unit/global deadlines every
0.2 seconds and enqueues a heartbeat every second.

## Live JSON locking and failure handling

`rf_common.write` uses a unique PID/thread/UUID temporary name. Replacement gets
at most seven attempts, with bounded 0.05/0.1/0.2/0.4/0.8/1-second backoffs for
`PermissionError`. It does not monkeypatch the frozen old writer. Pool progress
and receipts use a dedicated bounded-queue writer thread: Windows readers briefly
locking a live JSON file cannot pause the independent RSS/deadline watchdog.
Persistent writer failure triggers safe owned-session shutdown. There is no
unbounded retry, broad process kill, WSL restart or external process preemption.

Candidate models, validation predictions and candidate receipts are persisted by
the frozen RF worker; the launcher preserves all logs and SHA/exit evidence.
Existing output, incomplete receipt or old per-unit log prevents automatic
rerun. Completed units are skipped only after SHA revalidation of all artifacts
and actual supervising-pool exit proof. Failed attempts are not overwritten.

The unit records its actual PID/PGID and worker exit. It does not invent its own
future exit code. After the private session is really reaped, the pool writes
`pool-exit-verification.json` with actual wrapper exit, absent-session evidence and
pool stdout/stderr SHA; completion is counted only after that proof validates.

## Test evidence

Only synthetic metadata and sleeping child processes were tested. Tests exercise
missing authority, changed source/train input, contract validation, forbidden
binary code proofs, full original time windows, partial39 index rejection,
2/8 GiB RSS gates, real private parent/child cleanup, resumption SHA/exit proof,
bounded transient/persistent PermissionError handling, and continued independent
watchdog ticks while the writer retries. No sklearn/NumPy/Torch/RDKit or RF worker
is imported by these launch gates/tests.

Preparation is not a real fit, a valid central issuance, or permission to score.
