"""Exact fixed-spec preflight, executed before any numerical imports."""
import hashlib
import json
from pathlib import Path

WHITELIST_SHA256 = '3168fcd4c0d1d19b3a37c973b292c7b0ba08c5e4eee51ec507b355c0fc59f632'
HERE = Path(__file__).resolve().parent


def validate_spec(path, root):
    path, root = Path(path).resolve(), Path(root).resolve()
    white = HERE / 'whitelist.json'
    if hashlib.sha256(white.read_bytes()).hexdigest() != WHITELIST_SHA256:
        raise ValueError('Fixed 13-candidate whitelist changed')
    registry = json.loads(white.read_text(encoding='utf-8'))
    matches = [e for e in registry['entries'] if (HERE / e['spec_path']).resolve() == path]
    if len(matches) != 1 or hashlib.sha256(path.read_bytes()).hexdigest() != matches[0]['spec_sha256']:
        raise ValueError('Spec is not one of the exact fixed 13 candidates')
    spec = json.loads(path.read_text(encoding='utf-8'))
    if set(spec['paths']) != {'train', 'validation'}:
        raise ValueError('Only TRAIN and VAL may be referenced')
    if spec['max_epochs'] != 100 or spec['patience'] != 5 or len(spec['candidates']) != 1:
        raise ValueError('Unregistered epoch/patience/candidate budget')
    if not spec['fresh_from_seed'] or spec['old_checkpoint_loaded']:
        raise ValueError('This entry only restarts from seed')
    if tuple([spec['method_id'], spec['view_id'], spec['seed'], spec['candidate_index']]) != tuple(matches[0]['key']):
        raise ValueError('Candidate identity changed')
    for split in ('train', 'validation'):
        ref = spec['paths'][split]
        if ref != matches[0][split]:
            raise ValueError('Frozen data reference changed')
        expected = root / 'methods/dta/prepared' / spec['view_id'] / 'formal' / (split + '.jsonl')
        if (root / ref['path']).resolve() != expected.resolve():
            raise ValueError('Unregistered partition path')
        p = root / ref['path']
        if p.is_symlink() or any(a.is_symlink() for a in p.parents if a != root.parent):
            raise ValueError('Linked data paths are forbidden')
    output = root / spec['run_root']
    if output.resolve().parent != (root/'runs/dta_validation_budget_sensitivity_v2').resolve():
        raise ValueError('Output escaped the new independent campaign')
    if output.exists() or any(a.is_symlink() for a in output.parents if a != root.parent):
        raise ValueError('Output exists or has linked ancestry')
    return spec
