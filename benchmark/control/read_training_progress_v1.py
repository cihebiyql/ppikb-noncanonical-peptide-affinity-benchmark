"""WSL-only observer; never changes a producer or reads scientific payloads."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

if os.name != "posix":
    raise RuntimeError("Read live producer metadata through WSL only")
root = Path(__file__).resolve().parents[1]
p = root / "launch/pool-runs-v5-all-recovery/progress.json"
d = json.loads(p.read_text(encoding="utf-8"))
age = (datetime.now(timezone.utc) - datetime.fromisoformat(d["at"])).total_seconds()
if d["status"] == "running" and age > 120:
    raise RuntimeError(f"Producer heartbeat is stale by {age:.1f} seconds")
print(json.dumps({k: d.get(k) for k in (
    "status", "at", "complete_count", "pending", "active", "failed_count",
    "watchdog_reason", "reason", "pool_RSS_bytes", "new_launch_gate",
    "test_scoring_started",
)}, ensure_ascii=False))
