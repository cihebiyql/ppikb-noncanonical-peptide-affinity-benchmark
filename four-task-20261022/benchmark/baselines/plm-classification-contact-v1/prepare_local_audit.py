"""Keep the remote numeric audit intact and derive a filename-only local repeat."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
source=HERE/'verify_heads.py'
prior=json.loads((ROOT/'runs/plm-classification-contact-v1/heads/independent-recalculation.json').read_text(encoding='utf-8'))
digest=hashlib.sha256(source.read_bytes()).hexdigest();assert digest==prior['code_sha256']
text=source.read_text(encoding='utf-8');before="(args.root/'independent-recalculation.json')"
assert text.count(before)==1
text=text.replace(before,"(args.root/'independent-recalculation.local-v1.json')")
target=HERE/'verify_heads_local.py';assert not target.exists();target.write_bytes(text.encode('utf-8'))
(HERE/'local-verifier-adaptation.json').write_text(json.dumps({'source_sha256':digest,
    'target_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
    'only_change':'Separate audit receipt output filename','remote_audit_unchanged':True},indent=2),encoding='utf-8')
print(target)
