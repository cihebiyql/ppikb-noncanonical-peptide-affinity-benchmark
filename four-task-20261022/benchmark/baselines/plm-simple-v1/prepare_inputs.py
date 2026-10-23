"""Freeze raw-input coverage without changing the parent observation or split."""
import collections
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
AA = frozenset('ACDEFGHIKLMNPQRSTVWY')
MAX_RESIDUES = 2048  # Declared compute budget, not an ESM2 API hard maximum.

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def write_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')

def rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def reason(seq):
    if not seq:
        return 'empty'
    if set(seq) - AA:
        return 'non_AA20_raw_symbol'
    if len(seq) > MAX_RESIDUES:
        return 'exceeds_declared_2048_residue_compute_budget'
    return None

def main():
    destination = HERE / 'inputs'
    destination.mkdir(exist_ok=True)
    original_manifest = ROOT / 'data/view_manifest.json'
    manifest = json.loads(original_manifest.read_text(encoding='utf-8'))
    requested = ['ppikb_kd_source_cold_scope_v2', 'ppikb_kd_target_cold_scope_v2',
                 'ppikb_effect_metadata_silver_source_cold']
    lookup = {v['id']:v for v in manifest['views']}
    source = ROOT / 'data/ppikb_kd_source_cold_scope_v2.csv'
    observations = {r['row_id']:r for r in rows(source)}
    sequences, views, reports = {}, [], []
    for view_id in requested:
        view = lookup[view_id]
        path = Path(view['path'])
        assert sha(path) == view['sha256'], view_id
        original = rows(path)
        retained, coverage = [], []
        for original_row in original:
            row = dict(original_row)
            issues = []
            if view['task'] == 'effect':
                ref = observations.get(row['reference_row_id'])
                var = observations.get(row['variant_row_id'])
                if ref is None or var is None:
                    issues.append('parent_observation_missing')
                    fields = {}
                else:
                    fields = {'embedding_peptide_wt':ref['peptide_sequence_raw'],
                              'embedding_peptide_mut':var['peptide_sequence_raw'],
                              'embedding_target':ref['target_sequence']}
                    if ref['target_sequence'] != var['target_sequence']:
                        issues.append('parent_target_sequence_not_identical')
            else:
                fields = {'embedding_peptide':row['peptide_sequence_raw'],
                          'embedding_target':row['target_sequence']}
            for field, sequence in fields.items():
                rejected = reason(sequence)
                if rejected:
                    issues.append(field + ':' + rejected)
            coverage.append({'row_id':row['row_id'], 'split':row['split'],
                             'evaluation_stratum':row['evaluation_stratum'],
                             'covered':not issues, 'reasons':issues})
            if not issues:
                row.update(fields)
                row['chemical_identity_encoded'] = 'false'
                for sequence in fields.values():
                    key = hashlib.sha256(sequence.encode('ascii')).hexdigest()
                    assert key not in sequences or sequences[key] == sequence
                    sequences[key] = sequence
                retained.append(row)
        new_id = view_id + '_esm2_raw20_len2048'
        output = destination / (new_id + '.csv')
        if output.exists():
            raise FileExistsError('Freeze once; preserve existing inputs: ' + str(output))
        with output.open('w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(retained[0]))
            writer.writeheader(); writer.writerows(retained)
        write_json(destination / (new_id + '.coverage.json'), coverage)
        derived = {**view, 'id':new_id, 'parent_view_id':view_id, 'path':str(output),
                   'sha256':sha(output), 'rows':len(retained),
                   'split_counts':dict(collections.Counter(r['split'] for r in retained)),
                   'stratum_counts':dict(collections.Counter(r['evaluation_stratum'] for r in retained)),
                   'parent_input_sha256':sha(path), 'chemical_identity_encoded':False,
                   'coverage_rule':'Exact raw uppercase AA20 sequences; no normalization, projection or truncation. Max2048residues explicit compute budget.',
                   'coverage_path':str(destination / (new_id + '.coverage.json'))}
        comparison = None
        if view['task'] == 'affinity':
            side = 'source' if 'source_cold' in view_id else 'target'
            cohort = ROOT / 'methods/interaction/nc-backbone-ablation' / (view_id + '_native_backbone_ablation.csv')
            cohort_rows = rows(cohort)
            covered_ids = {r['row_id'] for r in retained}
            comparison = {'path':str(cohort), 'sha256':sha(cohort), 'parent_cohort_rows':len(cohort_rows),
                          'overlap_split_counts':dict(collections.Counter(r['split'] for r in cohort_rows if r['row_id'] in covered_ids)),
                          'missing_test_ids':[r['row_id'] for r in cohort_rows if r['split']=='test' and r['row_id'] not in covered_ids]}
        reports.append({'view_id':new_id, 'original_rows':len(original), 'retained_rows':len(retained),
                        'covered_split_counts':derived['split_counts'], 'strata':derived['stratum_counts'],
                        'excluded_reason_counts':dict(collections.Counter(x for r in coverage for x in r['reasons'])),
                        'pepinter6336_id_overlap':comparison})
        views.append(derived)
    sequence_path = destination / 'unique-sequences.jsonl'
    with sequence_path.open('w',encoding='utf-8',newline='\n') as f:
        for key, sequence in sorted(sequences.items()):
            f.write(json.dumps({'sequence_id':key, 'sequence':sequence, 'length':len(sequence)})+'\n')
    write_json(HERE / 'coverage-manifest.json', {'schema':'frozen-esm2.raw-input-coverage.v1',
        'parent_manifest_sha256':sha(original_manifest), 'raw_parent_observation_sha256':sha(source),
        'views':views, 'reports':reports, 'unique_sequence_count':len(sequences),
        'sequence_manifest_path':str(sequence_path), 'sequence_manifest_sha256':sha(sequence_path),
        'normalization':None, 'chemical_identity_encoded':False, 'max_residues_compute_budget':MAX_RESIDUES,
        'model_api_hard_maximum_claimed':False, 'original_views_changed':False})
    print(json.dumps({'reports':reports,'unique_sequences':len(sequences)},ensure_ascii=False,indent=2))

if __name__ == '__main__':
    main()
