"""Preserve the first path-limit attempt; derive a shorter-output-only fixed-prediction repeat."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
original=HERE/'score_common_classification.py'
old='common-classification-fixed-predictions'
new='common-classification-v2'
partial=ROOT/'runs/plm-classification-contact-v1'/old
files=sorted(partial.rglob('test-predictions.csv'))
long=partial/'classification-target-cold-native-common-test-no-exact-affinitytrain2290'/'hist_gradient_boosting'/'seed-00'/'test-predictions.csv'
assert len(str(long))>259 and not long.exists()
source=original.read_text(encoding='utf-8');assert source.count(old)==1
target=HERE/'score_common_classification_revision2.py';assert not target.exists()
target.write_text(source.replace(old,new),encoding='utf-8')
builder=HERE/'build_delivery_report.py';text=builder.read_text(encoding='utf-8')
assert old in text
revised=HERE/'build_delivery_report_revision2.py';assert not revised.exists()
revised.write_text(text.replace(old,new),encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
receipt={'schema':'fixed-prediction.windows-path-adaptation.v2',
    'first_attempt_preserved':str(partial),'completed_partial_prediction_files':len(files),
    'first_missing_expected_path':str(long),'first_missing_path_characters':len(str(long)),
    'observed_setup_failure':'Tool returned missing path/setup failure after original output was partially written; first missing long path is over Windows MAX_PATH.',
    'source_sha256':sha(original),'revised_sha256':sha(target),'only_scoring_change':'Shorter output directory name',
    'builder_source_sha256':sha(builder),'builder_revised_sha256':sha(revised),
    'partial_file_hashes':[{'path':str(p),'sha256':sha(p)} for p in files],
    'new_fit_count':0,'new_forward_count':0,'threshold_or_primary_predictions_changed':False}
(HERE/'common-windows-path-revision2.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in receipt.items() if k!='partial_file_hashes'}))
