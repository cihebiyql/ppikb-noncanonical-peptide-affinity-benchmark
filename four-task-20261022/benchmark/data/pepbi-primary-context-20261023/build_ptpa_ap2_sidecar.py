"""Primary-cell/sequence audit; never edits candidates, labels or predictions."""
from pathlib import Path
import csv
import hashlib
import json
import math
import re
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CANDIDATE = ROOT / 'data/pepbi-external-audit-20261023/conditional-sequence-external-candidates.csv'
RAW = ROOT / 'data/pepbi-external-audit-20261023/all329-row-audit.json'
PTPA_DOI = '10.1515/hsz-2014-0106'
AP2_DOI = '10.1038/sj.emboj.7600445'

# Transcribed from primary Figure1B (PTPA, printedp882) and Figure5 (AP2,p4377).
# Original PDFs and rendered source pages are retained, with no OCR used as gold.
PTPA_UM = {'PDYFL': 68.2, 'TPDYFL': 49.5, 'RTPDYFL': 40.6, 'TRRTPDYFL': 52.9}
AP2_UM = {
    ('Amph-P2', 'F740D'): 2.5, ('Amph-P2', 'W840A'): 79., ('Amph-P2', 'V800D'): 1.9,
    ('Eps15-P1', 'F740D'): 85., ('Eps15-P1', 'G742D'): 82., ('Eps15-P1', 'W840A'): 43.,
    ('Eps15-P2', 'F740D'): 107., ('Eps15-P2', 'G725E, G742D'): 132.,
    ('Syj-P3', 'W840A'): .4, ('Syj-P3', 'V800D'): .8,
    ('Syj-P4', 'F740D'): 123., ('Syj-P4', 'G725E, G742D'): 171.,
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        return list(csv.DictReader(handle))


def save(name, obj):
    (HERE / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    assert sha(CANDIDATE) == '35573d98d14b4ae65575ba9557a1508ea145c30a47a2855f7ef0bfdd625bdef4'
    candidates = read_csv(CANDIDATE)
    original = json.loads(RAW.read_text(encoding='utf-8'))
    by_id = {row['row_id']: row for row in original}
    ap2 = [row for row in original if row['Binding Group'] == 'α-adaptin - Motif Peptide']
    wt_set = {row['Protein Sequence'] for row in ap2 if row['Protein Mutation(s)'] == 'X'}
    assert len(wt_set) == 1
    wt = next(iter(wt_set))
    assert len(wt) == 238
    # Infer a consistent reporting-number offset only from simple, actual single changes.
    offsets = set()
    for row in ap2:
        mutation = re.fullmatch(r'([A-Z])(\d+)([A-Z])', row['Protein Mutation(s)'])
        diff = [(i + 1, a, b) for i, (a, b) in enumerate(zip(wt, row['Protein Sequence'])) if a != b]
        if mutation and len(diff) == 1 and diff[0][1:] == (mutation[1], mutation[3]):
            offsets.add(int(mutation[2]) - diff[0][0])
    assert offsets == {700}
    result = []
    for candidate in candidates:
        doi = candidate['study_id']
        if doi not in {PTPA_DOI, AP2_DOI}:
            continue
        raw_ids = json.loads(candidate['raw_source_row_ids'])
        records = [by_id[row_id] for row_id in raw_ids]
        source = records[0]
        assert all(row['Protein Sequence'] == candidate['target_sequence'] and
                   row['Peptide Sequence'] == candidate['peptide_sequence'] for row in records)
        recorded = float(candidate['original_Kd_M']) * 1e6
        row = dict(row_id=candidate['row_id'], raw_rows=raw_ids, source_DOI=doi,
                   binding_group=candidate['binding_group'], peptide_sequence=candidate['peptide_sequence'],
                   recorded_Kd_uM=recorded, recorded_temperature_K=float(candidate['temperature_K']),
                   original_labels_unchanged=True, numeric_exact_primary_verified=False,
                   numeric_compatible_with_primary_summary=False,
                   peptide_termini_primary_verified=False, full_assay_construct_identity_certified=False,
                   source_cell_conflict_or_unresolved=False, target_sequence_additional_mutations=[],
                   new_fit=0, new_model_forward=0)
        if doi == PTPA_DOI:
            value = PTPA_UM[candidate['peptide_sequence']]
            row.update(primary_location='Figure1B,printedpage882;ITCmethodsprintedpage887',
                       primary_Kd_uM=value, primary_value_kind='point_mean',
                       numeric_exact_primary_verified=math.isclose(recorded, value, rel_tol=1e-12, abs_tol=1e-12),
                       numeric_compatible_with_primary_summary=True,
                       primary_temperature_K=293.15, assay_buffer_primary_verified=True,
                       peptide_termini_primary_verified=True, primary_peptide_chemistry='NH2-peptide-COOH;unmodified',
                       primary_assay_construct='tag-cleaved full-length humanPTPA1-323',
                       target_sequence_pattern_matches_reported_mutations=True,
                       remaining_scope='Exact post-cleavage scar and complete assay-construct chemical identity not fully reconstructed')
            assert len(candidate['target_sequence']) == 323
            assert row['numeric_exact_primary_verified']
        else:
            mutation = source['Protein Mutation(s)']
            name = source['Peptide Name']
            diff = [(i + 1, a, b) for i, (a, b) in enumerate(zip(wt, candidate['target_sequence'])) if a != b]
            actual = {f'{a}{i + 700}{b}' for i, a, b in diff}
            declared = set(re.findall(r'[A-Z]\d+[A-Z]', mutation))
            assert len(candidate['target_sequence']) == len(wt)
            row.update(primary_location='Figure5,printedpage4377', primary_peptide_name=name,
                       primary_reported_variant=mutation, primary_temperature_K=283.15,
                       assay_buffer_primary_verified=False,
                       input_relative_to_unique_workbook_WT_changes=[f'{a}{i}{b}' for i, a, b in diff],
                       reporting_number_offset_inferred=700,
                       full_assay_construct_identity_certified=False,
                       target_sequence_pattern_matches_reported_mutations=(actual == declared),
                       target_sequence_additional_mutations=sorted(actual - declared),
                       remaining_scope='Originalsupplementarymethods/Table3 notobtained;termini/tag/completeconstruct unverified')
            assert declared.issubset(actual)
            key = (name, mutation)
            if key in AP2_UM:
                value = AP2_UM[key]
                exact = math.isclose(recorded, value, rel_tol=1e-12, abs_tol=1e-12)
                rounded = key in {('Syj-P3', 'W840A'), ('Syj-P3', 'V800D')} and abs(recorded - value) <= .05
                row.update(primary_Kd_uM=value, primary_value_kind='rounded_point_summary' if rounded and not exact else 'point',
                           numeric_exact_primary_verified=exact,
                           numeric_compatible_with_primary_summary=(exact or rounded))
                assert exact or rounded
            elif key == ('Syj-P3', 'F740D'):
                row.update(primary_Kd_uM=None, primary_value_kind='lower_bound', primary_lower_bound_uM=160.,
                           source_cell_conflict_or_unresolved=True,
                           issue='PrimaryFigure5reports>160uM;record167uMexactprecisionnotverifiedwithoutTableS3')
            elif key == ('Eps15-P2', 'V800D'):
                row.update(primary_Kd_uM=None, primary_value_kind='cell_empty',
                           source_cell_conflict_or_unresolved=True,
                           issue='PrimaryFigure5Eps15P2/V800Dcellisempty;135uMisprintedforEps15P1/V800D;donotassigncorrectionwithoutSI')
            else:
                raise AssertionError(key)
        assert row['recorded_temperature_K'] == row['primary_temperature_K']
        row['source_cell_and_reported_variant_pattern_supported'] = bool(
            row['numeric_compatible_with_primary_summary'] and row['target_sequence_pattern_matches_reported_mutations'])
        result.append(row)
    assert len(result) == 18
    save('ptpa-ap2-primary-sidecar.json', result)
    fields = list(dict.fromkeys(key for row in result for key in row))
    with (HERE / 'ptpa-ap2-primary-sidecar.csv').open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({key: json.dumps(value, ensure_ascii=False) if isinstance(value, list) else value
                         for key, value in row.items()} for row in result)
    panels = []
    for view in ['ppikb_kd_source_cold_scope_v2', 'ppikb_kd_target_cold_scope_v2']:
        path = ROOT / f'data/{view}.csv'
        train = [row for row in read_csv(path) if row['split'] == 'train']
        exact = {(row['peptide_sequence'], row['target_sequence']) for row in train}
        dois = {row.get('study_id', '').lower().removeprefix('https://doi.org/') for row in train}
        pair_overlap = [row['row_id'] for row in candidates if row['study_id'] in {PTPA_DOI, AP2_DOI}
                        and (row['peptide_sequence'], row['target_sequence']) in exact]
        doi_overlap = sorted({row['source_DOI'] for row in result if row['source_DOI'].lower() in dois})
        assert not pair_overlap and not doi_overlap
        panels.append(dict(view_id=view, source_sha256=sha(path), training_rows=len(train),
                           candidate_rows_checked=18, exact_pair_overlap=pair_overlap, source_DOI_overlap=doi_overlap))
    summary = dict(at=datetime.now(timezone.utc).isoformat(), candidates_checked=18,
                   PTPA=4, AP2=14, numeric_exact_primary_verified=sum(r['numeric_exact_primary_verified'] for r in result),
                   numeric_compatible_with_primary_summary=sum(r['numeric_compatible_with_primary_summary'] for r in result),
                   source_cell_unresolved=sum(r['source_cell_conflict_or_unresolved'] for r in result),
                   target_sequence_additional_mutation_rows=sum(bool(r['target_sequence_additional_mutations']) for r in result),
                   source_cell_and_reported_variant_pattern_supported=sum(r['source_cell_and_reported_variant_pattern_supported'] for r in result),
                   full_assay_construct_identity_certified_rows=0,
                   candidate_sha256_unchanged=sha(CANDIDATE), training_source_independence=panels,
                   manual_models_have_no_pretrained_encoder=True,
                   new_fit=0, new_model_forward=0, original_data_or_predictions_changed=False,
                   evidence=[dict(path=str(path.relative_to(HERE)), sha256=sha(path)) for path in
                             [HERE/'raw/PTPA.pdf', HERE/'raw/AP2.pdf', HERE/'page-evidence/PTPA-page2.png',
                              HERE/'page-evidence/AP2-page7.png']])
    assert summary['numeric_exact_primary_verified'] == 14
    assert summary['numeric_compatible_with_primary_summary'] == 16
    assert summary['source_cell_unresolved'] == 2
    assert summary['target_sequence_additional_mutation_rows'] == 3
    assert summary['source_cell_and_reported_variant_pattern_supported'] == 13
    save('ptpa-ap2-summary.json', summary)
    print(json.dumps({key: value for key, value in summary.items() if key not in {'evidence', 'training_source_independence'}}))


if __name__ == '__main__':
    main()
