"""Summarize exact metadata result records with the unchanged central validator.

Only contract/result/receipt JSON metadata is read. No registry is overwritten,
no raw scientific payload is opened, and pending review never counts accepted.
"""
import argparse
import importlib.util
import json
from collections import Counter, defaultdict
from pathlib import Path

import prepare_campaign as pc
from archive_stage_result import metadata


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", required=True, help="JSON object records:[{contract:{path,sha256},result:{path,sha256}}]")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    index = pc.read(args.index)
    if index.get("root_result_archival_authorized") is not True:
        raise PermissionError("Root metadata archival authorization absent")
    output = pc.inside_admin(args.out)
    output.mkdir(exist_ok=False)
    module_spec = importlib.util.spec_from_file_location("authoritative_reproduction_validator", pc.STANDARD / "validate_reproduction.py")
    validator = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(validator)
    rows = []
    matrices = defaultdict(lambda: defaultdict(list))
    auxiliary_matrices = defaultdict(lambda: defaultdict(list))
    errors = []
    for item in index["records"]:
        contract = metadata(item["contract"])
        result = metadata(item["result"])
        contract_file = Path(item["contract"]["path"])
        if str(contract_file).startswith("/mnt/d/"):
            contract_file = Path("D:/" + str(contract_file)[len("/mnt/d/"):])
        report = validator.validate(contract, result, contract_bytes=contract_file.read_bytes(), check_files=False)
        uid = contract["run_id"]
        pc.write_new(output / (uid + ".central-validation.json"), report)
        if not report["valid"]:
            errors.append({"run_id": uid, "family": "RF_auxiliary" if contract["benchmark_metadata"]["method_id"] == "RF-Classic" else "NN_core", "errors": report["errors"]})
        coordinate = contract["benchmark_metadata"]
        stage = "evaluation" if "evaluation_stage" in contract else "training"
        family = "RF_auxiliary" if coordinate["method_id"] == "RF-Classic" else "NN_core"
        group_store = auxiliary_matrices if family == "RF_auxiliary" else matrices
        group_store[stage][(coordinate["method_id"], coordinate["split_id"], coordinate["regime_id"])].append(coordinate["seed"])
        rows.append({"task_id": contract["task_id"], "run_id": uid, "stage": stage, "family": family, "paper_count_contribution": 0 if family == "RF_auxiliary" else 1, "method_id": coordinate["method_id"], "split_id": coordinate["split_id"], "regime_id": coordinate["regime_id"], "seed": coordinate["seed"], "lifecycle_status": result["lifecycle_status"], "reproduction_level": result["reproduction_level"], "scope_coverage": result["scope_coverage"], "review_status": result["review"]["status"], "central_valid": report["valid"], "central_accepted": report["valid_for_acceptance"], "training_lineage_recorded": bool(result.get("stage_lineage", {}).get("training_stage")), "contract": item["contract"], "result": item["result"]})
    stage_coverage = {}
    for stage, groups in matrices.items():
        stage_coverage[stage] = {"groups": len(groups), "records": sum(len(values) for values in groups.values()), "complete200_matrix": len(groups) == 20 and all(sorted(values) == list(range(10)) for values in groups.values())}
    auxiliary_coverage = {stage: {"groups": len(groups), "records": sum(len(values) for values in groups.values()), "complete40_matrix": len(groups) == 4 and all(sorted(values) == list(range(10)) for values in groups.values())} for stage, groups in auxiliary_matrices.items()}
    summary = {"schema": "nc-stage-result-archive-summary.v1", "at": pc.now(), "source_index_path": str(Path(args.index).resolve()), "source_index_sha256": pc.sha(args.index), "record_count": len(rows), "central_valid_count": sum(row["central_valid"] for row in rows), "central_accepted_count": sum(row["central_accepted"] for row in rows), "stage_coverage": stage_coverage, "auxiliary_RF_coverage": auxiliary_coverage, "distinct_core_papers": len({row["task_id"] for row in rows if row["family"] == "NN_core"}), "auxiliary_RF_paper_contribution": 0, "status_counts": dict(Counter(row["lifecycle_status"] for row in rows)), "errors": errors, "raw_payload_reads": 0, "registry_changes": 0, "full_paper_claim": False, "scope": "Metadata administrative validation only; prior source/producer payload-hash checks are linked, not repeated as --check-files here"}
    pc.write_new(output / "summary.json", summary)
    pc.write_new(output / "result-record-index.json", {"records": rows})
    complete_evaluation = stage_coverage.get("evaluation", {}).get("complete200_matrix") is True and all(row["training_lineage_recorded"] for row in rows if row["stage"] == "evaluation" and row["family"] == "NN_core")
    complete_rf = auxiliary_coverage.get("evaluation", {}).get("complete40_matrix") is True and all(row["training_lineage_recorded"] for row in rows if row["stage"] == "evaluation" and row["family"] == "RF_auxiliary")
    core_accepted = all(row["central_accepted"] for row in rows if row["family"] == "NN_core")
    rf_accepted = bool([row for row in rows if row["family"] == "RF_auxiliary"]) and all(row["central_accepted"] for row in rows if row["family"] == "RF_auxiliary")
    core_errors = [entry for entry in errors if entry["family"] == "NN_core"]
    pc.write_new(output / "batch-result-adoption-proposal.json", {"batch": "peptide-binding-nc-benchmark-20261022", "ready_for_root_adoption": not core_errors and complete_evaluation and core_accepted, "full_requested_NN_grid_with_training_lineage": complete_evaluation, "auxiliary_RF_complete_and_accepted": complete_rf and rf_accepted, "full_extended_NN_plus_RF_grid_complete": not errors and complete_evaluation and core_accepted and complete_rf and rf_accepted, "auxiliary_RF_paper_contribution": 0, "existing_old62_unchanged": True, "actual_registry_writes": 0, "records": rows})
    print(json.dumps({key: summary[key] for key in ("record_count", "central_valid_count", "central_accepted_count", "stage_coverage", "raw_payload_reads", "registry_changes")}))
    raise SystemExit(0 if not errors else 2)
