"""Serial, bounded external inference jobs; never retrain or tune models."""
import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=root / "runs" / "cpu-external-v1")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    jobs = []
    for view in ("profaff_pKd_domain_backbone_all162_external", "uniair_her2_pKd_protein_extension_external"):
        for train_view in ("ppikb_kd_source_cold_scope_v2", "ppikb_kd_target_cold_scope_v2"):
            command = [sys.executable, str(Path(__file__).with_name("run_cpu_external.py")),
                       "--manifest", str(args.manifest), "--external-view", view,
                       "--training-view-dir", str(root / "runs" / "cpu-v2" / train_view), "--output", str(args.output)]
            started = time.time()
            log_path = args.output / f"{view}__from__{train_view}.log"
            with log_path.open("w", encoding="utf-8") as log:
                child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
                try:
                    code = child.wait(timeout=300)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
                    code = 124
            record = {"external_view": view, "training_view": train_view, "command": command,
                      "pid": child.pid, "exit_code": code, "elapsed_seconds": time.time()-started,
                      "completed_at": datetime.now(timezone.utc).isoformat(), "log": str(log_path)}
            jobs.append(record)
            (args.output / "batch-receipt.json").write_text(json.dumps({"jobs": jobs, "new_fits": 0}, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps({"external_view": view, "training_view": train_view, "exit_code": code}), flush=True)
    return 0 if all(record["exit_code"] == 0 for record in jobs) else 2


if __name__ == "__main__":
    raise SystemExit(main())
