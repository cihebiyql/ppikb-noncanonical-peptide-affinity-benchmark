"""One bounded request to the public EuropePMC supplementary-file API."""
from pathlib import Path
import hashlib
import io
import json
import urllib.request
import zipfile
from datetime import datetime, timezone

HERE = Path(__file__).resolve().parent
URL = 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC526462/supplementaryFiles'
receipt = {'url': URL, 'at': datetime.now(timezone.utc).isoformat(), 'request_attempts': 1}
try:
    request = urllib.request.Request(URL, headers={'User-Agent': 'Primary-evidence-audit/1.0'})
    with urllib.request.urlopen(request, timeout=20) as response:
        blob = response.read(8 * 1024 * 1024 + 1)
        assert len(blob) <= 8 * 1024 * 1024
        receipt.update(status_code=response.status, final_url=response.url)
    (HERE / 'raw/AP2-supplementary-api-response.zip').write_bytes(blob)
    receipt.update(response_bytes=len(blob), response_sha256=hashlib.sha256(blob).hexdigest())
    archive = zipfile.ZipFile(io.BytesIO(blob))
    names = [n for n in archive.namelist() if n.rsplit('/', 1)[-1] == '7600445s1.pdf']
    assert len(names) == 1, 'Expected observed supplementary PDF not uniquely present'
    info = archive.getinfo(names[0])
    assert 0 < info.file_size <= 4 * 1024 * 1024
    pdf = archive.read(names[0])
    assert pdf.startswith(b'%PDF')
    (HERE / 'raw/AP2-SI.pdf').write_bytes(pdf)
    receipt.update(status='downloaded_expected_PDF', member=names[0], pdf_bytes=len(pdf),
                   pdf_sha256=hashlib.sha256(pdf).hexdigest())
except Exception as error:
    receipt.update(status='failed_or_expected_PDF_not_available', error_type=type(error).__name__, error=str(error))
(HERE / 'AP2-SI-retrieval-receipt.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
print(json.dumps(receipt))
