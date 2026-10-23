"""Minimal auditable adaptation of the already verified generic CPU runner."""
import difflib
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
source=ROOT/'baselines/frozen-code/cpu-baselines-v2.py'
original=source.read_text(encoding='utf-8')
text=original
start=text.index('def build_features(frame, task):')
end=text.index('\n\ndef models(binary):',start)
text=text[:start]+'def build_features(frame, task):\n    return plm_features.build_features(frame, task)\n'+text[end:]
for before,after in [
 ('from threadpoolctl import threadpool_limits','from threadpoolctl import threadpool_limits\nimport plm_features'),
 ('FEATURE_VERSION = "manual-aa20-raw-unknown-loglength-hashed-dipeptide64-v1"','FEATURE_VERSION = plm_features.FEATURE_VERSION'),
 ('ROOT = Path(__file__).resolve().parents[1]','ROOT = Path(__file__).resolve().parents[2]'),
 ('else Ridge(**params)','else Ridge(solver="lsqr", tol=1e-4, max_iter=1000, **params)'),
 ('ROOT / "runs" / "cpu-v1"','ROOT / "runs" / "plm-simple-v1" / "heads"'),
 ('"code_sha256": sha(__file__), "seeds": SEEDS','"code_sha256": sha(__file__), "feature_code_sha256": sha(plm_features.__file__), "seeds": SEEDS'),
 ('x, feature_audit = build_features(frame, task)','x, feature_audit = build_features(frame, task)\n    np.savez_compressed(view_root / "features.npz", features=x, row_ids=frame.row_id.to_numpy(dtype=str))')]:
    assert text.count(before)==1,before
    text=text.replace(before,after)
target=HERE/'run_heads.py'
assert not target.exists()
target.write_text(text,encoding='utf-8')
(HERE/'adaptation.diff').write_text(''.join(difflib.unified_diff(original.splitlines(True),text.splitlines(True),fromfile=str(source),tofile=str(target))),encoding='utf-8')
(HERE/'adaptation-receipt.json').write_text(json.dumps({'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
    'runner_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'changes':['frozen mean-pool features','Ridge LSQR cap','new output','feature code hash','save fixed matrix'],
    'generic_baseline_not_full_paper':True,'new_dependencies':False},indent=2),encoding='utf-8')
