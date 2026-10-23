"""Reuse the verified bounded control mechanism with the new independently allocated cores/nice."""
import difflib
import hashlib
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
source=ROOT/'baselines/plm-simple-v1/controls/supervise_controls.py'
text=original=source.read_text(encoding='utf-8')
for before,after in [('[25,30]','[25,26]'),('[57,62]','[57,58]'),('[25,30,57,62]','[25,26,57,58]'),('os.nice(15)','os.nice(19)')]:
    assert before in text,before;text=text.replace(before,after)
target=HERE/'supervise_heads.py';assert not target.exists();target.write_bytes(text.encode('utf-8'))
(HERE/'head-supervisor-adaptation.diff').write_text(''.join(difflib.unified_diff(original.splitlines(True),text.splitlines(True),
    fromfile=str(source),tofile=str(target))),encoding='utf-8')
(HERE/'head-supervisor-source.json').write_text(json.dumps({'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
    'target_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'cores':[25,26],'siblings':[57,58],'nice':19,
    'old_lease_not_reused':True,'resource_reference':'methods/dta/additional-CPU-slot-20261023T050621Z.json'},indent=2),encoding='utf-8')
