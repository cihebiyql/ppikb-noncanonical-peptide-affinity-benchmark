"""Root-authorized post-issue recovery binding/index only; starts no process."""
import copy
import json
from pathlib import Path

import prepare_campaign as pc

BASE = Path(__file__).resolve().parent
PROJECT = BASE.parent
CONTROL = PROJECT / "control"
REC = BASE / "io-recovery01"
WSL = "/mnt/d/work/科研工作台/research-tasks/peptide-binding-nc-benchmark-20261021"
OLD = "MGraphDTA__target_reference_homology_cold__NC_only__seed08"
NEW = OLD + "__io_recovery01"


def local(value):
    return Path("D:/" + value[len("/mnt/d/"):]) if str(value).startswith("/mnt/d/") else Path(value)


def wsl(value):
    return WSL + "/" + str(Path(value).relative_to(PROJECT)).replace("\\", "/")


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    issued_path = REC / "issued-root-v2" / "freeze-index.json"
    issued = pc.read(issued_path)
    if issued["frozen_units"] != 1 or issued["blocked_units"] != 0:
        raise ValueError("Root has not actually issued the recovery contract")
    recovered = issued["records"][0]
    if recovered["run_id"] != NEW or pc.sha(recovered["contract_path"]) != recovered["contract_sha256"]:
        raise ValueError("Root-issued recovery contract differs")
    contract = pc.read(recovered["contract_path"])
    if contract["contract_sha256"] if "contract_sha256" in contract else False:
        raise ValueError("Contract must not contain a fabricated self-hash")
    spec_ref = contract["execution"]["fit_spec"]
    if pc.sha(spec_ref["path"]) != spec_ref["sha256"]:
        raise ValueError("Recovery spec changed")
    envelope = pc.read(recovered["validation_binding_path"])
    if envelope["valid_for_execution"] is not True or envelope["contract_sha256"] != recovered["contract_sha256"]:
        raise ValueError("Exact issued validation missing")
    old_binding_path = CONTROL / "unit-bindings-v4" / (OLD + ".json")
    binding = pc.read(old_binding_path)
    binding.update(unit_id=NEW, spec=wsl(Path(spec_ref["path"])), spec_sha256=spec_ref["sha256"], contract=wsl(Path(recovered["contract_path"])), contract_sha256=recovered["contract_sha256"], validation=wsl(Path(recovered["validation_binding_path"])), validation_sha256=recovered["validation_binding_sha256"], deadline="2026-10-21T20:09:02.438325+00:00", binding_receipt=WSL + "/launch/bound-entry-receipts-v5-recovery/" + NEW + ".json")
    new_binding_path = CONTROL / "unit-bindings-v5-recovery" / (NEW + ".json")
    write_new(new_binding_path, binding)
    old_pool_path = CONTROL / "unit-index-v4-all-regimes.json"
    pool = pc.read(old_pool_path)
    original_unit = next(unit for unit in pool["units"] if unit["unit_id"] == OLD)
    replacement = copy.deepcopy(original_unit)
    replacement.update(unit_id=NEW, spec=binding["spec"], spec_sha256=binding["spec_sha256"], contract=binding["contract"], contract_sha256=binding["contract_sha256"], validation=binding["validation"], validation_sha256=binding["validation_sha256"], unit_binding=wsl(new_binding_path), unit_binding_sha256=pc.sha(new_binding_path))
    completed, pending_nc, pending_standard = [], [], []
    for unit in pool["units"]:
        if unit["unit_id"] == OLD:
            continue
        spec = pc.read(local(unit["spec"]))
        proof = spec["launch_proof"]
        if (local(proof["receipt_root"]) / "unit-complete.json").exists():
            completed.append(unit)
        elif spec["regime"] == "NC_only":
            pending_nc.append(unit)
        else:
            pending_standard.append(unit)
    if (len(completed), len(pending_nc), len(pending_standard)) != (86, 13, 100):
        raise ValueError("Root-reported no-live-pool scheduling state changed; do not guess or duplicate")
    pool["units"] = [replacement, *pending_nc, *pending_standard, *completed]
    pool["output_root"] = WSL + "/launch/pool-runs-v5-all-recovery"
    pool["recovery_issuance"] = {"authority": "Explicit parent root authorization after actual diagnostic/resource gate and central recovery contract issue", "superseded_interrupted_unit": OLD, "new_recovery_unit": NEW, "original_unit_absolute_deadline": binding["deadline"], "original_global_deadline_unchanged": pool["deadline"], "dispatch_order_basis": "Recovery first, then13 previously unstarted NC, then100 standard;86 completion-receipt-present cells last for runtime verify-skip. No numerical validation/test performance consulted", "completion_presence_not_new_scientific_verification": True, "prior_pool_index": {"path": str(old_pool_path), "sha256": pc.sha(old_pool_path)}, "root_diagnostic": {"path": str(CONTROL / "recovery-diagnosis-v1" / "diagnosis-summary.json"), "sha256": pc.sha(CONTROL / "recovery-diagnosis-v1" / "diagnosis-summary.json")}, "root_resource_probe": {"path": str(CONTROL / "recovery-resource-probe-v1.json"), "sha256": pc.sha(CONTROL / "recovery-resource-probe-v1.json")}, "actual_processes_launched_by_this_preparation": 0}
    pool_path = CONTROL / "unit-index-v5-all-recovery.json"
    write_new(pool_path, pool)
    old_freeze_path = BASE / "issued-gpu-v4" / "freeze-index.json"
    old_freeze = pc.read(old_freeze_path)
    records = [copy.deepcopy(record) if record["run_id"] != OLD else copy.deepcopy(recovered) for record in old_freeze["records"]]
    if len(records) != 200 or len({r["run_id"] for r in records}) != 200:
        raise ValueError("Eligible training roster must stay200")
    eligible_path = REC / "eligible-training-freeze-index-v5.json"
    pc.write_new(eligible_path, {"schema": "nc-eligible-training-contract-roster-v5", "created_at": pc.now(), "purpose": "199 original frozen contracts +one explicitly issued isolated recovery contract; not an execution completion claim", "units": 200, "frozen_units": 200, "source_freeze_indices": [{"path": str(old_freeze_path), "sha256": pc.sha(old_freeze_path)}, {"path": str(issued_path), "sha256": pc.sha(issued_path)}], "scientific_execution_index": {"path": str(REC / "execution-index-v5-recovery.json"), "sha256": pc.sha(REC / "execution-index-v5-recovery.json")}, "superseded_failed_record": next(r for r in old_freeze["records"] if r["run_id"] == OLD), "records": records})
    dispatch = {"created_at": pc.now(), "binding": {"path": str(new_binding_path), "sha256": pc.sha(new_binding_path)}, "full200_launch_index": {"path": str(pool_path), "sha256": pc.sha(pool_path)}, "eligible_training_contract_index": {"path": str(eligible_path), "sha256": pc.sha(eligible_path)}, "priority": {"recovery": 1, "pending_NC": 13, "pending_standard": 100, "runtime_verify_skip_presence": 86}, "same_old_cell_feature_cache_proofs_reused_exactly": replacement["feature_cache_proofs"] == original_unit["feature_cache_proofs"], "scientific_cells": 200, "retained_original_interruption_attempts": 1, "old_files_changed": 0, "raw_gold_weights_predictions_cache_payload_reads": 0, "models_launched": 0}
    pc.write_new(REC / "ROOT-LAUNCH-READY-v5.json", dispatch)
    print(json.dumps(dispatch, ensure_ascii=False))
