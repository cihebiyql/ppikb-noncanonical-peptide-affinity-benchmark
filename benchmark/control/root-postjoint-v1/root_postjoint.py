"""Windows root-only wrapper. WSL science prep then metadata issuance; no score."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent.parent
WSL = "/mnt/d/work/科研工作台/research-tasks/peptide-binding-nc-benchmark-20261021"
PYTHON = "/root/.venvs/peptide-omnipanel-v31-web311-20260723/bin/python"
DEADLINE = datetime.fromisoformat("2026-10-22T01:45:00+00:00")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def wsl(path):
    return WSL + "/" + str(Path(path).resolve().relative_to(PROJECT)).replace("\\", "/")


def write(path, body):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(body, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def root_execute(exit_proof, exit_sha, name, authorized=False):
    if authorized is not True:
        raise PermissionError("Explicit --root-execute-postjoint-authorized required; preparation never executes")
    if os.name != "nt":
        raise RuntimeError("Use existing WindowsPython311; all scientific file traversal runs in WSL")
    if not re.fullmatch("[A-Za-z0-9_.-]+", name):
        raise ValueError("Simple unique execution-name required")
    remaining = (DEADLINE - datetime.now(timezone.utc)).total_seconds()
    if remaining <= 1800:
        raise TimeoutError("Original global cutoff cannot fit full evaluation budget")
    frozen = json.loads((HERE / "SOURCE-FREEZE-v1.json").read_text(encoding="utf-8"))
    for row in frozen["files"]:
        if sha(PROJECT / row["relative_path"]) != row["sha256"]:
            raise ValueError("Frozen code/spec changed: " + row["relative_path"])
    exit_proof = Path(exit_proof).resolve()
    if exit_proof.suffix != ".json" or sha(exit_proof) != exit_sha:
        raise ValueError("Actual root wait proof must be a pinned immutable JSON inside project")
    output = HERE / name
    output.mkdir(exist_ok=False)
    write(output / "ROOT-EXPLICIT-EXECUTION.json", {"root_execute_postjoint_authorized": True, "requested_at": datetime.now(timezone.utc).isoformat(), "pool_exit_proof": {"path": wsl(exit_proof), "sha256": exit_sha}, "deadline": DEADLINE.isoformat(), "score_launch_authorized_by_this_wrapper": False})
    science = ["wsl.exe", "--exec", "env", "PYTHONPATH=" + WSL + "/resources/local-gpu-route/vendor-dependencies", "CUDA_VISIBLE_DEVICES=", "OMP_NUM_THREADS=1", "OPENBLAS_NUM_THREADS=1", "MKL_NUM_THREADS=1", "NUMEXPR_NUM_THREADS=1", "timeout", "--signal=TERM", "--kill-after=15s", "1900s", PYTHON, WSL + "/control/root-postjoint-v1/wsl_prepare.py", "--root-execute-postjoint-authorized", "--output", wsl(output), "--pool-exit-proof", wsl(exit_proof), "--pool-exit-proof-sha256", exit_sha]
    write(output / "scientific-command.json", {"argv": science, "read_scope": "WSL only; no live producer file is opened by Windows"})
    with (output / "WSL.stdout.log").open("xb") as out, (output / "WSL.stderr.log").open("xb") as err:
        code = subprocess.call(science, stdout=out, stderr=err)
    write(output / "WSL-process-exit.json", {"exit_code": code, "ended_at": datetime.now(timezone.utc).isoformat(), "stdout_sha256": sha(output / "WSL.stdout.log"), "stderr_sha256": sha(output / "WSL.stderr.log")})
    if code != 0:
        raise RuntimeError("WSL gate/barrier/audit failed; preserve output, no auto-retry or score")
    prepared = json.loads((output / "WSL-PREPARED.json").read_text(encoding="utf-8"))
    if prepared.get("status") != "actual_joint_and_checkpoint_audit_complete_score_not_launched" or prepared.get("score_processes_started") != 0:
        raise ValueError("Actual immutable WSL completion not confirmed")
    if (DEADLINE - datetime.now(timezone.utc)).total_seconds() <= 1800:
        raise TimeoutError("No complete1800sec evaluation reserve remains; no contract issuance")
    issuer_out = PROJECT / "administration" / ("root-postjoint-issued-" + name)
    issuer = [sys.executable, "-X", "utf8", str(PROJECT / "administration/postjoint_issue_all.py"), "--inputs", str(output / "issuer-inputs.json"), "--out", str(issuer_out)]
    write(output / "issuer-command.json", {"argv": issuer})
    with (output / "issuer.stdout.log").open("xb") as out, (output / "issuer.stderr.log").open("xb") as err:
        result = subprocess.run(issuer, stdout=out, stderr=err, timeout=600, check=False)
    write(output / "issuer-exit.json", {"exit_code": result.returncode, "ended_at": datetime.now(timezone.utc).isoformat(), "stdout_sha256": sha(output / "issuer.stdout.log"), "stderr_sha256": sha(output / "issuer.stderr.log")})
    if result.returncode != 0:
        raise RuntimeError("Central contract issuance failed; no actual score launched")
    issuance_path = issuer_out / "POSTJOINT-ISSUANCE.json"
    issued = json.loads(issuance_path.read_text(encoding="utf-8"))
    ready = {"status": "root_prepared_actual_joint_audit_and240contracts_score_not_started", "issued_metadata": {"path": str(issuance_path), "sha256": sha(issuance_path)}, "pools": issued["pools"], "actual_score_processes_launched": 0, "deadline": DEADLINE.isoformat()}
    write(output / "NEXT-POOL-COMMANDS.json", ready)
    print(json.dumps(ready, ensure_ascii=False, indent=2))
    return ready


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root-execute-postjoint-authorized", action="store_true")
    parser.add_argument("--pool-exit-proof", required=True)
    parser.add_argument("--pool-exit-proof-sha256", required=True)
    parser.add_argument("--execution-name", required=True)
    args = parser.parse_args()
    root_execute(args.pool_exit_proof, args.pool_exit_proof_sha256, args.execution_name, args.root_execute_postjoint_authorized)
