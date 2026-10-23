"""Combine independent metadata axes for all27 already evaluated candidates."""
from pathlib import Path
from datetime import datetime, timezone
import csv
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CANDIDATE = ROOT / 'data/pepbi-external-audit-20261023/conditional-sequence-external-candidates.csv'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def main():
    with CANDIDATE.open(encoding='utf-8-sig', newline='') as handle:
        candidates = list(csv.DictReader(handle))
    assert sha(CANDIDATE) == '35573d98d14b4ae65575ba9557a1508ea145c30a47a2855f7ef0bfdd625bdef4'
    first = {r['row_id']: r for r in load(HERE / 'ptpa-ap2-primary-sidecar.json')}
    second = {r['row_id']: r for r in load(HERE / 'stac-profilin/primary-context-sidecar.json')}
    assert not set(first).intersection(second)
    assert set(first).union(second) == {r['row_id'] for r in candidates}
    rows = []
    for source in candidates:
        rid = source['row_id']
        record = first.get(rid) or second[rid]
        exact = record.get('numeric_exact_primary_verified', record.get('exact_primary_Kd_verified', False))
        compatible = record.get('numeric_compatible_with_primary_summary', exact)
        rows.append(dict(row_id=rid, study_id=source['study_id'], binding_group=source['binding_group'],
            primary_numeric_status='exact_published_point' if exact else 'compatible_with_rounded_summary' if compatible else 'unverified_or_source_cell_unresolved',
            primary_temperature_verified=record.get('primary_temperature_K') == float(source['temperature_K'])
                if rid in first else record.get('temperature_verified', False),
            peptide_termini_primary_verified=record.get('peptide_termini_primary_verified', False),
            assay_buffer_primary_verified=record.get('assay_buffer_primary_verified', False)
                if rid in first else bool(record.get('primary_buffer_summary')),
            extra_target_mutations_vs_reported_variant=record.get('target_sequence_additional_mutations', []),
            full_assay_construct_and_chemical_identity_certified=False,
            scope='supervised-source-disjoint conditional validation relative to100 manual models',
            manual_models_have_no_pretrained_encoder=True,
            detail_file='ptpa-ap2-primary-sidecar.json' if rid in first else 'stac-profilin/primary-context-sidecar.json',
            original_candidate_labels_changed=False))
    numeric = {key: sum(r['primary_numeric_status'] == key for r in rows) for key in
               ['exact_published_point', 'compatible_with_rounded_summary', 'unverified_or_source_cell_unresolved']}
    assert numeric == {'exact_published_point': 19, 'compatible_with_rounded_summary': 2,
                       'unverified_or_source_cell_unresolved': 6}
    assert sum(r['primary_temperature_verified'] for r in rows) == 23
    assert sum(r['peptide_termini_primary_verified'] for r in rows) == 4
    assert sum(r['assay_buffer_primary_verified'] for r in rows) == 9
    summary = dict(schema='pepbi.primary-context-multiaxis-index.v1',
        at=datetime.now(timezone.utc).isoformat(), candidates=27, primary_numeric_status_counts=numeric,
        temperature_verified_rows=23, peptide_termini_verified_rows=4, assay_buffer_verified_rows=9,
        additional_AP2_target_mutation_rows=3, STAC2_PDB_vs_assay_prefix_unresolved_rows=3,
        manual_100_models_supervised_source_disjoint_rows=27,
        manual_models_have_no_foundation_pretraining_exposure_source=True,
        complete_assay_chemical_identity_certified_rows=0, original_all27_view_modified=False,
        performance_used_for_qualification=False, new_fit=0, new_forward=0,
        input_files=[dict(path=str(p), sha256=sha(p)) for p in [CANDIDATE,
            HERE/'ptpa-ap2-primary-sidecar.json', HERE/'ptpa-ap2-summary.json',
            HERE/'stac-profilin/primary-context-sidecar.json', HERE/'stac-profilin/manual-source-independence.json']],
        rows=rows)
    (HERE / 'primary-context-index.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    with (HERE / 'primary-context-index.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({k: json.dumps(v) if isinstance(v, list) else v for k, v in row.items()} for row in rows)
    print(json.dumps({k: v for k, v in summary.items() if k not in {'input_files', 'rows'}}))


if __name__ == '__main__':
    main()
