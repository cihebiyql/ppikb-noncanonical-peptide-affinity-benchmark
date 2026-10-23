"""Bound one owned classical CPU process group; leave shared environments intact."""
import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import pathlib
import signal
import socket
import subprocess
import time

import psutil


def sha(path):
    digest = hashlib.sha256()
    with open(path,"rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""):
            digest.update(block)
    return digest.hexdigest()


def write(path,data):
    temporary = path.with_suffix(path.suffix+".tmp")
    temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec",required=True)
    args = parser.parse_args()
    if socket.gethostname()!="node23":
        raise RuntimeError("wrong host")
    spec_path = pathlib.Path(args.spec)
    spec = json.loads(spec_path.read_text())
    output = pathlib.Path(spec["output"])
    output.mkdir(parents=True,exist_ok=False)
    lock = open(output.parent/"cpu-molecular.lock","w")
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if not set(spec["cpu_affinity"]).issubset(os.sched_getaffinity(0)):
        raise RuntimeError("requested CPU cores unavailable")
    if spec["cpu_threads"]!=2 or len(spec["cpu_affinity"])!=2:
        raise RuntimeError("only two-CPU molecular jobs authorized")
    if psutil.virtual_memory().available < 2*spec["memory_limit_bytes"]:
        raise RuntimeError("insufficient RAM headroom")
    samples = []
    for _ in range(3):
        samples.append(100-psutil.cpu_percent(interval=1))
    if min(samples)<50:
        raise RuntimeError("shared host no longer has sufficient idle CPU")
    checks = [{"path":item["path"],"expected":item["sha256"],"actual":sha(item["path"])} for item in spec["input_hashes"]]
    write(output/"input-hash-checks.json",checks)
    if any(item["actual"]!=item["expected"] for item in checks):
        raise RuntimeError("frozen input/code hash mismatch")
    environment = dict(os.environ,CUDA_VISIBLE_DEVICES="",OMP_NUM_THREADS="2",MKL_NUM_THREADS="2",OPENBLAS_NUM_THREADS="2",NUMEXPR_NUM_THREADS="2",PYTHONDONTWRITEBYTECODE="1")
    stdout = open(output/"stdout.log","w")
    stderr = open(output/"stderr.log","w")
    worker = subprocess.Popen(spec["command"],cwd=spec["cwd"],env=environment,stdout=stdout,stderr=stderr,start_new_session=True)
    group = os.getpgid(worker.pid)
    owned = psutil.Process(worker.pid)
    owned.cpu_affinity(spec["cpu_affinity"])
    owned.nice(15)
    started = time.monotonic()
    receipt = {"started_at":dt.datetime.now(dt.timezone.utc).isoformat(),"pid":worker.pid,"pgid":group,
               "cpu_affinity":spec["cpu_affinity"],"cpu_threads":2,"gpu":False,"nice":15,"idle_samples":samples,
               "spec_sha256":sha(spec_path),"peak_rss_bytes":0,"termination_reason":None}
    write(output/"launch.json",receipt)
    while worker.poll() is None:
        try:
            processes = [owned]+owned.children(recursive=True)
            rss = sum(proc.memory_info().rss for proc in processes if proc.is_running())
        except psutil.Error:
            rss = 0
        receipt["peak_rss_bytes"] = max(rss,receipt["peak_rss_bytes"])
        reason = "owned-memory-limit" if rss>spec["memory_limit_bytes"] else None
        if time.monotonic()-started > spec["timeout_seconds"]:
            reason = "owned-process-group-timeout"
        if dt.datetime.now(dt.timezone.utc)>=dt.datetime.fromisoformat(spec["deadline_at"]):
            reason = "frozen-deadline"
        if reason:
            receipt["termination_reason"] = reason
            os.killpg(group,signal.SIGTERM)
            try:
                worker.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(group,signal.SIGKILL)
            break
        time.sleep(1)
    code = worker.wait()
    stdout.close();stderr.close()
    survivors = []
    for proc in psutil.process_iter(["pid","status"]):
        try:
            if os.getpgid(proc.pid)==group and proc.status()!=psutil.STATUS_ZOMBIE:
                survivors.append(proc.pid)
        except (psutil.Error,ProcessLookupError,PermissionError):
            pass
    if survivors:
        os.killpg(group,signal.SIGKILL)
    receipt.update({"completed_at":dt.datetime.now(dt.timezone.utc).isoformat(),"elapsed_seconds":time.monotonic()-started,
                    "exit_code":code,"worker_pid_absent":not psutil.pid_exists(worker.pid),"surviving_owned_group_pids_before_cleanup":survivors})
    write(output/"process-receipt.json",receipt)
    return code if not receipt["termination_reason"] and not survivors else 3


if __name__=="__main__":
    raise SystemExit(main())
