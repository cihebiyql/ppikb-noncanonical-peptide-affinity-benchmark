"""Train auditable manual-feature baselines on frozen four-task CSV views."""
from __future__ import annotations

import os
for _name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ[_name] = "2"
os.environ["CUDA_VISIBLE_DEVICES"] = ""

import argparse
import csv
import hashlib
import json
import math
import platform
import sys
import time
import traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import scipy
from scipy.stats import spearmanr
import sklearn
from sklearn.dummy import DummyClassifier, DummyRegressor
from sklearn.ensemble import ExtraTreesClassifier, ExtraTreesRegressor
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import average_precision_score, balanced_accuracy_score, brier_score_loss
from sklearn.metrics import f1_score, matthews_corrcoef, r2_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits
import plm_binary_features

AA = "ACDEFGHIKLMNPQRSTVWY"
AA_INDEX = {a: i for i, a in enumerate(AA)}
SEEDS = list(range(10))
FEATURE_VERSION = plm_binary_features.FEATURE_VERSION
ROOT = Path(__file__).resolve().parents[1]


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def json_write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    tmp.replace(path)


def clean_num(value):
    if value is None:
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def text_value(row, *names):
    for name in names:
        value = row.get(name, "")
        if value is not None and not (isinstance(value, float) and math.isnan(value)) and str(value):
            return str(value)
    return ""


def seq_features(seq):
    """Unknown/lowercase symbols stay unknown; do not canonicalize chemical identity."""
    features = np.zeros(87, dtype=np.float32)
    n = len(seq)
    if not n:
        features[22] = 1.0
        return features
    counts = Counter(seq)
    for aa, i in AA_INDEX.items():
        features[i] = counts[aa] / n
    features[20] = sum(value for char, value in counts.items() if char not in AA_INDEX) / n
    features[21] = math.log1p(n)
    for left, right in zip(seq, seq[1:]):
        if left in AA_INDEX and right in AA_INDEX:
            bucket = (AA_INDEX[left] * 20 + AA_INDEX[right]) % 64
            features[23 + bucket] += 1.0 / max(1, n - 1)
    return features


def is_binary(task):
    return is_contact(task) or any(word in task.lower() for word in ("class", "interaction", "binding_binary", "binary"))


def is_contact(task):
    return "contact" in task.lower() or "site" in task.lower()


def is_effect(task):
    return any(word in task.lower() for word in ("effect", "delta", "ddg"))


def build_features(frame, task):
    return plm_binary_features.build_features(frame, task)


def models(binary):
    return {
        "constant": [{"strategy": "prior"}, {"strategy": "uniform"}] if binary else [{"strategy": "mean"}, {"strategy": "median"}],
        "linear": [{"C": 0.1}, {"C": 1.0}] if binary else [{"alpha": 0.1}, {"alpha": 10.0}],
        "random_forest": [{"n_estimators": 48, "max_depth": 8, "min_samples_leaf": 3}, {"n_estimators": 64, "max_depth": 14, "min_samples_leaf": 2}],
        "extra_trees": [{"n_estimators": 48, "max_depth": 8, "min_samples_leaf": 3}, {"n_estimators": 64, "max_depth": 14, "min_samples_leaf": 2}],
        "hist_gradient_boosting": [{"max_iter": 60, "max_leaf_nodes": 15, "learning_rate": 0.05}, {"max_iter": 90, "max_leaf_nodes": 31, "learning_rate": 0.1}],
    }


