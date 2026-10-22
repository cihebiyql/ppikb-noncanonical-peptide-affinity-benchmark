"""One explicit root-authorized CUDA retry metadata preparation; never launch.

Preparation/tests read only closed failure metadata/logs and frozen code/specs.
Real execution, separately invoked by root after actual outer-tool exit1 with source-inferred native2, hashes and
atomically archives the two failed output trees before reusing their namespaces.
"""
import argparse
import copy
import hashlib
import json
import os
import re
import socket
import stat
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent.parent
UID = "MGraphDTA__target_reference_homology_cold__standard_only__seed06"
ATTEMPT = UID + "__cuda_recovery02"
CEILING = "2026-10-21T22:54:18.479676+00:00"
GLOBAL = "2026-10-22T01:45:00+00:00"
POOL_SHA = "fe51a0d03f4f9c08e710e9d8b582d56c497d8c59dc5d14e8cbc6e6d8b41e51d2"
SCIENCE_SHA = "c7b3bde68c9a741c0ac3f255a825e4a55dd7234e2b4e6d48f212fee8d5609ab1"
SPEC_SHA = "62cb03bbc33f3bbcfd63f4d9c2b59513d7b6d60ffe7528462e6e18d73f17e8f7"
CONTRACT_SHA = "3ed3deba92dff057d824050a419bb790df82d4eb15ae23ab4b41e34a0641f4f2"


def read(path): return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""): h.update(block)
    return h.hexdigest()


def ref(path): return {"path": str(path), "sha256": sha(path)}


