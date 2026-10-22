"""Adopt the data owner's frozen-v1 facts into a new immutable draft revision."""
import copy
import json
from pathlib import Path

import prepare_campaign as pc

BASE = Path(__file__).resolve().parent
PROJECT = BASE.parent
FROZEN = PROJECT / "data-protocol" / "frozen-v1"


if __name__ == "__main__":
    config = pc.read(BASE / "campaign-config.current-facts-v1.json")
    manifest_path = FROZEN / "manifest.json"
    manifest = pc.read(manifest_path)
    for relative, expected in manifest["files"].items():
        if pc.sha(FROZEN / relative) != expected["sha256"]:
            raise ValueError("Frozen data byte mismatch: " + relative)
    sidecar = PROJECT / "model-audit" / "papers" / "primary-method-verification-sidecar-v2.json"
    if sidecar.exists():
        primary = {row["doi"].lower(): row for row in pc.read(sidecar)["models"]}
        for method in config["methods"]:
            paper = primary[method["paper_identity_key"]]
            method["identity"]["pdf"].update(path=paper["pdf_path"], sha256=paper["pdf_sha256"], version="version_of_record" if paper["pdf_path"] else "missing")
            method["identity"]["eligibility"]["evidence_paths"].append(str(sidecar))
            if paper["pdf_path"]:
                method["identity"]["missing_pdf_note"] = None
    definitions = {
        "MAE": "mean(abs(predicted_pKd-observed_pKd))",
        "RMSE": "sqrt(mean((predicted_pKd-observed_pKd)^2))",
        "Pearson": "Pearson product-moment correlation; null with reason if undersized/constant group",
        "Spearman": "Pearson correlation of average-tied ranks; null with reason if undersized/constant group",
        "R2": "1-SSE/SST; null with reason if observed group is undersized/constant",
    }
    splits = []
    for split_id in manifest["primary_panels"]:
        folder = FROZEN / "splits" / split_id
        summary = pc.read(folder / "summary.json")
        targets = []
        strata = {"all": summary["split_sizes"]["test"], **summary["strata_by_split"]["test"]}
        strata["NC_core"] = sum(value for key, value in summary["strata_by_split"]["test"].items() if key != "standard20_control")
        for stratum, count in strata.items():
            for metric, definition in definitions.items():
                target = copy.deepcopy(config["targets"][0])
                target.update(target_id=stratum + ":" + metric, metric=metric, metric_definition=definition, denominator=count, unit="pKd (-log10 molar Kd)" if metric in ("MAE", "RMSE") else "dimensionless", dataset_reference=split_id + "/test/" + stratum)
                target["evidence_paths"].append(str(folder / "summary.json"))
                targets.append(target)
        dataset = {
            "name": "PPIKB_NC2099_standard7520_Kd_frozen_v1", "version": "frozen-v1", "source_url": "https://www.nature.com/articles/s41597-026-07962-1", "license": None,
            "path": str(manifest_path), "manifest_sha256": pc.sha(manifest_path), "sha256": pc.sha(manifest_path), "sample_count": manifest["rows"],
            "statistical_unit": "measurement record; full declared source/chemical or target-reference components assigned together",
            "splits": {"train": str(folder / "train-ids.json"), "validation": str(folder / "validation-ids.json"), "test": str(folder / "test-ids.json"), "split_manifest_sha256": pc.sha(folder / "assignments.csv")},
            "preprocessing": "No label repair; all original9619 records retained; raw/atomic isomeric SMILES preserved; no peptide cap; annotations used for strata only; model protein prefix limits disclosed",
            "leakage_check": {"status": "verified_under_declared_panel_definition", "method": split_id, "evidence_paths": [str(FROZEN / "independent-leakage-verification.json"), str(folder / "summary.json")]},
            "integrity": "complete", "notes": "Frozen input/label metadata checked by byte SHA at preparation; actual remote training projections must still be hash-verified before launch. Source panel not70/15/15 due giant component; achieved counts preserved.",
            "frozen_files": [{"path": str(FROZEN / key), "sha256": manifest["files"][key]["sha256"]} for key in ("inputs.jsonl", "labels.jsonl", "quality-flags.jsonl", "residue-class-graph-discordance.json")],
            "actual_panel_counts": summary["split_sizes"], "actual_panel_strata": summary["strata_by_split"],
        }
        splits.append({"split_id": split_id, "datasets": [dataset], "contract_targets": targets, "summary_path": str(folder / "summary.json"), "summary_sha256": pc.sha(folder / "summary.json")})
    config["splits"] = splits
    config["data_frozen_manifest_path"] = str(manifest_path)
    config["data_frozen_manifest_sha256"] = pc.sha(manifest_path)
    config["known_pending_fields"] = ["stable task/linked historic IDs", "actual train/validation projection SHA and fit-spec path", "execution environment snapshot", "actual run_unit wrapper and remote process-control/resource gate", "per-unit command/log/timeout", "remaining2 genuine PDFs"]
    # prepare_campaign clones panel-specific targets supplied here; no target values invented.
    path = BASE / "campaign-config.frozen-data-facts-v2.json"
    pc.write_new(path, config)
    index = pc.prepare(path, BASE / "drafts-frozen-data-facts-v2")
    print(json.dumps({"drafts": index["planned_run_rows"], "frozen_data_manifest_sha256": pc.sha(manifest_path), "actual_model_runs": 0}))
