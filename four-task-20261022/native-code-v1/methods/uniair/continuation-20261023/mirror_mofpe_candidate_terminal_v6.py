"""Copy only indexed terminal states/small logs to the authorized E task tree.

All epoch weight originals remain on NFS. Capacity holds retain partial copies.
This is an administrative transfer; it imports no scientific/model packages.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import time
import uuid
from uniair_local_mirror_admission_v1 import tree_bytes, decide
from artifact_transfer_failclosed_v1 import AdmissionRejected, require_admission, transfer_after_precheck
C = Path(__file__).resolve().parent
B = C.parents[2]
REMOTE = '<REMOTE_BENCHMARK_ROOT>'
POLICY_SHA = 'f064605b23b25157af412f1e424126eaa8d596119c0bb1134a1a309915574228'

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

def fresh_gate(root, pep_root, policy, planned):
    own, own_count = tree_bytes(root)
    pep, pep_count = tree_bytes(pep_root)
    free = shutil.disk_usage(root).free
    return {'at': dt.datetime.now(dt.timezone.utc).isoformat(), 'own_bytes_including_partials': own, 'PepInter_bytes_including_partials': pep, 'own_files': own_count, 'PepInter_files': pep_count, 'free_bytes': free, 'planned_remaining_bytes': planned, **decide(free, own, pep, planned, policy['own_budget_bytes'], policy['protected_PepInter_budget_bytes'], policy['minimum_volume_free_reserve_bytes'])}

def stop_owned_copy(process):
    if process.poll() is not None:
        return process.communicate(timeout=15)
    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), timeout=15)
    return process.communicate(timeout=15)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--manifest-sha', required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    assert sha(args.manifest) == args.manifest_sha and (not args.receipt.exists())
    manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
    assert manifest['schema'] in ('fourtask.uniair.actual-candidate-terminal-inventory.v4', 'fourtask.uniair.actual-terminal-artifact-inventory.v1')
    assert manifest['remaining_owned_pids'] == [] and isinstance(manifest['actual_PID'], int)
    policy_path = B / 'resources/uniair-local-storage-policy-v1.json'
    assert sha(policy_path) == POLICY_SHA
    policy = json.loads(policy_path.read_text(encoding='utf-8'))
    sibling = json.loads((B / 'resources/local-storage-policy-v1.json').read_text(encoding='utf-8'))
    root = Path(policy['new_asset_root'])
    pep_root = Path(sibling['new_full_PepInter_asset_root'])
    assert root.drive.upper() == 'E:' and root.resolve().drive.upper() == 'E:'
    assert root.is_dir() and (not root.lstat().st_file_attributes & 1024)
    assert args.receipt.parent.resolve() == (root / 'receipts').resolve(), 'Receipt must be inside fixed authorized E receipts directory before any copy'
    receipt_reserve_bytes = 2 * 1024 ** 2
    events = []
    hold = None
    for record in manifest['records']:
        if not record['mirror_locally']:
            continue
        parts = PurePosixPath(record['relative_path']).parts
        assert parts and parts[0] in ('runs', 'resources') and all((part not in ('..', '.', '') for part in parts))
        assert record['remote_path'] == REMOTE + '/' + record['relative_path']
        assert '\n' not in record['remote_path'] and '\r' not in record['remote_path']
        target = root.joinpath(*parts)
        assert target.resolve().is_relative_to(root.resolve())
        if target.exists():
            assert target.is_file() and target.stat().st_size == record['bytes'] and (sha(target) == record['sha256'])
            events.append({'local_path': str(target), 'bytes': record['bytes'], 'sha256': record['sha256'], 'already_present_and_verified': True})
            continue
        admission = fresh_gate(root, pep_root, policy, record['bytes'] + receipt_reserve_bytes)
        try:
            require_admission({'exit_code': 0, 'output': json.dumps(admission)})
        except AdmissionRejected:
            hold = {'reason': 'fresh_E_byte_budget_hold', 'member': record['relative_path'], 'admission': admission}
            break
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(target.name + '.partial.' + uuid.uuid4().hex)
        process = transfer_after_precheck(lambda: {'exit_code': 0, 'output': json.dumps(admission)}, lambda value: subprocess.Popen(['scp', '-q', 'node1:' + record['remote_path'], str(partial)], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)))
        started = time.monotonic()
        stop_reason = None
        runtime_checks = []
        while process.poll() is None:
            try:
                stdout, stderr = process.communicate(timeout=1)
                break
            except subprocess.TimeoutExpired:
                partial_bytes = partial.stat().st_size if partial.exists() else 0
                check = fresh_gate(root, pep_root, policy, max(0, record['bytes'] - partial_bytes) + receipt_reserve_bytes)
                runtime_checks.append(check)
                if not check['admitted']:
                    stop_reason = 'runtime_E_byte_budget_hold'
                    break
                if time.monotonic() - started > 180:
                    stop_reason = 'owned_SCP_180second_timeout'
                    break
        if stop_reason:
            stdout, stderr = stop_owned_copy(process)
        else:
            stdout, stderr = process.communicate(timeout=15)
        event = {'remote_path': record['remote_path'], 'local_path': str(target), 'partial_path': str(partial), 'expected_bytes': record['bytes'], 'expected_sha256': record['sha256'], 'SCP_PID': process.pid, 'exit_code': process.returncode, 'elapsed_seconds': time.monotonic() - started, 'start_admission': admission, 'runtime_budget_checks': runtime_checks, 'stop_reason': stop_reason}
        event.update(SCP_stdout=stdout, SCP_stderr=stderr)
        if stop_reason or process.returncode != 0:
            event['partial_retained'] = partial.exists()
            event['partial_bytes'] = partial.stat().st_size if partial.exists() else 0
            events.append(event)
            hold = {'reason': stop_reason or 'SCP_nonzero', 'member': record['relative_path']}
            break
        if not partial.exists() or partial.stat().st_size != record['bytes'] or sha(partial) != record['sha256']:
            event['partial_retained'] = partial.exists()
            events.append(event)
            hold = {'reason': 'local_size_or_SHA_mismatch', 'member': record['relative_path']}
            break
        assert not target.exists()
        partial.rename(target)
        event.update(bytes=target.stat().st_size, sha256=sha(target), local_verified=True, post_transfer_admission=fresh_gate(root, pep_root, policy, receipt_reserve_bytes))
        events.append(event)
        if not event['post_transfer_admission']['admitted']:
            hold = {'reason': 'post_transfer_E_budget_hold', 'member': record['relative_path']}
            break
    result = {'schema': 'fourtask.uniair.terminal-local-mirror-receipt.v4', 'at': dt.datetime.now(dt.timezone.utc).isoformat(), 'job_id': manifest['job_id'], 'seed': manifest['seed'], 'candidate': manifest['candidate'], 'manifest_sha256': args.manifest_sha, 'policy_sha256': POLICY_SHA, 'actual_local_root': str(root), 'events': events, 'hold': hold, 'all_selected_terminal_members_mirrored': hold is None, 'remote_all_epoch_originals_preserved': True, 'all_epoch_weight_files_local_claim': False, 'scientific_model_instances': 0, 'new_forward_calls': 0, 'files_deleted': 0}
    payload = json.dumps(result, indent=2) + '\n'
    receipt_gate = fresh_gate(root, pep_root, policy, len(payload.encode('utf-8')))
    try:
        require_admission({'exit_code': 0, 'output': json.dumps(receipt_gate)})
    except AdmissionRejected:
        pointer_dir = C / 'mirror-admission-holds-v6'
        pointer_dir.mkdir(exist_ok=True)
        pointer = pointer_dir / (manifest['job_id'] + '.' + uuid.uuid4().hex + '.json')
        pointer.write_text(json.dumps({'receipt_E_pending': str(args.receipt), 'manifest_sha256': args.manifest_sha, 'reason': 'E receipt write also refused by f064;full detail in administrative stderr', 'no_large_D_transfer': True}) + '\n')
        raise
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(payload, encoding='utf-8')
    if hold is not None:
        raise AdmissionRejected(json.dumps({'receipt': str(args.receipt), 'hold': hold}))
    print(json.dumps({'receipt': str(args.receipt), 'fully_mirrored': hold is None, 'hold': hold, 'verified_members': sum((event.get('already_present_and_verified', False) or event.get('local_verified', False) for event in events))}))
if __name__ == '__main__':
    main()