def write(path, body):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(body, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def check_old_terminal(body, ids):
    if body.get("status") != "complete" or body.get("reason") is not None or body.get("pending") != 0 or body.get("active") != [] or body.get("cleanup_errors") != [] or body.get("complete_count") != 199 or body.get("failed_count") != 1:
        raise PermissionError("Only actual fully drained199-success/one-failure pool is eligible")
    if len(body.get("completed_units", [])) != 199 or set(body["completed_units"]) != set(ids) - {UID} or body.get("failed_units") != [{"unit_id": UID, "reason": "wrapper_exit_1"}] or body.get("index_sha256") != POOL_SHA or body.get("deadline") != GLOBAL:
        raise ValueError("Prior terminal is not exactly the predeclared CUDA-failed cell/v5 roster")


def check_wait(body, expected_code, index_sha):
    actual_code = 1 if expected_code == 2 else expected_code
    if type(body.get("exit_code")) is not int or body["exit_code"] != actual_code or type(body.get("pool_pid")) is not int or body["pool_pid"] <= 1 or body.get("index_sha256") != index_sha or body.get("root_observed_actual_wait") is not True or not body.get("observed_at") or not body.get("source"):
        raise PermissionError("Actual root-observed pool wait/exit identity required")
    if expected_code == 2:
        if body.get("outer_tool_exit_code") != 1 or body.get("native_expected_exit_from_verified_terminal") != 2 or body.get("native_exit_directly_observed") is not False or not isinstance(body.get("normalization_probe"), dict):
            raise PermissionError("Preserve observed host1, inferred native2 and explicit native-unobserved boundary")
    elif expected_code == 0 and (body.get("native_exit_directly_observed") is not True or body.get("native_exit_code") != 0):
        raise PermissionError("Future retry must have directly observed native0 parent wait proof")


def verify_host_mapping(body):
    probe_ref = body["normalization_probe"]
    probe_path = Path(probe_ref["path"])
    if probe_path.suffix != ".json" or sha(probe_path) != probe_ref["sha256"]: raise ValueError("Real same-route exit mapping probe changed")
    probe = read(probe_path)
    if probe.get("requested_native_exit_code") != 2 or probe.get("actual_outer_tool_exit_code") != 1 or probe.get("synthetic_only") is not True or not probe.get("observed_at") or not probe.get("source") or not probe.get("command"):
        raise PermissionError("Actual same-route synthetic native2-to-host1 observation required")
    if probe.get("direct_powershell_tool_result", {}).get("exit_code") != 1:
        raise ValueError("Probe must preserve actual direct PowerShell outer1 result")
    native = probe.get("python_parent_native_evidence", {})
    if native.get("synthetic_only") is not True or native.get("requested_native_exit_code") != 2 or native.get("subprocess_native_returncode") != 2:
        raise ValueError("Probe must preserve actual Python-parent native2 synthetic evidence")
    parsed = json.loads(probe["python_parent_tool_result"]["output"])
    if parsed != native or probe["python_parent_tool_result"].get("exit_code") != 0:
        raise ValueError("Probe structured native evidence must equal actual parent output")
    actual_ref = body.get("actual_parent_wait", {})
    actual_path = Path(actual_ref["path"])
    if actual_path.suffix != ".json" or sha(actual_path) != actual_ref["sha256"]:
        raise ValueError("Actual original parent-tool wait receipt hash differs")
    actual = read(actual_path)
    actual_result = actual.get("actual_tool_result", actual.get("result", actual))
    if actual_result.get("exit_code") != 1 or actual.get("session_id") != 98554 or not actual.get("observed_at"):
        raise ValueError("Actual original parent wait must retain observed outer1")
    supervisor = PROJECT / "launch/pool_supervisor.py"
    source_sha = "73a5dc2e13ebfbe19ebcf91b30d814304eacf0b8338345c4b35ef3202deb43b7"
    if sha(supervisor) != source_sha or "return 0 if not reason and not failed else 2" not in supervisor.read_text(encoding="utf-8"):
        raise ValueError("Native2 inference must bind actual frozen supervisor return expression")
    return {"actual_outer_tool_exit_code": 1, "native_expected_exit_from_verified_terminal": 2, "native_exit_directly_observed": False, "normalization_probe": probe_ref, "supervisor_source": {"path": str(supervisor), "sha256": source_sha}, "basis": "Verified199/1 terminal plus frozen source imply native2; actual outer wait observed1; no direct original native wait is asserted"}


def safe_target(source, destination, project=PROJECT, scope=HERE):
    if Path(source).is_symlink(): raise ValueError("Archive root cannot be a symbolic link")
    source, destination = Path(source).resolve(strict=True), Path(destination).resolve()
    if source in (project.resolve(), scope.resolve()) or not source.is_relative_to(project.resolve()) or not destination.is_relative_to(scope.resolve()) or destination.exists() or source.is_relative_to(scope.resolve()) or destination.is_relative_to(source):
        raise ValueError("Archive paths must be verified absolute project outputs into a new owned destination")
    return source, destination


def inventory(source, destination):
    """Actual runtime byte inventory. No deserialization, links or special files."""
    source = Path(source)
    rows = []
    def visit(directory):
        for child in sorted(directory.iterdir()):
            info = child.lstat()
            if stat.S_ISLNK(info.st_mode) or not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
                raise PermissionError("Links and special files cannot enter same-path recovery archive")
            if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
                raise PermissionError("Hardlinked files are not isolated failed-attempt bytes")
            rel = child.relative_to(source)
            row = {"original_path": str(child), "archive_path": str(Path(destination) / rel), "relative_path": str(rel), "type": "directory" if child.is_dir() else "file", "size": info.st_size, "mtime_ns": info.st_mtime_ns, "ctime_ns": info.st_ctime_ns, "observed_at": datetime.now(timezone.utc).isoformat()}
            if child.is_file(): row["sha256"] = sha(child)
            rows.append(row)
            if child.is_dir(): visit(child)
    visit(source)
    return rows


def assert_inventory(source, rows, archived=False):
    expected = {row["relative_path"] for row in rows}
    current = inventory(source, source)
    if {row["relative_path"] for row in current} != expected:
        raise ValueError("Archive inventory path set differs")
    by_rel = {row["relative_path"]: row for row in current}
    for old in rows:
        now = by_rel[old["relative_path"]]
        for key in ("type", "size", "mtime_ns", "sha256"):
            if now.get(key) != old.get(key): raise ValueError("Byte/metadata inventory changed: " + old["relative_path"])


def retry_binding(old, receipt):
    result = copy.deepcopy(old)
    result.update(binding_receipt=str(receipt), deadline=CEILING)
    if {key for key in set(old) | set(result) if old.get(key) != result.get(key)} != {"binding_receipt", "deadline"}:
        raise ValueError("Only binding receipt path and original deadline cap may change")
    return result


def execute(wait_path, wait_sha, execution_name, authorized=False):
    if authorized is not True: raise PermissionError("Explicit root execution authority required; no preparation-time move")
    if os.name != "posix" or socket.gethostname() != "cihebi": raise RuntimeError("Actual cihebi WSL only")
    if time.time() >= datetime.fromisoformat(CEILING).timestamp(): raise TimeoutError("Original failed-unit ceiling has expired")
    if not re.fullmatch("[A-Za-z0-9_.-]+", execution_name): raise ValueError("Unique simple execution name required")
    frozen = read(HERE / "SOURCE-FREEZE-v1.json")
    for row in frozen["code_and_metadata"]:
        if sha(PROJECT / row["relative_path"]) != row["sha256"]: raise ValueError("Frozen recovery input changed")
    if sha(wait_path) != wait_sha: raise ValueError("Root wait receipt hash differs")
    wait = read(wait_path); check_wait(wait, 2, POOL_SHA)
    host_observation = verify_host_mapping(wait)
    if Path("/proc", str(wait["pool_pid"])).exists(): raise PermissionError("Prior pool still exists; no archive/retry")
    old_index_path = PROJECT / "control/unit-index-v5-all-recovery.json"
    if sha(old_index_path) != POOL_SHA: raise ValueError("Original launch index changed")
    index = read(old_index_path); ids = [u["unit_id"] for u in index["units"]]
    pool_root = Path(index["output_root"])
    terminal_refs = []
    for path in (pool_root / "attempts").glob("*/terminal.json"):
        body = read(path)
        if body.get("status") == "complete":
            check_old_terminal(body, ids); terminal_refs.append(ref(path))
    if len(terminal_refs) != 1: raise ValueError("Unique actual drained prior-pool terminal required")
    check_old_terminal(read(pool_root / "progress.json"), ids)  # WSL only, after actual host1 wait; native2 is inferred.
    failed_terminal = read(pool_root / (UID + ".terminal.json"))
    if failed_terminal.get("status") != "failed" or failed_terminal.get("exit_code") != 1: raise ValueError("Original actualCUDA failure not retained")
    if Path("/proc", str(failed_terminal["pgid"])).exists(): raise PermissionError("Failed private process leader still present")
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit(): continue
        try:
            rest = (proc / "stat").read_text().rsplit(")", 1)[1].split()
            if int(rest[2]) == failed_terminal["pgid"] or int(rest[3]) == failed_terminal["pgid"]: raise PermissionError("Failed private PGID/session still has members")
        except (FileNotFoundError, ProcessLookupError): pass
    unit = next(u for u in index["units"] if u["unit_id"] == UID)
    if unit["spec_sha256"] != SPEC_SHA or unit["contract_sha256"] != CONTRACT_SHA or sha(unit["spec"]) != SPEC_SHA or sha(unit["contract"]) != CONTRACT_SHA: raise ValueError("Original scientific spec/contract changed")
    spec = read(unit["spec"]); receipt_root = Path(spec["launch_proof"]["receipt_root"]); fit_root = Path(spec["run_root"])
    if (receipt_root / "unit-complete.json").exists() or (fit_root / "selection.json").exists(): raise PermissionError("Cannot replace a complete/frozen scientific output")
    started = read(receipt_root / "unit-started.json")
    if started["effective_unit_deadline"] != CEILING or started["started_at"] != "2026-10-21T20:54:18.654494+00:00": raise ValueError("Original first-start/ceiling changed")
    closed = read(HERE / "closed-failure-facts.json")
    for item in closed["files"]:
        if sha(item["path"]) != item["sha256"]: raise ValueError("Closed failure metadata/log changed")
    output = HERE / execution_name; output.mkdir(exist_ok=False)
    if Path(PROJECT / "launch/pool-runs-v6-cuda-recovery02").exists():
        raise FileExistsError("New retry pool output must be absent before any failed-tree move")
    archive = output / "archive"; archive.mkdir()
    pairs = [(fit_root, archive / "fit-root"), (receipt_root, archive / "receipt-root")]
    trees = []
    for source, target in pairs:
        source, target = safe_target(source, target)
        trees.append({"original_root": str(source), "archive_root": str(target), "entries": inventory(source, target)})
    intent = {"attempt_id": ATTEMPT, "scientific_unit_id": UID, "namespace_reuse": True, "scientific_paths_no_longer_identify_the_original_attempt": True, "archive_operation": "same-filesystem os.rename, no overwrite, no deletion, no deserialization", "prior_pool_wait": ref(wait_path), "prior_pool_exit_observation": host_observation, "prior_pool_terminal": terminal_refs[0], "prior_failed_terminal": ref(pool_root / (UID + ".terminal.json")), "original_first_start": started["started_at"], "original_absolute_unit_ceiling": CEILING, "original_global_deadline": GLOBAL, "scientific_index_sha256": SCIENCE_SHA, "spec_sha256": SPEC_SHA, "contract_sha256": CONTRACT_SHA, "trees": trees, "created_at": datetime.now(timezone.utc).isoformat()}
    write(output / "archive-intent.json", intent)
    for tree in trees: assert_inventory(tree["original_root"], tree["entries"])
    if time.time() >= datetime.fromisoformat(CEILING).timestamp(): raise TimeoutError("Original ceiling expired before archive; no namespace mutation")
    for tree in trees:
        os.rename(tree["original_root"], tree["archive_root"])
        assert_inventory(tree["archive_root"], tree["entries"], archived=True)
        if Path(tree["original_root"]).exists(): raise ValueError("Original namespace not vacant after archive")
    write(output / "archive-complete.json", {**intent, "status": "all_failed_tree_bytes_and_paths_archived_verified", "archive_intent": ref(output / "archive-intent.json"), "completed_at": datetime.now(timezone.utc).isoformat(), "actual_retry_launches": 0})
    if time.time() >= datetime.fromisoformat(CEILING).timestamp(): raise TimeoutError("Archive preserved but original ceiling expired; no retry metadata grant")
    binding_path = output / "retry-binding.json"
    binding = retry_binding(read(unit["unit_binding"]), output / "retry-binding-launch-receipt.json")
    write(binding_path, binding)
    retry_unit = copy.deepcopy(unit); retry_unit.update(unit_binding=str(binding_path), unit_binding_sha256=sha(binding_path))
    new_index = copy.deepcopy(index)
    new_index.update(max_concurrent=1, deadline=CEILING, output_root=str(PROJECT / "launch/pool-runs-v6-cuda-recovery02"), units=[retry_unit] + [copy.deepcopy(u) for u in index["units"] if u["unit_id"] != UID])
    if Path(new_index["output_root"]).exists(): raise FileExistsError("New retry pool output root already exists")
    index_path = output / "retry-pool-index.json"; write(index_path, new_index)
    lineage = {"schema": "explicit-cuda-recovery02.v1", "attempt_id": ATTEMPT, "scientific_unit_id": UID, "prior_failure": ref(HERE / "closed-failure-facts.json"), "prior_pool_wait": ref(wait_path), "prior_pool_terminal": terminal_refs[0], "archive_manifest": ref(output / "archive-complete.json"), "retry_binding": ref(binding_path), "retry_pool_index": ref(index_path), "old_launch_index_sha256": POOL_SHA, "scientific_index_sha256_unchanged": SCIENCE_SHA, "original_first_start": started["started_at"], "original_absolute_unit_ceiling": CEILING, "original_global_deadline": GLOBAL, "explicit_retry_limit": 1, "same_namespace_reused_after_verified_archive": True, "old_pool_logs_terminal_unchanged": True, "scientific_grid": "400 valid fits/200 selected cells; two historical interrupted candidate attempts retained separately", "launch_cli": [index["python"], str(PROJECT / "launch/pool_supervisor.py"), "--index", str(index_path), "--index-sha256", sha(index_path)], "required_environment": {"PYTHONPATH": index["PYTHONPATH"], "CUDA_VISIBLE_DEVICES": index["gpu_uuid"]}, "actual_retry_launches": 0}
    lineage["prior_pool_exit_observation"] = host_observation
    write(output / "RECOVERY-READY.json", lineage)
    print(json.dumps(lineage, ensure_ascii=False, indent=2)); return lineage


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root-execute-archive-and-retry-metadata-authorized", action="store_true")
    parser.add_argument("--pool-exit-proof", required=True)
    parser.add_argument("--pool-exit-proof-sha256", required=True)
    parser.add_argument("--execution-name", required=True)
    args = parser.parse_args()
    execute(args.pool_exit_proof, args.pool_exit_proof_sha256, args.execution_name, args.root_execute_archive_and_retry_metadata_authorized)
