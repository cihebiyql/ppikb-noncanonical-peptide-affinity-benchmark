"""Check the derived closed-training tables without opening scientific payloads."""
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
read = lambda name: json.loads((HERE / name).read_text(encoding="utf-8"))
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition: raise ValueError(message)


def main():
    mapping = read("training_metadata_map.original720.json")
    require(Counter(row["kind"] for row in mapping) == {"NN_candidate": 400, "NN_selection": 200, "RF_candidate": 80, "RF_selection": 40}, "Exact original720 metadata kind counts")
    require(len({row["path"] for row in mapping}) == 720, "No reused original receipt path")
    require(all(Path(row["path"]).name in ("complete.json", "selection.json") and len(row["sha256"]) == 64 for row in mapping), "Explicit original metadata names/digests")
    for family, total, metric, parameter in (("nn", 200, "best_validation_MAE", "learning_rate"), ("rf", 40, "validation_MAE", "min_samples_leaf")):
        candidates, choices = read(family + "-candidates.json"), read(family + "-selections.json")
        key = lambda row: tuple(row[name] for name in ("method_id", "panel", "regime", "seed"))
        by_cell = {}
        for row in candidates: by_cell.setdefault(key(row), []).append(row)
        require(len(by_cell) == total and len(candidates) == total * 2 and len(choices) == total, "Exact candidate/choice cell coverage")
        for chosen in choices:
            pair = by_cell[key(chosen)]
            require({row["candidate_index"] for row in pair} == {0, 1}, "Both original candidate indices")
            best = min(pair, key=lambda row: (row[metric], row["candidate_index"]))
            require(chosen["chosen_candidate_index"] == best["candidate_index"], "Actual frozen validation winner")
            require(chosen["chosen_" + parameter] == best[parameter], "Chosen hyperparameter retains source value")
            require(chosen["chosen_validation_MAE"] == best[metric], "Chosen value is validation, never holdout")
    neural = read("nn-candidates.json")
    require(all(row["completed_epoch_count"] is None and row["early_stopped"] is None and row["epochs_at_cap"] is None for row in neural), "Do not infer unavailable last/stopping epochs")
    require(all(type(row["best_epoch_zero_based"]) is int and 0 <= row["best_epoch_zero_based"] < 20 for row in neural), "Preserve original zero-based best epoch")
    groups = read("nn-choice-counts.json")
    require(len(groups) == 20 and all(row["selected_cells"] == 10 and row["learning_rate_0_001_count"] + row["learning_rate_0_0003_count"] == 10 for row in groups), "All five methods/two panels/two regimes/ten seeds")
    sidecar = read("interrupted-attempts.sidecar.json")
    require(sidecar["actual_extra_interrupted_attempts"] == 2 and len(sidecar["attempts"]) == 2 and sidecar["original_failed_json_files_found"] == 1, "Attempt count is independent of original filename count")
    require(sidecar["attempts"][0]["original_failed_json_absent"] and not sidecar["attempts"][0]["original_failed_json_refs"], "IO no original failed.json remains explicit")
    require(len(sidecar["attempts"][1]["original_archived_failed_json_refs"]) == 1, "One real archivedCUDA failed.json")
    audit = read("read-audit.json")
    require(audit["actual_gold_or_prediction_or_test_score_reads"] == 0 and audit["actual_model_weight_reads"] == 0, "Metadata-only read boundary")
    require(all(Path(row["path"]).suffix == ".json" and not any(token in row["path"] for token in ("/scores/", "/rf-scores-v1/", "/real-scores", ".pt", ".joblib", ".jsonl")) for row in audit["reads"]), "No scored/test/array/model file in actual read ledger")
    summary = read("summary.json")
    require(summary["NN_chosen_learning_rate_counts"] == {"0.0003": 82, "0.001": 118} and summary["RF_chosen_min_samples_leaf_counts"] == {"2": 17, "5": 23}, "Observed selection counts agree")
    report = {"schema": "closed-training-metadata-output-verification.v1", "verified_at": datetime.now(timezone.utc).isoformat(), "status": "passed", "original_metadata_rows": 720, "candidate_rows": 480, "selected_cells": 240, "NN_candidates": 400, "RF_candidates": 80, "interrupted_attempts": 2, "original_failed_json_count": 1, "no_stop_epoch_inference": True, "read_audit_entries": len(audit["reads"]), "raw_scientific_payload_or_test_score_reads": 0, "verifier_source_sha256": sha(__file__)}
    with (HERE / "verification.json").open("x", encoding="utf-8") as stream: json.dump(report, stream, ensure_ascii=False, indent=2); stream.write("\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
