"""Observe a root-supplied WSL command and preserve its actual native exit.

The outer observer returns zero after recording a completed child, even when the
child failed. Scientific success is determined by native-exit.json, never by the
observer's own return code. No model imports, process signals, or silent retries.
"""
import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def sha(p):
    h = hashlib.sha256()
    with Path(p).open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()

def save(p, value):
    with Path(p).open("x", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)

p = argparse.ArgumentParser()
p.add_argument("--command", required=True)
p.add_argument("--command-sha256", required=True)
a = p.parse_args()
if os.name != "nt":
    raise RuntimeError("Native WSL return-code observation uses the Windows parent")
command = Path(a.command).resolve()
if not command.is_relative_to(ROOT) or sha(command) != a.command_sha256:
    raise ValueError("Root-supplied immutable command must be inside this project")
body = json.loads(command.read_text(encoding="utf-8"))
argv = body["argv"]
if not isinstance(argv, list) or not argv or any(not isinstance(v, str) for v in argv) or Path(argv[0]).name.lower() != "wsl.exe":
    raise ValueError("An explicit WSL argv list is required")
out = Path(body["output_root"]).resolve()
if not out.is_relative_to(ROOT / "control" / "observed-pools"):
    raise ValueError("A fresh task-owned observer directory is required")
out.mkdir(parents=True, exist_ok=False)
with (out / "stdout.log").open("xb") as stdout, (out / "stderr.log").open("xb") as stderr:
    child = subprocess.Popen(argv, stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
    save(out / "process-started.json", dict(argv=argv, command_sha256=a.command_sha256,
         windows_wsl_pid=child.pid, windows_observer_pid=os.getpid(),
         started_at=datetime.now(timezone.utc).isoformat(), process_signals_sent=0))
    code = child.wait()
receipt = dict(native_wsl_exit_code=code, native_exit_directly_observed=True,
               actual_wait_completed=True, windows_wsl_pid=child.pid,
               observed_at=datetime.now(timezone.utc).isoformat(),
               command_sha256=a.command_sha256, stdout_sha256=sha(out / "stdout.log"),
               stderr_sha256=sha(out / "stderr.log"),
               observer_return_policy="zero_after_receipt_even_if_child_failed",
               process_signals_sent=0)
save(out / "native-exit.json", receipt)
print(json.dumps(receipt, ensure_ascii=False))
