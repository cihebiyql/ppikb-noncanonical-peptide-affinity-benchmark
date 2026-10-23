"""Read actual artifacts into a progress ledger; prepared jobs never count as results."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path, fallback=None):
    p = Path(path)
    return json.loads(p.read_text(encoding='utf-8-sig')) if p.is_file() else fallback

def main():
    manifest = read(ROOT / 'data/view_manifest.json', {'views': []})
    cpu = read(ROOT / 'baselines/DELIVERY-AUDIT.json', {})
    dta = []
    for root in (ROOT / 'runs').glob('dta*'):
        parent = root.name
        if 'diagnostic' in parent:
            continue
        if not root.exists():
            continue
        for p in root.glob('**/complete.json'):
            # Candidate fits are not separately completed scientific seed jobs.
            if p.parent.name.startswith('candidate-'):
                continue
            value = read(p, {})
            if value.get('status') == 'complete' and value.get('new_training') is True:
                dta.append(dict(method=value.get('method_id'), view=value.get('view_id'),
                                stage=value.get('stage'), seed=value.get('seed'),
                                path=str(p.relative_to(ROOT)), source_tree=parent))
    groups = defaultdict(list)
    for r in dta:
        groups[(r['source_tree'], r['method'], r['view'], r['stage'])].append(r['seed'])
    method_groups = [dict(source_tree=k[0], method=k[1], view=k[2], stage=k[3],
                          seeds=sorted(set(v)), count=len(set(v)), all_ten_seeds=set(v) == set(range(10)))
                     for k, v in groups.items()]
    pep = read(ROOT / 'methods/interaction/review/pepinter-source-independent-audit.json', {})
    ledger = dict(schema='fourtask.progress-ledger.v1', at=datetime.now(timezone.utc).isoformat(),
        overall_status='in_progress', full_requested_objective_complete=False,
        data_views=[{k: v.get(k) for k in ('id', 'task', 'endpoint', 'rows', 'split_counts', 'status')}
                    for v in manifest['views']],
        cpu_original_sequence_baselines={k: cpu.get(k) for k in ('passed', 'selected_training_results',
            'candidate_fits', 'external_model_applications', 'selected_prediction_files',
            'metric_cells_independently_verified')},
        dta_observed_complete_seed_jobs=dta, dta_groups=method_groups,
        pepinter_source_cached_component=dict(all_ten_seeds=pep.get('all_ten_seeds_present', False),
            seeds=pep.get('completed_test_seeds', []), coverage='2919 standard-residue cached subset only',
            class_of_evidence='frozen supervised backbone plus new native-head training, conditional exposure'),
        uniair=dict(model_training_completed=False, native_inference_completed=False,
            reason='See methods/uniair/component-alternative-findings.md; never infer training from imported modules.'),
        limits=['This is a local artifact readback; pending remote jobs need synced receipts.',
                'Smoke jobs, CPU chemical subset, full views and conditional components are different scopes.',
                'Native method coverage is not inferred from a traditional baseline completion.',
                'Data-view row counts are not additive independent biological sample counts.'])
    out = ROOT / 'STATUS.json'
    temp = out.with_suffix('.tmp')
    temp.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(out)
    print(json.dumps({'at': ledger['at'], 'views': len(ledger['data_views']),
                      'dta_complete_seed_jobs': len(dta), 'dta_groups': method_groups}, ensure_ascii=False))

if __name__ == '__main__':
    main()