def make_model(name, params, seed, binary):
    if name == "constant":
        return DummyClassifier(random_state=seed, **params) if binary else DummyRegressor(**params)
    if name == "linear":
        estimator = LogisticRegression(random_state=seed, max_iter=1500, class_weight="balanced", **params) if binary else Ridge(**params)
        return make_pipeline(StandardScaler(), estimator)
    if name == "random_forest":
        cls = RandomForestClassifier if binary else RandomForestRegressor
        return cls(random_state=seed, n_jobs=2, max_features="sqrt", **params)
    if name == "extra_trees":
        cls = ExtraTreesClassifier if binary else ExtraTreesRegressor
        return cls(random_state=seed, n_jobs=2, max_features="sqrt", **params)
    cls = HistGradientBoostingClassifier if binary else HistGradientBoostingRegressor
    # Explicitly disable internal train/validation reshuffling; only frozen validation selects.
    return cls(random_state=seed, early_stopping=False, **params)


def predict(model, x, binary):
    if not binary:
        return np.asarray(model.predict(x), dtype=np.float64)
    proba = model.predict_proba(x)
    classes = list(model.classes_)
    return np.asarray(proba[:, classes.index(1)] if 1 in classes else np.zeros(len(x)), dtype=np.float64)


def choose_threshold(y, pred):
    values = np.linspace(0.1, 0.9, 17)
    return float(max(values, key=lambda threshold: (matthews_corrcoef(y, pred >= threshold), -abs(threshold - 0.5))))


def metrics(y, pred, binary, threshold=0.5, effect=False):
    y, pred = np.asarray(y), np.asarray(pred)
    if not len(y):
        return {"n": 0}
    result = {"n": len(y)}
    if binary:
        two_classes = len(np.unique(y)) == 2
        cls = (pred >= threshold).astype(int)
        result.update({"auroc": clean_num(roc_auc_score(y, pred)) if two_classes else None,
                       "auprc": clean_num(average_precision_score(y, pred)) if two_classes else None,
                       "mcc": clean_num(matthews_corrcoef(y, cls)) if two_classes else None,
                       "f1": clean_num(f1_score(y, cls, zero_division=0)),
                       "balanced_accuracy": clean_num(balanced_accuracy_score(y, cls)) if two_classes else None,
                       "brier": clean_num(brier_score_loss(y, pred)), "threshold": threshold,
                       "positive_count": int(sum(y == 1))})
    else:
        valid_corr = len(y) >= 2 and np.ptp(y) > 0 and np.ptp(pred) > 0
        result.update({"mae": clean_num(np.mean(np.abs(y - pred))),
                       "rmse": clean_num(np.sqrt(np.mean((y - pred) ** 2))),
                       "bias": clean_num(np.mean(pred - y)),
                       "pearson": clean_num(np.corrcoef(y, pred)[0, 1]) if valid_corr else None,
                       "spearman": clean_num(spearmanr(y, pred).statistic) if valid_corr else None,
                       "r2": clean_num(r2_score(y, pred, force_finite=False)) if len(y) > 1 and np.ptp(y) > 0 else None})
        if effect:
            nonzero = y != 0
            result["direction_accuracy_nonzero"] = clean_num(np.mean(np.sign(y[nonzero]) == np.sign(pred[nonzero]))) if np.any(nonzero) else None
            result["nonzero_effect_n"] = int(sum(nonzero))
    return result


def macro_metrics(frame, pred, binary, threshold, task, group_column):
    rows = []
    for group, indexes in frame.groupby(group_column, sort=False).groups.items():
        local = frame.loc[indexes]
        rows.append({"group_id": str(group), **metrics(local["label"].to_numpy(), pred[local.index.to_numpy()], binary, threshold, is_effect(task))})
    names = [key for key in rows[0] if key not in {"n", "group_id", "threshold", "positive_count", "nonzero_effect_n"}] if rows else []
    means = {}
    for name in names:
        valid = [row[name] for row in rows if row.get(name) is not None]
        means[name] = {"mean": clean_num(np.mean(valid)) if valid else None, "valid_groups": len(valid)}
    return {"group_count": len(rows), "metrics": means}, rows


