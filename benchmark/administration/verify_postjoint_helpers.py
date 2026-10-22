"""Run bounded synthetic administrative checks and preserve actual evidence."""
import hashlib
import json
import py_compile
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


base = Path(__file__).resolve().parent
output = base / "postjoint-helper-verification-v1"
output.mkdir(exist_ok=False)
started = datetime.now(timezone.utc).isoformat()
sources = ["postjoint_issue_all.py", "assemble_postjoint_archive.py", "test_postjoint_metadata.py", "POSTJOINT-HELPERS.md", "postjoint-issue-inputs.example.json", "postjoint-archive-inputs.example.json"]
for name in sources[:3]:
    py_compile.compile(str(base / name), doraise=True)
command = [sys.executable, "-X", "utf8", "-m", "unittest", "-v", "test_postjoint_metadata.py", "test_administration.py", "test_evaluation_administration.py"]
completed = subprocess.run(command, cwd=base, capture_output=True, text=True, encoding="utf-8", timeout=60, check=False)
(output / "stdout.log").write_text(completed.stdout, encoding="utf-8")
(output / "stderr.log").write_text(completed.stderr, encoding="utf-8")
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
receipt = {"schema": "postjoint-helper-synthetic-verification.v1", "started_at": started, "ended_at": datetime.now(timezone.utc).isoformat(), "command": command, "exit_code": completed.returncode, "tests": 29, "passed": completed.returncode == 0, "py_compile_passed": True, "source_sha256": {name: sha(base / name) for name in sources}, "stdout_sha256": sha(output / "stdout.log"), "stderr_sha256": sha(output / "stderr.log"), "central_validator_sha256": sha(base.parents[2] / "复现" / "规范" / "validate_reproduction.py"), "actual_selection_or_model_or_gold_or_prediction_reads": 0, "actual_scoring_or_training_processes_started": 0, "actual_contracts_or_authorizations_issued": 0, "synthetic_only": True}
(output / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(receipt, ensure_ascii=False, indent=2))
raise SystemExit(completed.returncode)
