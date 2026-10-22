"""Canonicalize only actual failing contract-path references; no frozen edits."""
import ast
import copy
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


prior_exit = HERE / "validate.actual-exit.json"; prior = read(prior_exit)
if prior["exit_code"] != 1: raise ValueError("Require actual failed original validator, never relabel it")
stderr = Path(prior["stderr"]["path"])
if sha(stderr) != prior["stderr"]["sha256"]: raise ValueError("Original validator failure evidence changed")
error = stderr.read_text(encoding="utf-8")
if "contract_file.read_bytes()" not in error or "FileNotFoundError" not in error: raise ValueError("Not the actual failing original contract-byte metadata read")
missing = ast.literal_eval(error.strip().splitlines()[-1].split("No such file or directory: ", 1)[1])
if not missing.startswith("\\mnt\\d\\"): raise ValueError("Actual failed path is not the Windows-normalizedWSL prefix")
source = PROJECT / "administration/validate_stage_result_index.py"
if sha(source) != "1169d8ed1e4f44c29b9615dafb08faba2c4b2ae6a2e5a790fb14f97c44b3bf3b": raise ValueError("Original validator source must remain unchanged")
f1 = PROJECT / "administration/cuda-recovery02-hostexit-v2/f1"
original = f1 / "standard-result-index.with-CUDA-lineage.json"; original_index = read(original); index = copy.deepcopy(original_index)
if len(index["records"]) != 240 or index.get("root_reviewed_CUDA_supplement") is not True: raise ValueError("Actual reviewedCUDA240 index required")
changed = []
for entry in index["records"]:
    old = entry["contract"]["path"]
    if not old.startswith("/mnt/d/"): raise ValueError("Only the original240 WSL contract references may be adapted")
    new = "D:/" + old[len("/mnt/d/"):]
    if sha(new) != entry["contract"]["sha256"]: raise ValueError("Canonical contract path must identify exact unchanged original bytes")
    changed.append({"kind": "contract", "original_path": old, "Windows_path": new, "sha256_unchanged": entry["contract"]["sha256"]})
    entry["contract"]["path"] = new
if len(changed) != 240: raise ValueError("Exactly240 contract path representations must change")
for original_row, aliased in zip(original_index["records"], index["records"]):
    check = copy.deepcopy(aliased); check["contract"]["path"] = original_row["contract"]["path"]
    if check != original_row: raise ValueError("Result/metric/family/digest/lineage fields cannot change")
index["path_canonicalization_source_index"] = ref(original)
index["path_canonicalization_adapter"] = ref(__file__)
index["original_contract_result_bytes_and_all_metric_values_unchanged"] = True
target = f1 / "standard-result-index.with-CUDA.windows-paths.json"; write(target, index)
out = PROJECT / "administration/v1/normalized-v2"
if out.exists(): raise FileExistsError("Preserve earlier validator output; do not rerun/overwrite")
command = [sys.executable, "-X", "utf8", str(source), "--index", str(target), "--out", str(out)]
started = datetime.now(timezone.utc).isoformat()
stdout, stderr2 = HERE / "validate.windows-v3.stdout.log", HERE / "validate.windows-v3.stderr.log"
with stdout.open("xb") as so, stderr2.open("xb") as se:
    child = subprocess.Popen(command, stdout=so, stderr=se); code = child.wait(timeout=600)
receipt = {"schema": "explicit-original-validator-contract-path-adapter.v3", "original_failed_validator_exit": ref(prior_exit), "original_failed_validator_stderr": ref(stderr), "actual_original_unresolvable_path": missing, "prior_guard_only_adapter_rejection": {"source": ref(HERE / "validate_windows_paths_v2.py"), "actual_tool_chunk": "3f229e", "actual_exit_code": 1, "reason": "Guard used literal single backslashes against an exception repr with escaped backslashes; exited before index creation or validation; v3 parses actual exception path literal", "index_or_scientific_file_changes": 0}, "original_withCUDA_index": ref(original), "new_withCUDA_Windows_path_index": ref(target), "path_alias_changes": changed, "all_contract_result_digests_unchanged": True, "all_original_records_except_contract_path_representation_identical": True, "frozen_validator_source": ref(source), "command": command, "pid": child.pid, "actual_exit_code": code, "started_at": started, "ended_at": datetime.now(timezone.utc).isoformat(), "stdout": ref(stdout), "stderr": ref(stderr2), "new_validation_output": str(out), "metric_values_changed": False, "scientific_steps_rerun": 0, "registry_updates": 0}
write(HERE / "VALIDATION-WINDOWS-PATH-RECOVERY.json", receipt)
print(json.dumps({"actual_exit_code": code, "canonical_contract_refs": len(changed), "new_validation_output": str(out)}, ensure_ascii=False)); raise SystemExit(code)