def save_predictions(path, frame, prediction, threshold, binary):
    cols = [c for c in ("row_id", "source", "split", "group_id", "endpoint", "chemistry_class", "residue_class", "evaluation_stratum", "label", "residue_index", "structure_id", "negative_source") if c in frame]
    output = frame[cols].copy()
    output["prediction"] = prediction
    if binary:
        output["predicted_class"] = (prediction >= threshold).astype(int)
        output["threshold"] = threshold
    output.to_csv(path, index=False, float_format="%.17g")


def resolve_view(view, manifest_path):
    value = view.get("path") or view.get("csv_path") or view.get("csv")
    path = Path(value)
    if path.is_absolute():
        return path
    candidates = [manifest_path.parent / path, ROOT / path]
    return next((p for p in candidates if p.exists()), candidates[0])


def audit_frame(frame, task):
    for col in ("row_id", "split", "label", "group_id"):
        if col not in frame:
            raise ValueError(f"required column missing: {col}")
    if frame.row_id.duplicated().any():
        raise ValueError("row_id must be unique inside task view")
    aliases = {"val": "validation", "valid": "validation"}
    frame["split"] = frame["split"].replace(aliases)
    if not set(frame.split).issubset({"train", "validation", "test", "external"}):
        raise ValueError("unrecognized split")
    counts = frame.split.value_counts().to_dict()
    if any(counts.get(part, 0) == 0 for part in ("train", "validation", "test")):
        raise ValueError(f"all frozen train/validation/test required; observed {counts}")
    if not np.isfinite(frame.label).all():
        raise ValueError("labels must be finite measured/declared task labels")
    overlap = int((frame.groupby("group_id").split.nunique() > 1).sum())
    if overlap:
        raise ValueError(f"{overlap} dependency groups cross split")
    if is_binary(task) and not set(frame.label).issubset({0, 1}):
        raise ValueError("binary labels must equal zero or one")
    return {"split_counts": counts, "group_count": int(frame.group_id.nunique()), "cross_split_group_count": overlap}


