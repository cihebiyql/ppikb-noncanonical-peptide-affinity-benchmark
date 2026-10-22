"""Closed train/validation metadata only; no model, prediction, gold or test read."""
import csv
import hashlib
import json
import math
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent.parent
NN_INDEX_SHA = "c7b3bde68c9a741c0ac3f255a825e4a55dd7234e2b4e6d48f212fee8d5609ab1"
METHODS = {"GraphDTA-GIN", "MGraphDTA", "DGDTA-CL", "DeepNC-GEN", "GS-DTA"}
PANELS = {"source_peptide_dependency_cold", "target_reference_homology_cold"}
READS = []


def local(value):
    value = str(value)
    if os.name == "nt" and value.startswith("/mnt/d/"): return Path("D:/" + value[len("/mnt/d/"):])
    return Path(value)


def canonical(value):
    path = local(value).resolve()
    if os.name == "nt": return "/mnt/d/" + str(path)[3:].replace("\\", "/")
    return str(path)


def sha(path): return hashlib.sha256(local(path).read_bytes()).hexdigest()


def meta(path, role, expected=None):
    file = local(path)
    if file.suffix != ".json" or any(word in file.name.lower() for word in ("gold", "predictions")):
        raise PermissionError("Only explicit closed training/lineage JSON metadata can be read")
    raw = file.read_bytes(); digest = hashlib.sha256(raw).hexdigest()
    if expected and digest != expected: raise ValueError("Metadata SHA mismatch: " + str(file))
    READS.append({"path": canonical(file), "sha256": digest, "kind": role, "bytes": len(raw), "read_at": datetime.now(timezone.utc).isoformat()})
    return json.loads(raw), {"path": canonical(file), "sha256": digest}


def write(path, body):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(body, stream, ensure_ascii=False, indent=2, allow_nan=False); stream.write("\n")


def csv_out(path, rows):
    keys = list(dict.fromkeys(key for row in rows for key in row))
    with Path(path).open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=keys); writer.writeheader()
        for row in rows: writer.writerow({key: "null" if value is None else json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else value for key, value in row.items()})


def exact_grid(coordinates, neural=True):
    cells = {(p, r, s) for p in PANELS for r in ("NC_only", "standard_only") for s in range(10)}
    expected = {(m, *c) for m in METHODS for c in cells} if neural else cells
    if len(coordinates) != len(expected) or set(coordinates) != expected: raise ValueError("Incomplete/duplicate frozen200NN or40RF grid")


def winner(candidates, metric):
    if len(candidates) != 2 or {row["candidate_index"] for row in candidates} != {0, 1}: raise ValueError("Exactly original two candidate configurations required")
    if any(row.get("status") != "complete" or not isinstance(row.get(metric), (int, float)) or not math.isfinite(row[metric]) for row in candidates): raise ValueError("Finite completed validation-only candidates required")
    return min(candidates, key=lambda row: (row[metric], row["candidate_index"]))


