"""Join actual S299-S303 registration and real GS GPU evidence; no launch/freeze."""
from pathlib import Path
import copy
import json

import prepare_campaign as pc

BASE = Path(__file__).resolve().parent
PROJECT = BASE.parent
CONTROL = PROJECT / "control"
REGISTRATION = CONTROL / "registered-paper-map.json"
AUTH = CONTROL / "user-authorization.json"
GPU_RESULT = PROJECT / "methods" / "gs-dta" / "canary-gpu-v1" / "result.json"
GPU_RECEIPT = GPU_RESULT.parent / "watchdog-receipt.json"


if __name__ == "__main__":
    registered = pc.read(REGISTRATION)
    gs = pc.read(GPU_RESULT)
    watchdog = pc.read(GPU_RECEIPT)
    if gs["status"] != "passed" or gs["test_label_reads"] != 0 or gs["external_label_reads"] != 0 or watchdog["status"] != "passed" or watchdog["exit_code"] != 0:
        raise ValueError("Actual GS-DTA canary gate is not passed")
    current = pc.read(BASE / "campaign-config.gpu-five-facts-v3.json")
    method_sources = {item["method_id"]: item for item in current["methods"]}
    methods = {}
    for name, record in registered.items():
        if pc.sha(record["pdf_path"]) != record["pdf_sha256"]:
            raise ValueError("Registered PDF identity mismatch: " + name)
        audit = copy.deepcopy(method_sources[name]["input_encoding_audit"])
        if name == "GS-DTA":
            audit.update(status="verified", evidence_paths=audit["evidence_paths"] + [str(GPU_RESULT), str(GPU_RECEIPT)])
        methods[name] = {
            "task_id": record["task_id"],
            "identity": {"pdf": {"path": record["pdf_path"], "sha256": record["pdf_sha256"]}},
            "registered_task_identity": {"task_id": record["task_id"], "linked_task_ids": record["linked_task_ids"], "registration_path": str(REGISTRATION), "registration_sha256": pc.sha(REGISTRATION), "registration_receipt_path": str(CONTROL / "registration-receipt.json"), "registration_receipt_sha256": pc.sha(CONTROL / "registration-receipt.json")},
            "benchmark_metadata": {"input_encoding_audit": audit},
        }
    adoption = {
        "schema": "peptide-binding.nc-benchmark.actual-registration-adoption.v4",
        "is_template": True,
        "draft_index_path": str(BASE / "drafts-gpu-five-facts-v3" / "draft-index.json"),
        "shared": {
            "execution_scope": {"authorization_reference": "Direct latest user instruction and frozen control/user-authorization.json", "authorization_path": str(AUTH), "authorization_sha256": pc.sha(AUTH), "safety_assessment": "allowed"},
            "timing": {"timing_evidence_paths": [str(AUTH), str(PROJECT / "resources" / "live-probe.json")]},
            "resources": {"expected_hostname": "cihebi", "cpu_threads": 2, "data_loader_workers": 0, "memory_limit_bytes": 4294967296, "gpu_devices": ["GPU-e9419f8b-b24b-a22b-c8ec-8f5173f4b45a"], "gpu_memory_budget_bytes": 3221225472, "no_preemption": True, "budget_basis": "Root-owned one RTX5080, two concurrent private process groups; worker CPU2/RSS4GiB/allocator3GiB; pool owned GPU<=8GiB and hostRSS<=12GiB; no shared environment change", "start_gate": "Actual root launch pool rechecks GPU process/usage, CPU affinity/RSS and immutable inputs before each new unit; WSL external-process visibility limitations preserved"},
            "environment": {"environment_path": "/root/.venvs/peptide-omnipanel-v31-web311-20260723", "shared_environment_modified": False},
            "execution": {"working_directory": "/mnt/d/work/科研工作台/research-tasks/peptide-binding-nc-benchmark-20261021", "process_control": {"platform": "Linux WSL", "mechanism": "Root launch/pool_supervisor.py creates private PGID/session, checks owned PID identity/RSS/GPU reservations and bounds descendants to original deadline; run_unit.py children inherit PGID", "whole_tree_bounded": True}},
        },
        "methods": methods, "splits": {}, "units": {},
        "freeze_state": "waiting_only_for_final_v4_specs_launch_proof_and_environment_snapshot",
        "do_not_start_reason": ["Exact final unit commands and dynamic SHA binding policy not filled", "Final immutable fit spec/launch wrapper proof/environment freeze must be provided", "No formal contract issued and no workload launched by this preparation"],
    }
    path = BASE / "adoption.registered-gpu-prelaunch-v4.json"
    pc.write_new(path, adoption)
    print(json.dumps({"path": str(path), "registered_paper_count": len(methods), "GS_actual_GPU_status": gs["status"], "actual_training_runs": 0}, ensure_ascii=False))
