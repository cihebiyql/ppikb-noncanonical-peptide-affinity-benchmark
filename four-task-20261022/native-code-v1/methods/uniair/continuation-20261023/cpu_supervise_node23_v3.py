"""Bound only the owned worker process group and record actual termination."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time

import psutil


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def gpu_probe(device):
    rows = []
    for _ in range(3):
        raw = subprocess.check_output(['nvidia-smi', '-i', str(device), '--query-gpu=index,uuid,memory.used,utilization.gpu', '--format=csv,noheader,nounits'], text=True)
        fields = [x.strip() for x in raw.strip().split(',')]
        processes = subprocess.check_output(['nvidia-smi', '-i', str(device), '--query-compute-apps=pid,used_memory', '--format=csv,noheader,nounits'], text=True).strip()
        rows.append(dict(device=int(fields[0]), uuid=fields[1], memory_MiB=int(fields[2]), utilization=int(fields[3]), processes=processes))
        time.sleep(1)
    return dict(at=now(), samples=rows, passed=all(r['memory_MiB'] < 256 and r['utilization'] <= 5 and not r['processes'] for r in rows))


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--spec', required=True)
    args = p.parse_args()
    spec_path = Path(args.spec)
    spec = json.loads(spec_path.read_text())
    out = Path(spec['output'])
    out.mkdir(parents=True, exist_ok=True)  # New unique run pre-created for standard file validation.
    assert spec.get('gpu') is None and spec['cpu_threads'] <= 16 and spec['memory_limit_bytes'] <= 20*1024**3 and spec['timeout_seconds'] <= 7200
    if socket.gethostname() != 'node23':
        raise RuntimeError('Unexpected host')
    checks = []
    for item in spec['input_hashes']:
        digest = hashlib.file_digest(open(item['path'], 'rb'), 'sha256').hexdigest()
        checks.append(dict(path=item['path'], actual=digest, expected=item['sha256'], passed=digest == item['sha256']))
    write(out / 'hash-check.json', checks)
    if not all(x['passed'] for x in checks):
        raise RuntimeError('Frozen asset mismatch')
    if not spec['contract_validation']['valid_for_execution']:
        raise RuntimeError('Contract not approved for execution')
    gate = gpu_probe(spec['gpu']) if spec.get('gpu') is not None else dict(at=now(), passed=True, gpu=None)
    write(out / 'prestart-probe.json', gate)
    if not gate['passed']:
        raise RuntimeError('GPU is no longer idle')
    if psutil.virtual_memory().available < spec['memory_limit_bytes']:
        raise RuntimeError('Insufficient available RAM')
    env = os.environ.copy()
    env.update(OMP_NUM_THREADS=str(spec['cpu_threads']), MKL_NUM_THREADS=str(spec['cpu_threads']), OPENBLAS_NUM_THREADS=str(spec['cpu_threads']), TOKENIZERS_PARALLELISM='false', CUDA_VISIBLE_DEVICES='' if spec.get('gpu') is None else str(spec['gpu']))
    env.update(spec.get('environment', {}))
    stdout = open(out / 'stdout.log', 'w')
    stderr = open(out / 'stderr.log', 'w')
    start = time.monotonic()
    worker = subprocess.Popen(spec['command'], cwd=spec['cwd'], env=env, stdout=stdout, stderr=stderr, start_new_session=True)
    pgid = os.getpgid(worker.pid)
    owned = psutil.Process(worker.pid)
    available = sorted(os.sched_getaffinity(0))
    cores = available[spec.get('cpu_offset', 0):spec.get('cpu_offset', 0) + spec['cpu_threads']]
    if len(cores) != spec['cpu_threads']:
        raise RuntimeError('Invalid CPU assignment')
    owned.cpu_affinity(cores)
    receipt = dict(started_at=now(), pid=worker.pid, pgid=pgid, command=spec['command'], cpu_affinity=cores, spec_sha256=hashlib.file_digest(open(spec_path, 'rb'), 'sha256').hexdigest(), gpu=spec.get('gpu'), peak_rss_bytes=0, peak_gpu_MiB=0, termination_reason=None)
    write(out / 'launch.json', receipt)
    while worker.poll() is None:
        processes = [owned]
        try:
            processes += owned.children(recursive=True)
        except psutil.Error:
            pass
        rss = 0
        pids = []
        for proc in processes:
            try:
                rss += proc.memory_info().rss
                pids.append(proc.pid)
            except psutil.Error:
                pass
        receipt['peak_rss_bytes'] = max(rss, receipt['peak_rss_bytes'])
        gpu_mem = 0
        if spec.get('gpu') is not None:
            raw = subprocess.check_output(['nvidia-smi', '-i', str(spec['gpu']), '--query-compute-apps=pid,used_memory', '--format=csv,noheader,nounits'], text=True).strip()
            for row in raw.splitlines():
                fields = row.split(',')
                if len(fields) == 2 and fields[0].strip().isdigit() and int(fields[0]) in pids:
                    gpu_mem += int(fields[1].strip())
            receipt['peak_gpu_MiB'] = max(gpu_mem, receipt['peak_gpu_MiB'])
        elapsed = time.monotonic() - start
        reason = None
        if elapsed >= spec['timeout_seconds']:
            reason = 'whole-group timeout'
        elif psutil.virtual_memory().available < spec.get('minimum_system_available_bytes',0):
            reason = 'system available RAM below protected margin'
        elif rss > spec['memory_limit_bytes']:
            reason = 'owned tree RSS exceeded'
        elif gpu_mem * 1024**2 > spec.get('gpu_memory_limit_bytes', 2**100):
            reason = 'owned GPU memory exceeded'
        elif dt.datetime.now(dt.timezone.utc) >= dt.datetime.fromisoformat(spec['deadline_at']):
            reason = 'contract deadline'
        if reason:
            receipt['termination_reason'] = reason
            os.killpg(pgid, signal.SIGTERM)
            try:
                worker.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(pgid, signal.SIGKILL)
            break
        time.sleep(0.5)
    code = worker.wait()
    # Close remaining owned descendants even when a parent erroneously exits first.
    survivors = []
    for proc in psutil.process_iter(['pid']):
        try:
            if os.getpgid(proc.pid) == pgid and proc.status() != psutil.STATUS_ZOMBIE:
                survivors.append(proc.pid)
        except (psutil.Error, ProcessLookupError, PermissionError):
            pass
    if survivors:
        os.killpg(pgid, signal.SIGKILL)
    stdout.close()
    stderr.close()
    receipt.update(ended_at=now(), elapsed_seconds=time.monotonic()-start, exit_code=code, worker_pid_absent=not psutil.pid_exists(worker.pid), residual_group_pids_before_cleanup=survivors)
    write(out / 'process-receipt.json', receipt)
    return code if receipt['termination_reason'] is None and not survivors else 3


if __name__ == '__main__':
    raise SystemExit(main())
