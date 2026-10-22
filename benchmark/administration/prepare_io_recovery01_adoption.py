"""Join root's real diagnostic/resource metadata for one recovery contract.

Prepares an explicit freeze invocation; never freezes, binds or launches itself.
"""
from pathlib import Path
import json

import prepare_campaign as pc

BASE = Path(__file__).resolve().parent
PROJECT = BASE.parent
RECOVERY = BASE / "io-recovery01"


if __name__ == "__main__":
    prepared = pc.read(RECOVERY / "recovery-preparation-index.json")
    draft_ref = prepared["draft_contract"]
    if pc.sha(draft_ref["path"]) != draft_ref["sha256"]:
        raise ValueError("Recovery draft changed")
    draft = pc.read(draft_ref["path"])
    probe_path = PROJECT / "control" / "recovery-resource-probe-v1.json"
    probe = pc.read(probe_path)
    if probe["hostname"] != "cihebi" or probe["failed_wrapper_pid_alive"].get("705188") is not False or len(probe["gpu_samples"]) != 3 or any(row["compute"] or row["utilization_percent"] > 20 for row in probe["gpu_samples"]):
        raise ValueError("Root live failed-process/GPU resource proof did not pass")
    diagnostic_path = PROJECT / "control" / "recovery-diagnosis-v1" / "diagnosis-summary.json"
    diagnostic = pc.read(diagnostic_path)
    uid = draft["run_id"]
    source = {"run_id": uid, "method_id": draft["benchmark_metadata"]["method_id"], "split_id": draft["benchmark_metadata"]["split_id"], "regime_id": draft["benchmark_metadata"]["regime_id"], "seed": draft["benchmark_metadata"]["seed"], "contract_draft_path": draft_ref["path"]}
    index_path = RECOVERY / "single-recovery-draft-index.json"
    pc.write_new(index_path, {"schema": "nc-explicit-single-recovery-draft-index.v1", "runs": [source], "actual_runs": 0, "source_proof": prepared["source_proof"], "root_authority": "Explicit root instruction to preserve original absolute unit ceiling and stage history"})
    adoption_path = RECOVERY / "adoption-root-diagnostic-resource-v1.json"
    adoption = {"schema": "nc-recovery-real-diagnostic-resource-adoption.v1", "draft_index_path": str(index_path), "shared": {"resources": {"resource_probe_path": str(probe_path), "resource_probe_sha256": pc.sha(probe_path), "resource_probe_at": probe["at"], "start_gate": "Root fresh probe: failed wrapper705188 absent; three GPU samples no reported compute processes and1percent utilization; new pool must recheck actual ownership/memory and no overlapping old pool immediately before launch", "recovery_live_resource_status": "root_probe_passed_original_runtime_and_GPU"}, "timing": {"timing_evidence_paths": draft["timing"]["timing_evidence_paths"] + [str(probe_path), str(diagnostic_path)]}, "recovery_metadata": {"live_resource_ready": True, "diagnostic_receipt": {"path": str(diagnostic_path), "sha256": pc.sha(diagnostic_path)}, "resource_receipt": {"path": str(probe_path), "sha256": pc.sha(probe_path)}, "diagnosis_state": "Root synthetic minimal reproduction confirms Windows plain Python read handle can cause same-type WSL atomic-rename PermissionError13; original lacks exact path/stack, so attribution remains moderate. No safety/platform rejection or model/OOM claim."}}, "methods": {}, "splits": {}, "units": {}, "does_not_authorize_launch": True, "root_signature_step": "Root reviews exact metadata diff then invokes unchanged administrative freeze_contracts.py --freeze and separately issues binding with deadline equal original20:09:02.438325Z"}
    pc.write_new(adoption_path, adoption)
    formal = RECOVERY / "issued-root-v1"
    pc.write_new(RECOVERY / "ROOT-ISSUE-INSTRUCTIONS.json", {"freeze_argv": ["C:/Users/ciheb/AppData/Local/Programs/Python/Python311/python.exe", "-X", "utf8", str(BASE / "freeze_contracts.py"), "--adoption", str(adoption_path), "--out", str(formal), "--freeze"], "after_freeze_index": str(formal / "freeze-index.json"), "scientific_execution_index_v5": prepared["execution_index_v5"], "post_issue_binding_path": draft["execution"]["command"][-1], "binding_deadline_must_equal": prepared["recovery_binding_deadline_must_equal"], "global_deadline_not_extended": draft["recovery_metadata"]["original_global_effective_deadline"], "old_files_must_remain": True, "one_new_pool_only_after_actual_old_process_tree_exit": True, "actual_recovery_fits_started": 0})
    print(json.dumps({"adoption_path": str(adoption_path), "single_recovery_contract": uid, "root_freeze_instruction_path": str(RECOVERY / "ROOT-ISSUE-INSTRUCTIONS.json"), "models_started": 0}))
