"""Read-only E-volume quota guard for future complete PepInter checkpoint mirroring.
Does not transfer, remove or rewrite any model. Keeps UniAIR's2GiB reservation.
"""
import argparse, ctypes, json, os, shutil
from pathlib import Path
from common import now, save, sha
GIB = 1024 ** 3

def check_quota(free, own, other, new, pending=0, own_cap=195 * GIB, other_cap=2 * GIB, reserve=50 * GIB):
    if min(free, own, other, new, pending) < 0:
        raise ValueError('Negative byte accounting')
    unused_other = max(0, other_cap - other)
    future_free = free - new - pending
    future_own = own + new + pending
    reasons = []
    if own > own_cap or future_own > own_cap:
        reasons.append('PepInter_actual_plus_pending_exceeds195GiB')
    if other > other_cap:
        reasons.append('UniAIR_actual_tree_exceeds_registered2GiB_hold_for_owner_review')
    if future_free < reserve + unused_other:
        reasons.append('Freshfree_after_all_own_pending_and_new_bytes_must_cover50GiB_plus_unused_UniAIR_quota')
    return {'allowed': not reasons, 'reasons': reasons, 'actual_free_bytes': free, 'actual_PepInter_bytes_including_partials': own, 'actual_UniAIR_bytes_including_partials': other, 'new_payload_bytes': new, 'other_own_pending_bytes_not_yet_written': pending, 'unused_UniAIR_reservation_bytes': unused_other, 'projected_PepInter_bytes': future_own, 'projected_actual_free_bytes': future_free, 'required_projected_free_bytes': reserve + unused_other, 'PepInter_cap_bytes': own_cap, 'UniAIR_cap_bytes': other_cap, 'minimum_volume_reserve_bytes': reserve}

def tree_bytes(root):
    root = Path(root)
    total = 0
    if not root.exists():
        return 0
    if root.is_symlink() or getattr(root.lstat(), 'st_file_attributes', 0) & 1024:
        raise ValueError('No root junction/symlink')
    for parent, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            p = Path(parent) / name
            s = p.lstat()
            if p.is_symlink() or getattr(s, 'st_file_attributes', 0) & 1024:
                raise ValueError('No symlink/junction/reparsepoint in scientific local asset tree')
            if p.is_file():
                total += s.st_size
    return total

def assert_local_fixed_NTFS(root):
    if os.name != 'nt':
        raise RuntimeError('This guard measures the actual local Windows E volume; no remote/network equivalence')
    path = Path(root).absolute()
    if path.drive.upper() != 'E:':
        raise ValueError('Explicit approved E localroot required')
    for p in [path] + list(path.parents):
        if p.exists() and (p.is_symlink() or getattr(p.lstat(), 'st_file_attributes', 0) & 1024):
            raise ValueError('No junction/symlink root redirection')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetDriveTypeW.argtypes = [ctypes.c_wchar_p]
    kernel.GetDriveTypeW.restype = ctypes.c_uint
    if kernel.GetDriveTypeW(path.anchor) != 3:
        raise ValueError('E must be a real fixedlocal drive')
    fs = ctypes.create_unicode_buffer(64)
    get = kernel.GetVolumeInformationW
    get.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint]
    get.restype = ctypes.c_int
    if not get(path.anchor, None, 0, None, None, None, fs, 64):
        raise ctypes.WinError(ctypes.get_last_error())
    if fs.value != 'NTFS':
        raise ValueError('Approved localNTFS volume required')
    return {'drive': 'E:', 'drive_type': 3, 'filesystem': fs.value, 'links_or_junctions': False}
if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--new-payload-bytes', type=int, required=True)
    p.add_argument('--own-other-pending-bytes', type=int, default=0)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    R = Path(__file__).resolve().parents[2]
    own_policy = R / 'resources/local-storage-policy-v1.json'
    other_policy = R / 'resources/uniair-local-storage-policy-v1.json'
    own_root = Path('<APPROVED_ARTIFACT_ROOT>/peptide-four-task-benchmark-20261022/pepinter-full-native')
    other = json.loads(other_policy.read_text())
    other_root = Path(other['new_asset_root'])
    assert other['own_budget_bytes'] == 2 * GIB and other['protected_PepInter_budget_bytes'] == 195 * GIB and (other['minimum_volume_free_reserve_bytes'] == 50 * GIB)
    if other_root != Path('<APPROVED_ARTIFACT_ROOT>/peptide-four-task-benchmark-20261022/uniair-mofpe-candidates-v1'):
        raise ValueError('Unexpected sharedquota assetroot revision needsreview')
    volume = assert_local_fixed_NTFS(own_root)
    value = check_quota(shutil.disk_usage(own_root).free, tree_bytes(own_root), tree_bytes(other_root), a.new_payload_bytes, a.own_other_pending_bytes)
    value.update(checked_at=now(), read_only_no_model_transfer=True, volume=volume, own_asset_root=str(own_root), other_asset_root=str(other_root), own_policy_sha256=sha(own_policy), UniAIR_policy_sha256=sha(other_policy), no_old_D_asset_moved=True, requires_copycontroller_exclusive_lock_and_pending_ledger_for_atomic_admission=True)
    out = Path(a.output)
    assert not out.exists()
    save(out, value)
    print(json.dumps(value))
    if not value['allowed']:
        raise SystemExit(3)
