"""Diagnose existing400 valid NN epoch logs. No new fitting/selection/scoring."""
import csv
import hashlib
import json
import math
import os
import statistics
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent.parent
READS = []
RUNNER_SHA = "9abe4a9fba5840a6200aecf40fdfb436abbf61d78c3a9a2f28baae7712c6913e"


def local(value):
    value = str(value)
    return Path("D:/" + value[len("/mnt/d/"):]) if os.name == "nt" and value.startswith("/mnt/d/") else Path(value)


def canonical(value):
    path = local(value).resolve()
    return "/mnt/d/" + str(path)[3:].replace("\\", "/") if os.name == "nt" else str(path)


def read(path, kind, expected=None):
    file = local(path)
    if file.suffix != ".json" and file.name != "epochs.jsonl": raise PermissionError("Only closed metadata and exact epochs.jsonl allowed")
    if any(token in canonical(file) for token in ("/scores/", "/rf-scores-v1/", "/real-scores", "predictions", "sealed-test")): raise PermissionError("No score/prediction/label reads")
    raw = file.read_bytes(); digest = hashlib.sha256(raw).hexdigest()
    if expected and digest != expected: raise ValueError("Actual closed file SHA differs")
    ref = {"path": canonical(file), "sha256": digest}
    READS.append({**ref, "kind": kind, "bytes": len(raw), "read_at": datetime.now(timezone.utc).isoformat()})
    if file.name == "epochs.jsonl": return [json.loads(line) for line in raw.splitlines() if line.strip()], ref
    return json.loads(raw), ref


def write(path, body):
    with Path(path).open("x", encoding="utf-8") as stream: json.dump(body, stream, ensure_ascii=False, indent=2, allow_nan=False); stream.write("\n")


