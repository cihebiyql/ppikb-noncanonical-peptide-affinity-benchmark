"""Explicit root-only post-producer preparation. No scoring or model forward."""
import argparse
import hashlib
import json
import os
import re
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent.parent
PYTHON = "/root/.venvs/peptide-omnipanel-v31-web311-20260723/bin/python"
DEADLINE = "2026-10-22T01:45:00+00:00"
CUTOFF = datetime.fromisoformat(DEADLINE).timestamp()
NN_INDEX_SHA = "c7b3bde68c9a741c0ac3f255a825e4a55dd7234e2b4e6d48f212fee8d5609ab1"
POOL_INDEX_SHA = "fe51a0d03f4f9c08e710e9d8b582d56c497d8c59dc5d14e8cbc6e6d8b41e51d2"


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, body):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(body, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def reference(path):
    return {"path": str(path), "sha256": sha(path)}


def reserve(now=None):
    if CUTOFF - (time.time() if now is None else now) <= 1800:
        raise TimeoutError("Full1800-second evaluation budget cannot fit original01:45UTC cutoff")


def check_terminal(body, ids):
    if body.get("status") != "complete" or body.get("reason") is not None or body.get("pending") != 0 or body.get("active") != [] or body.get("failed_count") != 0 or body.get("failed_units") != [] or body.get("cleanup_errors") != [] or body.get("complete_count") != 200:
        raise PermissionError("Original NN pool is not actually fully complete and successful")
    if len(body.get("completed_units", [])) != 200 or set(body["completed_units"]) != set(ids) or body.get("index_sha256") != POOL_INDEX_SHA or body.get("deadline") != DEADLINE:
        raise ValueError("Producer terminal is not exact approved recovery-aware200 grid/deadline")


def check_exit(body):
    if type(body.get("exit_code")) is not int or body["exit_code"] != 0 or type(body.get("pool_pid")) is not int or body["pool_pid"] <= 1 or body.get("index_sha256") != POOL_INDEX_SHA or not body.get("observed_at") or not body.get("source") or body.get("root_observed_actual_wait") is not True:
        raise PermissionError("Root actual successful pool wait evidence required; never infer exit from unit files")


def validate_frozen(frozen):
    for row in frozen["files"]:
        path = PROJECT / row["relative_path"]
        if path.suffix not in (".py", ".json", ".md") or any(token in path.name.lower() for token in ("gold", "predictions")):
            raise PermissionError("Preparation freeze may not traverse scientific payloads")
        if sha(path) != row["sha256"]:
            raise ValueError("Frozen source/spec changed: " + str(path))


def command(argv, output, name):
    reserve()
    maximum = min(600, int(CUTOFF - time.time() - 1800))
    if maximum <= 0:
        raise TimeoutError("Original global window exhausted")
    stdout = output / (name + ".stdout.log")
    stderr = output / (name + ".stderr.log")
    started = datetime.now(timezone.utc).isoformat()
    with stdout.open("xb") as out, stderr.open("xb") as err:
        process = subprocess.Popen(argv, stdout=out, stderr=err, start_new_session=True)
        try:
            code = process.wait(timeout=maximum)
        except BaseException:
            try:
                os.killpg(process.pid, 15)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, 9)
                process.wait(timeout=5)
            raise
    write(output / (name + ".execution.json"), {"argv": argv, "pid": process.pid, "pgid": process.pid, "exit_code": code, "started_at": started, "ended_at": datetime.now(timezone.utc).isoformat(), "stdout": reference(stdout), "stderr": reference(stderr), "deadline": DEADLINE})
    if code != 0:
        raise RuntimeError("Preparatory stage failed; preserve logs, no automatic retry: " + name)


