"""Independent stdlib-only verification of frozen-prediction sensitivity."""
import csv
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT/"runs"/"cpu-sensitivity-v1"


def sha(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            value.update(block)
    return value.hexdigest()


def read(path):
    with Path(path).open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def in_stratum(row, stratum):
    actual = row["evaluation_stratum"]
    if stratum == "all":
        return True
    if stratum == "NC_all_including_PTM":
        return actual != "standard20_control"
    if stratum == "PTM_any_including_mixed":
        return actual in {"PTM", "synthetic_and_PTM"}
    return actual == stratum


def calculate(rows):
    n = len(rows)
    if not n:
        return {"n": 0, "mae": None, "rmse": None, "r2": None}
    y, p = [float(row["label"]) for row in rows], [float(row["prediction"]) for row in rows]
    squared = math.fsum((b-a)**2 for a,b in zip(y,p))
    average = math.fsum(y)/n
    total = math.fsum((a-average)**2 for a in y)
    return {"n": n, "mae": math.fsum(abs(b-a) for a,b in zip(y,p))/n,
            "rmse": math.sqrt(squared/n), "r2": 1-squared/total if n>1 and max(y)>min(y) else None}


def main():
    record = json.loads((OUTPUT/"result-record.json").read_text(encoding="utf-8"))
    flags = {row["row_id"]: row["flag"] == "True" for row in read(OUTPUT/"flag-index.csv")}
    predictions = {}
    errors, checks = [], 0
    for item in record["reference_predictions"]:
        if sha(item["path"]) != item["sha256_before"] or item["sha256_before"] != item["sha256_after"]:
            errors.append({"path": item["path"], "error": "original_prediction_changed"})
        parsed = read(item["path"])
        predictions[(item["view_id"], item["model"], item["seed"])] = parsed
        original = json.loads(Path(item["result_path"]).read_text(encoding="utf-8"))["splits"]["test"]["metrics"]
        recomputed = calculate(parsed)
        for metric in ("mae", "rmse", "r2"):
            checks += 1
            wanted, actual = original[metric], recomputed[metric]
            if (wanted is None) != (actual is None) or (wanted is not None and abs(wanted-actual)>1e-10):
                errors.append({"path": item["result_path"], "error": "original_main_metric_does_not_match", "metric": metric})
    for item in read(OUTPUT/"per-seed-metrics.csv"):
        key = item["view_id"], item["model"], int(item["seed"])
        rows = [row for row in predictions[key] if in_stratum(row,item["stratum"])]
        if item["filter"] == "sensitivity_test_flag_excluded":
            rows = [row for row in rows if not flags[row["row_id"]]]
        actual = calculate(rows)
        for metric in ("n", "mae", "rmse", "r2"):
            wanted = float(item[metric]) if item[metric] else None
            value = actual[metric]
            checks += 1
            if (wanted is None) != (value is None) or (wanted is not None and abs(wanted-value)>1e-10):
                errors.append({"key": key, "stratum": item["stratum"], "filter": item["filter"], "metric": metric, "stored": wanted, "recomputed": value})
    effect = read(OUTPUT/"effect-pair-flag-membership.csv")
    for item in effect:
        actual = flags[item["reference_row_id"]] or flags[item["variant_row_id"]]
        checks += 1
        if actual != (item["either_source_flag"] == "True"):
            errors.append({"pair": item["row_id"], "error": "effect_flag_membership_mismatch"})
    result = {"passed": not errors, "checks": checks, "errors": errors, "prediction_files_sha_unchanged": len(predictions),
              "original_main_metric_cells_crosschecked": 3*len(predictions),
              "independent_implementation": "csv.DictReader, builtin float and math.fsum; no training code, pandas or sklearn imported",
              "code_sha256": sha(__file__), "new_fits": 0}
    (OUTPUT/"independent-verification.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("passed", "checks", "errors", "prediction_files_sha_unchanged", "new_fits")}))
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