def csv_out(path, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with Path(path).open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
        for row in rows: writer.writerow({key: "null" if value is None else value for key, value in row.items()})


def trajectory(log, complete, spec):
    cap, patience = spec["max_epochs"], spec["patience"]
    if not log or len(log) > cap or [r.get("epoch") for r in log] != list(range(len(log))): raise ValueError("Epoch path is empty/discontinuous/out of original budget")
    best, best_epoch, stale = math.inf, None, 0
    for index, row in enumerate(log):
        value = row["validation"]["all"]["MAE"]
        if type(value) not in (float, int) or not math.isfinite(value): raise ValueError("Invalid validation aggregate")
        improved = value < best
        if improved: best, best_epoch, stale = value, index, 0
        else: stale += 1
        if row.get("improved") is not improved or row.get("best_epoch") != best_epoch or row.get("train_n") != complete["train_n"]: raise ValueError("Logged improvement/best epoch differs from frozen source rule")
        if stale >= patience and index != len(log) - 1: raise ValueError("Source would have stopped before a subsequent logged epoch")
    if best_epoch != complete["best_epoch"] or best != complete["best_validation_MAE"]: raise ValueError("Final logged best differs from actual complete receipt")
    before = len(log) < cap
    if before and stale != patience: raise ValueError("Before-cap terminal log does not establish source patience stop")
    return {"actual_completed_epoch_count": len(log), "last_completed_epoch_zero_based": log[-1]["epoch"], "best_epoch_zero_based": best_epoch, "at_cap": len(log) == cap, "finished_before_cap": before, "early_stopped_before_cap": before and stale == patience, "final_consecutive_nonimprovement_count": stale, "stop_rule_reproduced": True, "stop_interpretation": "source_patience_stop_before_cap" if before else "finished_at_epoch_budget", "same_epoch_patience_condition_at_cap": (not before and stale == patience)}


def main():
    started = time.monotonic()
    if (HERE / "summary.json").exists(): raise FileExistsError("Preserve previous diagnostic outputs")
    parent = PROJECT / "reporting/training-metadata-v1"
    manifest, parent_ref = read(parent / "FINAL-MANIFEST.json", "frozen_prior_training_metadata_manifest", "92ff06efbac7182038eab1717ff749966c5cd5fe9afbefc50caf6bbde2f16d5b")
    candidate_path = parent / "nn-candidates.json"
    candidate_sha = next(row["sha256"] for row in manifest["artifacts"] if local(row["path"]).name == "nn-candidates.json")
    candidates, candidate_ref = read(candidate_path, "actual400_valid_candidate_metadata", candidate_sha)
    if len(candidates) != 400 or len({tuple(row[k] for k in ("method_id", "panel", "regime", "seed", "candidate_index")) for row in candidates}) != 400: raise ValueError("Exact original valid400 candidates required")
    source = PROJECT / "execution/runner.py"; source_bytes = source.read_bytes()
    if hashlib.sha256(source_bytes).hexdigest() != RUNNER_SHA: raise ValueError("Original production stopping source changed")
    source_text = source_bytes.decode("utf-8")
    if "if stale >= int(spec['patience']):" not in source_text or "improved = mae < best_mae" not in source_text: raise ValueError("Cannot reproduce original source stop condition")
    specs, units, results = {}, {}, []
    for item in candidates:
        if time.monotonic() - started > 240: raise TimeoutError("Bounded diagnostic preparation budget exhausted")
        row = {key: item[key] for key in ("method_id", "panel", "regime", "seed", "candidate_index", "learning_rate")}
        row.update(actual_completed_epoch_count=None, last_completed_epoch_zero_based=None, best_epoch_zero_based=item["best_epoch_zero_based"], at_cap=None, finished_before_cap=None, early_stopped_before_cap=None, stop_rule_reproduced=False, status="unknown", unknown_reason=None)
        try:
            key = item["spec_path"]
            if key not in specs: specs[key] = read(key, "original_frozen_fit_spec", item["spec_sha256"])
            spec, spec_ref = specs[key]
            unit_path = local(spec["launch_proof"]["receipt_root"]) / "unit-complete.json"
            if canonical(unit_path) not in units: units[canonical(unit_path)] = read(unit_path, "actual_successful_unit_artifact_hash_manifest")
            unit, unit_ref = units[canonical(unit_path)]
            if unit.get("status") != "complete" or unit.get("spec_sha256") != spec_ref["sha256"]: raise ValueError("Actual completed unit/spec linkage differs")
            complete_path = local(spec["run_root"]) / ("candidate-" + str(item["candidate_index"])) / "complete.json"
            if canonical(complete_path) != item["source_path"] or unit["artifacts"].get(canonical(complete_path)) != item["source_sha256"]: raise ValueError("Candidate receipt not bound by actual unit artifacts")
            complete, complete_ref = read(complete_path, "closed_valid_candidate_complete", item["source_sha256"])
            if complete.get("status") != "complete" or complete.get("candidate_index") != item["candidate_index"] or complete.get("fit_spec_sha256") != spec_ref["sha256"]: raise ValueError("Candidate metadata identity differs")
            log_path = complete_path.parent / "epochs.jsonl"
            expected_log_sha = unit["artifacts"].get(canonical(log_path))
            if not expected_log_sha: raise ValueError("No actual unit artifact SHA for exact epoch log")
            log, log_ref = read(log_path, "closed_valid_candidate_epoch_log", expected_log_sha)
            row.update(trajectory(log, complete, spec)); row.update(status="verified_complete_epoch_trace", log_path=log_ref["path"], log_sha256=log_ref["sha256"], complete_path=complete_ref["path"], complete_sha256=complete_ref["sha256"], unit_manifest_path=unit_ref["path"], unit_manifest_sha256=unit_ref["sha256"], max_epochs=spec["max_epochs"], patience=spec["patience"])
        except Exception as error:
            row["unknown_reason"] = type(error).__name__ + ": " + str(error)
        results.append(row)
    grouped = {}
    for row in results:
        key = tuple(row[k] for k in ("method_id", "panel", "regime", "learning_rate")); grouped.setdefault(key, []).append(row)
    if len(grouped) != 40 or any(len(rows) != 10 or {r["seed"] for r in rows} != set(range(10)) for rows in grouped.values()): raise ValueError("Exact40 groups of10 seeds required")
    aggregates = []
    for key, rows in sorted(grouped.items()):
        values = [r["actual_completed_epoch_count"] for r in rows if r["status"] == "verified_complete_epoch_trace"]
        aggregates.append({"method_id": key[0], "panel": key[1], "regime": key[2], "learning_rate": key[3], "candidate_count": 10, "verified_epoch_count": len(values), "completed_epochs_min": min(values) if values else None, "completed_epochs_mean": statistics.mean(values) if values else None, "completed_epochs_max": max(values) if values else None, "at_cap_count": sum(r["at_cap"] is True for r in rows), "finished_before_cap_count": sum(r["finished_before_cap"] is True for r in rows), "early_stopped_before_cap_count": sum(r["early_stopped_before_cap"] is True for r in rows), "unknown_count": sum(r["status"] == "unknown" for r in rows)})
    counts = Counter(r["status"] for r in results)
    summary = {"schema": "derived-existing-NN-epoch-budget-diagnostic.v1", "created_at": datetime.now(timezone.utc).isoformat(), "actual_valid_candidates": 400, "actual_groups": 40, "actual_verified_complete_epoch_traces": counts["verified_complete_epoch_trace"], "unknown_candidates": counts["unknown"], "at_cap20_count": sum(r["at_cap"] is True for r in results), "finished_before_cap_count": sum(r["finished_before_cap"] is True for r in results), "source_patience_early_stopped_before_cap_count": sum(r["early_stopped_before_cap"] is True for r in results), "complete_receipts_alone_still_do_not_provide_last_epoch": True, "old_unknown_metadata_not_overwritten": True, "historical_two_partial_attempts_excluded": True, "new_training_or_tuning_or_scoring": 0, "raw_label_prediction_model_or_test_score_reads": 0, "elapsed_diagnostic_seconds": time.monotonic() - started}
    write(HERE / "candidates400.json", results); csv_out(HERE / "candidates400.csv", results)
    write(HERE / "groups40.json", aggregates); csv_out(HERE / "groups40.csv", aggregates)
    write(HERE / "summary.json", summary)
    write(HERE / "read-audit.json", {"reads": READS, "epoch_log_reads": sum(r["kind"] == "closed_valid_candidate_epoch_log" for r in READS), "raw_label_prediction_model_or_test_score_reads": 0})
    write(HERE / "source-provenance.json", {"parent_manifest": parent_ref, "valid400_candidate_table": candidate_ref, "frozen_production_runner": {"path": canonical(source), "sha256": RUNNER_SHA}, "builder": {"path": canonical(__file__), "sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}, "epoch_log_discovery": "Only exact candidate-root/epochs.jsonl from original frozen spec; digest must be actual successful unit.artifacts value", "stop_semantics": "Strict validation MAE improvement resets stale; source breaks when stale>=patience. early_stopped_before_cap requires continuous complete trace, matching complete best and fully reproduced source condition; at-cap condition is separately retained.", "artifact_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.iterdir() if p.is_file() and p.name not in ("source-provenance.json", "build.py")}})
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__": main()
