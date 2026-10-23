"""Freeze only the already audited five DTA implementations; never execute them."""
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
OLD = HERE.parents[2] / 'peptide-binding-nc-benchmark-20261021'
FOLDERS = ('graphdta-deepnc', 'mgraph-dgdta', 'gs-dta')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    rows = []
    for folder in FOLDERS:
        source = OLD / 'methods' / folder
        for path in sorted(source.rglob('*.py')):
            relative = path.relative_to(source)
            # Preserve author modules and adapters, not historical launch/tests.
            if '__pycache__' in relative.parts:
                continue
            if len(relative.parts) == 1 and path.name not in ('adapter.py', 'author_model.py', 'author_features.py'):
                continue
            if len(relative.parts) > 1 and relative.parts[0] not in ('vendor', 'patched-author', 'original-author'):
                continue
            target = HERE / 'frozen' / folder / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                if digest(target) != digest(path):
                    raise RuntimeError('Frozen source changed: ' + str(target))
            else:
                shutil.copyfile(path, target)
            rows.append({'original_path': str(path), 'path': target.relative_to(HERE).as_posix(),
                         'sha256': digest(target), 'bytes': target.stat().st_size})
    result = {'schema': 'fourtask.dta-source-freeze.v1', 'files': rows,
              'old_project_modified': False, 'old_runs_resumed': False,
              'claim': 'new common-data author-architecture retraining, not original paper main-table reproduction',
              'chirality_encoded': False, 'protein_caps': {'MGraphDTA': 1200, 'others': 1000},
              'known_repairs': ['DeepNC GEN constructor name', 'DGDTA dimensions/LSTM batch_first/GCN dropout'],
              'not_supported': ['native residue contact/site prediction']}
    (HERE / 'source-manifest.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'files': len(rows), 'bytes': sum(x['bytes'] for x in rows)}, ensure_ascii=False))

if __name__ == '__main__':
    main()
