"""Freeze this standalone derived evidence package only; no scientific source edit."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
files = ["build.py", "verify_outputs.py", "finalize_manifest.py", "nn-candidates.json", "nn-candidates.csv", "nn-selections.json", "nn-selections.csv", "rf-candidates.json", "rf-candidates.csv", "rf-selections.json", "rf-selections.csv", "nn-choice-counts.json", "nn-choice-counts.csv", "training_metadata_map.original720.json", "interrupted-attempts.sidecar.json", "summary.json", "read-audit.json", "provenance.json", "verification.json", "超参数与训练元信息.md"]
report = {"schema": "standalone-closed-training-hyperparameters-evidence.v1", "created_at": datetime.now(timezone.utc).isoformat(), "scope": "Closed train/validation metadata and two original failure lineages; no test-performance interpretation", "artifacts": [{"path": str(HERE / name), "sha256": sha(HERE / name)} for name in files], "original_training_metadata_map": {"path": str(HERE / "training_metadata_map.original720.json"), "sha256": sha(HERE / "training_metadata_map.original720.json"), "rows": 720}, "actual_fit_selection_coverage": {"NN_candidates": 400, "NN_selected": 200, "RF_candidates": 80, "RF_selected": 40}, "extra_interrupted_attempts": 2, "real_original_failed_json_count": 1, "training_metadata_map_recommended_for_frozen_reporter": False, "unknown_last_epoch_and_earlystop_not_inferred": True, "actual_label_prediction_model_or_test_score_reads": 0, "registry_writes": 0, "scientific_processes_started": 0}
with (HERE / "FINAL-MANIFEST.json").open("x", encoding="utf-8") as stream: json.dump(report, stream, ensure_ascii=False, indent=2); stream.write("\n")
print(json.dumps({"artifacts": len(files), "manifest_sha256": sha(HERE / "FINAL-MANIFEST.json"), "original720_map_sha256": sha(HERE / "training_metadata_map.original720.json")}, indent=2))