def run_view(view, manifest_path, output_root, deadline, models_requested=None):
    path = resolve_view(view, manifest_path)
    view_id = view.get("id") or view.get("view_id") or path.stem
    task = view["task"]
    view_root = output_root / view_id
    view_root.mkdir(parents=True, exist_ok=True)
    if view.get("sha256") and sha(path) != view["sha256"]:
        raise ValueError("view input SHA256 differs from frozen manifest")
    frame = pd.read_csv(path, keep_default_na=False, float_precision="round_trip")
    for original, canonical in ((view.get("label_column", "label"), "label"), (view.get("split_column", "split"), "split"), (view.get("group_column", "group_id"), "group_id")):
        if original != canonical:
            frame[canonical] = frame[original]
    frame["label"] = pd.to_numeric(frame["label"], errors="raise").astype(float)
    audit = audit_frame(frame, task)
    x, feature_audit = build_features(frame, task)
    np.savez_compressed(view_root / "features.npz", features=x, row_ids=frame.row_id.to_numpy(dtype=str))
    if x.nbytes > 1024 ** 3:
        raise MemoryError("feature matrix exceeds 1GiB per-view budget")
    parts = {p: np.flatnonzero(frame.split.to_numpy() == p) for p in ("train", "validation", "test", "external")}
    binary = is_binary(task)
    y = frame.label.to_numpy()
    if binary and len(np.unique(y[parts["train"]])) < 2:
        raise ValueError("binary training view has only one class")
    input_sha = sha(path)
    contract = {"schema": "four-task.cpu-baseline-contract.v1", "created_at": now(), "task": task, "view_id": view_id, "endpoint": view.get("endpoint"),
                "input_path": str(path), "input_sha256": input_sha, "manifest_sha256": sha(manifest_path),
                "code_sha256": sha(__file__), "feature_code_sha256": sha(plm_binary_features.__file__), "seeds": SEEDS, "split_seed_is_not_training_seed": True,
                "models": models(binary), "selection": "validation AUPRC (two classes), otherwise negative Brier" if binary else "validation MAE",
                "classification_threshold": "validation MCC on frozen 0.1..0.9 grid; ties closest to 0.5",
                "feature_audit": feature_audit, "data_audit": audit, "gpu": False, "max_threads": 2,
                "python": sys.version, "sklearn": sklearn.__version__, "numpy": np.__version__, "scipy": scipy.__version__,
                "platform": platform.platform(), "pid": os.getpid(), "runtime_cap_seconds": deadline - time.time(),
                "source_reproduction_level": "new common-data training, not original paper result reproduction"}
    contract_path = view_root / "task-contract.json"
    if contract_path.exists():
        old = json.loads(contract_path.read_text(encoding="utf-8"))
        if old["input_sha256"] != input_sha or old["code_sha256"] != contract["code_sha256"]:
            raise ValueError("refusing to overwrite a run after input or implementation changed")
    else:
        json_write(contract_path, contract)
    all_metrics = []
    for name, grid in models(binary).items():
        if models_requested and name not in models_requested:
            continue
        for seed in SEEDS:
            run = view_root / name / f"seed-{seed:02d}"
            receipt = run / "result.json"
            if receipt.exists():
                prior = json.loads(receipt.read_text(encoding="utf-8"))
                if prior.get("status") == "succeeded":
                    all_metrics.append(prior)
                    continue
            if time.time() >= deadline:
                raise TimeoutError("CPU baseline wall-clock budget reached before next fit")
            run.mkdir(parents=True, exist_ok=True)
            started = time.time()
            print(f"[{now()}] START {view_id} {name} seed={seed}", flush=True)
            candidates = []
            best = None
            for candidate, params in enumerate(grid):
                if time.time() >= deadline:
                    raise TimeoutError("CPU baseline budget reached between candidate fits")
                est = make_model(name, params, seed, binary)
                fit_started = time.time()
                with threadpool_limits(limits=2):
                    est.fit(x[parts["train"]], y[parts["train"]])
                    vp = predict(est, x[parts["validation"]], binary)
                threshold = choose_threshold(y[parts["validation"]], vp) if binary else 0.5
                vm = metrics(y[parts["validation"]], vp, binary, threshold, is_effect(task))
                objective = vm["auprc"] if binary and vm["auprc"] is not None else (-vm["brier"] if binary else -vm["mae"])
                joblib.dump(est, run / f"candidate-{candidate}.joblib", compress=3)
                save_predictions(run / f"candidate-{candidate}-validation.csv", frame.iloc[parts["validation"]], vp, threshold, binary)
                item = {"candidate": candidate, "parameters": params, "validation_metrics": vm, "selection_objective": objective,
                        "fit_seconds": time.time() - fit_started, "model_sha256": sha(run / f"candidate-{candidate}.joblib")}
                candidates.append(item)
                json_write(run / "candidates.json", candidates)
                if best is None or objective > best[0]:
                    best = (objective, candidate, threshold, est)
            _, winner, threshold, est = best
            result = {"view_id": view_id, "task": task, "model": name, "seed": seed, "status": "succeeded", "selected_candidate": winner,
                      "contract_sha256": sha(contract_path), "input_sha256": input_sha, "threshold": threshold if binary else None,
                      "started_at_unix": started, "completed_at": now(), "elapsed_seconds": time.time() - started, "splits": {}}
            for part in ("validation", "test", "external"):
                indexes = parts[part]
                if not len(indexes):
                    continue
                with threadpool_limits(limits=2):
                    pred = predict(est, x[indexes], binary)
                if not np.isfinite(pred).all():
                    raise ValueError("nonfinite prediction")
                selected = frame.iloc[indexes].reset_index(drop=True)
                prediction_path = run / f"{part}-predictions.csv"
                save_predictions(prediction_path, selected, pred, threshold, binary)
                macro, groups = macro_metrics(selected, pred, binary, threshold, task, "group_id")
                json_write(run / f"{part}-group-metrics.json", groups)
                complex_macro = None
                if is_contact(task):
                    complex_macro, complex_rows = macro_metrics(selected, pred, binary, threshold, task, "structure_id")
                    json_write(run / f"{part}-complex-metrics.json", complex_rows)
                subgroup = {}
                for subgroup_column in ("source", "chemistry_class", "residue_class", "evaluation_stratum", "negative_source"):
                    if subgroup_column in selected:
                        subgroup[subgroup_column] = []
                        for value, ids in selected.groupby(subgroup_column).groups.items():
                            subgroup[subgroup_column].append({"value": str(value), **metrics(selected.loc[ids, "label"].to_numpy(), pred[np.asarray(ids)], binary, threshold, is_effect(task))})
                result["splits"][part] = {"metrics": metrics(y[indexes], pred, binary, threshold, is_effect(task)), "macro": macro, "per_complex_macro": complex_macro,
                                         "subgroups": subgroup, "prediction_path": str(prediction_path), "prediction_sha256": sha(prediction_path)}
            result["elapsed_seconds"] = time.time() - started
            json_write(receipt, result)
            all_metrics.append(result)
            print(f"[{now()}] DONE {view_id} {name} seed={seed} sec={result['elapsed_seconds']:.2f}", flush=True)
            aggregate(output_root)
    return all_metrics


