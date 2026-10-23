"""Apply frozen CPU winners to explicitly selected external-only task views."""
import argparse
import hashlib
import json
import os
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from run_cpu_baselines import (FEATURE_VERSION, aggregate, build_features, is_binary,
                               is_effect, json_write, macro_metrics, metrics, now,
                               predict, resolve_view, save_predictions, sha)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--external-view", required=True)
    parser.add_argument("--training-view-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    view = next(value for value in manifest["views"] if value["id"] == args.external_view)
    if view.get("status") not in {"external_ready", "ready", "frozen"}:
        raise ValueError("external input view is not frozen/ready")
    training_contract_path = args.training_view_dir / "task-contract.json"
    training_contract = json.loads(training_contract_path.read_text(encoding="utf-8"))
    if training_contract["feature_audit"]["version"] != FEATURE_VERSION:
        raise ValueError("training and external feature definitions differ")
    if view["task"] != training_contract["task"]:
        raise ValueError("training/external task mismatch; no implicit effect/affinity conversion")
    # Endpoint is supplied explicitly in task views; no mixing of pKd with pAffinity or DDG.
    training_endpoint = training_contract.get("endpoint")
    if training_endpoint and training_endpoint != view.get("endpoint"):
        if training_endpoint not in view.get("compatible_training_endpoints", []):
            raise ValueError("training and external endpoints differ without explicit data-protocol compatibility")
    path = resolve_view(view, args.manifest)
    input_sha = sha(path)
    if view.get("sha256") and input_sha != view["sha256"]:
        raise ValueError("external view SHA mismatch")
    frame = pd.read_csv(path, keep_default_na=False, float_precision="round_trip")
    for original, canonical in ((view.get("label_column", "label"), "label"), (view.get("group_column", "group_id"), "group_id")):
        if original != canonical:
            frame[canonical] = frame[original]
    if "split" not in frame:
        frame["split"] = "external"
    frame["split"] = frame["split"].replace({"external_test": "external"})
    if set(frame.split) != {"external"}:
        raise ValueError("external runner requires external-only rows")
    if frame.row_id.duplicated().any():
        raise ValueError("external row IDs duplicated")
    frame["label"] = pd.to_numeric(frame.label, errors="raise").astype(float)
    if not np.isfinite(frame.label).all():
        raise ValueError("nonfinite external labels")
    x, feature_audit = build_features(frame, view["task"])
    _, feature_counts = np.unique(x, axis=0, return_counts=True)
    feature_audit["unique_feature_vectors"] = len(feature_counts)
    feature_audit["rows_sharing_feature_vector"] = int(sum(feature_counts[feature_counts > 1]))
    feature_audit["feature_vector_sha256"] = hashlib.sha256(x.tobytes()).hexdigest()
    if is_effect(view["task"]):
        feature_audit["effect_rows_with_zero_sequence_change_features"] = int(sum(np.all(x[:, -174:] == 0, axis=1)))
    if x.shape[1] != training_contract["feature_audit"]["shape"][1]:
        raise ValueError("external feature dimension differs")
    binary = is_binary(view["task"])
    view_id = view["id"] + "__from__" + training_contract["view_id"]
    view_root = args.output / view_id
    view_root.mkdir(parents=True, exist_ok=True)
    contract = {"schema": "four-task.cpu-external-contract.v1", "created_at": now(), "view_id": view_id,
                "task": view["task"], "endpoint": view.get("endpoint"), "input_path": str(path),
                "training_endpoint": training_endpoint,
                "endpoint_compatibility_from_data_protocol": view.get("compatible_training_endpoints", []),
                "input_sha256": input_sha, "training_contract_path": str(training_contract_path),
                "training_contract_sha256": sha(training_contract_path), "feature_audit": feature_audit,
                "training_or_validation_on_external": False, "threshold_selection_on_external": False,
                "source_independence_status": view.get("independence_status", view.get("independence", "not_certified_by_this_runner")),
                "split_aliases": {"external_test": "external"},
                "gpu": False, "threads": 2, "pid": os.getpid(), "code_sha256": sha(__file__)}
    contract_path = view_root / "task-contract.json"
    if contract_path.exists():
        prior = json.loads(contract_path.read_text(encoding="utf-8"))
        if prior["input_sha256"] != input_sha or prior["training_contract_sha256"] != contract["training_contract_sha256"]:
            raise ValueError("refusing overwrite of changed external contract")
    else:
        json_write(contract_path, contract)
    count = 0
    for result_path in sorted(args.training_view_dir.glob("*/seed-*/result.json")):
        trained = json.loads(result_path.read_text(encoding="utf-8"))
        if trained["status"] != "succeeded":
            continue
        started = time.time()
        candidate_path = result_path.parent / f"candidate-{trained['selected_candidate']}.joblib"
        candidates = json.loads((result_path.parent / "candidates.json").read_text(encoding="utf-8"))
        selected = next(row for row in candidates if row["candidate"] == trained["selected_candidate"])
        if sha(candidate_path) != selected["model_sha256"]:
            raise ValueError("frozen winner model hash mismatch")
        model = joblib.load(candidate_path)
        with threadpool_limits(limits=2):
            predicted = predict(model, x, binary)
        if not np.isfinite(predicted).all():
            raise ValueError("nonfinite external prediction")
        threshold = trained["threshold"] if binary else 0.5
        run = view_root / trained["model"] / f"seed-{trained['seed']:02d}"
        run.mkdir(parents=True, exist_ok=True)
        prediction_path = run / "external-predictions.csv"
        save_predictions(prediction_path, frame, predicted, threshold, binary)
        macro, groups = macro_metrics(frame, predicted, binary, threshold, view["task"], "group_id")
        json_write(run / "external-group-metrics.json", groups)
        values = metrics(frame.label.to_numpy(), predicted, binary, threshold, is_effect(view["task"]))
        subgroups = {}
        for column in ("source", "chemistry_class", "residue_class", "evaluation_stratum"):
            if column in frame:
                subgroups[column] = []
                for value, indexes in frame.groupby(column).groups.items():
                    subgroups[column].append({"value": str(value), **metrics(frame.loc[indexes, "label"].to_numpy(), predicted[np.asarray(indexes)], binary, threshold, is_effect(view["task"]))})
        record = {"view_id": view_id, "task": view["task"], "model": trained["model"], "seed": trained["seed"],
                  "status": "succeeded", "threshold": threshold if binary else None, "completed_at": now(),
                  "contract_sha256": sha(contract_path), "training_result_sha256": sha(result_path),
                  "model_sha256": sha(candidate_path), "elapsed_seconds": time.time() - started,
                  "splits": {"external": {"metrics": values, "macro": macro, "subgroups": subgroups, "prediction_path": str(prediction_path),
                                            "prediction_sha256": sha(prediction_path)}}}
        json_write(run / "result.json", record)
        count += 1
    aggregate(args.output)
    json_write(view_root / "execution-status.json", {"completed_at": now(), "prediction_runs": count, "required_seed_count": 10,
                                                     "source_model_counts": count // 10, "new_fits": 0})
    print(json.dumps({"view_id": view_id, "prediction_runs": count, "new_fits": 0}))
    return 0 if count else 2


if __name__ == "__main__":
    raise SystemExit(main())
