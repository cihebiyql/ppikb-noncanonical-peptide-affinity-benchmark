"""Fetch only publicly reachable primary evidence; retain failures, no authentication."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import urllib.request

HERE = Path(__file__).resolve().parent
SOURCES = [
    ('PTPA.pdf', 'https://dr.ntu.edu.sg/server/api/core/bitstreams/3c65d8a1-0efd-4428-af75-b60ecc4d0ea9/content'),
    ('AP2.pdf', 'https://www2.mrc-lmb.cam.ac.uk/groups/hmm/publica/AP2Hub_EMBO2004/AP2Praefcke2004.pdf'),
    ('STAC.html', 'https://www.pnas.org/doi/10.1073/pnas.1708852114'),
    ('Profilin.html', 'https://www.sciencedirect.com/science/article/pii/S0022283607013861'),
]


def main():
    raw = HERE / 'raw'
    raw.mkdir(exist_ok=True)
    rows = []
    for name, url in SOURCES:
        row = {'url': url, 'name': name, 'at': datetime.now(timezone.utc).isoformat()}
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'Primary-evidence-audit/1.0'})
            with urllib.request.urlopen(request, timeout=20) as response:
                content = response.read(16 * 1024 * 1024 + 1)
                assert len(content) <= 16 * 1024 * 1024
                row.update(status_code=response.status, final_url=response.url,
                           content_type=response.headers.get('Content-Type'))
            (raw / name).write_bytes(content)
            row.update(bytes=len(content), sha256=hashlib.sha256(content).hexdigest(),
                       status='downloaded', is_pdf=content.startswith(b'%PDF'))
            if name.endswith('.pdf'):
                assert row['is_pdf'], 'Expected primary PDF; retained response is not a PDF'
        except Exception as error:
            row.update(status='failed_or_not_expected_format', error_type=type(error).__name__, error=str(error))
        rows.append(row)
        (HERE / 'retrieval-receipt.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps([{'name': x['name'], 'status': x['status'], 'bytes': x.get('bytes')} for x in rows]))


if __name__ == '__main__':
    main()
