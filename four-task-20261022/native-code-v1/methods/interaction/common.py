"""Data and evaluation contracts shared by the two interaction adapters."""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import math
from pathlib import Path

AA = frozenset("ACDEFGHIKLMNPQRSTVWY")


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def save(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path, rows, fields=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        fields = fields or (list(rows[0]) if rows else [])
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def first(row, keys, default=""):
    return next((row[k] for k in keys if row.get(k) not in (None, "")), default)


def read_view(path, split_column="split", sequence_projection="reject_nonstandard", require_labels=True):
    """Reject unknown chemistry; never uppercase, remove symbols, truncate or impute labels."""
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        source = list(csv.DictReader(handle))
    rows, excluded, seen = [], [], set()
    for index, raw in enumerate(source):
        row_id = first(raw, ["row_id", "obs_id", "sample_id", "pair_id"], str(index))
        if row_id in seen:
            raise ValueError("Duplicate observation ID: " + row_id)
        seen.add(row_id)
        peptide = first(raw, ["peptide_sequence", "peptide", "Epitope"])
        target = first(raw, ["target_sequence", "target", "protein_sequence", "Sequence"])
        split = first(raw, [split_column])
        if split == "val":
            split = "validation"
        if split == "external_test":
            split = "external"
        label = first(raw, ["label", "y", "pKd", "pAffinity", "DDG"])
        residue = first(raw, ["evaluation_stratum", "residue_class", "residue_category", "chemical_class", "residue_group"], "unknown")
        reasons = []
        if not peptide or not target:
            reasons.append("missing_peptide_or_target")
        if set(peptide + target) - AA:
            reasons.append("unsupported_residue_symbols")
        canonical_classes = {"standard", "standard20", "standard20_control", "standard20_supported", "canonical", "standard_amino_acids", "unmodified", "unknown", "standard_sequence_chemical_identity_unverified"}
        if sequence_projection == "reject_nonstandard" and residue not in canonical_classes:
            reasons.append("explicit_nonstandard_chemistry_not_encoded")
        if split not in {"train", "validation", "test", "external"}:
            reasons.append("missing_or_invalid_frozen_split")
        numeric_label = None
        if require_labels:
            try:
                numeric_label = float(label)
                if not math.isfinite(numeric_label):
                    raise ValueError("Nonfinite")
            except (TypeError, ValueError):
                reasons.append("missing_or_nonfinite_label")
        if reasons:
            excluded.append({"row_id": row_id, "reasons": "|".join(reasons), "residue_class": residue})
            continue
        rows.append({"row_id": row_id, "peptide": peptide, "target": target, "split": split,
                     "label": numeric_label, "group_id": first(raw, ["group_id", "target_id", "Protein", "complex_id"], sha_text(target)),
                     "source": first(raw, ["source", "dataset", "source_name"]), "residue_class": residue,
                     "endpoint": first(raw, ["endpoint", "label_type"]), "chemical_identity_encoded": False,
                     "standard_residue_sequence_retained": True,
                     "raw": raw})
    if not rows:
        raise ValueError("No observations satisfy the explicit model input contract")
    return rows, excluded


def sha_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def score(y, pred, task):
    import numpy as np
    from scipy import stats
    from sklearn import metrics
    y = np.asarray(y, dtype=float)
    pred = np.asarray(pred, dtype=float)
    if y.shape != pred.shape or not len(y) or not np.isfinite(y).all() or not np.isfinite(pred).all():
        raise ValueError("Scoring requires equally sized finite real arrays")
    result = {"n": int(len(y))}
    if task == "classification":
        if not set(y) <= {0., 1.}:
            raise ValueError("Classification labels must be explicit binary values")
        hard = pred >= .5
        two = len(np.unique(y)) == 2
        result.update(auroc=float(metrics.roc_auc_score(y, pred)) if two else None,
                      auprc=float(metrics.average_precision_score(y, pred)) if two else None,
                      f1=float(metrics.f1_score(y, hard, zero_division=0)),
                      mcc=float(metrics.matthews_corrcoef(y, hard)) if two else None,
                      balanced_accuracy=float(metrics.balanced_accuracy_score(y, hard)) if two else None,
                      brier=float(metrics.brier_score_loss(y, pred)), threshold=.5)
    else:
        err = pred - y
        variable = len(y) >= 2 and np.ptp(y) > 0 and np.ptp(pred) > 0
        result.update(mae=float(np.abs(err).mean()), rmse=float(np.sqrt((err * err).mean())), bias=float(err.mean()),
                      r2=float(metrics.r2_score(y, pred)) if len(y) >= 2 and np.ptp(y) > 0 else None,
                      pearson=float(stats.pearsonr(y, pred).statistic) if variable else None,
                      spearman=float(stats.spearmanr(y, pred).statistic) if variable else None)
        if task == "effect":
            clear = y != 0
            result["nonzero_sign_accuracy"] = float(np.mean(np.sign(y[clear]) == np.sign(pred[clear]))) if clear.any() else None
    return result


def prediction_rows(rows, predicted, seed, method):
    return [{"row_id": row["row_id"], "label": row["label"], "prediction": float(value), "split": row["split"],
             "source": row["source"], "endpoint": row["endpoint"], "group_id": row["group_id"],
             "residue_class": row["residue_class"], "chemical_identity_encoded": row["chemical_identity_encoded"],
             "method": method, "seed": seed} for row, value in zip(rows, predicted)]


def summarized(results):
    import numpy as np
    keys = sorted({key for row in results for key in row["metrics"] if key not in {"n", "threshold"}})
    output = {}
    for key in keys:
        vals = [r["metrics"][key] for r in results if r["metrics"].get(key) is not None]
        output[key] = {"mean": float(np.mean(vals)) if vals else None,
                       "sd": float(np.std(vals, ddof=1)) if len(vals) > 1 else None, "valid_seeds": len(vals)}
    return output
