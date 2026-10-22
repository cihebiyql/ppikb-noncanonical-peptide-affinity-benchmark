"""Write actual administrative test receipts; no model or GPU work is launched."""
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
WORKSPACE = BASE.parents[2]
STANDARD = WORKSPACE / "复现" / "规范"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    started = datetime.now(timezone.utc).isoformat()
    evidence = BASE / "administrative-verification-v1"
    evidence.mkdir(exist_ok=False)
    commands = [
        [sys.executable, "-X", "utf8", "-m", "unittest", "-v", "test_administration.py"],
        [sys.executable, "-X", "utf8", str(STANDARD / "validate_reproduction.py"), "--contract", str(STANDARD / "task-contract.template.json"), "--result", str(STANDARD / "result-record.template.json"), "--allow-template"],
    ]
    receipts = []
    for index, command in enumerate(commands):
        result = subprocess.run(command, cwd=BASE, capture_output=True, text=True, encoding="utf-8", timeout=30)
        stdout = evidence / f"check-{index}-stdout.txt"
        stderr = evidence / f"check-{index}-stderr.txt"
        stdout.write_text(result.stdout, encoding="utf-8")
        stderr.write_text(result.stderr, encoding="utf-8")
        receipts.append({"command": command, "exit_code": result.returncode, "stdout_path": str(stdout), "stdout_sha256": digest(stdout), "stderr_path": str(stderr), "stderr_sha256": digest(stderr)})
    parsed = []
    for path in sorted(BASE.glob("*.json")):
        json.loads(path.read_text(encoding="utf-8-sig"))
        parsed.append({"path": str(path), "sha256": digest(path)})
    report = {"schema": "peptide-binding.nc-benchmark.administration-verification.v1", "started_at": started, "ended_at": datetime.now(timezone.utc).isoformat(), "hostname": platform.node(), "python": sys.version, "scientific_models_executed": 0, "gpu_workloads_launched": 0, "all_commands_exit_zero": all(item["exit_code"] == 0 for item in receipts), "checks": receipts, "parseable_json": parsed, "scope": "Administrative guard unit tests and central template structure only; not a model-run or full-pipeline test"}
    save(evidence / "receipt.json", report)
    assets = []
    for path in sorted(BASE.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts:
            assets.append({"path": str(path), "size_bytes": path.stat().st_size, "sha256": digest(path)})
    save(evidence / "artifact-manifest.json", {"created_at": datetime.now(timezone.utc).isoformat(), "files": assets})
    print(json.dumps({"passed": report["all_commands_exit_zero"], "receipt_path": str(evidence / "receipt.json"), "scientific_models_executed": 0}, ensure_ascii=False))
    sys.exit(0 if report["all_commands_exit_zero"] else 1)
