# CUDA failure02: bounded explicit same-configuration retry

Preparation reads only the closed failed unit's metadata/logs and immutable source/spec files. No actual scientific output is archived or retried during preparation; no real model, gold or prediction file is opened. Synthetic tests retain their small fixtures in this owned directory.

The original candidate0 failed with `torch.AcceleratorError: CUDA error: unknown error`, exit1, during PyG aggregation. The message warns asynchronous reporting may point to another call. This is an observed runtime error, without a claim of deterministic model defect, OOM, driver cause or platform rejection. No driver/WSL restart or source/environment change is proposed.

## Scope and clock

- Scientific cell: `MGraphDTA / target_reference_homology_cold / standard_only / seed6`.
- Original spec SHA `62cb03bbc33f3bbcfd63f4d9c2b59513d7b6d60ffe7528462e6e18d73f17e8f7`; contract SHA `3ed3deba92dff057d824050a419bb790df82d4eb15ae23ab4b41e34a0641f4f2` remain unchanged.
- Original first start20:54:18.654494UTC and **absolute unit ceiling22:54:18.479676UTC on2026-10-21** remain fixed. Both new retry pool index and new binding use this ceiling. Project deadline remains2026-10-22 01:45UTC. These are separate stage bounds, not a fresh2-hour window.
- Scientific execution index **c7b3bde68c9a741c0ac3f255a825e4a55dd7234e2b4e6d48f212fee8d5609ab1** and RF frozen source/index relationship remain unchanged. No frozen source/spec/contract/validator is edited.
- One new runtime `attempt_id` is distinct from its existing scientific `unit_id`. The new binding changes only its actual binding receipt path and deadline. Its file path/launcher command differ explicitly as runtime routing; original contract scientific configuration and positive validation remain linked. New pool has one worker, same GPU/CPU/epoch/LR/seed/dependency budget, one pending retry and199 verified skips.

## Root step1: wait for the original pool to drain and actually exit2

Do not run the helper while that pool is alive. Root must first observe its real wait result and save an immutable actual wait proof JSON **inside the project**:

```json
{
  "exit_code": 2,
  "pool_pid": "ACTUAL_LINUX_SUPERVISOR_PID_AS_INTEGER",
  "index_sha256": "fe51a0d03f4f9c08e710e9d8b582d56c497d8c59dc5d14e8cbc6e6d8b41e51d2",
  "root_observed_actual_wait": true,
  "observed_at": "ACTUAL_UTC_TIME",
  "source": "ACTUAL_PARENT_WAIT_OR_SESSION_EXIT_EVIDENCE"
}
```

This is a schema illustration, not actual evidence. The prior frozen pool's truthful drained state is `status=complete, reason=null, complete199, failed1, actual exit2`. The helper requires the sole failed cell/reason, original200-coordinate set, no pending/active/cleanup errors, actual root-observed wait, absence of prior pool PID and absence of failed private PGID/session members. Producer progress is read only via WSL after actual exit. Old pool logs and terminal files remain in place.

Under the existing generic WSL Python/vendor route, root may then explicitly invoke:

```text
env PYTHONPATH=/mnt/d/work/科研工作台/research-tasks/peptide-binding-nc-benchmark-20261021/resources/local-gpu-route/vendor-dependencies CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
/root/.venvs/peptide-omnipanel-v31-web311-20260723/bin/python \
/mnt/d/work/科研工作台/research-tasks/peptide-binding-nc-benchmark-20261021/administration/cuda-recovery02/recovery.py \
--root-execute-archive-and-retry-metadata-authorized \
--pool-exit-proof ACTUAL_OLD_WAIT_JSON --pool-exit-proof-sha256 ACTUAL_SHA \
--execution-name execution-v1
```

The runtime helper first writes a dry `archive-intent.json` with every original path→archive path, byte SHA, size, type and timestamps for the failed fit-root and receipt-root. It rejects symlinks, hardlinks, special files, destinations that exist and resolved paths outside the project/owned archive. It rechecks the complete inventory immediately before mutation, uses same-filesystem `os.rename` without deletion/overwrite, rechecks every archived byte/path/mtime, and writes `archive-complete.json`. It never deserializes model or prediction artifacts; runtime hashing is explicitly part of the root-authorized complete byte archive. Root directories are moved intact. If any step fails, earlier intent/moves remain preserved; no automatic rollback/retry occurs.

This is **explicit namespace reuse**: scientific output paths now refer to the retry; they no longer by themselves identify the old attempt. The archive manifest is the permanent original-attempt address map. The old binding launch receipt, outer old pool stdout/stderr/started/terminal remain untouched. The two failed output trees are the only actual directories moved.