def main():
    if (HERE / "summary.json").exists(): raise FileExistsError("Preserve existing metadata report")
    nn_index, nn_index_ref = meta(PROJECT / "administration/io-recovery01/execution-index-v5-recovery.json", "frozen_NN_scientific_index", NN_INDEX_SHA)
    nn_barrier, nn_barrier_ref = meta(PROJECT / "administration/cuda-recovery02-hostexit-v2/postjoint-v2-execution1/all200-selections-frozen.json", "actual_NN200_barrier")
    if (nn_barrier.get("status"), nn_barrier.get("selection_count"), nn_barrier.get("candidate_fit_count"), nn_barrier.get("execution_index_sha256")) != ("all_selections_frozen", 200, 400, NN_INDEX_SHA): raise ValueError("Actual approvedNN200/400 barrier required")
    by_selection = {row["selection_path"]: row for row in nn_index["per_seed_selections"]}
    if len(by_selection) != 200 or set(by_selection) != {row["path"] for row in nn_barrier["selections"]}: raise ValueError("Barrier path set differs from original scientific plan")
    rf_barrier, rf_barrier_ref = meta(PROJECT / "auxiliary-rf-baseline/all40-selections-frozen-v1.json", "actual_RF40_barrier", "c03db701826feaa688ba87bb9cee5e5fea67f2fd17f83dab7c8454aafcea9e12")
    rf_index, rf_index_ref = meta(PROJECT / "auxiliary-rf-baseline/specs-v1/task-spec-index.json", "frozen_RF_task_index", rf_barrier["task_index_sha256"])
    rf_by_path = {row["selection_path"]: row for row in rf_index["units"]}
    if len(rf_by_path) != 40 or set(rf_by_path) != {row["selection_path"] for row in rf_barrier["selections"]}: raise ValueError("RF barrier/path set differs from frozen specs")
    mapping, nn_candidates, nn_choices, rf_candidates, rf_choices, nn_ids, rf_ids = [], [], [], [], [], [], []
    for entry in nn_barrier["selections"]:
        selected, selected_ref = meta(entry["path"], "NN_selection", entry["sha256"])
        spec, spec_ref = meta(by_selection[entry["path"]]["spec_path"], "NN_fit_spec", selected["fit_spec_sha256"])
        coordinate = tuple(selected[key] for key in ("method_id", "split_id", "regime", "seed")); nn_ids.append(coordinate)
        if selected.get("status") != "frozen" or selected.get("holdout_metrics_consulted") is not False or coordinate != tuple(spec[key] for key in ("method_id", "split_id", "regime", "seed")) or canonical(local(spec["run_root"]) / "selection.json") != canonical(entry["path"]): raise ValueError("NN scientific identity/validation-only freeze mismatch")
        current = []
        for index in (0, 1):
            complete, complete_ref = meta(local(spec["run_root"]) / ("candidate-" + str(index)) / "complete.json", "NN_candidate")
            if complete.get("fit_spec_sha256") != spec_ref["sha256"] or complete.get("candidate_index") != index or complete.get("hyperparameters") != spec["candidates"][index] or complete.get("test_label_reads") != 0 or complete.get("external_label_reads") != 0: raise ValueError("NN candidate provenance or protocol differs")
            retained = next(row for row in selected["candidates"] if row["candidate_index"] == index)
            if retained != complete: raise ValueError("Selected candidate metadata differs from actual closed candidate receipt")
            row = {"method_id": coordinate[0], "panel": coordinate[1], "regime": coordinate[2], "seed": coordinate[3], "candidate_index": index, "learning_rate": complete["hyperparameters"]["learning_rate"], "weight_decay": complete["hyperparameters"]["weight_decay"], "best_epoch_zero_based": complete["best_epoch"], "best_validation_MAE": complete["best_validation_MAE"], "elapsed_process_seconds": complete["elapsed_seconds"], "train_n": complete["train_n"], "validation_n": complete["validation_n"], "validation_scope": complete["validation_scope"], "effective_validation_scope": complete["effective_validation_scope"], "max_epochs": spec["max_epochs"], "patience": spec["patience"], "completed_epoch_count": complete.get("completed_epoch_count"), "early_stopped": complete.get("early_stopped"), "epochs_at_cap": complete.get("epochs_at_cap"), "source_path": complete_ref["path"], "source_sha256": complete_ref["sha256"], "spec_path": spec_ref["path"], "spec_sha256": spec_ref["sha256"]}
            nn_candidates.append(row); current.append(complete)
            mapping.append({"kind": "NN_candidate", **complete_ref})
        best = winner(current, "best_validation_MAE")
        if selected["candidate_index"] != best["candidate_index"] or selected["checkpoint_sha256"] != best["checkpoint_sha256"]: raise ValueError("NN selection differs from validation-MAE/lower-index winner")
        nn_choices.append({"method_id": coordinate[0], "panel": coordinate[1], "regime": coordinate[2], "seed": coordinate[3], "chosen_candidate_index": best["candidate_index"], "chosen_learning_rate": best["hyperparameters"]["learning_rate"], "chosen_best_epoch_zero_based": best["best_epoch"], "chosen_validation_MAE": best["best_validation_MAE"], "candidate0_learning_rate": current[0]["hyperparameters"]["learning_rate"], "candidate0_best_epoch_zero_based": current[0]["best_epoch"], "candidate0_validation_MAE": current[0]["best_validation_MAE"], "candidate1_learning_rate": current[1]["hyperparameters"]["learning_rate"], "candidate1_best_epoch_zero_based": current[1]["best_epoch"], "candidate1_validation_MAE": current[1]["best_validation_MAE"], "completed_epoch_count": None, "early_stopped": None, "epochs_at_cap": None, "selection_path": selected_ref["path"], "selection_sha256": selected_ref["sha256"], "spec_sha256": spec_ref["sha256"]})
        mapping.append({"kind": "NN_selection", **selected_ref})
    for entry in rf_barrier["selections"]:
        selected, selected_ref = meta(entry["selection_path"], "RF_selection", entry["selection_sha256"])
        registered = rf_by_path[entry["selection_path"]]
        spec, spec_ref = meta(registered["spec_path"], "RF_fit_spec", registered["spec_sha256"])
        coordinate = tuple(selected[key] for key in ("panel", "regime", "seed")); rf_ids.append(coordinate)
        if selected.get("status") != "frozen" or selected.get("validation_only") is not True or selected.get("gold_reads") != 0 or selected.get("spec_sha256") != spec_ref["sha256"] or selected["model_sha256"] != entry["model_sha256"] or coordinate != tuple(spec[key] for key in ("panel", "regime", "seed")) or canonical(local(spec["output_root"]) / "selection.json") != canonical(entry["selection_path"]): raise ValueError("RF scientific/provenance/validation-only freeze mismatch")
        current = []
        for index in (0, 1):
            complete, complete_ref = meta(local(spec["output_root"]) / ("candidate-" + str(index)) / "complete.json", "RF_candidate")
            retained = next(row for row in selected["candidates"] if row["candidate_index"] == index)
            if retained != complete or complete.get("spec_sha256") != spec_ref["sha256"] or complete.get("holdout_reads") != 0: raise ValueError("RF candidate provenance differs")
            params = complete["effective_parameters"]
            rf_candidates.append({"method_id": selected["method_id"], "panel": coordinate[0], "regime": coordinate[1], "seed": coordinate[2], "candidate_index": index, "n_estimators": params["n_estimators"], "max_features": params["max_features"], "min_samples_leaf": params["min_samples_leaf"], "random_state": params["random_state"], "n_jobs": params["n_jobs"], "validation_MAE": complete["validation_MAE"], "elapsed_process_seconds": complete["seconds"], "train_n": complete["train_n"], "validation_n": complete["validation_n"], "effective_parameters": params, "source_path": complete_ref["path"], "source_sha256": complete_ref["sha256"], "spec_sha256": spec_ref["sha256"]})
            current.append(complete); mapping.append({"kind": "RF_candidate", **complete_ref})
        best = winner(current, "validation_MAE")
        if selected["candidate_index"] != best["candidate_index"] or selected["model_sha256"] != best["model_sha256"]: raise ValueError("RF selection differs from validation winner")
        rf_choices.append({"method_id": selected["method_id"], "panel": coordinate[0], "regime": coordinate[1], "seed": coordinate[2], "chosen_candidate_index": best["candidate_index"], "chosen_min_samples_leaf": best["effective_parameters"]["min_samples_leaf"], "chosen_validation_MAE": best["validation_MAE"], "candidate0_min_samples_leaf": current[0]["effective_parameters"]["min_samples_leaf"], "candidate0_validation_MAE": current[0]["validation_MAE"], "candidate1_min_samples_leaf": current[1]["effective_parameters"]["min_samples_leaf"], "candidate1_validation_MAE": current[1]["validation_MAE"], "selection_path": selected_ref["path"], "selection_sha256": selected_ref["sha256"], "spec_sha256": spec_ref["sha256"]})
        mapping.append({"kind": "RF_selection", **selected_ref})
    exact_grid(nn_ids); exact_grid(rf_ids, neural=False)
    if (len(nn_candidates), len(nn_choices), len(rf_candidates), len(rf_choices), len(mapping)) != (400, 200, 80, 40, 720): raise ValueError("Exact400/200+80/40 original metadata coverage required")
    interruptions = failure_evidence()
    group_choices = []
    for method in sorted(METHODS):
        for panel in sorted(PANELS):
            for regime in ("NC_only", "standard_only"):
                group = [row for row in nn_choices if (row["method_id"], row["panel"], row["regime"]) == (method, panel, regime)]
                count = Counter(row["chosen_learning_rate"] for row in group)
                group_choices.append({"method_id": method, "panel": panel, "regime": regime, "selected_cells": len(group), "learning_rate_0_001_count": count[0.001], "learning_rate_0_0003_count": count[0.0003], "chosen_best_epoch_zero_based_counts": dict(sorted(Counter(row["chosen_best_epoch_zero_based"] for row in group).items())), "completed_epoch_count": None, "early_stopped_count": None, "epochs_at_cap_count": None})
    summary = {"created_at": datetime.now(timezone.utc).isoformat(), "actual_NN_candidate_fits": 400, "actual_NN_selections": 200, "actual_RF_candidate_fits": 80, "actual_RF_selections": 40, "actual_original_metadata_map_rows": 720, "actual_extra_interrupted_attempts": 2, "all_validation_winners_match_frozen_selections": True, "candidate_order_tie_break": "lower candidate_index", "NN_chosen_learning_rate_counts": dict(sorted(Counter(row["chosen_learning_rate"] for row in nn_choices).items())), "RF_chosen_min_samples_leaf_counts": dict(sorted(Counter(row["chosen_min_samples_leaf"] for row in rf_choices).items())), "NN_best_epoch_indexing": "zero-based, as stored by original source", "NN_completed_epoch_count": None, "NN_early_stopped_count": None, "NN_epochs_at_cap_count": None, "NN_cumulative_candidate_process_seconds": sum(row["elapsed_process_seconds"] for row in nn_candidates), "RF_cumulative_candidate_process_seconds": sum(row["elapsed_process_seconds"] for row in rf_candidates), "process_seconds_are_not_parallel_wall_time": True, "test_score_or_label_or_prediction_or_model_reads": 0, "reporter_training_map_recommended": False, "reporter_map_reason": "Frozen renderer hardcodes one IO interruption and training projection drops some validation fields/derived interruption provenance. Use this complete standalone hyperparameter report plus two-attempt sidecar; do not bind optional training_metadata_map as a full interruption account.", "source_barriers": {"NN": nn_barrier_ref, "RF": rf_barrier_ref}}
    for name, rows in (("nn-candidates", nn_candidates), ("nn-selections", nn_choices), ("rf-candidates", rf_candidates), ("rf-selections", rf_choices), ("nn-choice-counts", group_choices)):
        write(HERE / (name + ".json"), rows); csv_out(HERE / (name + ".csv"), rows)
    write(HERE / "training_metadata_map.original720.json", mapping)
    write(HERE / "interrupted-attempts.sidecar.json", interruptions)
    write(HERE / "summary.json", summary)
    write(HERE / "read-audit.json", {"scope": "explicit frozen barriers/specs/closed train-validation receipts and two original failure lineages only", "reads": READS, "actual_reads": len(READS), "actual_raw_training_or_validation_labels_reads": 0, "actual_model_weight_reads": 0, "actual_gold_or_prediction_or_test_score_reads": 0, "directory_scans_to_choose_results": 0})
    write(HERE / "provenance.json", {"NN_scientific_index": nn_index_ref, "RF_task_index": rf_index_ref, "barriers": summary["source_barriers"], "reporter_field_mapping": {"path": canonical(PROJECT / "reporting/FIELD-MAPPING.md"), "sha256": sha(PROJECT / "reporting/FIELD-MAPPING.md")}, "reporter_source": {"path": canonical(PROJECT / "reporting/report_builder.py"), "sha256": sha(PROJECT / "reporting/report_builder.py")}, "builder_source": {"path": canonical(__file__), "sha256": sha(__file__)}, "output_hashes": {p.name: sha(p) for p in HERE.iterdir() if p.is_file() and p.name not in ("provenance.json", "build.py")}})
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def failure_evidence():
    training, _ = meta(PROJECT / "administration/io-recovery01/eligible-training-freeze-index-v5.json", "eligible_training_contract_index")
    first = next(row for row in training["records"] if row["run_id"].endswith("__io_recovery01"))
    parent, parent_ref = meta(first["contract_path"], "IO_recovery_contract", first["contract_sha256"])
    original = parent["recovery_metadata"]
    old_spec, old_spec_ref = meta(original["original_fit_spec"]["path"], "original_IO_failed_spec", original["original_fit_spec"]["sha256"])
    terminal, terminal_ref = meta(original["original_terminal"]["path"], "original_IO_failed_terminal", original["original_terminal"]["sha256"])
    io_failed = []
    for index in (0, 1):
        path = local(old_spec["run_root"]) / ("candidate-" + str(index)) / "failed.json"
        if path.is_file():
            raw, file_ref = meta(path, "original_IO_candidate_failed_receipt"); io_failed.append(file_ref)
    chain, chain_ref = meta(PROJECT / "administration/cuda-recovery02-hostexit-v2/postjoint-v2-execution1/CUDA-ATTEMPT-CHAIN.json", "actual_CUDA_attempt_chain")
    archive_ref = chain["archive_manifest"]
    archive, archive_actual = meta(archive_ref["path"], "actual_CUDA_failed_tree_archive_manifest", archive_ref["sha256"])
    cuda_failed = []
    for tree in archive["trees"]:
        if not tree["original_root"].endswith("/" + chain["scientific_unit_id"]) or not tree["original_root"].endswith("/fits/" + chain["scientific_unit_id"]): continue
        for item in tree["entries"]:
            if item["relative_path"].replace("\\", "/") == "candidate-0/failed.json" and item["type"] == "file":
                raw, file_ref = meta(item["archive_path"], "original_archived_CUDA_candidate_failed_receipt", item["sha256"]); cuda_failed.append(file_ref)
    if chain.get("extra_interrupted_attempts") != 2 or not cuda_failed: raise ValueError("Two retained attempts and actual archivedCUDA failure metadata required")
    return {"actual_extra_interrupted_attempts": 2, "kind": "derived_evidence_sidecar_not_original_failed_json", "original_failed_json_files_found": len(io_failed) + len(cuda_failed), "original_failed_json_file_count_is_not_attempt_count": True, "attempts": [{"attempt_type": "IO_watchdog_interruption", "count": 1, "recovery_contract": parent_ref, "original_failed_spec": old_spec_ref, "original_failed_terminal": terminal_ref, "original_failed_json_refs": io_failed, "original_failed_json_absent": not io_failed, "never_fabricated_failed_json": True, "runtime_error_attribution": "Watchdog PermissionError/termination; source-recorded interrupted process retained"}, {"attempt_type": "CUDA_unknown_error", "count": 1, "attempt_chain": chain_ref, "full_archive_manifest": archive_actual, "original_archived_failed_json_refs": cuda_failed, "runtime_error_attribution": "CUDAunknown runtime error; native overall old exit remained unobserved, outer1 retained in chain"}], "reporter_optional_map_should_not_be_used_as_complete_interruption_account": True}


if __name__ == "__main__": main()
