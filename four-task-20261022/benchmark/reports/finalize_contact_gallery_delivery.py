"""Finalize only a gallery whose independent numerical/visual audit passed."""
from pathlib import Path
import hashlib
import json
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent / 'contact-site-gallery-v3'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    receipt = json.loads((HERE / 'gallery-receipt.json').read_text(encoding='utf-8'))
    audit = json.loads((HERE / 'independent-audit.json').read_text(encoding='utf-8'))
    assert audit['overall_passed'] is True and not audit['errors']
    assert all(check['passed'] for check in audit['checks'])
    assert audit['new_fit_count'] == audit['new_model_forward_count'] == 0
    assert receipt['test_complexes'] == 12 and receipt['test_residues'] == 1470
    for item in receipt['input_files']:
        assert sha(Path(item['path'])) == item['sha256'], item['path']
    for item in receipt['outputs']:
        assert sha(HERE / item['path']) == item['sha256'], item['path']
    files = [{'path': str(p.relative_to(HERE)), 'bytes': p.stat().st_size, 'sha256': sha(p)}
             for p in sorted(HERE.rglob('*')) if p.is_file() and p.name != 'DELIVERY-MANIFEST.json']
    result = {'schema': 'fourtask.contact-gallery.delivery.v1',
              'at': datetime.now(timezone.utc).isoformat(), 'status': 'complete',
              'independent_checks': len(audit['checks']), 'new_fit_count': 0,
              'new_model_forward_count': 0, 'files': files,
              'finalizer_sha256': sha(Path(__file__))}
    target = HERE / 'DELIVERY-MANIFEST.json'
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    loaded = json.loads(target.read_text(encoding='utf-8'))
    assert all(sha(HERE / row['path']) == row['sha256'] for row in loaded['files'])
    print(json.dumps({'status': result['status'], 'independent_checks': len(audit['checks']),
                      'delivered_files': len(files), 'manifest_sha256': sha(target)}))


if __name__ == '__main__':
    main()
