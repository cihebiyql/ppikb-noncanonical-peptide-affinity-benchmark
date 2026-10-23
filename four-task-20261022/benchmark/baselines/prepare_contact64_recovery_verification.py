"""Route an unchanged macro verifier's outputs to a new recovery directory."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = ROOT/"baselines/contact64/verify_contact64.py"
target = ROOT/"baselines/recovery-20261023/verify_contact64_recovery.py"
text = source.read_text(encoding="utf-8")
before = 'RUN = ROOT/"runs"/"cpu-contact64-v1"'
after = before+'\nOUT = Path(__file__).resolve().parent/"contact64-fresh"\nOUT.mkdir(parents=True,exist_ok=True)'
if text.count(before)!=1:
    raise ValueError("unexpected verifier source")
text = text.replace(before,after)
text = text.replace('to_csv(RUN/','to_csv(OUT/')
text = text.replace('(RUN/"independent-complex-macro-verification.json")','(OUT/"independent-complex-macro-verification.json")')
target.write_text(text,encoding="utf-8")
receipt = {"source":str(source),"source_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),"target":str(target),
           "target_sha256":hashlib.sha256(target.read_bytes()).hexdigest(),"changes":"output path only; no training/prediction/metric formula changes",
           "old_verification_outputs_overwritten":False}
(target.parent/"contact64-verifier-recovery-source.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding="utf-8")
print(target)
