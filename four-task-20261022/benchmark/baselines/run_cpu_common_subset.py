"""Align frozen CPU predictions to PepInter component test IDs; no fitting."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from run_cpu_baselines import aggregate, json_write, macro_metrics, metrics, save_predictions


ROOT = Path(__file__).resolve().parents[1]
SOURCE_MANIFEST = ROOT/"methods"/"interaction"/"cached-component"/"manifest.metadata-revision2.json"
OUTPUT = ROOT/"runs"/"cpu-common-subset-v1"


def sha(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024*1024), b""):
            value.update(block)
    return value.hexdigest()


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    source_manifest_sha = sha(SOURCE_MANIFEST)
    manifest = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    reference_receipts, run_records = [], []
    for view in manifest["views"]:
        source_path = Path(view["path"])
        if sha(source_path) != view["sha256"]:
            raise ValueError("cached subset CSV hash differs from revision2 manifest")
        reference = pd.read_csv(source_path, keep_default_na=False, float_precision="round_trip")
        if reference.row_id.duplicated().any():
            raise ValueError("cached subset has duplicate observation IDs")
        reference = reference[reference.split == "test"].reset_index(drop=True)
        if len(reference) != view["split_counts"]["test"]:
            raise ValueError("reference test count differs from manifest")
        if set(reference.evaluation_stratum) != {"standard20_control"}:
            raise ValueError("this manifest was declared standard20-only; do not silently broaden chemistry coverage")
        source_view = view["id"].removesuffix("_exact_cached_subset")
        output_view_id = source_view + "__pepinter_cached_test_common"
        view_root = OUTPUT/output_view_id
        view_root.mkdir(parents=True, exist_ok=True)
        contract_path = view_root/"task-contract.json"
        contract = {"schema": "four-task.cpu-common-test-subset.v1", "created_at": datetime.now(timezone.utc).isoformat(),
                    "view_id": output_view_id, "task": "affinity", "endpoint": "pKd", "source_training_view": source_view,
                    "cached_manifest_path": str(SOURCE_MANIFEST), "cached_manifest_sha256": source_manifest_sha,
                    "reference_csv_path": str(source_path), "reference_csv_sha256": view["sha256"],
                    "reference_test_n": len(reference), "reference_test_strata": reference.evaluation_stratum.value_counts().to_dict(),
                    "cached_subset_all_splits_n": view["rows"], "cpu_training_view_all_splits_n": view["full_view_rows"],
                    "training_budget_alignment": False, "test_membership_alignment": True,
                    "is_eight_method_all_common_subset": False, "no_nc_or_ptm_coverage_claim": True,
                    "seeds": list(range(10)), "new_fits": 0, "new_model_predictions": 0, "model_selection_changes": 0,
                    "code_path": str(Path(__file__)), "code_sha256": sha(__file__),
                    "metric_implementation_path": str(Path(__file__).with_name("run_cpu_baselines.py")),
                    "metric_implementation_sha256": sha(Path(__file__).with_name("run_cpu_baselines.py")),
                    "label_policy": "require exactly equal float64 labels by row_id; no alternate gold labels or tolerance-based rewriting",
                    "comparison_boundary": "aligned test denominator only; CPU training data still full view, PepInter component training coverage smaller; supervised backbone exposure separate"}
        json_write(contract_path, contract)
        reference[["row_id", "source", "group_id", "evaluation_stratum", "label"]].to_csv(view_root/"frozen-test-reference.csv", index=False, float_format="%.17g")
        matching = list((ROOT/"runs"/"cpu-v2"/source_view).glob("*/seed-*/result.json"))
        if len(matching) != 50:
            raise ValueError("expected five models times ten seeds in frozen CPU source")
        for result_path in sorted(matching):
            source_result = json.loads(result_path.read_text(encoding="utf-8"))
            previous_prediction = source_result["splits"]["test"]
            prediction_path = Path(previous_prediction["prediction_path"])
            before = sha(prediction_path)
            if before != previous_prediction["prediction_sha256"]:
                raise ValueError("source prediction hash differs from original training receipt")
            full = pd.read_csv(prediction_path, keep_default_na=False, float_precision="round_trip")
            if full.row_id.duplicated().any():
                raise ValueError("source test prediction duplicated IDs")
            if not set(reference.row_id).issubset(set(full.row_id)):
                raise ValueError("cached test IDs are not a subset of this frozen CPU test panel")
            selected = full.set_index("row_id").loc[reference.row_id].reset_index()
            if not np.array_equal(selected.label.to_numpy(), reference.label.to_numpy()):
                difference = np.abs(selected.label.to_numpy()-reference.label.to_numpy())
                raise ValueError(f"cached/frozen labels disagree: {int(sum(difference != 0))} rows; maximum {max(difference)}")
            if selected.group_id.tolist() != reference.group_id.tolist():
                raise ValueError("reference group membership differs from frozen CPU labels")
            if selected.evaluation_stratum.tolist() != reference.evaluation_stratum.tolist():
                raise ValueError("reference chemistry strata differ from frozen CPU predictions")
            predicted = selected.prediction.to_numpy()
            run = view_root/source_result["model"]/f"seed-{source_result['seed']:02d}"
            run.mkdir(parents=True, exist_ok=True)
            subset_path = run/"test-predictions.csv"
            save_predictions(subset_path, selected, predicted, .5, False)
            macro, groups = macro_metrics(selected, predicted, False, .5, "affinity", "group_id")
            json_write(run/"test-group-metrics.json", groups)
            values = metrics(selected.label.to_numpy(), predicted, False)
            after = sha(prediction_path)
            if before != after:
                raise ValueError("original prediction changed during subset evaluation")
            record = {"view_id": output_view_id, "task": "affinity", "model": source_result["model"], "seed": source_result["seed"],
                      "status": "succeeded", "completed_at": datetime.now(timezone.utc).isoformat(), "contract_sha256": sha(contract_path),
                      "source_training_result_path": str(result_path), "source_training_result_sha256": sha(result_path),
                      "source_prediction_path": str(prediction_path), "source_prediction_sha256_before": before,
                      "source_prediction_sha256_after": after, "source_prediction_unchanged": before == after,
                      "reference_label_exact_match": True, "reference_group_exact_match": True, "source_test_n": len(full),
                      "subset_test_n": len(selected), "new_fits": 0, "new_model_predictions": 0,
                      "splits": {"test": {"metrics": values, "macro": macro,
                                           "subgroups": {"evaluation_stratum": [{"value": "standard20_control", **values}]},
                                           "prediction_path": str(subset_path), "prediction_sha256": sha(subset_path)}}}
            json_write(run/"result.json", record)
            run_records.append(record)
            reference_receipts.append({"view_id": output_view_id, "model": record["model"], "seed": record["seed"],
                                       "source_prediction_path": str(prediction_path), "sha256_before": before, "sha256_after": after,
                                       "reference_label_exact_match": True, "source_n": len(full), "subset_n": len(selected)})
    if sha(SOURCE_MANIFEST) != source_manifest_sha:
        raise ValueError("component reference manifest changed during analysis")
    aggregate(OUTPUT)
    json_write(OUTPUT/"execution-receipt.json", {"completed_at": datetime.now(timezone.utc).isoformat(), "view_count": len(manifest["views"]),
                                               "evaluated_model_seed_results": len(run_records), "new_fits": 0, "new_model_predictions": 0,
                                               "all_original_prediction_sha_unchanged": all(row["sha256_before"] == row["sha256_after"] for row in reference_receipts),
                                               "all_reference_labels_exact_match": True,
                                               "eight_method_all_common_subset": False, "training_budget_aligned": False,
                                               "reference_receipts": reference_receipts})
    print(json.dumps({"evaluated_model_seed_results": len(run_records), "new_fits": 0, "new_model_predictions": 0,
                      "reference_labels_exact_match": True, "original_predictions_unchanged": True}))


if __name__ == "__main__":
    main()
