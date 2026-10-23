"""Recalculate primary test metrics solely from frozen per-row predictions."""
import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata
from sklearn.metrics import average_precision_score, roc_auc_score


def finite(value):
    if value is None:
        return None
    return float(value) if math.isfinite(float(value)) else None


def correlation(x, y):
    if len(x) < 2 or np.ptp(x) == 0 or np.ptp(y) == 0:
        return None
    xc, yc = x - np.mean(x), y - np.mean(y)
    return finite(np.dot(xc, yc) / math.sqrt(np.dot(xc, xc) * np.dot(yc, yc)))


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify(root):
    checked, differences, files = 0, [], []
    for path in sorted(root.glob("*/*/seed-*/result.json")):
        result = json.loads(path.read_text(encoding="utf-8"))
        for split, stored in result["splits"].items():
            pred_path = Path(stored["prediction_path"])
            file_sha = sha(pred_path)
            if file_sha != stored["prediction_sha256"]:
                differences.append({"path": str(pred_path), "problem": "prediction_sha256_mismatch"})
                continue
            frame = pd.read_csv(pred_path, float_precision="round_trip")
            y, p = frame.label.to_numpy(), frame.prediction.to_numpy()
            expected = stored["metrics"]
            if "mae" in expected:
                squared = (p - y) ** 2
                reference = {"mae": finite(np.abs(p-y).sum()/len(y)), "rmse": finite(math.sqrt(squared.sum()/len(y))),
                             "bias": finite((p-y).sum()/len(y)), "pearson": correlation(y,p),
                             "spearman": correlation(rankdata(y), rankdata(p)),
                             "r2": finite(1-squared.sum()/((y-y.mean())**2).sum()) if len(y)>1 and np.ptp(y)>0 else None}
                if "direction_accuracy_nonzero" in expected:
                    nonzero = y != 0
                    reference["direction_accuracy_nonzero"] = finite(np.mean(np.sign(y[nonzero]) == np.sign(p[nonzero]))) if np.any(nonzero) else None
                    reference["nonzero_effect_n"] = int(sum(nonzero))
            else:
                binary = p >= frame.threshold.to_numpy()
                tp = int(sum(binary & (y == 1))); tn = int(sum(~binary & (y == 0)))
                fp = int(sum(binary & (y == 0))); fn = int(sum(~binary & (y == 1)))
                denom = (tp+fp)*(tp+fn)*(tn+fp)*(tn+fn)
                two = len(np.unique(y)) == 2
                reference = {"brier": finite(np.mean((p-y)**2)), "f1": finite(2*tp/(2*tp+fp+fn)) if 2*tp+fp+fn else 0.,
                             "mcc": finite((tp*tn-fp*fn)/math.sqrt(denom)) if denom else (0. if two else None),
                             "balanced_accuracy": finite((tp/(tp+fn)+tn/(tn+fp))/2) if two else None,
                             "auroc": finite(roc_auc_score(y,p)) if two else None,
                             "auprc": finite(average_precision_score(y,p)) if two else None}
            for name, actual in reference.items():
                wanted = expected[name]
                checked += 1
                if (actual is None) != (wanted is None) or (actual is not None and abs(actual-wanted) > 1e-10):
                    differences.append({"path": str(path), "split": split, "metric": name, "stored": wanted, "recomputed": actual})
            files.append({"path": str(pred_path), "sha256": file_sha, "n": len(frame)})
    report = {"checked_metric_cells": checked, "prediction_files": len(files), "differences": differences, "passed": bool(checked) and not differences,
              "verification_code_sha256": sha(Path(__file__)), "files": files}
    (root/"independent-recalculation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("checked_metric_cells", "prediction_files", "differences", "passed")}, ensure_ascii=False))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    raise SystemExit(verify(parser.parse_args().root))
