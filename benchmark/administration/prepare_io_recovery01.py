"""Prepare one isolated, explicitly requested I/O recovery; never execute/issue.

Only spec/contract/receipt metadata and small original log hashes are read.
Partial trained artifacts are listed by stat only, never opened or overwritten.
"""
import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import prepare_campaign as pc

BASE = Path(__file__).resolve().parent
PROJECT = BASE.parent
WSL = "/mnt/d/work/科研工作台/research-tasks/peptide-binding-nc-benchmark-20261021"
OLD_UID = "MGraphDTA__target_reference_homology_cold__NC_only__seed08"
NEW_UID = OLD_UID + "__io_recovery01"


def local(value):
    value = str(value)
    return Path("D:/" + value[len("/mnt/d/"):]) if value.startswith("/mnt/d/") else Path(value)


def wsl(value):
    return WSL + "/" + str(Path(value).relative_to(PROJECT)).replace("\\", "/")


if __name__ == "__main__":
    source_index_path = PROJECT / "control" / "gpu-fit-specs-v4" / "execution-index.json"
    source_index = pc.read(source_index_path)
    matches = [unit for unit in source_index["units"] if unit["unit_id"] == OLD_UID]
    if len(matches) != 1:
        raise ValueError("Original failed scientific coordinate not unique")
    original = matches[0]
    spec_path = local(original["spec_path"])
    original_spec = pc.read(spec_path)
    if pc.sha(spec_path) != original["spec_sha256"]:
        raise ValueError("Immutable original spec changed")
    contract_path = BASE / "issued-gpu-v4" / OLD_UID / "task-contract.json"
    contract = pc.read(contract_path)
    receipts = PROJECT / "launch" / "receipts-v4" / OLD_UID
    unit_started_path = receipts / "unit-started.json"
    unit_started = pc.read(unit_started_path)
    terminal_path = PROJECT / "launch" / "pool-runs-v4-nc-all-seeds" / (OLD_UID + ".terminal.json")
    terminal = pc.read(terminal_path)
    binding_path = PROJECT / "control" / "unit-bindings-v4" / (OLD_UID + ".json")
    original_binding = pc.read(binding_path)
    bound_receipt_path = PROJECT / "launch" / "bound-entry-receipts-v4" / (OLD_UID + ".json")
    bound = pc.read(bound_receipt_path)
    if terminal["status"] != "failed" or terminal["exit_code"] != -15:
        raise ValueError("Original actual failed terminal receipt differs")
    if pc.sha(contract_path) != unit_started["contract_sha256"] or unit_started["spec_sha256"] != original["spec_sha256"]:
        raise ValueError("Original start receipt binding differs")
    absolute = unit_started["effective_unit_deadline"]
    if absolute != "2026-10-21T20:09:02.438325+00:00" or unit_started["started_at"] != "2026-10-21T18:09:02.570268+00:00":
        raise ValueError("Do not reset or guess original unit clock")
    if bound["actual_unit_deadline"] != absolute:
        raise ValueError("Actual original entrypoint deadline differs")
    if local(original["selection_path"]).exists():
        raise ValueError("Original cell already has a selection; do not create duplicate recovery")
    if (receipts / "unit-complete.json").exists() or (local(original_spec["run_root"]) / "candidate-0" / "complete.json").exists():
        raise ValueError("Original interrupted candidate has completion evidence; root must reassess")
    output = BASE / "io-recovery01"
    output.mkdir(exist_ok=False)
    new_spec = copy.deepcopy(original_spec)
    new_spec["run_root"] = WSL + "/formal-runs-gpu-v4/fits/" + NEW_UID
    new_spec["launch_proof"]["receipt_root"] = WSL + "/launch/receipts-v4/" + NEW_UID
    scientific_old = copy.deepcopy(original_spec)
    scientific_new = copy.deepcopy(new_spec)
    for value in (scientific_old, scientific_new):
        value.pop("run_root")
        value["launch_proof"].pop("receipt_root")
    if scientific_old != scientific_new:
        raise ValueError("Recovery attempted to change scientific or code inputs")
    new_spec_path = output / (NEW_UID + ".fit-spec.json")
    pc.write_new(new_spec_path, new_spec)
    draft = copy.deepcopy(contract)
    draft.update(run_id=NEW_UID, is_template=True, contract_status="draft", created_at=pc.now(), frozen_at=None, revision=1, previous_contract_sha256=None, revision_reason="Explicit one-time isolated I/O recovery; original failed attempt and all clocks retained")
    draft["execution_scope"]["prior_run_ids"] = sorted(set(draft["execution_scope"].get("prior_run_ids", []) + [OLD_UID]))
    draft["execution_scope"]["relation_to_prior_run"] = "Explicit parent-requested isolated recovery of one interrupted runtime I/O attempt. Same method/seed/panel/regime/candidates/data/model tree/runner; original -15 terminal, partial outputs and source contracts/specs untouched. Not a reset or a new scientific cell. Root diagnosis and live resource readiness still required before issue."
    draft["timing"]["additional_deadlines_at"] = sorted(set(draft["timing"].get("additional_deadlines_at", []) + [absolute]))
    draft["timing"]["effective_deadline_at"] = absolute
    draft["execution"].update(command=[contract["execution"]["command"][0], WSL + "/control/run_bound_unit.py", "--binding", WSL + "/control/unit-bindings-v5-recovery/" + NEW_UID + ".json"], timeout_seconds=1200, stdout_path=WSL + "/launch/pool-runs-v5-recovery/" + NEW_UID + ".stdout.log", stderr_path=WSL + "/launch/pool-runs-v5-recovery/" + NEW_UID + ".stderr.log", fit_spec={"path": str(new_spec_path), "sha256": pc.sha(new_spec_path)}, launch_proof=copy.deepcopy(new_spec["launch_proof"]))
    draft["benchmark_metadata"]["fit_spec_sha256"] = pc.sha(new_spec_path)
    draft["recovery_metadata"] = {"original_run_id": OLD_UID, "recovery_number": 1, "authorized_action": "Draft-only isolated one-slot I/O recovery requested directly by parent; no automatic retry", "original_unit_started_at": unit_started["started_at"], "original_binding_started_at": bound["started_at"], "original_absolute_unit_deadline": absolute, "original_global_effective_deadline": contract["timing"]["effective_deadline_at"], "new_unit_timeout_seconds": 1200, "first_scope_clock_unchanged": True, "diagnosis_state": "Root reports watchdog PermissionError13 suspected Windows live atomic-JSON sharing lock; formal diagnostic receipt and live resource gate pending", "not_classified_as_platform_restriction_or_OOM": "Root-provided scope statement; actual -15 terminal retained; no new biology or source-unit investigation", "original_contract": {"path": str(contract_path), "sha256": pc.sha(contract_path)}, "original_fit_spec": {"path": str(spec_path), "sha256": pc.sha(spec_path)}, "original_terminal": {"path": str(terminal_path), "sha256": pc.sha(terminal_path)}, "original_unit_started": {"path": str(unit_started_path), "sha256": pc.sha(unit_started_path)}, "original_binding": {"path": str(binding_path), "sha256": pc.sha(binding_path)}, "original_bound_entry_receipt": {"path": str(bound_receipt_path), "sha256": pc.sha(bound_receipt_path)}, "scientific_changes": [], "only_spec_deltas": ["run_root", "launch_proof.receipt_root"], "source_outputs_read_or_overwritten": False, "live_resource_ready": False, "diagnostic_receipt": None}
    draft["review"].update(status="pending", reviewer=None, reviewed_at=None)
    new_contract_path = output / "task-contract.draft.json"
    pc.write_new(new_contract_path, draft)
    original_output = local(original_spec["run_root"])
    inventory = [{"relative_path": str(file.relative_to(original_output)).replace("\\", "/"), "size_bytes": file.stat().st_size, "payload_opened": False} for file in sorted(original_output.rglob("*")) if file.is_file()]
    sources = [source_index_path, spec_path, contract_path, terminal_path, unit_started_path, binding_path, bound_receipt_path]
    for name in ("candidate-0.started.json", "candidate-0.stderr.log", "candidate-0.stdout.log"):
        file = receipts / name
        if file.exists():
            sources.append(file)
    proof = {"schema": "nc-explicit-isolated-io-recovery-source-proof.v1", "created_at": pc.now(), "original_run_id": OLD_UID, "new_run_id": NEW_UID, "original_actual_exit_code": terminal["exit_code"], "original_unit_started_at": unit_started["started_at"], "original_absolute_unit_deadline": absolute, "original_global_deadline": contract["timing"]["effective_deadline_at"], "frozen_scientific_input_equivalence": scientific_old == scientific_new, "only_spec_deltas": ["run_root", "launch_proof.receipt_root"], "original_sources": [{"path": str(file), "sha256": pc.sha(file)} for file in sources], "interrupted_output_inventory_stat_only": inventory, "new_spec": {"path": str(new_spec_path), "sha256": pc.sha(new_spec_path)}, "new_draft_contract": {"path": str(new_contract_path), "sha256": pc.sha(new_contract_path)}, "weights_gold_predictions_opened": 0, "models_launched": 0, "old_files_modified": 0, "root_diagnosis_and_resource_gate_pending": True}
    proof_path = output / "recovery-source-proof.json"
    pc.write_new(proof_path, proof)
    new_index = copy.deepcopy(source_index)
    replacement = next(row for row in new_index["units"] if row["unit_id"] == OLD_UID)
    old_selection_path = replacement["selection_path"]
    replacement.update(unit_id=NEW_UID, spec_path=str(new_spec_path), spec_wsl_path=wsl(new_spec_path), spec_sha256=pc.sha(new_spec_path), draft_contract_path=str(new_contract_path), selection_path=new_spec["run_root"] + "/selection.json", binding_wsl_path=WSL + "/control/unit-bindings-v5-recovery/" + NEW_UID + ".json")
    changed_jobs = 0
    for job in new_index["candidate_fits"]:
        if job["unit_id"] == OLD_UID:
            job.update(unit_id=NEW_UID, spec_path=str(new_spec_path), spec_sha256=pc.sha(new_spec_path))
            changed_jobs += 1
    changed_selections = 0
    for row in new_index["per_seed_selections"]:
        if row["selection_path"] == old_selection_path:
            row.update(spec_path=wsl(new_spec_path), selection_path=new_spec["run_root"] + "/selection.json")
            changed_selections += 1
    if changed_jobs != 2 or changed_selections != 1 or len(new_index["units"]) != 200 or len(new_index["candidate_fits"]) != 400:
        raise ValueError("Recovery must replace exactlyone cell/two candidate references")
    new_index.update(schema="nc-gpu-fit-specs-v5-isolated-io-recovery", issued=False, predecessor_index=str(source_index_path), predecessor_index_sha256=pc.sha(source_index_path), recovery_provenance={"path": str(proof_path), "sha256": pc.sha(proof_path)}, superseded_interrupted_attempts=[{"unit_id": OLD_UID, "candidate_index": 0, "terminal": {"path": str(terminal_path), "sha256": pc.sha(terminal_path)}, "status": "interrupted_without_complete_receipt", "retained_partial_output_root": original_spec["run_root"], "original_spec_sha256": original["spec_sha256"]}], attempt_accounting={"expected_valid_candidate_configurations": 400, "expected_scientific_selection_cells": 200, "additional_retained_interrupted_attempts": 1, "completed_valid_fits_not_claimed_by_preparation": True})
    new_index_path = output / "execution-index-v5-recovery.json"
    pc.write_new(new_index_path, new_index)
    pc.write_new(output / "recovery-preparation-index.json", {"created_at": pc.now(), "new_run_id": NEW_UID, "draft_contract": {"path": str(new_contract_path), "sha256": pc.sha(new_contract_path)}, "new_spec": {"path": str(new_spec_path), "sha256": pc.sha(new_spec_path)}, "execution_index_v5": {"path": str(new_index_path), "sha256": pc.sha(new_index_path)}, "source_proof": {"path": str(proof_path), "sha256": pc.sha(proof_path)}, "recovery_binding_deadline_must_equal": absolute, "original_global_clock_preserved": True, "issued": False, "actual_recovery_fits": 0, "remaining_full_pool_issuance": "Root must bind original completed/unstarted199cells plus this new isolatedcell after actual diagnosis/resource/process-absence gate; never run two pools concurrently"})
    print(json.dumps({"new_run_id": NEW_UID, "draft_only": True, "spec_deltas": proof["only_spec_deltas"], "unit_absolute_ceiling": absolute, "new_execution_index_sha256": pc.sha(new_index_path), "scientific_cells": 200, "valid_candidate_configurations": 400, "retained_interrupted_attempts": 1, "actual_recovery_fits": 0}))
