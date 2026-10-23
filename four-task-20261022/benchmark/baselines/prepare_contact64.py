"""Create a frozen contact64 runner without changing completed baseline code."""
import difflib
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/"baselines"/"frozen-code"/"cpu-baselines-v2.py"
TARGET = ROOT/"baselines"/"contact64"/"run_contact64.py"
text = SOURCE.read_text(encoding="utf-8")
original = text
replacements = [
    ('ROOT = Path(__file__).resolve().parents[1]', 'ROOT = Path(__file__).resolve().parents[2]'),
    ('"evaluation_stratum", "label", "residue_index") if c in frame]', '"evaluation_stratum", "label", "residue_index", "structure_id") if c in frame]'),
    ('"source_reproduction_level": "new common-data training, not original paper result reproduction"}',
     '"source_reproduction_level": "new common-data training, not original paper result reproduction",\n                "contact_features_whitelist": ["peptide_sequence", "target_sequence", "residue_index"],\n                "excluded_input_columns": ["minimum_heavyatom_distance_A", "observed_target"],\n                "complex_id_column": "structure_id", "component_id_column": "group_id"}'),
    ('json_write(run / f"{part}-group-metrics.json", groups)',
     'json_write(run / f"{part}-group-metrics.json", groups)\n                complex_macro, complex_groups = macro_metrics(selected, pred, binary, threshold, task, "structure_id")\n                json_write(run / f"{part}-complex-metrics.json", complex_groups)'),
    ('"macro": macro,\n                                         "subgroups": subgroup', '"macro": macro, "per_complex_macro": complex_macro,\n                                         "subgroups": subgroup'),
    ('ROOT / "runs" / "cpu-v1"', 'ROOT / "runs" / "cpu-contact64-v1"'),
]
for before, after in replacements:
    if text.count(before) != 1:
        raise ValueError(f"expected one occurrence for contact64 adapter: {before!r}")
    text = text.replace(before, after)
TARGET.parent.mkdir(parents=True, exist_ok=True)
if TARGET.exists() and TARGET.read_text(encoding="utf-8") != text:
    raise ValueError("refusing to overwrite a different contact64 runner")
TARGET.write_text(text, encoding="utf-8")
(TARGET.parent/"adaptation.diff").write_text("".join(difflib.unified_diff(original.splitlines(True), text.splitlines(True), fromfile=str(SOURCE), tofile=str(TARGET))), encoding="utf-8")
receipt = {"source": str(SOURCE), "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
           "target": str(TARGET), "target_sha256": hashlib.sha256(TARGET.read_bytes()).hexdigest(),
           "changes": ["output path", "preserve structure_id", "separate complex and component macro metrics", "explicit sequence input whitelist"],
           "feature_implementation_changed": False, "old_runs_changed": False}
(TARGET.parent/"source-adaptation-receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(receipt, ensure_ascii=False))
