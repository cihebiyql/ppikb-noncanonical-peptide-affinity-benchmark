"""Freeze contracts and sequentially launch five bounded, real GPU canaries."""
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
GPU = 'GPU-e9419f8b-b24b-a22b-c8ec-8f5173f4b45a'
METHODS = ['GraphDTA-GIN', 'MGraphDTA', 'DGDTA-CL', 'DeepNC-GEN', 'MRBDTA']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def gpu_state():
    values = {}
    for key, args in [('gpu', ['--query-gpu=uuid,memory.used,utilization.gpu']), ('compute', ['--query-compute-apps=pid,process_name,used_memory'])]:
        call = subprocess.run(['nvidia-smi'] + args + ['--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=10)
        if call.returncode:
            raise RuntimeError(call.stderr)
        values[key] = call.stdout.strip()
    line = next(line for line in values['gpu'].splitlines() if GPU in line)
    values['used_MiB'] = int(line.split(',')[1])
    values['time_epoch'] = time.time()
    return values


def tree_rss(root):
    rows = []
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():
            continue
        try:
            fields = (p / 'stat').read_text().split(')', 1)[1].split()
            rows.append((int(p.name), int(fields[1]), p))
        except (OSError, ValueError, IndexError):
            pass
    members = {root}
    while True:
        children = {pid for pid, parent, _ in rows if parent in members}
        if children <= members:
            break
        members |= children
    total = 0
    for pid, _, directory in rows:
        if pid in members:
            try:
                total += next(int(line.split()[1]) * 1024 for line in (directory / 'status').read_text().splitlines() if line.startswith('VmRSS:'))
            except (OSError, StopIteration):
                pass
    return total


def main():
    assert platform.node() == 'cihebi'
    dest = HERE / 'gpu-canary-v1'
    dest.mkdir(exist_ok=False)
    sample = PROJECT / 'execution/canary-staging-v1/train-only-32.jsonl'
    assert sha(sample) == '1562172160338140f24cf3de9e2e46c6c14d5e305627caec9e37ceaacb8a8333'
    available = sorted(os.sched_getaffinity(0))
    os.sched_setaffinity(0, available[:2])
    reports = []
    for method in METHODS:
        original = json.loads((PROJECT / f'execution/canary-contracts-v1/{method}-contract.json').read_text())
        contract = dict(original)
        contract.update(stage='local-GPU-train-only-performance-canary', host='cihebi', cpu_threads=2,
                        memory_gib=8, timeout_seconds=180, gpu_count=1, GPU_UUID=GPU,
                        train_sample=str(sample), methods_root=str(PROJECT / 'execution/canary-methods-v1'),
                        receipt_path=str(dest / f'{method}-result.json'),
                        python=sys.executable, CUDA_VISIBLE_DEVICES=GPU,
                        optimizer_steps=2, batch_size=1 if method == 'MRBDTA' else 32,
                        gradient_accumulation=16 if method == 'MRBDTA' else 1,
                        GPU_peak_budget_bytes=8 * 1024**3,
                        GPU_allocator_budget_bytes=7 * 1024**3,
                        watchdog='process-tree RSS 8 GiB / observed global GPU memory delta 8 GiB / 180 sec; 0.1 sec poll, GPU 1 sec poll',
                        dependency_manifest_sha256=sha(HERE / 'dependency-export-manifest.json'),
                        canary_script_sha256=sha(HERE / 'gpu_canary.py'),
                        no_full_training=True, no_checkpoints_retained=True)
        contract_path = dest / f'{method}-contract.json'
        write(contract_path, contract)
        probes = []
        for _ in range(3):
            probe = gpu_state()
            probes.append(probe)
            if probe['compute']:
                write(dest / f'{method}-launch-block.json', {'reason':'compute_process_observed_before_launch', 'probes':probes})
                raise RuntimeError('GPU busy; no launch')
            time.sleep(2)
        baseline = probes[-1]['used_MiB']
        env = dict(os.environ, CUDA_VISIBLE_DEVICES=GPU, PYTHONPATH=str(HERE / 'vendor-dependencies'),
                   OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2', NUMEXPR_NUM_THREADS='2')
        started = time.monotonic()
        rss_max = gpu_delta_max = 0
        reason = None
        monitor = []
        last_gpu = 0.
        with (dest / f'{method}.stdout.log').open('w') as out, (dest / f'{method}.stderr.log').open('w') as err:
            child = subprocess.Popen([sys.executable, str(HERE / 'gpu_canary.py'), '--contract', str(contract_path)], env=env, stdout=out, stderr=err, start_new_session=True)
            while child.poll() is None:
                rss_max = max(rss_max, tree_rss(child.pid))
                elapsed = time.monotonic() - started
                if elapsed - last_gpu >= 1.:
                    state = gpu_state()
                    last_gpu = elapsed
                    delta = max(0, state['used_MiB'] - baseline) * 1024**2
                    gpu_delta_max = max(gpu_delta_max, delta)
                    monitor.append(state)
                if rss_max > 8 * 1024**3:
                    reason = 'process_tree_RSS_above_8GiB'
                elif gpu_delta_max > 8 * 1024**3:
                    reason = 'observed_GPU_delta_above_8GiB'
                elif elapsed > 180:
                    reason = 'timeout_180sec'
                if reason:
                    os.killpg(child.pid, signal.SIGKILL)
                    break
                time.sleep(.1)
            code = child.wait()
        after = gpu_state()
        receipt = {'method_id':method, 'contract_sha256':sha(contract_path), 'pid':child.pid, 'exit_code':code, 'stop_reason':reason,
                   'elapsed_seconds':time.monotonic()-started, 'max_process_tree_RSS_bytes':rss_max,
                   'max_observed_global_GPU_delta_bytes':gpu_delta_max,
                   'prelaunch_three_GPU_probes':probes, 'GPU_monitor':monitor, 'post_exit_GPU_probe':after,
                   'process_exited':not Path(f'/proc/{child.pid}').exists(),
                   'success':code == 0 and reason is None, 'GPU_delta_includes_desktop_variation':True,
                   'outputs':{}}
        for path in (dest / f'{method}-result.json', dest / f'{method}.stdout.log', dest / f'{method}.stderr.log'):
            if path.exists():
                receipt['outputs'][path.name]={'sha256':sha(path), 'bytes':path.stat().st_size}
        write(dest / f'{method}-watchdog-receipt.json', receipt)
        reports.append({k:receipt[k] for k in ['method_id','pid','exit_code','stop_reason','elapsed_seconds','max_process_tree_RSS_bytes','max_observed_global_GPU_delta_bytes','process_exited','success']})
        write(dest / 'launch-summary.json', reports)
        print(json.dumps(reports[-1]), flush=True)
        if reason:
            break
    return 0 if len(reports) == 5 and all(r['success'] for r in reports) else 1


if __name__ == '__main__':
    raise SystemExit(main())
