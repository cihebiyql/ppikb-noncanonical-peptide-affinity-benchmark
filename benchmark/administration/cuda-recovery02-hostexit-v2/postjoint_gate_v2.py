"""Actual two-pool lineage gate; called only by explicit root v2 post-joint run."""
from pathlib import Path
import copy
import time
from datetime import datetime, timezone

import recovery as r


def retry_terminal(body, ids, index_sha):
    if body.get("status") != "complete" or body.get("reason") is not None or body.get("pending") != 0 or body.get("active") != [] or body.get("cleanup_errors") != [] or body.get("complete_count") != 200 or body.get("failed_count") != 0 or body.get("failed_units") != []:
        raise PermissionError("Actual successful retry200/0 terminal required; failed retry is terminal")
    if len(body.get("completed_units", [])) != 200 or set(body["completed_units"]) != set(ids) or body.get("index_sha256") != index_sha or body.get("deadline") != r.CEILING:
        raise ValueError("Retry terminal must use original unit absolute ceiling and exact200 scientific grid")


def gate(ready_path, ready_sha, retry_wait_path, retry_wait_sha, output, authorized=False):
    if authorized is not True: raise PermissionError("Explicit root actual post-retry gate permission required")
    if r.sha(ready_path) != ready_sha or r.sha(retry_wait_path) != retry_wait_sha: raise ValueError("Root recovery/wait metadata changed")
    ready = r.read(ready_path)
    if ready.get("attempt_id") != r.ATTEMPT or ready.get("scientific_index_sha256_unchanged") != r.SCIENCE_SHA or ready.get("explicit_retry_limit") != 1: raise ValueError("Not the uniquely authorized CUDA recovery")
    archive_ref = ready["archive_manifest"]
    if r.sha(archive_ref["path"]) != archive_ref["sha256"]: raise ValueError("Original-byte archive manifest changed")
    archived = r.read(archive_ref["path"])
    if archived.get("status") != "all_failed_tree_bytes_and_paths_archived_verified" or not archived.get("namespace_reuse") or archived.get("original_absolute_unit_ceiling") != r.CEILING: raise ValueError("Closed verified same-namespace archive proof required")
    for tree in archived["trees"]: r.assert_inventory(tree["archive_root"], tree["entries"], archived=True)
    old_wait_ref = ready["prior_pool_wait"]
    if r.sha(old_wait_ref["path"]) != old_wait_ref["sha256"]: raise ValueError("Prior actual wait evidence changed")
    old_wait = r.read(old_wait_ref["path"]); r.check_wait(old_wait, 2, r.POOL_SHA)
    host_observation = r.verify_host_mapping(old_wait)
    old_index = r.read(r.PROJECT / "control/unit-index-v5-all-recovery.json"); ids = [u["unit_id"] for u in old_index["units"]]
    old_term_ref = ready["prior_pool_terminal"]
    if r.sha(old_term_ref["path"]) != old_term_ref["sha256"]: raise ValueError("Prior actual199/1 terminal changed")
    r.check_old_terminal(r.read(old_term_ref["path"]), ids)
    retry_index_ref = ready["retry_pool_index"]
    if r.sha(retry_index_ref["path"]) != retry_index_ref["sha256"]: raise ValueError("Actual retry index changed")
    retry_index = r.read(retry_index_ref["path"])
    if retry_index["deadline"] != r.CEILING or retry_index["max_concurrent"] != 1 or [u["unit_id"] for u in retry_index["units"]][0] != r.UID or {u["unit_id"] for u in retry_index["units"]} != set(ids): raise ValueError("Retry pool resource/clock/coordinates differ")
    retry_wait = r.read(retry_wait_path); r.check_wait(retry_wait, 0, retry_index_ref["sha256"])
    for pid in (old_wait["pool_pid"], retry_wait["pool_pid"]):
        if Path("/proc", str(pid)).exists(): raise PermissionError("A producer pool remains alive")
    pool = Path(retry_index["output_root"])
    retry_terminal(r.read(pool / "progress.json"), ids, retry_index_ref["sha256"])  # WSL only after exit0.
    terminals = []
    for path in (pool / "attempts").glob("*/terminal.json"):
        body = r.read(path)
        if body.get("status") == "complete":
            retry_terminal(body, ids, retry_index_ref["sha256"]); terminals.append(r.ref(path))
    if len(terminals) != 1: raise ValueError("Unique actual successful retry-pool terminal required")
    failed_ref = archived["prior_failed_terminal"]
    if r.sha(failed_ref["path"]) != failed_ref["sha256"]: raise ValueError("Old failed terminal not preserved")
    success_path = pool / (r.UID + ".terminal.json")
    success = r.read(success_path)
    if success.get("exit_code") != 0 or success.get("status") != "complete" or success.get("finished_at") is None or datetime.fromisoformat(success["finished_at"].replace("Z", "+00:00")) > datetime.fromisoformat(r.CEILING): raise ValueError("Explicit retry did not actually finish within original ceiling")
    if len(list(pool.glob("*.terminal.json"))) != 1: raise ValueError("Retry must launch only one scientific unit,199 others verify-skip")
    scientific = r.PROJECT / "administration/io-recovery01/execution-index-v5-recovery.json"
    if r.sha(scientific) != r.SCIENCE_SHA: raise ValueError("Original c7b3 scientific index changed")
    original_unit = next(u for u in old_index["units"] if u["unit_id"] == r.UID)
    spec = r.read(original_unit["spec"]); selection_path = Path(spec["run_root"]) / "selection.json"
    selected = r.read(selection_path)
    if selected.get("status") != "frozen" or selected.get("holdout_metrics_consulted") is not False or selected.get("fit_spec_sha256") != r.SPEC_SHA: raise ValueError("Recovered model selection not original scientific configuration")
    chain = {"schema": "cuda-attempt-chain-supplement.v1", "attempt_id": r.ATTEMPT, "scientific_unit_id": r.UID, "evaluation_unit_id": r.UID + "__evaluation_v1", "coordinate": {"method_id": "MGraphDTA", "split_id": "target_reference_homology_cold", "regime": "standard_only", "seed": 6}, "prior_failed_stage": r.ref(r.HERE / "closed-failure-facts.json"), "prior_pool_wait_outer1_native_unobserved": old_wait_ref, "prior_pool_exit_observation": host_observation, "prior_pool_terminal199success1failed": old_term_ref, "prior_failed_terminal": failed_ref, "archive_manifest": archive_ref, "retry_binding": ready["retry_binding"], "retry_pool_index": retry_index_ref, "retry_pool_wait_exit0": r.ref(retry_wait_path), "retry_pool_terminal200success0failed": terminals[0], "retry_unit_terminal_exit0": r.ref(success_path), "selection": r.ref(selection_path), "original_first_start": archived["original_first_start"], "original_absolute_unit_ceiling": r.CEILING, "original_global_deadline": r.GLOBAL, "same_namespace_reuse": True, "complete_oldpath_to_archivepath_SHA_map": archive_ref, "scientific_index_sha256_unchanged": r.SCIENCE_SHA, "valid_NN_fits": 400, "selected_NN_cells": 200, "extra_interrupted_attempts": 2, "RF_valid_fits_unchanged": 80, "created_at": datetime.now(timezone.utc).isoformat(), "must_attach_to_final_standard_cell_result": True}
    r.write(Path(output) / "CUDA-ATTEMPT-CHAIN.json", chain)
    return chain
