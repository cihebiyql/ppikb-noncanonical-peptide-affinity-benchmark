"""Capture a running scientific pool's process identity, without signalling it."""
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--pid", type=int, required=True)
p.add_argument("--output", required=True)
a = p.parse_args()
if os.name != "posix":
    raise RuntimeError("WSL process identity capture only")
proc = Path("/proc") / str(a.pid)
command = (proc / "cmdline").read_bytes()
if b"pool" not in command or b"peptide-binding-nc-benchmark-20261021" not in command:
    raise ValueError("Not this task's scientific pool")
stat = (proc / "stat").read_text()
tail = stat.rsplit(")", 1)[1].split()
result = dict(pid=a.pid, ppid=int(tail[1]), process_group=int(tail[2]),
              session=int(tail[3]), start_ticks=int(tail[19]),
              command_line=command.replace(b"\0", b" ").decode(),
              command_sha256=hashlib.sha256(command).hexdigest(),
              observed_at=datetime.now(timezone.utc).isoformat(),
              signalled_or_modified=False)
with Path(a.output).open("x", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(json.dumps(result, ensure_ascii=False))
