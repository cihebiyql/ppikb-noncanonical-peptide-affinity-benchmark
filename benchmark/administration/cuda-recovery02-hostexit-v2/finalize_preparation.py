"""Freeze a new honest host-exit control revision; no actual archive/retry."""
import hashlib
import json
import os
import py_compile
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent; PROJECT = HERE.parent.parent
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
read = lambda path: json.loads(Path(path).read_text(encoding="utf-8-sig"))
def write(path, body):
    with Path(path).open("x", encoding="utf-8") as stream: json.dump(body, stream, ensure_ascii=False, indent=2); stream.write("\n")


def main():
    if (HERE / "SOURCE-FREEZE-v1.json").exists(): raise FileExistsError("No overwrite of frozen revision")
    replacements = {
        "postjoint_gate_v2.py": [('"prior_pool_wait_exit2": old_wait_ref', '"prior_pool_wait_outer1_native_unobserved": old_wait_ref, "prior_pool_exit_observation": host_observation')],
        "attach_archive_lineage.py": [('Original pool exit2/199success1failed', 'Original pool actual outer-tool exit1/199success1failed; native2 is inferred from frozen source and verified terminal, never directly observed')],
        "recovery.py": [('after actual pool exit2', 'after actual outer-tool exit1 with source-inferred native2'), ('# WSL only, after exit2.', '# WSL only, after actual host1 wait; native2 is inferred.')]
    }
    for name, pairs in replacements.items():
        path = HERE / name; text = path.read_text(encoding="utf-8")
        for old, new in pairs:
            if old not in text: raise ValueError("Expected exact control-only revision anchor absent")
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")
    for name in ("recovery.py", "postjoint_gate_v2.py", "postjoint_v2.py", "attach_archive_lineage.py", "test_recovery.py"): py_compile.compile(str(HERE / name), doraise=True)
    command = [sys.executable, "-X", "utf8", "-m", "unittest", "-v", "test_recovery.py"]
    result = subprocess.run(command, cwd=HERE, capture_output=True, encoding="utf-8", timeout=60, check=False)
    for name, text in (("synthetic.stdout.log", result.stdout), ("synthetic.stderr.log", result.stderr)):
        with (HERE / name).open("x", encoding="utf-8") as stream: stream.write(text)
    if result.returncode: raise RuntimeError("Synthetic tests failed")
    old = PROJECT / "administration/cuda-recovery02/SOURCE-FREEZE-v1.json"
    if sha(old) != "b20b3a08464d2534d583561bac2bda2dd1993d90a802cf8c12efb07e4fc4b0cf": raise ValueError("Original reviewed b20b freeze changed")
    paths = {HERE / name for name in ("recovery.py", "postjoint_gate_v2.py", "postjoint_v2.py", "attach_archive_lineage.py", "test_recovery.py", "finalize_preparation.py", "closed-failure-facts.json", "README.md")}
    paths.add(old)
    for item in read(old)["code_and_metadata"]: paths.add((PROJECT / item["relative_path"]).resolve())
    for name in ("old-v5-hostexit1-proof-v2.json", "host-exit-mapping-probe-v1.json", "old-v5-actual-tool-wait-result.json"):
        paths.add(PROJECT / "control" / name)
    freeze = {"schema": "CUDA-recovery02-hostexit-control-v2", "created_at": datetime.now(timezone.utc).isoformat(), "code_and_metadata": [{"relative_path": os.path.relpath(path, PROJECT).replace("\\", "/"), "sha256": sha(path)} for path in sorted(paths, key=str)], "supersedes_control_gate_only": {"original_freeze_path": str(old), "sha256": sha(old)}, "observed_original_outer_tool_exit": 1, "native_expected_from_verified_terminal_and_source": 2, "original_native_exit_directly_observed": False, "actual_same_route_synthetic_probe": {"relative_path": "control/host-exit-mapping-probe-v1.json", "sha256": sha(PROJECT / "control/host-exit-mapping-probe-v1.json")}, "synthetic_tests": {"command": command, "count": 25, "exit_code": result.returncode, "stdout_sha256": sha(HERE / "synthetic.stdout.log"), "stderr_sha256": sha(HERE / "synthetic.stderr.log")}, "actual_archive_or_retry_or_score_operations": 0, "actual_weight_gold_prediction_reads": 0, "scientific_index_unchanged": "c7b3bde68c9a741c0ac3f255a825e4a55dd7234e2b4e6d48f212fee8d5609ab1", "unit_ceiling_unchanged": "2026-10-21T22:54:18.479676+00:00", "current_execution_authorized": False}
    write(HERE / "SOURCE-FREEZE-v1.json", freeze)
    print(json.dumps({"files": len(paths), "tests": 25, "source_freeze_sha256": sha(HERE / "SOURCE-FREEZE-v1.json"), "actual_archive_or_retry": 0}))


if __name__ == "__main__": main()
