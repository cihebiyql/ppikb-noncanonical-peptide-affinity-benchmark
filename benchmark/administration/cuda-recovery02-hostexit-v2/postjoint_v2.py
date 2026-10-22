"""Root-only post-retry v2 gate and issuance. Never launch score pools."""
import argparse
import importlib.util
import os
import signal
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
import recovery as r
from postjoint_gate_v2 import gate


def load_original_utility():
    path = r.PROJECT / "control/root-postjoint-v1/wsl_prepare.py"
    spec = importlib.util.spec_from_file_location("frozen_root_v1_utility", path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def windows(path):
    value = str(Path(path).resolve())
    if not value.startswith("/mnt/d/"): raise ValueError("Only existing project D: Windows metadata route supported")
    return "D:/" + value[len("/mnt/d/"):]


def execute(ready_path, ready_sha, wait_path, wait_sha, name, authorized=False):
    if authorized is not True: raise PermissionError("Explicit root postjoint-v2 execution flag required")
    if os.name != "posix" or socket.gethostname() != "cihebi" or Path(sys.executable).resolve() != Path("/root/.venvs/peptide-omnipanel-v31-web311-20260723/bin/python").resolve(): raise RuntimeError("Existing generic cihebi WSL route required")
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "" or os.environ.get("PYTHONPATH") != str(r.PROJECT / "resources/local-gpu-route/vendor-dependencies"): raise RuntimeError("CPU-only preparation and frozen vendor route required")
    utility = load_original_utility(); utility.reserve()
    frozen = r.read(r.HERE / "SOURCE-FREEZE-v1.json")
    for row in frozen["code_and_metadata"]:
        if r.sha(r.PROJECT / row["relative_path"]) != row["sha256"]: raise ValueError("Frozen v2 source changed")
    utility.validate_frozen(r.read(r.PROJECT / "control/root-postjoint-v1/SOURCE-FREEZE-v1.json"))
    output = r.HERE / name
    if output.parent.resolve() != r.HERE.resolve() or output.name != name: raise ValueError("New owned execution directory required")
    output.mkdir(exist_ok=False)
    gate(ready_path, ready_sha, wait_path, wait_sha, output, authorized=True)
    chain = output / "CUDA-ATTEMPT-CHAIN.json"
    nn_index = r.PROJECT / "administration/io-recovery01/execution-index-v5-recovery.json"
    if r.sha(nn_index) != r.SCIENCE_SHA: raise ValueError("RF frozen c7b3 source must stay unchanged")
    py = utility.PYTHON
    nn_barrier, joint, audit = output / "all200-selections-frozen.json", output / "all240-joint-frozen.json", output / "NN200-checkpoint-byte-audit.json"
    rf_barrier = r.PROJECT / "auxiliary-rf-baseline/all40-selections-frozen-v1.json"
    if r.sha(rf_barrier) != "c03db701826feaa688ba87bb9cee5e5fea67f2fd17f83dab7c8454aafcea9e12": raise ValueError("Original RF40 barrier changed")
    utility.command([py, str(r.PROJECT / "execution/runner.py"), "freeze-barrier", "--index", str(nn_index), "--output", str(nn_barrier)], output, "01-NN-freeze")
    utility.command([py, str(r.PROJECT / "auxiliary-rf-baseline/rf_runner.py"), "joint-barrier", "--NN-barrier", str(nn_barrier), "--RF-barrier", str(rf_barrier), "--output", str(joint)], output, "02-RF-joint")
    evaluation = r.read(r.PROJECT / "evaluation/FROZEN-SCORER-v1.json")
    base_auth = {"root_scoring_authorized": True, "evaluation_code_sha256": evaluation["evaluation_code_sha256"], "runner_sha256": evaluation["frozen_runner_sha256"], "barrier_sha256": r.sha(nn_barrier), "execution_index_sha256": r.SCIENCE_SHA, "joint_barrier_sha256": r.sha(joint), "deadline_unix": utility.CUTOFF, "deadline": r.GLOBAL, "cuda_attempt_chain": r.ref(chain)}
    audit_auth = output / "NN-audit-only-authorization.json"
    r.write(audit_auth, {**base_auth, "allowed_phases": ["barrier_audit"], "allowed_score_spec_sha256": [], "scope": "Actual both-pool lineage passed, checkpoint byte audit only; cannot score"})
    utility.command([py, str(r.PROJECT / "evaluation/score_cached.py"), "audit-barrier", "--authorization", str(audit_auth), "--barrier", str(nn_barrier), "--execution-index", str(nn_index), "--output", str(audit)], output, "03-NN-full-checkpoint-audit")
    actual_audit = r.read(audit)
    if actual_audit.get("status") != "all_200_selections_and_checkpoints_verified" or len(actual_audit.get("selections", [])) != 200 or actual_audit.get("gold_reads") != 0 or actual_audit.get("model_forwards") != 0: raise ValueError("Actual full200 byte audit required")
    utility.reserve()
    nn_plan = r.read(r.PROJECT / "administration/evaluation-plan-eligible-v5.prebarrier.json")
    nn_specs = sorted({s["sha256"] for u in nn_plan["units"].values() for s in u["score_specs"]})
    rf_source = r.read(r.PROJECT / "auxiliary-rf-baseline/SOURCE-FREEZE-v1.json")
    rf_specs = sorted({e["score_spec_sha256"] for e in r.read(r.PROJECT / "auxiliary-rf-baseline/score-specs-v1/score-spec-index.json")["entries"]})
    if (len(nn_specs), len(rf_specs)) != (30, 6): raise ValueError("Original30+6 score specs required")
    nn_auth, rf_auth = output / "NN-score-authorization.json", output / "RF-score-authorization.json"
    r.write(nn_auth, {**base_auth, "allowed_phases": ["score"], "allowed_score_spec_sha256": nn_specs, "barrier_audit_sha256": r.sha(audit)})
    r.write(rf_auth, {"root_RF_holdout_score_authorized": True, "allowed_score_spec_sha256": rf_specs, "source_sha256": rf_source["source_sha256"], "joint_barrier_sha256": r.sha(joint), "frozen_stable_metrics_sha256": evaluation["evaluation_code_sha256"]["metrics_stable.py"], "deadline_unix": utility.CUTOFF, "deadline": r.GLOBAL, "cuda_attempt_chain": r.ref(chain), "paper_count_contribution": 0})
    mem = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
    cpu = output / "fresh-CPU-time-proof.json"
    r.write(cpu, {"hostname": socket.gethostname(), "observed_at": datetime.now(timezone.utc).isoformat(), "python": sys.executable, "CPU_count": os.cpu_count(), "allowed_CPU_ids": sorted(os.sched_getaffinity(0)), "requested_CPU_ids": [4, 5, 6, 7], "load_1_5_15": os.getloadavg(), "available_memory_bytes": int(mem["MemAvailable"].split()[0]) * 1024, "total_memory_bytes": int(mem["MemTotal"].split()[0]) * 1024, "CUDA_VISIBLE_DEVICES": "", "deadline": r.GLOBAL, "remaining_seconds": utility.CUTOFF - __import__("time").time(), "score_processes_started": 0})
    inputs = {"root_postjoint_metadata_issuance_authorized": True, "NN_score_authorization": r.ref(nn_auth), "RF_score_authorization": r.ref(rf_auth), "NN_barrier": r.ref(nn_barrier), "RF_barrier": r.ref(rf_barrier), "joint_barrier": r.ref(joint), "NN_checkpoint_audit": r.ref(audit), "live_CPU_proof": r.ref(cpu), "cuda_attempt_chain": r.ref(chain)}
    input_path = output / "issuer-inputs.json"; r.write(input_path, inputs)
    issued = output / "issued-240"
    winpy = "/mnt/c/Users/ciheb/AppData/Local/Programs/Python/Python311/python.exe"
    utility.command([winpy, "-X", "utf8", windows(r.PROJECT / "administration/postjoint_issue_all.py"), "--inputs", windows(input_path), "--out", windows(issued)], output, "04-metadata-issue")
    issuance = issued / "POSTJOINT-ISSUANCE.json"; manifest = r.read(issuance)
    sidecar = {"schema": "postjoint-CUDA-lineage-sidecar.v1", "issuance": r.ref(issuance), "cuda_attempt_chain": r.ref(chain), "scientific_evaluation_unit_id": r.UID + "__evaluation_v1", "must_augment_final_standard_result": True, "original_issuer_and_archive_sources_unchanged": True, "valid_NN_fits": 400, "selected_NN_cells": 200, "extra_interrupted_attempts": 2, "RF_fits_unchanged": 80}
    r.write(output / "POSTJOINT-CUDA-LINEAGE.json", sidecar)
    ready = {"status": "joint240_audited_and_issued_no_score_started", "issuance": r.ref(issuance), "cuda_lineage_sidecar": r.ref(output / "POSTJOINT-CUDA-LINEAGE.json"), "pools": manifest["pools"], "actual_score_launches": 0, "deadline": r.GLOBAL}
    r.write(output / "NEXT-POOL-COMMANDS.json", ready); print(__import__("json").dumps(ready, ensure_ascii=False, indent=2)); return ready


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root-execute-postjoint-v2-authorized", action="store_true")
    parser.add_argument("--recovery-ready", required=True); parser.add_argument("--recovery-ready-sha256", required=True)
    parser.add_argument("--retry-pool-exit-proof", required=True); parser.add_argument("--retry-pool-exit-proof-sha256", required=True)
    parser.add_argument("--execution-name", required=True)
    a = parser.parse_args()
    def interrupted(signum, frame):
        raise InterruptedError("Root postjoint-v2 interrupted; owned preparatory child cleanup required")
    signal.signal(signal.SIGTERM, interrupted); signal.signal(signal.SIGINT, interrupted)
    execute(a.recovery_ready, a.recovery_ready_sha256, a.retry_pool_exit_proof, a.retry_pool_exit_proof_sha256, a.execution_name, a.root_execute_postjoint_v2_authorized)
