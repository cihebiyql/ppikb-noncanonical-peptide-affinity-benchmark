"""Synthetic process-exit probe only; no scientific modules or files."""
import json
import subprocess
from datetime import datetime, timezone

argv = ["wsl.exe", "-d", "Ubuntu-22.04", "--", "/usr/bin/python3", "-c", "raise SystemExit(2)"]
result = subprocess.run(argv, capture_output=True, text=True, encoding="utf-8")
print(json.dumps(dict(synthetic_only=True, subprocess_native_returncode=result.returncode,
                     requested_native_exit_code=2, argv=argv,
                     observed_at=datetime.now(timezone.utc).isoformat())))
