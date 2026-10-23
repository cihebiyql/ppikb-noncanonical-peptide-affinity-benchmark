"""Prepare immutable common-data five-author-method jobs; no model imports."""
import argparse
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
METHODS = ('GraphDTA-GIN', 'MGraphDTA', 'DGDTA-CL', 'DeepNC-GEN', 'GS-DTA')
REMOTE = '/data/qlyu/projects/peptide-four-task-benchmark-20261022'
PYTHON = '/data/qlyu/projects/peptide-binding-benchmark-20261020/common-prior-methods-20261021/.venv/bin/python'

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            h.update(block)
    return h.hexdigest()

def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2)
    if path.exists() and path.read_text(encoding='utf-8') != text:
        raise FileExistsError('Immutable file already differs: ' + str(path))
    path.write_text(text, encoding='utf-8')

def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = ''.join(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n' for row in rows)
    if path.exists() and path.read_text(encoding='utf-8') != data:
        raise FileExistsError(path)
    path.write_text(data, encoding='utf-8')

def normalize(row, task):
    out = dict(row)
    out['record_id'] = str(row.get('row_id') or row.get('record_id') or '')
    if not out['record_id']:
        raise ValueError('Row identity required')
    out['label'] = float(row['label'])
    if task == 'effect':
        wt = row.get('smiles_wt') or row.get('parent_smiles') or row.get('wt_smiles')
        mt = row.get('smiles_mut') or row.get('mutant_smiles') or row.get('mut_smiles')
        if not wt or not mt:
            raise ValueError('Effect row missing both chemical identities')
        out['smiles_wt'], out['smiles_mut'] = wt, mt
    else:
        s = row.get('peptide_smiles') or row.get('canonical_isomeric_smiles') or row.get('smiles')
        if not s:
            raise ValueError('Missing chemical SMILES; do not fabricate from peptide sequence')
        out['peptide_smiles'] = s
    if not row.get('target_sequence'):
        raise ValueError('Missing target sequence')
    if task == 'classification' and out['label'] not in (0, 1):
        raise ValueError('Classification needs explicit binary labels')
    return out

def partition(rows):
    groups = {'train': [], 'validation': [], 'test': []}
    seen = set()
    for row in rows:
        name = {'val': 'validation', 'valid': 'validation'}.get(row['split'], row['split'])
        if name not in groups:
            continue
        if row['record_id'] in seen:
            raise ValueError('Duplicate row id across partitions')
        seen.add(row['record_id'])
        groups[name].append(row)
    if any(not x for x in groups.values()):
        raise ValueError('Three nonempty partitions required')
    return groups

def prepare(view, stage):
    path = Path(view['path'])
    if sha(path) != view['sha256']:
        raise ValueError('Source view hash mismatch')
    task = {'affinity': 'regression', 'binding': 'classification'}.get(view['task'], view['task'])
    if task not in ('regression', 'classification', 'effect'):
        raise ValueError('Native five DTA methods have no residue-site output')
    with path.open(encoding='utf-8-sig', newline='') as stream:
        groups = partition([normalize(row, task) for row in csv.DictReader(stream)])
    if stage == 'smoke':
        for name, limit in [('train', 64), ('validation', 32), ('test', 32)]:
            groups[name] = sorted(groups[name], key=lambda r: r['record_id'])[:limit]
    folder = HERE / 'prepared' / view['id'] / stage
    paths = {}
    for name, rows in groups.items():
        file = folder / (name + '.jsonl')
        write_rows(file, rows)
        paths[name] = {'path': file.relative_to(ROOT).as_posix(), 'sha256': sha(file), 'n': len(rows)}
    source = HERE / 'source-manifest.json'
    source_spec = {'path': source.relative_to(ROOT).as_posix(), 'sha256': sha(source)}
    prepared = []
    for method in METHODS:
        for seed in ([0] if stage == 'smoke' else range(10)):
            job_id = f'{view["id"]}--{method}--{stage}--seed{seed}'
            run = f'runs/dta/{view["id"]}/{method}/{stage}/seed-{seed}'
            spec = {'schema': 'fourtask.dta-spec.v1', 'job_id': job_id, 'stage': stage,
                    'method_id': method, 'view_id': view['id'], 'task': task,
                    'endpoint': view.get('endpoint'), 'seed': seed, 'paths': paths,
                    'source_manifest': source_spec,
                    'input_view': {'path': path.relative_to(ROOT).as_posix(), 'sha256': view['sha256']},
                    'run_root': run, 'batch_size': 16, 'cpu_threads': 1,
                    'gpu_allocator_budget_bytes': 2*1024**3, 'timeout_seconds': 3600,
                    'max_epochs': 1 if stage == 'smoke' else 20,
                    'patience': 1 if stage == 'smoke' else 5,
                    'candidates': [{'learning_rate': 1e-3}, {'learning_rate': 3e-4}],
                    'native_architecture': True,
                    'reproduction_type': 'author_architecture_common_data_retraining' if task == 'regression'
                    else ('potential_difference_effect_loss_adaptation' if task == 'effect' else 'binary_loss_adaptation'),
                    'test_used_for_selection': False, 'holdout_reuse': 'score_only_after_selection_frozen',
                    'known_limitation': 'atom chirality omitted; author protein prefixes retained',
                    'smoke_subset_only': stage == 'smoke'}
            spec_path = HERE / 'specs' / (job_id + '.json')
            dump(spec_path, spec)
            relative = spec_path.relative_to(ROOT).as_posix()
            prepared.append({'job_id': job_id, 'stage': stage, 'method_id': method,
                             'view_id': view['id'], 'task': task, 'seed': seed,
                             'spec': relative, 'spec_sha256': sha(spec_path),
                             'argv': [PYTHON, 'methods/dta/train.py', '--spec', relative],
                             'working_directory': REMOTE, 'output_root': run,
                             'timeout_seconds': 3600, 'cpu_threads': 1,
                             'memory_limit_bytes': 6*1024**3, 'gpu_memory_budget_bytes': 2*1024**3,
                             'source_manifest': source_spec['path'], 'source_manifest_sha256': source_spec['sha256'],
                             'status': 'prepared_requires_standard_contract_and_live_resource_gate',
                             'statistical_unit': 'measurement' if task != 'effect' else 'comparable_effect_pair',
                             'sample_counts': {k: len(v) for k, v in groups.items()},
                             'metric': 'log_loss' if task == 'classification' else 'MAE',
                             'endpoint': view.get('endpoint')})
    return prepared

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--view', action='append', required=True)
    parser.add_argument('--stage', choices=('smoke', 'formal'), required=True)
    args = parser.parse_args()
    manifest = json.loads((ROOT / 'data' / 'view_manifest.json').read_text(encoding='utf-8-sig'))
    views = {row['id']: row for row in manifest['views']}
    target = HERE / 'jobs.json'
    old = json.loads(target.read_text(encoding='utf-8')) if target.exists() else {'schema': 'fourtask.dta-jobs.v1', 'jobs': []}
    by_id = {job['job_id']: job for job in old['jobs']}
    for name in args.view:
        for job in prepare(views[name], args.stage):
            if job['job_id'] in by_id and by_id[job['job_id']] != job:
                raise ValueError('Existing immutable job differs')
            by_id[job['job_id']] = job
    old['jobs'] = sorted(by_id.values(), key=lambda j: (j['stage'] != 'smoke', j['job_id']))
    # Index can append jobs; each spec/input remains immutable and individually hashed.
    target.write_text(json.dumps(old, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'jobs': len(old['jobs']), 'index_sha256': sha(target)}))

if __name__ == '__main__':
    main()
