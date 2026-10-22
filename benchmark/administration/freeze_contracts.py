"""Apply explicit factual adoption overlays, validate centrally, freeze ready units.

This is administrative only: it does not run contract commands or launch models.
Missing PDFs, unknown launch facts and expired windows remain blocking.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
from pathlib import Path

import prepare_campaign as pc


def merge(base, patch):
    result = copy.deepcopy(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def run(adoption_path, output_path, freeze=False):
    adoption = pc.read(adoption_path)
    index = pc.read(adoption["draft_index_path"])
    output = pc.inside_admin(output_path)
    if output.exists():
        raise FileExistsError("Use a new revision, never overwrite frozen/blocked evidence")
    output.mkdir(parents=True)
    source = pc.STANDARD / "validate_reproduction.py"
    module_spec = importlib.util.spec_from_file_location("authoritative_reproduction_validator", source)
    validator = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(validator)
    records = []
    moment = pc.now()
    for row in index["runs"]:
        original = pc.read(row["contract_draft_path"])
        candidate = original
        for overlay in (adoption.get("shared", {}), adoption.get("methods", {}).get(row["method_id"], {}), adoption.get("splits", {}).get(row["split_id"], {}), adoption.get("units", {}).get(row["run_id"], {})):
            candidate = merge(candidate, overlay)
        protected_clock_fields = ("first_substantive_started_at", "earliest_associated_preparation_at", "wall_clock_cap_hours", "original_deadline_at", "additional_deadlines_at", "effective_deadline_at", "prior_window_expired", "retry_resets_clock")
        if any(candidate["timing"].get(key) != original["timing"].get(key) for key in protected_clock_fields):
            raise ValueError("Clock changes require a separately reviewed scientific-scope revision, not a freeze overlay")
        if candidate["run_id"] != row["run_id"]:
            raise ValueError("Adoption cannot silently change run identity")
        if candidate["execution"]["seeds"] != [row["seed"]]:
            raise ValueError("Adoption cannot silently change seed coverage")
        candidate.update(is_template=False, contract_status="frozen", frozen_at=moment)
        folder = output / row["run_id"]
        folder.mkdir()
        report = validator.validate(candidate, check_files=True, contract_directory=folder)
        ready = bool(report["valid_for_execution"])
        report_path = folder / "central-validator-report.json"
        pc.write_new(report_path, report)
        record = {key: row[key] for key in ("run_id", "method_id", "split_id", "regime_id", "seed")}
        record.update(valid_for_execution=ready, frozen=bool(ready and freeze), validation_path=str(report_path), validation_sha256=pc.sha(report_path), actual_model_runs=0)
        if ready and freeze:
            contract_path = folder / "task-contract.json"
            pc.write_new(contract_path, candidate)
            record.update(contract_path=str(contract_path), contract_sha256=pc.sha(contract_path))
            binding_path = folder / "execution-validation.json"
            binding = {"valid_for_execution": True, "contract_sha256": record["contract_sha256"], "central_validation_path": str(report_path), "central_validation_sha256": pc.sha(report_path), "central_validator_path": str(source), "central_validator_sha256": pc.sha(source), "validated_at": moment, "scope": "Bound central validation of this exact issued contract; root must still verify remote files/capacity immediately before launch"}
            pc.write_new(binding_path, binding)
            record.update(validation_binding_path=str(binding_path), validation_binding_sha256=pc.sha(binding_path))
            result_template = pc.read(pc.STANDARD / "result-record.template.json")
            result_template.update(task_id=candidate["task_id"], run_id=candidate["run_id"], contract_path=str(contract_path), contract_sha256=record["contract_sha256"])
            result_template["benchmark_metadata"] = copy.deepcopy(candidate["benchmark_metadata"])
            comparisons = []
            for endpoint in candidate["targets"]:
                comparison = copy.deepcopy(result_template["metric_comparisons"][0])
                for key in ("target_id", "paper_endpoint", "metric", "metric_definition", "statistical_unit", "denominator", "unit", "paper_value"):
                    comparison[key] = copy.deepcopy(endpoint.get(key))
                comparison.update(comparability="not_comparable", actual_value=None, passed=None, reason="Not executed; frozen new-dataset endpoint awaiting actual predictions and scoring evidence")
                comparisons.append(comparison)
            result_template["metric_comparisons"] = comparisons
            pc.write_new(folder / "result-record.template.json", result_template)
        else:
            candidate.update(is_template=True, contract_status="draft", frozen_at=None)
            candidate["administrative_blocker_note"] = "Candidate evaluated with real facts but not issued as a frozen contract; see central-validator-report.json. No bypass or execution performed."
            pc.write_new(folder / "task-contract.unissued-draft.json", candidate)
        records.append(record)
    summary = {"schema": "peptide-binding.nc-benchmark.contract-freeze.v1", "created_at": moment, "adoption_path": str(Path(adoption_path).resolve()), "adoption_sha256": pc.sha(adoption_path), "draft_index_path": adoption["draft_index_path"], "draft_index_sha256": pc.sha(adoption["draft_index_path"]), "validator_path": str(source), "validator_sha256": pc.sha(source), "freeze_requested": freeze, "units": len(records), "ready_units": sum(r["valid_for_execution"] for r in records), "frozen_units": sum(r["frozen"] for r in records), "blocked_units": sum(not r["valid_for_execution"] for r in records), "actual_model_runs": 0, "records": records, "launch_gate": "Even a valid local contract does not verify skipped remote hashes or current remote capacity. Root must verify actual remote artifacts/resources/process-control and remaining timeout immediately before launch."}
    pc.write_new(output / "freeze-index.json", summary)
    print(json.dumps({key: summary[key] for key in ("units", "ready_units", "frozen_units", "blocked_units", "actual_model_runs")}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adoption", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--freeze", action="store_true", help="Issue only centrally valid frozen contracts; never run any command")
    args = parser.parse_args()
    run(args.adoption, args.out, args.freeze)
