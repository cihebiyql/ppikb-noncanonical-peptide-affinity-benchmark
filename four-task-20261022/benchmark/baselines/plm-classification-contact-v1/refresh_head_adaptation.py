"""Record the final pre-training metadata-only prediction-column adjustment."""
import difflib
import hashlib
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
source=ROOT/'baselines/frozen-code/cpu-baselines-v2.py';target=HERE/'run_heads.py'
assert not (ROOT/'runs/plm-classification-contact-v1/heads').exists()
old=json.loads((HERE/'head-adaptation-receipt.json').read_text(encoding='utf-8'))
history=HERE/'preparation-history';history.mkdir(exist_ok=True)
(history/'head-adaptation-initial.json').write_text(json.dumps(old,indent=2),encoding='utf-8')
old['head_code_sha256']=hashlib.sha256(target.read_bytes()).hexdigest()
old['additional_prediction_metadata_column']='negative_source; retained solely for evaluation, never a feature'
(HERE/'head-adaptation-receipt.json').write_text(json.dumps(old,indent=2),encoding='utf-8')
(HERE/'adaptation.diff').write_text(''.join(difflib.unified_diff(source.read_text(encoding='utf-8').splitlines(True),
    target.read_text(encoding='utf-8').splitlines(True),fromfile=str(source),tofile=str(target))),encoding='utf-8')
