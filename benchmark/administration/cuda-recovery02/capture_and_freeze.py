"""Prepare closed-failure/code metadata and synthetic evidence; never real archive."""
import hashlib
import json
import os
import py_compile
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent; PROJECT = HERE.parent.parent
read = lambda path: json.loads(Path(path).read_text(encoding="utf-8-sig"))
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
def local(value): return Path("D:/" + str(value)[len("/mnt/d/"):]) if str(value).startswith("/mnt/d/") else Path(value)
def write(path, body):
    with Path(path).open("x", encoding="utf-8") as stream: json.dump(body, stream, ensure_ascii=False, indent=2); stream.write("\n")


def main():
    if (HERE / "SOURCE-FREEZE-v1.json").exists(): raise FileExistsError("Never overwrite a reviewed freeze")
    uid = "MGraphDTA__target_reference_homology_cold__standard_only__seed06"
    index = read(PROJECT / "control/unit-index-v5-all-recovery.json"); unit = next(u for u in index["units"] if u["unit_id"] == uid)
    spec = read(local(unit["spec"])); receipt = local(spec["launch_proof"]["receipt_root"]); oldpool = local(index["output_root"])
    closed = [receipt / name for name in ("unit-started.json", "candidate-0.started.json", "candidate-0.receipt.json", "candidate-0.stdout.log", "candidate-0.stderr.log", "unit-failed.json")]
    closed += [oldpool / (uid + suffix) for suffix in (".started.json", ".terminal.json", ".stdout.log", ".stderr.log")]
    facts = []
    for path in closed:
        if path.suffix not in (".json", ".log"): raise PermissionError("Closed metadata/log only")
        facts.append({"path": "/mnt/d/" + str(path.resolve())[3:].replace("\\", "/"), "sha256": sha(path), "size": path.stat().st_size, "observed_at": datetime.now(timezone.utc).isoformat()})
    stderr = (receipt / "candidate-0.stderr.log").read_text(encoding="utf-8")
    if "CUDA error: unknown error" not in stderr: raise ValueError("Actual closed failure reason not established")
    stage = read(receipt / "candidate-0.receipt.json")
    if stage["exit_code"] != 1 or stage["timed_out"] is not False: raise ValueError("Not the actual finite technical failure")
    write(HERE / "closed-failure-facts.json", {"scientific_unit_id": uid, "actual_failure": "torch.AcceleratorError: CUDA error: unknown error", "causal_attribution": "Runtime reports CUDA unknown error in PyG aggregation; asynchronous stack may not identify cause. No claim of deterministic model bug, OOM or platform refusal.", "candidate_index": 0, "candidate_exit_code": 1, "wrapper_exit_code": 1, "parent_pool_still_running_at_preparation": True, "no_global_pool_exit_claim": True, "files": facts, "spec": {"path": unit["spec"], "sha256": unit["spec_sha256"]}, "contract": {"path": unit["contract"], "sha256": unit["contract_sha256"]}, "original_first_start": "2026-10-21T20:54:18.654494+00:00", "original_absolute_unit_ceiling": "2026-10-21T22:54:18.479676+00:00", "global_deadline": "2026-10-22T01:45:00+00:00", "actual_model_gold_prediction_bytes_read": 0})
    for name in ("recovery.py", "postjoint_gate_v2.py", "postjoint_v2.py", "attach_archive_lineage.py", "test_recovery.py", "capture_and_freeze.py"): py_compile.compile(str(HERE / name), doraise=True)
    command = [sys.executable, "-X", "utf8", "-m", "unittest", "-v", "test_recovery.py"]
    result = subprocess.run(command, cwd=HERE, capture_output=True, encoding="utf-8", timeout=60, check=False)
    for name, text in (("synthetic.stdout.log", result.stdout), ("synthetic.stderr.log", result.stderr)):
        with (HERE / name).open("x", encoding="utf-8") as stream: stream.write(text)
    if result.returncode: raise RuntimeError("Synthetic tests failed; no freeze")
    paths = {HERE / name for name in ("recovery.py", "postjoint_gate_v2.py", "postjoint_v2.py", "attach_archive_lineage.py", "test_recovery.py", "capture_and_freeze.py", "README.md", "closed-failure-facts.json")}
    for key in ("spec", "contract", "validation", "unit_binding"): paths.add(local(unit[key]))
    paths.add(PROJECT / "control/unit-index-v5-all-recovery.json")
    paths.add(PROJECT / "administration/io-recovery01/execution-index-v5-recovery.json")
    paths.add(PROJECT / "control/root-postjoint-v1/SOURCE-FREEZE-v1.json")
    v1 = read(PROJECT / "control/root-postjoint-v1/SOURCE-FREEZE-v1.json")
    for row in v1["files"]: paths.add((PROJECT / row["relative_path"]).resolve())
    rows = [{"relative_path": os.path.relpath(path, PROJECT).replace("\\", "/"), "sha256": sha(path)} for path in sorted(paths, key=str)]
    frozen = {"schema": "CUDA-recovery02-source-freeze.v1", "created_at": datetime.now(timezone.utc).isoformat(), "code_and_metadata": rows, "closed_failure_facts": {"path": str(HERE / "closed-failure-facts.json"), "sha256": sha(HERE / "closed-failure-facts.json")}, "synthetic_tests": {"command": command, "count": 21, "exit_code": result.returncode, "stdout_sha256": sha(HERE / "synthetic.stdout.log"), "stderr_sha256": sha(HERE / "synthetic.stderr.log")}, "actual_failed_tree_archive_operations": 0, "actual_retry_or_score_launches": 0, "actual_model_gold_prediction_reads": 0, "current_execution_authorized": False}
    write(HERE / "SOURCE-FREEZE-v1.json", frozen)
    print(json.dumps({"files": len(rows), "tests": 21, "actual_real_archive_or_retry": 0, "source_freeze_sha256": sha(HERE / "SOURCE-FREEZE-v1.json")}))


if __name__ == "__main__": main()
