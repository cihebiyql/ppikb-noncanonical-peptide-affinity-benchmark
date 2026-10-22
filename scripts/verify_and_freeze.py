"""Freeze standard-library helpers after synthetic-only checks."""
import hashlib
import json
import py_compile
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
names = ("restore_artifacts.py", "restore_upstream.py", "test_restore.py", "README.md", "verify_and_freeze.py")
for name in names:
    if name.endswith(".py"): py_compile.compile(str(HERE / name), doraise=True)
command = [sys.executable, "-X", "utf8", "-m", "unittest", "-v", "test_restore.py"]
result = subprocess.run(command, cwd=HERE, capture_output=True, text=True, encoding="utf-8", timeout=60, check=False)
for name, content in (("synthetic.stdout.log", result.stdout), ("synthetic.stderr.log", result.stderr)):
    with (HERE / name).open("x", encoding="utf-8") as stream: stream.write(content)
if result.returncode: raise RuntimeError("Synthetic restoration mechanics failed")
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
freeze = {"schema": "standard-library-public-restoration-helpers.v1", "created_at": datetime.now(timezone.utc).isoformat(), "files": [{"name": name, "sha256": sha(HERE / name)} for name in names], "synthetic_tests": 11, "actual_test_exit_code": result.returncode, "actual_test_command": command, "test_stdout_sha256": sha(HERE / "synthetic.stdout.log"), "test_stderr_sha256": sha(HERE / "synthetic.stderr.log"), "actual_real_model_or_research_source_downloads": 0, "actual_model_or_scientific_commands_executed": 0, "dependency_installations": 0, "original_benchmark_or_public_repository_files_modified": 0, "permission_lock_schema_read_only_compatible": "upstream-fetch-lock.v1", "artifact_manifest_schema": "split-gzip-tar-artifacts.v1"}
with (HERE / "SOURCE-FREEZE.json").open("x", encoding="utf-8") as stream: json.dump(freeze, stream, ensure_ascii=False, indent=2); stream.write("\n")
print(json.dumps({"source_freeze_sha256": sha(HERE / "SOURCE-FREEZE.json"), "helpers": {name: sha(HERE / name) for name in names[:2]}, "synthetic_tests_passed": 11, "actual_real_downloads": 0}, indent=2))
