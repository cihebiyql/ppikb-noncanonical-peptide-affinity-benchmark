"""Use exact cache dataset IDs and explicit panels; metadata only, no scoring."""
from pathlib import Path
import copy
import json

import prepare_campaign as pc

BASE = Path(__file__).resolve().parent
PROJECT = BASE.parent
WSL = "/mnt/d/work/科研工作台/research-tasks/peptide-binding-nc-benchmark-20261021"
PANELS = ("source_peptide_dependency_cold", "target_reference_homology_cold")


def wsl(path):
    return WSL + "/" + str(Path(path).relative_to(PROJECT)).replace("\\", "/")


if __name__ == "__main__":
    cache_index = PROJECT / "evaluation" / "X-cache-final-manifest-v2.json"
    caches = pc.read(cache_index)["entries"]
    source_registry_path = PROJECT / "evaluation" / "authorized-manifest-v2.json"
    registry = pc.read(source_registry_path)["datasets"]
    frozen = pc.read(PROJECT / "evaluation" / "FROZEN-SCORER-v1.json")
    if pc.sha(cache_index) != frozen["X_cache_final_manifest_sha256"]:
        raise ValueError("Final metadata cache registry changed")
    output = BASE / "score-spec-assets-v2"
    output.mkdir(exist_ok=False)
    mapping, specs, verified = {}, [], []
    for cache in caches:
        data, method = cache["dataset_id"], cache["method_id"]
        manifest = Path(cache["cache_manifest_path"])
        if pc.sha(manifest) != cache["cache_manifest_sha256"]:
            raise ValueError("Individual cache metadata changed")
        meta = pc.read(manifest)
        source = registry[data]
        if meta["dataset_id"] != data or meta["method_id"] != method or meta["input_sha256"] != source["input_sha256"] or meta["input_sha256"] != cache["input_sha256"]:
            raise ValueError("Cache/input identity differs")
        allowed_panels = (PANELS[0],) if data == "source_test" else (PANELS[1],) if data == "target_test" else PANELS
        old_spec = BASE / "score-spec-assets-v1" / (data + "__" + method + ".json")
        for panel in allowed_panels:
            spec = pc.read(old_spec)
            spec.update(dataset_id=data, selection_split_id=panel, input_rows=source["wsl_path"], input_rows_sha256=source["input_sha256"])
            if spec["dataset_id"] != meta["dataset_id"] or spec["input_rows_sha256"] != meta["input_sha256"] or spec["input_rows"] != source["wsl_path"]:
                raise ValueError("Explicit score/cache/input canonical identity differs")
            file = output / (data + "__" + panel + "__" + method + ".json")
            pc.write_new(file, spec)
            role = "internal" if data in ("source_test", "target_test") else data
            ref = {"role": role, "dataset_id": data, "method_id": method, "selection_split_id": panel, "n": cache["n"], "path": wsl(file), "sha256": pc.sha(file)}
            mapping[(data, method, panel)] = ref
            specs.append(ref)
            verified.append({"spec_path": wsl(file), "spec_sha256": ref["sha256"], "dataset_id_exact": data, "cache_dataset_id_exact": meta["dataset_id"], "method_id_exact": method, "selection_split_id_exact": panel, "input_rows": spec["input_rows"], "input_sha256": spec["input_rows_sha256"], "cache_manifest_path": wsl(manifest), "cache_manifest_sha256": cache["cache_manifest_sha256"], "cache_manifest_has_input_path_field": "input_rows" in meta or "input_path" in meta, "input_path_authority": {"path": wsl(source_registry_path), "sha256": pc.sha(source_registry_path), "key": "datasets." + data + ".wsl_path"}, "payloads_opened": False})
    if len(specs) != 30:
        raise ValueError("Expected10internal+10external75+10supplement13 shared specs")
    old_plan = pc.read(BASE / "score-spec-assets-v1" / "evaluation-plan.prebarrier.json")
    units = {}
    execution = pc.read(PROJECT / "control" / "gpu-fit-specs-v4" / "execution-index.json")
    for unit in execution["units"]:
        panel, method = unit["split_id"], unit["method_id"]
        internal = "source_test" if panel == PANELS[0] else "target_test"
        units[unit["unit_id"]] = {"selection": {"path": unit["selection_path"], "sha256": None}, "checkpoint_sha256": None, "score_specs": [mapping[(internal, method, panel)], mapping[("external75", method, panel)], mapping[("supplement13", method, panel)]]}
    plan = copy.deepcopy(old_plan)
    plan["units"] = units
    code_files = {ref["path"]: ref for ref in plan["code_files"]}
    paths = [PROJECT / "control" / "scoring-launch-v1" / name for name in ("score_common.py", "score_unit.py", "score_pool.py")]
    paths += [PROJECT / "launch" / name for name in ("common.py", "run_unit.py", "pool_supervisor.py")]
    for folder in ("graphdta-deepnc", "mgraph-dgdta", "gs-dta"):
        paths += [file for file in (PROJECT / "methods" / folder).rglob("*.py") if "__pycache__" not in file.parts]
        paths += [file for file in (PROJECT / "methods" / folder).rglob("*.json") if "vocab" in file.name.lower()]
    for file in paths:
        code_files[wsl(file)] = {"path": wsl(file), "sha256": pc.sha(file)}
    plan["code_files"] = list(code_files.values())
    identity_path = output / "spec-cache-identity-verification.json"
    pc.write_new(identity_path, {"created_at": pc.now(), "status": "all30_score_metadata_spec_cache_identities_exact", "shared_specs": 30, "unique_cache_manifests": 20, "canonical_path_rule": "Spec input_rows must exactly equal the frozen input registry datasets[cache.dataset_id].wsl_path. Original cache metadata stores input SHA but no input path; this sidecar states that limitation instead of fabricating a cache path field.", "verifications": verified, "gold_reads": 0, "input_payload_reads": 0, "cache_payload_reads": 0, "selection_reads": 0, "checkpoint_reads": 0, "scoring_authorized": False})
    plan["spec_cache_identity_verification"] = {"path": wsl(identity_path), "sha256": pc.sha(identity_path)}
    plan["superseded_specs"] = "v1 display-ID drafts retained; never include their hashes in score authorization"
    pc.write_new(output / "evaluation-plan.prebarrier.json", plan)
    pc.write_new(output / "score-spec-assets-manifest.json", {"created_at": pc.now(), "shared_score_specs": 30, "future_unit_contracts": 200, "future_score_calls": 600, "expected_prediction_rows": 265800, "scoring_authorized": False, "specs": specs, "spec_cache_identity_verification": plan["spec_cache_identity_verification"], "raw_scientific_payloads_read": 0, "models_launched": 0})
    print(json.dumps({"shared_specs": len(specs), "unit_mappings": len(units), "identities_exact": True, "scoring_authorized": False, "raw_payload_reads": 0}))
