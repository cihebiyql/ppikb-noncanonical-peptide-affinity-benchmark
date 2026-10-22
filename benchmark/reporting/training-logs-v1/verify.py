"""Verify derived epoch-budget tables and preserve hashes; no payload rereads."""
import hashlib
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
read = lambda name: json.loads((HERE / name).read_text(encoding="utf-8"))
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
rows, groups, summary, audit = read("candidates400.json"), read("groups40.json"), read("summary.json"), read("read-audit.json")
assert len(rows) == 400 and len(groups) == 40
assert len({row["log_path"] for row in rows}) == 400
assert all(row["actual_completed_epoch_count"] == row["last_completed_epoch_zero_based"] + 1 and row["status"] == "verified_complete_epoch_trace" and row["stop_rule_reproduced"] for row in rows)
assert sum(row["at_cap"] is True for row in rows) == 10
assert sum(row["finished_before_cap"] is True for row in rows) == 390
assert all(row["final_consecutive_nonimprovement_count"] == row["patience"] and row["actual_completed_epoch_count"] < row["max_epochs"] for row in rows if row["early_stopped_before_cap"])
assert sum(row["early_stopped_before_cap"] is True for row in rows) == 390
for group in groups:
    subset = [row for row in rows if all(row[key] == group[key] for key in ("method_id", "panel", "regime", "learning_rate"))]
    values = [row["actual_completed_epoch_count"] for row in subset]
    assert len(subset) == 10 and {row["seed"] for row in subset} == set(range(10))
    assert (min(values), statistics.mean(values), max(values)) == (group["completed_epochs_min"], group["completed_epochs_mean"], group["completed_epochs_max"])
    assert group["at_cap_count"] + group["finished_before_cap_count"] + group["unknown_count"] == 10
logs = [row for row in audit["reads"] if row["kind"] == "closed_valid_candidate_epoch_log"]
assert len(logs) == 400 and {row["sha256"] for row in logs} == {row["log_sha256"] for row in rows}
assert all(Path(row["path"]).name == "epochs.jsonl" for row in logs)
assert not any(any(token in row["path"] for token in ("/scores/", "predictions", ".pt", ".joblib", "sealed-test")) for row in audit["reads"])
parent_manifest = HERE.parent / "training-metadata-v1/FINAL-MANIFEST.json"
assert sha(parent_manifest) == "92ff06efbac7182038eab1717ff749966c5cd5fe9afbefc50caf6bbde2f16d5b"
values = [row["actual_completed_epoch_count"] for row in rows]
result = {"schema": "existing-training-log-budget-verification.v1", "verified_at": datetime.now(timezone.utc).isoformat(), "status": "passed", "actual_log_count": 400, "actual_groups": 40, "epoch_count_min": min(values), "epoch_count_mean": statistics.mean(values), "epoch_count_max": max(values), "at_cap20": 10, "finished_before_cap": 390, "source_reproduced_patience_stops_before_cap": 390, "unknown": 0, "old20_file_manifest_unchanged": True, "actual_scientific_payload_or_test_score_reads": 0, "artifacts": [{"path": str(path), "sha256": sha(path)} for path in sorted(HERE.iterdir()) if path.is_file() and path.name != "verification.json"]}
with (HERE / "verification.json").open("x", encoding="utf-8") as stream: json.dump(result, stream, ensure_ascii=False, indent=2); stream.write("\n")
print(json.dumps({key: value for key, value in result.items() if key != "artifacts"}, ensure_ascii=False, indent=2))