def prepare(output, exit_path, exit_sha, authorized=False):
    if authorized is not True:
        raise PermissionError("Explicit --root-execute-postjoint-authorized is required")
    reserve()
    if os.name != "posix" or socket.gethostname() != "cihebi" or Path(sys.executable).resolve() != Path(PYTHON).resolve():
        raise RuntimeError("Original cihebi generic WSL environment required")
    if os.environ.get("PYTHONPATH") != str(PROJECT / "resources/local-gpu-route/vendor-dependencies") or os.environ.get("CUDA_VISIBLE_DEVICES") != "":
        raise RuntimeError("Existing vendor route and CPU-only preparatory environment required")
    output = Path(output).resolve()
    if output.parent != HERE.resolve() or not re.fullmatch("[A-Za-z0-9_.-]+", output.name) or not output.is_dir():
        raise ValueError("Windows root wrapper must create one exclusive execution directory")
    frozen = read(HERE / "SOURCE-FREEZE-v1.json")
    validate_frozen(frozen)
    if sha(exit_path) != exit_sha:
        raise ValueError("Actual root pool wait proof changed")
    exited = read(exit_path)
    check_exit(exited)
    if Path("/proc", str(exited["pool_pid"])).exists():
        raise PermissionError("Original producer pool PID is still present; no wait/poll/retry")
    index_path = PROJECT / "control/unit-index-v5-all-recovery.json"
    if sha(index_path) != POOL_INDEX_SHA:
        raise ValueError("Approved launch index changed")
    pool_index = read(index_path)
    ids = [unit["unit_id"] for unit in pool_index["units"]]
    root = Path(pool_index["output_root"])
    # These producer files are read ONLY by WSL, after actual root wait and PID
    # disappearance. No Windows reader touches live atomic producer metadata.
    progress = read(root / "progress.json")
    check_terminal(progress, ids)
    terminals = []
    for path in (root / "attempts").glob("*/terminal.json"):
        body = read(path)
        if body.get("status") == "complete":
            check_terminal(body, ids)
            terminals.append(reference(path))
    if len(terminals) != 1:
        raise ValueError("Exactly one immutable successful producer attempt terminal required")
    write(output / "producer-completion-gate.json", {"status": "verified_actual_pool_completed_and_exited", "actual_wait": reference(exit_path), "producer_terminal": terminals[0], "producer_progress": reference(root / "progress.json"), "pool_pid_absent": exited["pool_pid"], "checked_at": datetime.now(timezone.utc).isoformat(), "launch_index_sha256": POOL_INDEX_SHA})
    nn_index = PROJECT / "administration/io-recovery01/execution-index-v5-recovery.json"
    if sha(nn_index) != NN_INDEX_SHA:
        raise ValueError("Scientific NNv5 source mismatch")
    nn_barrier = output / "all200-selections-frozen.json"
    rf_barrier = PROJECT / "auxiliary-rf-baseline/all40-selections-frozen-v1.json"
    if sha(rf_barrier) != "c03db701826feaa688ba87bb9cee5e5fea67f2fd17f83dab7c8454aafcea9e12":
        raise ValueError("Actual previously root-frozenRF40 barrier changed")
    command([PYTHON, str(PROJECT / "execution/runner.py"), "freeze-barrier", "--index", str(nn_index), "--output", str(nn_barrier)], output, "01-NN-freeze")
    joint = output / "all240-joint-frozen.json"
    command([PYTHON, str(PROJECT / "auxiliary-rf-baseline/rf_runner.py"), "joint-barrier", "--NN-barrier", str(nn_barrier), "--RF-barrier", str(rf_barrier), "--output", str(joint)], output, "02-RF-joint")
    frozen_eval = read(PROJECT / "evaluation/FROZEN-SCORER-v1.json")
    common_auth = {"root_scoring_authorized": True, "evaluation_code_sha256": frozen_eval["evaluation_code_sha256"], "runner_sha256": frozen_eval["frozen_runner_sha256"], "barrier_sha256": sha(nn_barrier), "execution_index_sha256": NN_INDEX_SHA, "joint_barrier_sha256": sha(joint), "deadline_unix": CUTOFF, "deadline": DEADLINE, "root_actual_pool_wait_evidence": reference(exit_path)}
    audit_auth = output / "NN-audit-only-authorization.json"
    write(audit_auth, {**common_auth, "allowed_phases": ["barrier_audit"], "allowed_score_spec_sha256": [], "scope": "Root explicit runtime request after actualNN200+RF40; metadata and checkpoint byte audit only, no model forward or gold"})
    audit = output / "NN200-checkpoint-byte-audit.json"
    command([PYTHON, str(PROJECT / "evaluation/score_cached.py"), "audit-barrier", "--authorization", str(audit_auth), "--barrier", str(nn_barrier), "--execution-index", str(nn_index), "--output", str(audit)], output, "03-NN-checkpoint-audit")
    audit_body = read(audit)
    if audit_body.get("status") != "all_200_selections_and_checkpoints_verified" or len(audit_body.get("selections", [])) != 200 or audit_body.get("gold_reads") != 0 or audit_body.get("model_forwards") != 0:
        raise ValueError("Actual fullNN checkpoint byte audit did not pass")
    reserve()
    nn_auth = output / "NN-score-authorization.json"
    nn_plan = read(PROJECT / "administration/evaluation-plan-eligible-v5.prebarrier.json")
    nn_specs = sorted({row["sha256"] for unit in nn_plan["units"].values() for row in unit["score_specs"]})
    rf_source = read(PROJECT / "auxiliary-rf-baseline/SOURCE-FREEZE-v1.json")
    rf_index = read(PROJECT / "auxiliary-rf-baseline/score-specs-v1/score-spec-index.json")
    rf_specs = sorted({row["score_spec_sha256"] for row in rf_index["entries"]})
    if len(nn_specs) != 30 or len(rf_specs) != 6:
        raise ValueError("Original frozen30+6 scoring specs required")
    write(nn_auth, {**common_auth, "allowed_phases": ["score"], "barrier_audit_sha256": sha(audit), "allowed_score_spec_sha256": nn_specs, "scope": "Root explicit runtime postjoint permission; frozen inference only, no selection or refit"})
    rf_auth = output / "RF-score-authorization.json"
    write(rf_auth, {"root_RF_holdout_score_authorized": True, "allowed_score_spec_sha256": rf_specs, "source_sha256": rf_source["source_sha256"], "joint_barrier_sha256": sha(joint), "frozen_stable_metrics_sha256": frozen_eval["evaluation_code_sha256"]["metrics_stable.py"], "deadline_unix": CUTOFF, "deadline": DEADLINE, "paper_count_contribution": 0, "scope": "Root explicit runtime postjoint permission; auxiliary CPU-only frozen RF inference"})
    mem = dict(line.split(":", 1) for line in Path("/proc/meminfo").read_text().splitlines())
    proof = output / "fresh-CPU-time-proof.json"
    write(proof, {"hostname": socket.gethostname(), "observed_at": datetime.now(timezone.utc).isoformat(), "python": sys.executable, "CPU_count": os.cpu_count(), "allowed_CPU_ids": sorted(os.sched_getaffinity(0)), "requested_CPU_ids": [4, 5, 6, 7], "load_1_5_15": os.getloadavg(), "available_memory_bytes": int(mem["MemAvailable"].strip().split()[0]) * 1024, "total_memory_bytes": int(mem["MemTotal"].strip().split()[0]) * 1024, "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES"), "deadline": DEADLINE, "remaining_seconds": CUTOFF - time.time(), "score_processes_started": 0})
    inputs = {"root_postjoint_metadata_issuance_authorized": True, "NN_score_authorization": reference(nn_auth), "RF_score_authorization": reference(rf_auth), "NN_barrier": reference(nn_barrier), "RF_barrier": reference(rf_barrier), "joint_barrier": reference(joint), "NN_checkpoint_audit": reference(audit), "live_CPU_proof": reference(proof)}
    write(output / "issuer-inputs.json", inputs)
    write(output / "WSL-PREPARED.json", {"status": "actual_joint_and_checkpoint_audit_complete_score_not_launched", "issuer_inputs": reference(output / "issuer-inputs.json"), "source_freeze": reference(HERE / "SOURCE-FREEZE-v1.json"), "score_processes_started": 0, "model_forwards": 0, "gold_reads": 0, "actual_checkpoint_bytes_audited_by_frozen_scorer": True, "deadline": DEADLINE})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root-execute-postjoint-authorized", action="store_true")
    parser.add_argument("--output", required=True)
    parser.add_argument("--pool-exit-proof", required=True)
    parser.add_argument("--pool-exit-proof-sha256", required=True)
    args = parser.parse_args()
    def interrupted(signum, frame):
        raise InterruptedError("Bounded root preparation interrupted; owned child cleanup required")
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    prepare(args.output, args.pool_exit_proof, args.pool_exit_proof_sha256, args.root_execute_postjoint_authorized)
