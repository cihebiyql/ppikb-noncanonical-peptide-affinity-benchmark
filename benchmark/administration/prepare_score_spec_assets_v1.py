"""Prepare20 shared frozen-code scoring metadata specs, never execute scoring.

Only code/JSON manifests are read. Gold/input/cache/selection/weights/prediction
payloads are not opened or hashed; their expected digests come from manifests.
"""
from pathlib import Path
import json

import prepare_campaign as pc

BASE = Path(__file__).resolve().parent
PROJECT = BASE.parent
WSL = "/mnt/d/work/科研工作台/research-tasks/peptide-binding-nc-benchmark-20261021"


def wsl(path):
    return WSL + "/" + str(Path(path).relative_to(PROJECT)).replace("\\", "/")


if __name__ == "__main__":
    frozen_path = PROJECT / "evaluation" / "FROZEN-SCORER-v1.json"
    frozen = pc.read(frozen_path)
    manifest_path = PROJECT / "evaluation" / "X-cache-final-manifest-v2.json"
    if pc.sha(manifest_path) != frozen["X_cache_final_manifest_sha256"]:
        raise ValueError("Final X-cache metadata changed")
    entries = pc.read(manifest_path)["entries"]
    datasets = pc.read(PROJECT / "evaluation" / "authorized-manifest-v2.json")["datasets"]
    for name, expected in frozen["evaluation_code_sha256"].items():
        if pc.sha(PROJECT / "evaluation" / name) != expected:
            raise ValueError("Frozen scorer source changed")
    runner = PROJECT / "execution" / "runner.py"
    if pc.sha(runner) != frozen["frozen_runner_sha256"]:
        raise ValueError("Frozen training runner changed")
    parity = PROJECT / "evaluation" / "forward-y-parity-receipt.json"
    if pc.sha(parity) != frozen["forward_y_proof_sha256"]:
        raise ValueError("Fixed no-y-forward metadata proof changed")
    panel_folders = {"source_test": "source_peptide_dependency_cold", "target_test": "target_reference_homology_cold"}
    gold = {}
    for key, panel in panel_folders.items():
        metadata = pc.read(PROJECT / "execution" / "prepared-panels-wsl-v3" / panel / "panel-manifest.json")
        gold[key] = (metadata["sealed_label_source"], metadata["sealed_label_source_sha256"])
    external_meta = pc.read(PROJECT / "external-validation" / "scoring-views-v1" / "scoring-view-manifest.json")
    reference = next(row for row in external_meta["artifacts"] if Path(row["path"]).name == "gold75.jsonl")
    gold["external75"] = (WSL + "/external-validation/scoring-views-v1/gold75.jsonl", reference["sha256"])
    supplemental_meta = pc.read(PROJECT / "external-validation" / "scoring-supplement13-v1" / "root-accepted-manifest.json")
    gold["supplement13"] = (WSL + "/external-validation/scoring-supplement13-v1/gold/gold13.jsonl", supplemental_meta["gold_policy"]["accepted_gold_copy_sha256"])
    output = BASE / "score-spec-assets-v1"
    output.mkdir(exist_ok=False)
    mapping = {}
    rows = []
    dataset_ids = {"source_test": "internal-test", "target_test": "internal-test", "external75": "external75-PTM-reference-view-v1", "supplement13": "postfreeze-supplement13-reference-view-v1"}
    for entry in entries:
        data = entry["dataset_id"]
        method = entry["method_id"]
        source = datasets[data]
        if entry["input_sha256"] != source["input_sha256"]:
            raise ValueError("Input metadata identity differs")
        spec = {"dataset_id": dataset_ids[data], "holdout_kind": {"source_test": "internal_source_peptide_dependency_cold", "target_test": "internal_target_reference_homology_cold", "external75": "retrospective_PTM_reference_view_75_primary67_conditional8_cold2_not_family_cold", "supplement13": "separate_retrospective13_source_declared_chemical_cold_target_related_heavy_reference"}[data], "selection_split_id": panel_folders.get(data), "method_id": method, "runner": wsl(runner), "methods_root": WSL + "/methods", "adapter_tree_sha256": entry["adapter_tree_sha256"], "input_rows": source["wsl_path"], "input_rows_sha256": source["input_sha256"], "cache_path": entry["wsl_cache_path"], "cache_manifest": wsl(Path(entry["cache_manifest_path"])), "cache_manifest_sha256": entry["cache_manifest_sha256"], "forward_y_proof": wsl(parity), "forward_y_proof_sha256": frozen["forward_y_proof_sha256"], "gold_rows": gold[data][0], "gold_rows_sha256": gold[data][1], "output_root": WSL + "/formal-runs-gpu-v4/scores", "device": "cuda:0", "gpu_explicitly_authorized": True, "gpu_allocator_budget_bytes": 3 * 1024**3, "cpu_threads": 2, "batch_size": 32, "prepared_metadata_only_not_scoring_authorization": True}
        path = output / (data + "__" + method + ".json")
        pc.write_new(path, spec)
        role = "internal" if data in panel_folders else data
        ref = {"role": role, "dataset_id": spec["dataset_id"], "cache_dataset_id": data, "method_id": method, "n": entry["n"], "path": wsl(path), "sha256": pc.sha(path)}
        mapping[(data, method)] = ref
        rows.append(ref)
    if len(rows) != 20:
        raise ValueError("Exactly20 shared cache/data/method specs required")
    execution = pc.read(PROJECT / "control" / "gpu-fit-specs-v4" / "execution-index.json")
    units = {}
    for unit in execution["units"]:
        internal = "source_test" if unit["split_id"] == panel_folders["source_test"] else "target_test"
        method = unit["method_id"]
        units[unit["unit_id"]] = {"selection": {"path": unit["selection_path"], "sha256": None}, "checkpoint_sha256": None, "score_specs": [mapping[(internal, method)], mapping[("external75", method)], mapping[("supplement13", method)]]}
    code_files = [{"path": wsl(PROJECT / "evaluation" / name), "sha256": expected} for name, expected in frozen["evaluation_code_sha256"].items()]
    code_files.append({"path": wsl(runner), "sha256": frozen["frozen_runner_sha256"]})
    plan = {"schema": "nc-score-stage-prepared-plan.v1", "root_authorized_after_barrier": False, "authorization": None, "barrier": {"path": WSL + "/formal-runs-gpu-v4/all-selections-frozen.json", "sha256": None}, "barrier_audit": None, "code_files": code_files, "pool_output_root": WSL + "/control/scoring-launch-v1/pool-runs", "units": units, "prepared_from_frozen_metadata": True, "actual_gold_reads": 0, "actual_input_payload_reads": 0, "actual_cache_payload_reads": 0, "actual_selection_reads": 0, "actual_checkpoint_reads": 0, "scoring_authorized": False}
    pc.write_new(output / "evaluation-plan.prebarrier.json", plan)
    pc.write_new(output / "score-spec-assets-manifest.json", {"created_at": pc.now(), "shared_score_specs": 20, "future_unit_contracts": 200, "future_score_calls": 600, "expected_prediction_rows": 265800, "scoring_authorized": False, "source_frozen_scorer": {"path": str(frozen_path), "sha256": pc.sha(frozen_path)}, "cache_metadata_manifest": {"path": str(manifest_path), "sha256": pc.sha(manifest_path)}, "specs": rows, "scientific_payload_files_opened": 0, "models_launched": 0})
    print(json.dumps({"shared_specs": len(rows), "unit_mappings": len(units), "scoring_authorized": False, "scientific_payload_reads": 0}))
