"""Explicit metadata path-alias repair; preserve failed validator and frozen source."""
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent; PROJECT = HERE.parent.parent
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
read = lambda path: json.loads(Path(path).read_text(encoding="utf-8"))
def write(path, body):
    with Path(path).open("x", encoding="utf-8") as stream: json.dump(body, stream, ensure_ascii=False, indent=2); stream.write("\n")
def ref(path): return {"path": str(path), "sha256": sha(path)}
def canonical(value): return "D:/" + value[len("/mnt/d/"):] if value.startswith("/mnt/d/") else value


prior_exit = HERE / "validate.actual-exit.json"; prior = read(prior_exit)
if prior["exit_code"] != 1: raise ValueError("Only actual retained failed Windows-path validator attempt may be adapted")
stderr = Path(prior["stderr"]["path"])
if sha(stderr) != prior["stderr"]["sha256"]: raise ValueError("Original failure evidence changed")
error = stderr.read_text(encoding="utf-8")
if "contract_file.read_bytes()" not in error or "FileNotFoundError" not in error or "\\mnt\\d\\" not in error: raise ValueError("Observed failure does not match this narrowly diagnosed path canonicalization")
source = PROJECT / "administration/validate_stage_result_index.py"
if sha(source) != "1169d8ed1e4f44c29b9615dafb08faba2c4b2ae6a2e5a790fb14f97c44b3bf3b": raise ValueError("Original central wrapper changed; do not alter or bypass it")
f1 = PROJECT / "administration/cuda-recovery02-hostexit-v2/f1"
original = f1 / "standard-result-index.with-CUDA-lineage.json"; index = read(original)
if len(index["records"]) != 240 or index.get("root_reviewed_CUDA_supplement") is not True: raise ValueError("Actual reviewedCUDA240 index required")
changed = []
for entry in index["records"]:
    for kind in ("contract", "result"):
        old = entry[kind]["path"]; new = canonical(old)
        if sha(new) != entry[kind]["sha256"]: raise ValueError("Canonical reference does not resolve to exact unchanged original file bytes")
        if old != new: changed.append({"kind": kind, "original_path": old, "Windows_path": new, "sha256_unchanged": entry[kind]["sha256"]})
        entry[kind]["path"] = new
index["path_canonicalization_source_index"] = ref(original)
index["path_canonicalization_adapter"] = ref(__file__)
index["original_contract_result_bytes_and_all_metric_values_unchanged"] = True
target = f1 / "standard-result-index.with-CUDA.windows-paths.json"; write(target, index)
out = PROJECT / "administration/v1/normalized-v2"
if out.exists(): raise FileExistsError("Use a new validator revision; never overwrite original failure")
command = [sys.executable, "-X", "utf8", str(source), "--index", str(target), "--out", str(out)]
started = datetime.now(timezone.utc).isoformat()
stdout, stderr2 = HERE / "validate.windows-v2.stdout.log", HERE / "validate.windows-v2.stderr.log"
with stdout.open("xb") as so, stderr2.open("xb") as se:
    child = subprocess.Popen(command, stdout=so, stderr=se); code = child.wait(timeout=600)
receipt = {"schema": "explicit-original-validator-Windows-path-adapter.v2", "original_failed_validator_exit": ref(prior_exit), "original_failed_validator_stderr": ref(stderr), "original_withCUDA_index": ref(original), "new_withCUDA_Windows_path_index": ref(target), "path_alias_changes": changed, "all_contract_result_digests_unchanged": True, "frozen_validator_source": ref(source), "command": command, "pid": child.pid, "actual_exit_code": code, "started_at": started, "ended_at": datetime.now(timezone.utc).isoformat(), "stdout": ref(stdout), "stderr": ref(stderr2), "new_validation_output": str(out), "metric_values_changed": False, "scientific_steps_rerun": 0, "registry_updates": 0}
write(HERE / "VALIDATION-WINDOWS-PATH-RECOVERY.json", receipt)
print(json.dumps({"actual_exit_code": code, "canonical_path_refs": len(changed), "new_validation_output": str(out)}, ensure_ascii=False)); raise SystemExit(code)
