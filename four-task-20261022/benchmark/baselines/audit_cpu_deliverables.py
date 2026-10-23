"""Verify the complete CPU delivery against actual per-seed files and hashes."""
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRAIN_RUNS = ["cpu-v2", "cpu-additional-v1", "cpu-contact-v1", "cpu-effect-v1"]
EXTERNAL_RUNS = ["cpu-external-v1", "cpu-effect-external-v1"]
MODELS = {"constant", "linear", "random_forest", "extra_trees", "hist_gradient_boosting"}


def sha(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            value.update(block)
    return value.hexdigest()


def main():
    errors, receipts, contracts, outputs, coverage = [], [], {}, [], defaultdict(list)
    candidates = 0
    rows = 0
    frozen_codes = {sha(path): str(path) for path in (ROOT/"baselines"/"frozen-code").glob("*.py")}
    audits = []
    for run_id in TRAIN_RUNS + EXTERNAL_RUNS:
        run_root = ROOT/"runs"/run_id
        audit_path = run_root/"independent-recalculation.json"
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        audits.append({"run_id": run_id, "passed": audit["passed"], "checked_metric_cells": audit["checked_metric_cells"], "prediction_files": audit["prediction_files"]})
        if not audit["passed"]:
            errors.append({"run": run_id, "problem": "independent_metric_recalculation_failed"})
        for result_path in sorted(run_root.glob("*/*/seed-*/result.json")):
            record = json.loads(result_path.read_text(encoding="utf-8"))
            key = (run_id, record["view_id"], record["model"])
            coverage[key].append(record["seed"])
            contract_path = result_path.parent.parent.parent/"task-contract.json"
            actual_contract_sha = sha(contract_path)
            if actual_contract_sha != record["contract_sha256"]:
                errors.append({"path": str(result_path), "problem": "contract_hash_mismatch"})
            if str(contract_path) not in contracts:
                contract = json.loads(contract_path.read_text(encoding="utf-8"))
                if sha(Path(contract["input_path"])) != contract["input_sha256"]:
                    errors.append({"path": str(contract_path), "problem": "input_hash_mismatch"})
                if contract["code_sha256"] not in frozen_codes:
                    errors.append({"path": str(contract_path), "problem": "no_matching_frozen_execution_code"})
                contracts[str(contract_path)] = {"path": str(contract_path), "sha256": actual_contract_sha,
                                                  "code_snapshot": frozen_codes.get(contract["code_sha256"])}
            if run_id in TRAIN_RUNS:
                params = json.loads((result_path.parent/"candidates.json").read_text(encoding="utf-8"))
                if len(params) != 2:
                    errors.append({"path": str(result_path), "problem": "expected_two_validation_candidates"})
                for candidate in params:
                    weight = result_path.parent/f"candidate-{candidate['candidate']}.joblib"
                    if sha(weight) != candidate["model_sha256"]:
                        errors.append({"path": str(weight), "problem": "candidate_hash_mismatch"})
                    candidates += 1
            for split, item in record["splits"].items():
                path = Path(item["prediction_path"])
                if sha(path) != item["prediction_sha256"]:
                    errors.append({"path": str(path), "problem": "prediction_hash_mismatch"})
                with path.open(encoding="utf-8", newline="") as stream:
                    reader = csv.reader(stream)
                    next(reader)
                    n = sum(1 for _ in reader)
                if n != item["metrics"]["n"]:
                    errors.append({"path": str(path), "problem": "prediction_denominator_mismatch"})
                rows += n
                outputs.append({"path": str(path), "sha256": item["prediction_sha256"], "n": n})
            receipts.append({"run_id": run_id, "view_id": record["view_id"], "model": record["model"], "seed": record["seed"],
                             "path": str(result_path), "sha256": sha(result_path)})
    for key, seeds in coverage.items():
        if sorted(seeds) != list(range(10)):
            errors.append({"group": key, "problem": "missing_or_duplicate_seeds", "seeds": seeds})
    views = defaultdict(set)
    for run_id, view, model in coverage:
        views[(run_id, view)].add(model)
    for key, present in views.items():
        if present != MODELS:
            errors.append({"view": key, "problem": "model_set_incomplete", "models": sorted(present)})
    result = {"schema": "four-task.cpu-delivery-audit.v1", "completed_at": datetime.now(timezone.utc).isoformat(),
              "passed": not errors, "errors": errors, "training_views": sum(run in TRAIN_RUNS for run, _ in views),
              "external_application_views": sum(run in EXTERNAL_RUNS for run, _ in views),
              "selected_training_results": sum(row["run_id"] in TRAIN_RUNS for row in receipts),
              "external_model_applications": sum(row["run_id"] in EXTERNAL_RUNS for row in receipts),
              "candidate_fits": candidates, "selected_prediction_files": len(outputs), "selected_prediction_rows": rows,
              "metric_cells_independently_verified": sum(row["checked_metric_cells"] for row in audits),
              "independent_audits": audits, "contract_count": len(contracts), "contracts": list(contracts.values()),
              "seed_coverage": [{"run_id": key[0], "view_id": key[1], "model": key[2], "seeds": sorted(seeds)} for key,seeds in coverage.items()],
              "result_receipts": receipts, "selected_predictions": outputs,
              "excluded_diagnostic_run": "cpu-v1", "scientific_boundary": "manual sequence baselines; pilot/silver/local-variant/conditional external scopes retained"}
    output = ROOT/"baselines"/"DELIVERY-AUDIT.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("passed", "errors", "training_views", "external_application_views", "selected_training_results", "external_model_applications", "candidate_fits", "selected_prediction_files", "selected_prediction_rows", "metric_cells_independently_verified")}, ensure_ascii=False))
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