`execution-v1/RECOVERY-READY.json` returns a pinned new pool index and exact launch argv/environment. **The helper does not launch it.** Root separately starts the original frozen supervisor with that new immutable index. The new actual pool output directory is `launch/pool-runs-v6-cuda-recovery02`; it must not exist before metadata preparation. Its pool deadline is the original22:54 ceiling, and the new bound entry receipt is isolated. Expiry or a second failure is terminal: keep the incomplete scope; do not repeat recovery or reset clocks.

## Root step2: new post-joint v2 gate, after the retry pool actually exits0

Root saves a second actual wait proof with `exit_code:0`, actual new Linux supervisor PID and the **new retry pool index SHA**. Run the new v2 driver rather than altering the old v1 helper or its freeze:

```text
env PYTHONPATH=/mnt/d/work/科研工作台/research-tasks/peptide-binding-nc-benchmark-20261021/resources/local-gpu-route/vendor-dependencies CUDA_VISIBLE_DEVICES= OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
timeout --signal=TERM --kill-after=15s 1900s \
/root/.venvs/peptide-omnipanel-v31-web311-20260723/bin/python \
/mnt/d/work/科研工作台/research-tasks/peptide-binding-nc-benchmark-20261021/administration/cuda-recovery02/postjoint_v2.py \
--root-execute-postjoint-v2-authorized \
--recovery-ready ACTUAL_RECOVERY_READY_JSON --recovery-ready-sha256 ACTUAL_SHA \
--retry-pool-exit-proof ACTUAL_NEW_WAIT_JSON --retry-pool-exit-proof-sha256 ACTUAL_SHA \
--execution-name postjoint-v2-execution1
```

The gate separately verifies old exit2/199success1failure and new exit0/200success0failure, their real pool terminal hashes/PID absence, full immutable archive inventory, original cap on successful retry finish, exactly one newly launched scientific unit, actual same-config selection and unchanged c7b3 index. It emits `CUDA-ATTEMPT-CHAIN.json` with method/panel/regime/seed, full prior failure/oldwait/archive/mapping/newbinding/newwait/success/selection references.

Only then does v2 run the original frozen NN freeze, RF joint and audit-only checkpoint-byte audit. It creates final NN/RF scoring permissions only after the actual audit succeeds; all stages retain the original01:45 project window and require a full1800sec evaluation reserve. Existing generic WSL/runtime/vendor assets are reused. The existing WindowsPython311 metadata issuer is called through WSL interop with Windows absolute metadata paths; its source is unchanged. Each preparatory subprocess has a≤600sec cap; SIGTERM/INT cleanup applies to its private child session.

The unchanged issuer receives an extra `cuda_attempt_chain` reference in its root input metadata. `POSTJOINT-CUDA-LINEAGE.json` separately binds the issued240 metadata and the required chain, and `NEXT-POOL-COMMANDS.json` returns the two score pool argv/SHA. **No score process is launched by v2.** Old v1 code/freeze, original scientific index, frozen training/scorer/RF code and old62/platform-denied workflows remain untouched.

## Root step3: keep the CUDA history in the final standard result

The unchanged standard archive assembler does not infer this second failure from the unchanged original contract. After actual720 scores/independent600+120 audits and ordinary standard-record assembly, run `attach_archive_lineage.py` with explicit root archival authority:

```text
WINDOWS_PYTHON311 -X utf8 administration/cuda-recovery02/attach_archive_lineage.py \
--root-attach-final-lineage-authorized \
--index ACTUAL_STANDARD_RESULT_INDEX_JSON \
--chain ACTUAL_CUDA_ATTEMPT_CHAIN_JSON \
--out administration/cuda-recovery02/final-archive-lineage-v1
```

It writes a **new copy of exactly the affected evaluation result**, adds the failure/archive/retry lineage to `stage_lineage`, `differences` and hashed artifacts, runs the unchanged central validator, and emits a new result index referencing that copy plus the other239 unchanged records. Original accepted/pending records and original index are not overwritten. Default review becomes pending for the augmented result. Root may explicitly add `--root-review-accept-lineage` only after reviewing the actual chain and when the original result was already accepted/succeeded; lineage-only review cannot replace the full scoped-result review. Validate/adopt the **new** index and use it in the final new-batch summary proposal.

Final accounting remains **400 valid NN configurations/200 selected cells plus two preserved interrupted attempts**, with RF80 fits unchanged. The first I/O recovery remains in existing contract lineage; the second CUDA failure is mandatory in the new immutable supplement. No metric-based change or test-dependent method choice occurs.
