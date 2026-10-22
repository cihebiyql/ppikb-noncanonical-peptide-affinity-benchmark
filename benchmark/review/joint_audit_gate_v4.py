"""Outer joint-NN200/RF40 gate for unchanged NN/reference audit scripts.

Preparing this code authorizes no execution. This module reads selection metadata
only after explicit root authorization; it never reads weights or gold itself.
"""
import argparse
import hashlib
import itertools
import json
import subprocess
import sys
import time
from pathlib import Path

METHODS = ('GraphDTA-GIN', 'MGraphDTA', 'DGDTA-CL', 'DeepNC-GEN', 'GS-DTA')
PANELS = ('source_peptide_dependency_cold', 'target_reference_homology_cold')
REGIMES = ('NC_only', 'standard_only')
INDEX_SHA = 'c7b3bde68c9a741c0ac3f255a825e4a55dd7234e2b4e6d48f212fee8d5609ab1'
TARGETS = {'nn': 'recompute_metrics.py', 'references': 'deterministic_references.py'}


def local(path):
    value = str(path).replace('\\', '/')
    if sys.platform != 'win32' and len(value) > 2 and value[1:3] == ':/':
        value = '/mnt/' + value[0].lower() + '/' + value[3:]
    return Path(value)


def read(path):
    return json.loads(local(path).read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(local(path).read_bytes()).hexdigest()


def require(path, digest):
    if sha(path) != digest:
        raise ValueError('SHA mismatch: ' + str(path))


def require_joint(authorization_path, joint_path, mode):
    """No real selection metadata reads before root auth + joint-file digest."""
    auth = read(authorization_path)
    if auth.get('root_joint_real_audit_authorized') is not True:
        raise PermissionError('Await explicit root authorization after joint NN200/RF40 barrier')
    if mode not in auth.get('allowed_modes', []):
        raise PermissionError('Audit/reference mode not authorized')
    if time.time() >= auth.get('deadline_unix', 0):
        raise TimeoutError('Root absolute deadline reached')
    require(__file__, auth['outer_gate_sha256'])
    target = Path(__file__).parent / TARGETS[mode]
    require(target, auth['allowed_target_sha256'][mode])
    require(joint_path, auth['joint_barrier_sha256'])
    joint = read(joint_path)
    if (joint.get('status'), joint.get('NN_selections'), joint.get('RF_selections')) != ('all_200_NN_plus_40_RF_frozen', 200, 40):
        raise ValueError('Joint barrier incomplete')
    if joint.get('NN_execution_index_sha256') != INDEX_SHA:
        raise ValueError('Unapproved NN recovery identity')
    require(joint['NN_execution_index_path'], INDEX_SHA)
    index = read(joint['NN_execution_index_path'])
    require(joint['NN_barrier_path'], joint['NN_barrier_sha256'])
    require(joint['RF_barrier_path'], joint['RF_barrier_sha256'])
    nn, rf = read(joint['NN_barrier_path']), read(joint['RF_barrier_path'])
    if (nn.get('status'), nn.get('selection_count'), nn.get('candidate_fit_count')) != ('all_selections_frozen', 200, 400):
        raise ValueError('Original hard NN200 gate missing')
    if (rf.get('status'), rf.get('selection_count'), rf.get('candidate_fit_count')) != ('all_40_RF_selections_frozen', 40, 80):
        raise ValueError('RF40 gate missing')
    if nn.get('execution_index_sha256') != INDEX_SHA:
        raise ValueError('NN barrier uses different execution index')
    if len(nn.get('selections', [])) != 200 or len(rf.get('selections', [])) != 40:
        raise ValueError('Barrier entry count mismatch')
    approved = {str(local(e['selection_path']).resolve()) for e in index['per_seed_selections']}
    seen = set()
    for entry in nn['selections']:
        if str(local(entry['path']).resolve()) not in approved:
            raise ValueError('NN selection path not approved')
        require(entry['path'], entry['sha256'])
        selected = read(entry['path'])
        identity = tuple(selected[k] for k in ('method_id', 'split_id', 'regime', 'seed'))
        if identity in seen or selected.get('status') != 'frozen' or selected.get('holdout_metrics_consulted') is not False:
            raise ValueError('Invalid NN selection metadata')
        seen.add(identity)
    if seen != set(itertools.product(METHODS, PANELS, REGIMES, range(10))):
        raise ValueError('NN200 coordinate grid incomplete')
    seen = set()
    rf_entries = rf['selections']
    if joint.get('RF_selection_entries') != rf_entries:
        raise ValueError('Joint RF entries differ from frozen RF barrier')
    for entry in rf_entries:
        require(entry['selection_path'], entry['selection_sha256'])
        selected = read(entry['selection_path'])
        identity = tuple(selected[k] for k in ('panel', 'regime', 'seed'))
        if identity in seen or selected.get('status') != 'frozen' or selected.get('validation_only') is not True or selected.get('gold_reads') != 0:
            raise ValueError('Invalid RF selection metadata')
        if identity != tuple(entry[k] for k in ('panel', 'regime', 'seed')):
            raise ValueError('RF identity mismatch')
        seen.add(identity)
    if seen != set(itertools.product(PANELS, REGIMES, range(10))):
        raise ValueError('RF40 coordinate grid incomplete')
    return joint, target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root-authorization', required=True)
    parser.add_argument('--joint-barrier', required=True)
    parser.add_argument('--mode', choices=TARGETS, required=True)
    parser.add_argument('target_arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    joint, target = require_joint(args.root_authorization, args.joint_barrier, args.mode)
    extra = args.target_arguments
    if extra[:1] == ['--']:
        extra = extra[1:]
    # The unchanged child retains its original completeNN200 check as well.
    for name, expected in (('--selection-barrier', joint['NN_barrier_path']), ('--barrier-sha256', joint['NN_barrier_sha256'])):
        if extra.count(name) != 1 or extra[extra.index(name) + 1] != str(expected):
            raise ValueError('Child must use the same frozen NN barrier: ' + name)
    if '--audit-authorized-after-freeze' not in extra:
        raise ValueError('Child explicit post-freeze gate must remain present')
    subprocess.run([sys.executable, str(target), *extra], check=True)


if __name__ == '__main__':
    main()
