"""Post-hoc discordance sensitivity from unchanged frozen test predictions."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT/"runs"/"cpu-sensitivity-v1"
METADATA = ROOT/"data"/"ppikb_preserved_input_metadata.jsonl"
TRAINING = ROOT/"runs"/"cpu-v2"
VIEWS = ["ppikb_kd_source_cold_scope_v2", "ppikb_kd_target_cold_scope_v2"]


def sha(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b""):
            result.update(chunk)
    return result.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def flag_index():
    records = {}
    with METADATA.open(encoding="utf-8") as stream:
        for line in stream:
            record = json.loads(line)
            row_id = record["record_id"]
            value = record["residue_class_graph_discordance"]
            if type(value) is not bool:
                raise ValueError("discordance flag must be explicit boolean, never inferred from a truthy string")
            item = {"row_id": row_id, "flag": value, "evaluation_stratum": record["evaluation_stratum"]}
            if row_id in records and records[row_id] != item:
                raise ValueError("conflicting metadata rows")
            records[row_id] = item
    return records


def memberships(frame):
    category = frame.evaluation_stratum
    result = {"all": np.ones(len(frame), dtype=bool),
              "NC_all_including_PTM": (category != "standard20_control").to_numpy(),
              "PTM_any_including_mixed": category.isin(["PTM", "synthetic_and_PTM"]).to_numpy()}
    for value in ("synthetic_D_backbone", "PTM", "synthetic_and_PTM", "other_NC", "standard20_control"):
        result[value] = (category == value).to_numpy()
    return result


def calculate(y, predicted):
    n = len(y)
    return {"n": n,
            "mae": float(mean_absolute_error(y, predicted)) if n else None,
            "rmse": float(math.sqrt(mean_squared_error(y, predicted))) if n else None,
            "r2": float(r2_score(y, predicted, force_finite=False)) if n > 1 and np.ptp(y) > 0 else None}


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    metadata_sha = sha(METADATA)
    flags = flag_index()
    index_frame = pd.DataFrame(flags.values()).sort_values("row_id")
    index_frame.to_csv(OUTPUT/"flag-index.csv", index=False)
    contract = {"schema": "four-task.cpu-discordance-sensitivity.v1", "created_at": datetime.now(timezone.utc).isoformat(),
                "metadata_path": str(METADATA), "metadata_sha256": metadata_sha, "code_path": str(Path(__file__)), "code_sha256": sha(__file__),
                "views": VIEWS, "metadata_rows": len(flags), "metadata_flagged_rows": int(index_frame.flag.sum()),
                "new_fits": 0, "new_model_predictions": 0, "model_selection_changes": 0,
                "analysis": "post-hoc test-only exclusion with unchanged predictions; training and validation still contain flagged observations",
                "filters": ["main_all_flags_retained", "sensitivity_test_flag_excluded"],
                "stratum_rollups_overlap": ["NC_all_including_PTM", "PTM_any_including_mixed"],
                "seeds": list(range(10)), "r2_undefined": "null for n<2 or constant true labels",
                "independent_verification": "separate standard-library CSV parser and math.fsum implementation"}
    write_json(OUTPUT/"task-contract.json", contract)
    metric_rows, reference_files, counts, effect_sources = [], [], [], []
    for view_id in VIEWS:
        expected_membership = None
        for result_path in sorted((TRAINING/view_id).glob("*/seed-*/result.json")):
            result = json.loads(result_path.read_text(encoding="utf-8"))
            stored = result["splits"]["test"]
            prediction_path = Path(stored["prediction_path"])
            before = sha(prediction_path)
            if before != stored["prediction_sha256"]:
                raise ValueError("original prediction hash differs from its training result receipt")
            frame = pd.read_csv(prediction_path, float_precision="round_trip", keep_default_na=False)
            if any(row_id not in flags for row_id in frame.row_id):
                raise ValueError("test prediction lacks a required metadata flag; no missing-to-false fallback")
            frame["flag"] = frame.row_id.map(lambda row_id: flags[row_id]["flag"])
            if any(flags[row.row_id]["evaluation_stratum"] != row.evaluation_stratum for row in frame.itertuples()):
                raise ValueError("prediction/metadata chemistry stratum mismatch")
            signature = [(row.row_id, row.evaluation_stratum, row.flag) for row in frame.itertuples()]
            if expected_membership is None:
                expected_membership = signature
                frame[["row_id", "evaluation_stratum", "flag"]].to_csv(OUTPUT/f"{view_id}-test-membership.csv", index=False)
            elif expected_membership != signature:
                raise ValueError("models/seeds have different test row membership or order")
            y, predicted = frame.label.to_numpy(), frame.prediction.to_numpy()
            for stratum, stratum_mask in memberships(frame).items():
                main_n = int(sum(stratum_mask))
                for filter_name, mask in (("main_all_flags_retained", stratum_mask),
                                          ("sensitivity_test_flag_excluded", stratum_mask & ~frame.flag.to_numpy())):
                    values = calculate(y[mask], predicted[mask])
                    metric_rows.append({"view_id": view_id, "model": result["model"], "seed": result["seed"], "stratum": stratum,
                                        "filter": filter_name, "original_stratum_n": main_n, "excluded_flagged_n": main_n-values["n"], **values})
                    if result["seed"] == 0 and result["model"] == "constant":
                        counts.append({"view_id": view_id, "stratum": stratum, "filter": filter_name,
                                       "original_stratum_n": main_n, "excluded_flagged_n": main_n-values["n"], "retained_n": values["n"]})
            after = sha(prediction_path)
            if before != after:
                raise ValueError("original prediction changed during sensitivity calculation")
            reference_files.append({"view_id": view_id, "model": result["model"], "seed": result["seed"], "path": str(prediction_path),
                                    "sha256_before": before, "sha256_after": after, "unchanged": before == after,
                                    "result_path": str(result_path), "result_sha256": sha(result_path)})
    metrics_frame = pd.DataFrame(metric_rows)
    metrics_frame.to_csv(OUTPUT/"per-seed-metrics.csv", index=False, float_format="%.17g")
    long = metrics_frame.melt(id_vars=["view_id", "model", "seed", "stratum", "filter", "n", "original_stratum_n", "excluded_flagged_n"], value_vars=["mae", "rmse", "r2"], var_name="metric", value_name="value")
    long.groupby(["view_id", "model", "stratum", "filter", "metric"], dropna=False).agg(mean=("value", "mean"), sd=("value", "std"), valid_seed_count=("value", "count"), seed_count=("seed", "nunique"), n=("n", "first"), excluded_flagged_n=("excluded_flagged_n", "first")).reset_index().to_csv(OUTPUT/"mean-sd-metrics.csv", index=False, float_format="%.17g")
    pd.DataFrame(counts).to_csv(OUTPUT/"test-denominators.csv", index=False)
    effect_path = ROOT/"data"/"ppikb_effect_metadata_silver_source_cold.csv"
    effect_sha = sha(effect_path)
    effects = pd.read_csv(effect_path, keep_default_na=False)
    for row in effects.itertuples():
        if row.reference_row_id not in flags or row.variant_row_id not in flags:
            raise ValueError("effect pair source ID absent from metadata")
        ref_flag, mut_flag = flags[row.reference_row_id]["flag"], flags[row.variant_row_id]["flag"]
        effect_sources.append({"row_id": row.row_id, "split": row.split, "reference_row_id": row.reference_row_id,
                               "variant_row_id": row.variant_row_id, "reference_flag": ref_flag, "variant_flag": mut_flag,
                               "either_source_flag": ref_flag or mut_flag, "evaluation_stratum": row.evaluation_stratum})
    effect_frame = pd.DataFrame(effect_sources)
    effect_frame.to_csv(OUTPUT/"effect-pair-flag-membership.csv", index=False)
    effect_summary = []
    for name, frame in [("all", effect_frame)] + list(effect_frame.groupby("split")):
        effect_summary.append({"split": name, "pairs": len(frame), "either_source_flag_pairs": int(frame.either_source_flag.sum()),
                               "either_source_flag_fraction": float(frame.either_source_flag.mean()),
                               "reference_flag_pairs": int(frame.reference_flag.sum()), "variant_flag_pairs": int(frame.variant_flag.sum())})
    write_json(OUTPUT/"effect-pair-flag-summary.json", {"source_path": str(effect_path), "source_sha256": effect_sha,
                                                       "pairs": effect_summary, "pair_filter_or_retraining_performed": False})
    if sha(METADATA) != metadata_sha or sha(effect_path) != effect_sha:
        raise ValueError("source metadata or effect view changed")
    receipt = {"schema": "four-task.cpu-sensitivity-result.v1", "completed_at": datetime.now(timezone.utc).isoformat(),
               "contract_sha256": sha(OUTPUT/"task-contract.json"), "metadata_flagged_rows": int(index_frame.flag.sum()),
               "per_seed_metric_rows": len(metrics_frame), "referenced_prediction_files": len(reference_files),
               "all_original_predictions_unchanged": all(row["unchanged"] for row in reference_files), "new_fits": 0,
               "new_model_predictions": 0, "training_still_contains_flags": True, "reference_predictions": reference_files}
    write_json(OUTPUT/"result-record.json", receipt)
    print(json.dumps({key: receipt[key] for key in ("metadata_flagged_rows", "per_seed_metric_rows", "referenced_prediction_files", "all_original_predictions_unchanged", "new_fits", "training_still_contains_flags")}))


if __name__ == "__main__":
    main()
