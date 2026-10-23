"""Freeze a classical molecular-feature runner, preserving completed sequence runs."""
import difflib
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT/"baselines"/"frozen-code"/"cpu-baselines-v2.py"
TARGET = ROOT/"baselines"/"molecular"/"run_molecular_baselines.py"
original = SOURCE.read_text(encoding="utf-8")
text = original
start = text.index("def build_features(frame, task):")
end = text.index("\n\ndef models(binary):",start)
text = text[:start]+"def build_features(frame, task):\n    return molecular_features.build_features(frame, task)\n"+text[end:]
replacements = [
    ('from threadpoolctl import threadpool_limits','from threadpoolctl import threadpool_limits\nimport molecular_features'),
    ('FEATURE_VERSION = "manual-aa20-raw-unknown-loglength-hashed-dipeptide64-v1"','FEATURE_VERSION = molecular_features.FEATURE_VERSION'),
    ('ROOT = Path(__file__).resolve().parents[1]','ROOT = Path(__file__).resolve().parents[2]'),
    ('else Ridge(**params)','else Ridge(solver="lsqr", tol=1e-4, max_iter=1000, **params)'),
    ('{"max_iter": 60, "max_leaf_nodes": 15, "learning_rate": 0.05}, {"max_iter": 90, "max_leaf_nodes": 31, "learning_rate": 0.1}',
     '{"max_iter": 40, "max_leaf_nodes": 15, "learning_rate": 0.05, "max_bins": 64}, {"max_iter": 80, "max_leaf_nodes": 31, "learning_rate": 0.1, "max_bins": 64}'),
    ('ROOT / "runs" / "cpu-v1"','ROOT / "runs" / "cpu-molecular-v1"'),
    ('x, feature_audit = build_features(frame, task)',
     'x, feature_audit = build_features(frame, task)\n    np.savez_compressed(view_root / "features.npz", features=x, row_ids=frame.row_id.to_numpy(dtype=str))'),
    ('"code_sha256": sha(__file__), "seeds": SEEDS',
     '"code_sha256": sha(__file__), "feature_code_path": str(Path(molecular_features.__file__)), "feature_code_sha256": sha(molecular_features.__file__), "seeds": SEEDS'),
]
for before,after in replacements:
    if text.count(before)!=1:
        raise ValueError(f"expected one molecular runner replacement: {before!r}")
    text = text.replace(before,after)
if TARGET.exists() and TARGET.read_text(encoding="utf-8")!=text:
    raise ValueError("refusing overwrite of a different frozen molecular runner")
TARGET.write_text(text,encoding="utf-8")
(TARGET.parent/"adaptation.diff").write_text("".join(difflib.unified_diff(original.splitlines(True),text.splitlines(True),fromfile=str(SOURCE),tofile=str(TARGET))),encoding="utf-8")
(TARGET.parent/"source-adaptation-receipt.json").write_text(json.dumps({"source":str(SOURCE),"source_sha256":hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
    "target":str(TARGET),"target_sha256":hashlib.sha256(TARGET.read_bytes()).hexdigest(),"changes":["classical chiral molecular features","ridge LSQR sparse-friendly iterative solver","predeclared smaller histogram grid for 2CPU","new isolated output path","feature-code hash"],
    "no_new_dependencies":True,"old_runs_changed":False},ensure_ascii=False,indent=2),encoding="utf-8")
print(TARGET)
