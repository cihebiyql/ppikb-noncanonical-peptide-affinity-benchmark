"""Independent identity/label/prediction extraction checks using only stdlib."""
import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT/"runs"/"cpu-common-subset-v1"


def sha(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            value.update(block)
    return value.hexdigest()


def read(path):
    with Path(path).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def main():
    errors, files, checked_rows = [], [], 0
    contract_paths = list(OUTPUT.glob("*/task-contract.json"))
    for contract_path in contract_paths:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        if sha(contract["cached_manifest_path"]) != contract["cached_manifest_sha256"]:
            errors.append({"contract": str(contract_path), "problem": "reference_manifest_hash_changed"})
        if sha(contract["reference_csv_path"]) != contract["reference_csv_sha256"]:
            errors.append({"contract": str(contract_path), "problem": "reference_csv_hash_changed"})
        reference = {row["row_id"]: row for row in read(contract["reference_csv_path"]) if row["split"] == "test"}
        model_seeds = {}
        for path in sorted(contract_path.parent.glob("*/seed-*/result.json")):
            result = json.loads(path.read_text(encoding="utf-8"))
            original_path = Path(result["source_prediction_path"])
            if sha(original_path) != result["source_prediction_sha256_before"] or result["source_prediction_sha256_before"] != result["source_prediction_sha256_after"]:
                errors.append({"path": str(path), "problem": "source_prediction_hash_changed"})
            original = {row["row_id"]: row for row in read(original_path)}
            subset_path = Path(result["splits"]["test"]["prediction_path"])
            subset = read(subset_path)
            if sha(subset_path) != result["splits"]["test"]["prediction_sha256"]:
                errors.append({"path": str(path), "problem": "subset_prediction_hash_changed"})
            if len(subset) != len(reference) or {row["row_id"] for row in subset} != set(reference):
                errors.append({"path": str(path), "problem": "cached_test_membership_mismatch"})
            for row in subset:
                row_id = row["row_id"]
                source = original[row_id]
                gold = reference[row_id]
                for column in ("label", "prediction"):
                    if float(row[column]) != float(source[column]):
                        errors.append({"row_id": row_id, "problem": f"extracted_{column}_changed"})
                if float(row["label"]) != float(gold["label"]):
                    errors.append({"row_id": row_id, "problem": "frozen_reference_label_mismatch"})
                if row["evaluation_stratum"] != "standard20_control":
                    errors.append({"row_id": row_id, "problem": "unexpected_nc_ptm_coverage"})
                checked_rows += 1
            model_seeds.setdefault(result["model"], []).append(result["seed"])
            files.append({"path": str(subset_path), "n": len(subset), "sha256": sha(subset_path)})
        if len(model_seeds) != 5 or any(sorted(seeds) != list(range(10)) for seeds in model_seeds.values()):
            errors.append({"contract": str(contract_path), "problem": "model_or_seed_coverage_mismatch"})
    result = {"passed": not errors, "errors": errors, "prediction_files": len(files), "checked_subset_rows": checked_rows,
              "new_fits": 0, "new_model_predictions": 0, "original_predictions_unchanged": not errors,
              "independent_implementation": "stdlib csv.DictReader, builtin float and SHA256; no training/scoring code imported",
              "code_sha256": sha(__file__), "eight_method_all_common_subset": False}
    (OUTPUT/"independent-membership-verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("passed", "errors", "prediction_files", "checked_subset_rows", "new_fits")}))
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
