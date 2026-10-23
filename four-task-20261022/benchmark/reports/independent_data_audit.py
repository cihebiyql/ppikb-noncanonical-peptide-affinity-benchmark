"""Independent standard-library readback of frozen scientific views, no fitting."""
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()

def main():
    m = json.loads((ROOT / 'data/view_manifest.json').read_text(encoding='utf-8-sig'))
    reports, errors = [], []
    for view in m['views']:
        path = Path(view['path'])
        rows = list(csv.DictReader(path.open(encoding='utf-8-sig', newline='')))
        count = Counter(r['split'] for r in rows)
        ids = [r['row_id'] for r in rows]
        groups, seq_inputs = defaultdict(set), defaultdict(set)
        for r in rows:
            groups[r['group_id']].add(r['split'])
            effective = [r.get('peptide_sequence', ''), r.get('target_sequence', '')]
            if view['task'] == 'contact':
                effective.append(r.get('residue_index', ''))
            if view['task'] == 'effect':
                effective += [r.get(k, '') for k in ('peptide_wt_sequence', 'peptide_mut_sequence',
                                                     'target_wt_sequence', 'target_mut_sequence')]
            key = hashlib.sha256(json.dumps(effective).encode()).hexdigest()
            seq_inputs[key].add(r['split'])
        bad_groups = sum(len(s) > 1 for s in groups.values())
        collisions = sum(len(s) > 1 for s in seq_inputs.values())
        finite = sum(math.isfinite(float(r['label'])) for r in rows)
        checks = dict(hash_matches=digest(path) == view['sha256'], row_count_matches=len(rows) == view['rows'],
                      split_counts_match=dict(count) == view['split_counts'], unique_row_ids=len(set(ids)) == len(ids),
                      finite_labels=finite == len(rows), group_leakage_absent=bad_groups == 0)
        for name, passed in checks.items():
            if not passed:
                errors.append({'view': view['id'], 'check': name})
        reports.append(dict(view_id=view['id'], task=view['task'], endpoint=view.get('endpoint'),
            rows=len(rows), partition_counts=dict(count), checks=checks, cross_split_groups=bad_groups,
            sequence_only_effective_input_cross_split_collisions=collisions,
            interpretation='Sequence-only identity is a per-model diagnostic; it does not alter frozen chemistry-based split after fitting.'))
    output = dict(schema='fourtask.independent-data-readback.v1', at=datetime.now(timezone.utc).isoformat(),
                  view_count=len(reports), reports=reports, errors=errors,
                  checks_pass=not errors,
                  limitation='No new certification of chemistry/construct/assay provenance; hash/readback and dependency checks only.')
    (ROOT / 'reports/independent-data-readback.json').write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'view_count': len(reports), 'errors': errors, 'sequence_collision_views': [
        [r['view_id'], r['sequence_only_effective_input_cross_split_collisions']] for r in reports
        if r['sequence_only_effective_input_cross_split_collisions']]}))
    if errors:
        raise SystemExit(2)

if __name__ == '__main__':
    main()
