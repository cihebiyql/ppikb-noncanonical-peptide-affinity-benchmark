# Explicit root post-joint driver

Preparation does not run this driver. It requires an explicit root flag and an immutable actual root-observed NN pool exit proof. It never starts either score pool and does not wait/poll for training to finish.

After root's actual wait on the unique NN pool returns exit0, root writes a separate JSON using the keys shown in `pool-exit-proof.example.json`: real `pool_pid`, `exit_code:0`, `observed_at`, actual wait/session `source`, approved index hash, and `root_observed_actual_wait:true`. The example remains invalid and is never used as proof. The file must be inside this project. This is necessary because a child metadata driver cannot retrospectively perform the parent's OS wait and must not infer exit0 from outputs.

Run with the existing Windows Python311 (substitute actual proof, SHA and a fresh execution name):

```powershell
& 'C:\Users\ciheb\AppData\Local\Programs\Python\Python311\python.exe' -X utf8 `
  'D:\work\科研工作台\research-tasks\peptide-binding-nc-benchmark-20261021\control\root-postjoint-v1\root_postjoint.py' `
  --root-execute-postjoint-authorized `
  --pool-exit-proof '<actual immutable root wait proof JSON inside project>' `
  --pool-exit-proof-sha256 '<actual SHA256>' `
  --execution-name 'execution-v1'
```

The wrapper verifies its frozen source/spec metadata. Through WSL only, it verifies the actual root wait proof, absence of that pool PID, exact v5 launch index and full200 success metadata. It requires a unique immutable `attempts/*/terminal.json`, zero failed/pending/active units, correct completed IDs and unchanged deadline. The only producer `progress.json` read is by WSL after actual exit. Windows never opens live producer metadata.

It then invokes only the existing frozen scientific entrypoints, in this order:

1. `execution/runner.py freeze-barrier` on recovery-aware c7b3… index; actual200 selection/checkpoint byte verification, no forward/gold.
2. `rf_runner.py joint-barrier` with unchanged actual RF40 barrier c03d… .
3. A tightly scoped **audit-only** authorization, created only after the producer/joint gates, allows `score_cached.py audit-barrier` to verify all200 actual checkpoint bytes and original validation choices. This authorization has no `score` phase or score-spec whitelist.
4. Only after that actual audit succeeds, create NN30-spec and RF6-spec scoring permissions, both pinned to the actual joint and original cutoff. Create a fresh CPU/time proof.
5. Invoke `administration/postjoint_issue_all.py` under Windows to validate/issue200NN+40RF metadata contracts/bindings and two immutable pool indices.

The output `NEXT-POOL-COMMANDS.json` contains exact next two pool argv/SHA and environment; **root separately launches them**. Scientific commands use the existing generic WSL Python/vendor route, CPU-only preparatory visibility and one-thread libraries. Each command is bounded by600sec and the remaining original time reserve; the WSL preparatory process has a1900sec GNU timeout and cleans its owned scientific child session on interruption. Metadata issuance is bounded by600sec. No package/environment changes occur.

The deadline stays **2026-10-22 01:45 UTC**. Every step requires a full remaining1800sec evaluation window. No actual authorization is generated during preparation or before producer/joint completion; final score permissions are generated only after the actual200-checkpoint audit. Audit-only permission is mechanically required by the frozen audit entrypoint and cannot score.

New execution directories and logs use exclusive creation. Errors preserve all earlier outputs, authorize no automatic retry, do not relax gates and never start scores. If partial metadata issuance occurs, root must inspect it before choosing any new revision; no hidden overwrite/restart. Recovery training20:09 remains a preserved training-stage bound, and old62/platform-denied workflows remain untouched.

`SOURCE-FREEZE-v1.json` binds this driver, existing administrative generators, frozen scientific source, original30+6 score specs, eligible NNv5 roster/index and unchanged central validator. `synthetic.*.log` records10 synthetic tests. No real selection, trained weight, label, cache or prediction is opened while preparing/testing/freezing this driver.
