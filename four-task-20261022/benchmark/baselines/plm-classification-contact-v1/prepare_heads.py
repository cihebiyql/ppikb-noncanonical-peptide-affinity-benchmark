"""Freeze the original five binary learner grids with a sequence-only ESM feature adapter."""
import difflib
import hashlib
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
source=ROOT/'baselines/frozen-code/cpu-baselines-v2.py'
original=source.read_text(encoding='utf-8');text=original
start=text.index('def build_features(frame, task):');end=text.index('\n\ndef models(binary):',start)
text=text[:start]+'def build_features(frame, task):\n    return plm_binary_features.build_features(frame, task)\n'+text[end:]
changes=[
    ('from threadpoolctl import threadpool_limits','from threadpoolctl import threadpool_limits\nimport plm_binary_features'),
    ('FEATURE_VERSION = "manual-aa20-raw-unknown-loglength-hashed-dipeptide64-v1"','FEATURE_VERSION = plm_binary_features.FEATURE_VERSION'),
    ('ROOT / "runs" / "cpu-v1"','ROOT / "runs" / "plm-classification-contact-v1" / "heads"'),
    ('"label", "residue_index")','"label", "residue_index", "structure_id", "negative_source")'),
    ('"code_sha256": sha(__file__), "seeds": SEEDS','"code_sha256": sha(__file__), "feature_code_sha256": sha(plm_binary_features.__file__), "seeds": SEEDS'),
    ('x, feature_audit = build_features(frame, task)',
     'x, feature_audit = build_features(frame, task)\n    np.savez_compressed(view_root / "features.npz", features=x, row_ids=frame.row_id.to_numpy(dtype=str))'),
    ('json_write(run / f"{part}-group-metrics.json", groups)',
     'json_write(run / f"{part}-group-metrics.json", groups)\n                complex_macro = None\n                if is_contact(task):\n                    complex_macro, complex_rows = macro_metrics(selected, pred, binary, threshold, task, "structure_id")\n                    json_write(run / f"{part}-complex-metrics.json", complex_rows)'),
    ('"splits"][part] = {"metrics": metrics(y[indexes], pred, binary, threshold, is_effect(task)), "macro": macro,',
     '"splits"][part] = {"metrics": metrics(y[indexes], pred, binary, threshold, is_effect(task)), "macro": macro, "per_complex_macro": complex_macro,'),
    ('("source", "chemistry_class", "residue_class", "evaluation_stratum")',
     '("source", "chemistry_class", "residue_class", "evaluation_stratum", "negative_source")')]
for before,after in changes:
    assert text.count(before)==1,before;text=text.replace(before,after)
target=HERE/'run_heads.py';assert not target.exists();target.write_bytes(text.encode('utf-8'))
(HERE/'adaptation.diff').write_text(''.join(difflib.unified_diff(original.splitlines(True),text.splitlines(True),
    fromfile=str(source),tofile=str(target))),encoding='utf-8')
(HERE/'head-adaptation-receipt.json').write_text(json.dumps({'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
    'head_code_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
    'model_grid_or_validation_threshold_rule_changed':False,'new_dependencies':False,
    'contact_features':'target residue320 plus peptide mean320; no distance, coords, labels or observed mask',
    'classification_features':'raw peptide mean320 plus target mean320'},indent=2),encoding='utf-8')
print(target)
