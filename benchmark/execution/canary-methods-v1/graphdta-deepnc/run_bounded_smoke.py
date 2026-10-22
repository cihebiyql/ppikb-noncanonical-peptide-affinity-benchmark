"""Single-core / 4 GiB RSS / 180 second / no-GPU process-tree watchdog."""
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time


def process_tree_rss(root):
    members = {root}
    rows = []
    for directory in Path("/proc").iterdir():
        if not directory.name.isdigit():
            continue
        try:
            fields = (directory / "stat").read_text().split(")", 1)[1].split()
            rows.append((int(directory.name), int(fields[1]), directory))
        except (OSError, ValueError, IndexError):
            pass
    while True:
        extra = {pid for pid, ppid, _ in rows if ppid in members}
        if extra <= members:
            break
        members |= extra
    total = 0
    for pid, _, directory in rows:
        if pid in members:
            try:
                total += next(int(line.split()[1]) * 1024 for line in (directory / "status").read_text().splitlines() if line.startswith("VmRSS:"))
            except (OSError, StopIteration):
                pass
    return total


def main():
    os.chdir(Path(__file__).resolve().parent)
    contract_path = Path("smoke-contract.json")
    contract = json.loads(contract_path.read_text())
    assert contract["expected_host"] == platform.node()
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", NUMEXPR_NUM_THREADS="1")
    affinity = {min(os.sched_getaffinity(0))}
    os.sched_setaffinity(0, affinity)
    started = time.time()
    reason = None
    maximum = 0
    with open("smoke.stdout.log", "w") as out, open("smoke.stderr.log", "w") as err:
        process = subprocess.Popen([sys.executable, "smoke.py"], env=env, stdout=out, stderr=err, start_new_session=True)
        while process.poll() is None:
            maximum = max(maximum, process_tree_rss(process.pid))
            if maximum > contract["max_tree_rss_bytes"]:
                reason = "4_GiB_RSS_limit"
            elif time.time() - started > contract["timeout_seconds"]:
                reason = "180_second_timeout"
            if reason:
                os.killpg(process.pid, signal.SIGKILL)
                break
            time.sleep(0.1)
        code = process.wait()
    receipt = {"contract_sha256": hashlib.sha256(contract_path.read_bytes()).hexdigest(), "host": platform.node(), "pid": process.pid, "exit_code": code, "stop_reason": reason, "elapsed_seconds": time.time() - started, "max_observed_process_tree_rss_bytes": maximum, "cpu_affinity": sorted(affinity), "watchdog_interval_seconds": 0.1, "CUDA_VISIBLE_DEVICES": "", "success": code == 0 and reason is None, "outputs": {}}
    for name in ("adapter.py", "smoke.py", "vendor-manifest.json", "smoke-results.json", "smoke.stdout.log", "smoke.stderr.log"):
        path = Path(name)
        if path.exists():
            receipt["outputs"][name] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}
    Path("smoke-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))
    return 0 if receipt["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
