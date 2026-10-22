# Post-joint metadata helpers

These are administrative preparation tools. No real training or scoring has been started by either helper. The examples have authorization set to `false` and no invented future proof paths or hashes.

## Issue after the actual joint barrier

Use the existing Windows Python 3.11 administrative interpreter. Actual model/score pools remain in the existing WSL environment. Place the actual metadata input JSON and all referenced proof JSON files inside this project; paths may be Windows absolute paths or their canonical `/mnt/d/` equivalents. Each proof reference is `{ "path": "actual existing JSON path", "sha256": "actual digest" }`.

Start from `postjoint-issue-inputs.example.json`. Root supplies:

- An actual recovery-aware NN200/400 barrier using scientific index `c7b3bde68c9a741c0ac3f255a825e4a55dd7234e2b4e6d48f212fee8d5609ab1`, the actual RF40/80 barrier, and an actual joint240 barrier linking both hashes.
- The authorized scorer's actual full NN200 selection/checkpoint byte audit. This helper reads selected JSON only after root's two actual score permissions and all joint/audit checks pass. It never opens trained weights.
- NN score authorization with `root_scoring_authorized=true`, `allowed_phases` containing `score`, the original 30 score-spec hashes, matching `barrier_sha256` / `barrier_audit_sha256`, and **`joint_barrier_sha256`**. This extra metadata pin needs no frozen NN scorer change.
- RF score authorization with `root_RF_holdout_score_authorized=true`, all six original score-spec hashes, actual eight-file source hash map, actual joint hash and original global deadline. Existing runtime gates verify the frozen source and deadline.
- An actual CPU identity/time proof, and explicit `root_postjoint_metadata_issuance_authorized=true` in the root-created input JSON.

The input must not assert future authorizations before they actually exist. The helper refuses when a complete 1800-second RF window no longer fits before **2026-10-22 01:45 UTC**. It preserves the original clock; the recovery training-only 20:09 ceiling remains in training lineage and does not become the separate evaluation deadline.

```powershell
& 'C:\Users\ciheb\AppData\Local\Programs\Python\Python311\python.exe' -X utf8 `
  'D:\work\科研工作台\research-tasks\peptide-binding-nc-benchmark-20261021\administration\postjoint_issue_all.py' `
  --inputs 'D:\work\科研工作台\research-tasks\peptide-binding-nc-benchmark-20261021\administration\ROOT-ACTUAL-POSTJOINT-INPUTS.json' `
  --out 'D:\work\科研工作台\research-tasks\peptide-binding-nc-benchmark-20261021\administration\postjoint-issued-v1'
```

Outputs are 200 NN and 40 auxiliary RF stage contracts, central validator reports/envelopes, 240 postissue bindings, two immutable pool indices and `POSTJOINT-ISSUANCE.json`. The latter returns exact WSL argv and index SHA for root to launch. The helper launches **zero** processes. NN uses one score worker/1200 seconds; RF uses four CPU slots 4–7/1800 seconds, unchanged frozen launcher resource gates. Reusing an existing output or binding path raises an error; never overwrite an issued revision or hide partial issuance.

## Assemble standard records after real scoring and independent review

Start from `postjoint-archive-inputs.example.json`. Root supplies the actual `POSTJOINT-ISSUANCE.json` plus independent NN600 and RF120 **per-score-audit JSON lists**. Explicit archival authority is required. `root_accept_reviewed_records=true` is a separate, later root adoption decision after reviewing these actual artifacts; leaving it false emits pending records only.

```powershell
& 'C:\Users\ciheb\AppData\Local\Programs\Python\Python311\python.exe' -X utf8 `
  'D:\work\科研工作台\research-tasks\peptide-binding-nc-benchmark-20261021\administration\assemble_postjoint_archive.py' `
  --inputs 'D:\work\科研工作台\research-tasks\peptide-binding-nc-benchmark-20261021\administration\ROOT-ACTUAL-ARCHIVE-INPUTS.json' `
  --out 'D:\work\科研工作台\research-tasks\peptide-binding-nc-benchmark-20261021\administration\postjoint-archive-v1'

& 'C:\Users\ciheb\AppData\Local\Programs\Python\Python311\python.exe' -X utf8 `
  'D:\work\科研工作台\research-tasks\peptide-binding-nc-benchmark-20261021\administration\validate_stage_result_index.py' `
  --index 'D:\work\科研工作台\research-tasks\peptide-binding-nc-benchmark-20261021\administration\postjoint-archive-v1\standard-result-index.json' `
  --out 'D:\work\科研工作台\research-tasks\peptide-binding-nc-benchmark-20261021\administration\postjoint-archive-v1\index-validation'
```

The first pass requires all 720 distinct producer receipt hashes, 318960 predicted rows, 240 exact scientific cells, actual unit binding/contract SHA, immutable process-start metadata, successful pool-side exit and process-tree absence, original training receipt/exit, and exact independent600/120 coverage with no metric disagreement. No standard result record is emitted until this full first pass succeeds. Archived results retain the original MGraph `-15` interrupted attempt and its separate successful recovery lineage; 400 valid NN fits/200 cells never become 201 cells.

The second pass fills 240 standard records and runs the unchanged central validator. It reads receipt/audit JSON metadata only. Its central result validation uses `check_files=false` because raw gold, weights, caches and prediction bytes were already checked by the authorized producers/root audit/independent reviewer; it does **not** claim a new full payload-byte audit. Pending records are retained when root later requests separate accepted copies. A mathematically undefined correlation remains `null` with its original denominator.

`five-paper-summary-rows.proposed.json` and `new-batch-adoption-proposal.json` target only the newly registered five-paper batch, pin its current summary SHA, and require root review/application. RF contributes zero papers. Neither helper edits the actual batch summary, old 62-paper ledger, frozen training/score sources, old v4 history, or platform-denied workflows. These are scoped common-data adaptations; they never claim original-paper main-table replication.

## Verification performed during preparation

`test_postjoint_metadata.py` tests authority-before-read, actual joint counts and v5 hashes, full NN/RF coordinate grids, no 201st recovery cell, exact binding schema mapping, independent600/120 uniqueness, disagreement/partial rejection and scientific-payload rejection. The tests use synthetic dictionaries and mocked metadata readers only. Combined with the existing administrative tests, 29 tests passed; the actual test receipt is stored in `postjoint-helper-verification-v1/`.