def aggregate(root):
    rows = []
    for result_path in root.glob("*/*/seed-*/result.json"):
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if result.get("status") != "succeeded":
            continue
        for split, values in result["splits"].items():
            for metric, value in values["metrics"].items():
                if metric not in {"n", "threshold", "positive_count", "nonzero_effect_n"}:
                    rows.append({"view_id": result["view_id"], "task": result["task"], "model": result["model"], "seed": result["seed"],
                                 "split": split, "metric": metric, "value": value, "n": values["metrics"]["n"]})
    if not rows:
        return
    frame = pd.DataFrame(rows)
    frame.to_csv(root / "per-seed-metrics.csv", index=False)
    summary = frame.groupby(["view_id", "task", "model", "split", "metric"], dropna=False).agg(mean=("value", "mean"), sd=("value", "std"), valid_seed_count=("value", "count"), seed_count=("seed", "nunique"), n=("n", "first")).reset_index()
    summary.to_csv(root / "mean-sd-metrics.csv", index=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ROOT / "data" / "view_manifest.json")
    parser.add_argument("--output", type=Path, default=ROOT / "runs" / "plm-classification-contact-v1" / "heads")
    parser.add_argument("--view", action="append")
    parser.add_argument("--model", action="append")
    parser.add_argument("--max-seconds", type=int, default=5400)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    started = time.time()
    deadline = started + args.max_seconds
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    records = []
    for view in manifest["views"]:
        if args.view and view.get("id") not in args.view:
            continue
        if view.get("status") not in {"ready", "model_ready", "frozen"}:
            records.append({"view_id": view.get("id"), "status": "not_ready", "reason": view.get("reason")})
            continue
        try:
            run_view(view, args.manifest, args.output, deadline, args.model)
            records.append({"view_id": view.get("id"), "status": "succeeded"})
        except Exception as exc:
            print(traceback.format_exc(), flush=True)
            records.append({"view_id": view.get("id"), "status": "failed", "error": str(exc), "traceback": traceback.format_exc()})
        json_write(args.output / "execution-status.json", {"pid": os.getpid(), "started_at_unix": started, "updated_at": now(), "views": records})
    aggregate(args.output)
    json_write(args.output / "execution-status.json", {"pid": os.getpid(), "started_at_unix": started, "completed_at": now(), "elapsed_seconds": time.time() - started, "views": records})
    return 0 if records and all(row["status"] in {"succeeded", "not_ready"} for row in records) else 2


if __name__ == "__main__":
    raise SystemExit(main())
