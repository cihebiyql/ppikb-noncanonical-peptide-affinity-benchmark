"""Summarize saved seed-level subgroup and group-macro metrics without refitting."""
import argparse
import json
from pathlib import Path

import pandas as pd


def summarize(root):
    subgroups, macros, runs = [], [], []
    for path in sorted(root.glob("*/*/seed-*/result.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("status") != "succeeded":
            continue
        runs.append({"view_id": record["view_id"], "task": record["task"], "model": record["model"], "seed": record["seed"],
                     "selected_candidate": record.get("selected_candidate"), "elapsed_seconds": record.get("elapsed_seconds")})
        for split, values in record["splits"].items():
            base = {"view_id": record["view_id"], "task": record["task"], "model": record["model"], "seed": record["seed"], "split": split}
            for subgroup_column, rows in values.get("subgroups", {}).items():
                for row in rows:
                    for metric, value in row.items():
                        if metric not in {"value", "n", "threshold", "positive_count", "nonzero_effect_n"}:
                            subgroups.append({**base, "subgroup_column": subgroup_column, "subgroup": row["value"], "n": row["n"], "metric": metric, "value": value})
            for metric, group_result in values.get("macro", {}).get("metrics", {}).items():
                macros.append({**base, "metric": metric, "value": group_result["mean"], "valid_groups": group_result["valid_groups"],
                               "all_groups": values["macro"]["group_count"]})
    pd.DataFrame(runs).to_csv(root / "selected-runs.csv", index=False)
    if subgroups:
        frame = pd.DataFrame(subgroups)
        frame.to_csv(root / "subgroup-per-seed-metrics.csv", index=False)
        keys = ["view_id", "task", "model", "split", "subgroup_column", "subgroup", "metric"]
        frame.groupby(keys, dropna=False).agg(mean=("value", "mean"), sd=("value", "std"), valid_seed_count=("value", "count"), seed_count=("seed", "nunique"), n=("n", "first")).reset_index().to_csv(root / "subgroup-mean-sd-metrics.csv", index=False)
    if macros:
        frame = pd.DataFrame(macros)
        frame.to_csv(root / "macro-per-seed-metrics.csv", index=False)
        frame.groupby(["view_id", "task", "model", "split", "metric"], dropna=False).agg(mean=("value", "mean"), sd=("value", "std"), valid_seed_count=("value", "count"), seed_count=("seed", "nunique"), valid_groups=("valid_groups", "first"), all_groups=("all_groups", "first")).reset_index().to_csv(root / "macro-mean-sd-metrics.csv", index=False)
    print(json.dumps({"run_receipts": len(runs), "subgroup_metric_cells": len(subgroups), "macro_metric_cells": len(macros)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    summarize(parser.parse_args().root)
