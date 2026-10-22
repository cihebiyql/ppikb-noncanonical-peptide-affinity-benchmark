"""Bind actual immutable launch specs/runtime to registered standard contracts.

Does not launch or freeze. Call freeze_contracts.py only after reviewing this join.
"""
import argparse
import copy
import json
from pathlib import Path

import prepare_campaign as pc

BASE = Path(__file__).resolve().parent
PROJECT = BASE.parent
WSL = "/mnt/d/work/科研工作台/research-tasks/peptide-binding-nc-benchmark-20261021"


def local(value):
    if value.startswith("/mnt/d/"):
        return Path("D:/" + value[len("/mnt/d/"):])
    return Path(value)


def wsl(value):
    value = str(Path(value).resolve()).replace("\\", "/")
    if value.startswith("D:/"):
        return "/mnt/d/" + value[len("D:/"):]
    raise ValueError("Expected this campaign's D drive path")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fit-index", required=True)
    parser.add_argument("--pool-output-root", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--formal-output", required=True)
    args = parser.parse_args()
    destination = pc.inside_admin(args.out)
    formal = pc.inside_admin(args.formal_output)
    adoption = pc.read(BASE / "adoption.registered-gpu-prelaunch-v4.json")
    fit_index_path = local(args.fit_index)
    index = pc.read(fit_index_path)
    runtime_path = PROJECT / "resources" / "local-gpu-route" / "runtime-freeze-for-training.json"
    runtime = pc.read(runtime_path)
    entry = PROJECT / "control" / "run_bound_unit.py"
    wrapper = PROJECT / "launch" / "run_unit.py"
    if runtime["hostname"] != "cihebi" or runtime["environment_modified"] or runtime["models_fitted"] != 0:
        raise ValueError("Unexpected actual environment snapshot")
    specs = {}
    for row in index["candidate_fits"]:
        file = local(row["spec_path"])
        if pc.sha(file) != row["spec_sha256"]:
            raise ValueError("Fit index differs from actual spec bytes: " + str(file))
        spec = pc.read(file)
        key = (spec["method_id"], spec["split_id"], spec["regime"], spec["seed"])
        if key in specs and specs[key][1] != row["spec_sha256"]:
            raise ValueError("Candidate configs do not share the same frozen fit spec")
        specs[key] = (file, row["spec_sha256"], spec)
    draft_index = pc.read(adoption["draft_index_path"])
    if len(specs) != 200 or len(index["candidate_fits"]) != 400:
        raise ValueError("Expected200 units/400 candidate fits")
    shared = adoption["shared"]
    shared["environment"].update(lockfile_path=str(runtime_path), lockfile_sha256=pc.sha(runtime_path), lockfile_kind="Observed installed runtime snapshot, plus SHA-bound reused vendor dependency manifests in launch proof; no package install or lockfile synthesis", runtime_versions={key: runtime[key] for key in ("python", "torch", "torch_geometric", "rdkit", "numpy", "scipy", "cuda_runtime")})
    shared["environment"]["numerical_policy"] = {"author_entrypoint_evidence_paths": [str(PROJECT / "model-audit" / "model-routes.json")], "parameter_dtype": "float32", "input_dtype": "float32 graph features/int64 tokens and edge indices", "autocast": False, "float32_matmul_precision": runtime["numerical_policy"]["float32_matmul_precision"], "cuda_matmul_allow_tf32": runtime["numerical_policy"]["cuda_matmul_allow_tf32"], "cudnn_allow_tf32": runtime["numerical_policy"]["cudnn_allow_tf32"], "determinism": "Actual runtime deterministic_algorithms=true,warn_only=true; architecture-specific nondeterministic warnings retained; seeds0–9, no bit-exact CUDA claim", "applied_before_model_instantiation": True, "actual_policy_receipt_path": str(runtime_path), "notes": "Snapshot inspected exact generic WSL interpreter and reused vendor modules; formal runner binds the same source and applies policy before model creation."}
    shared["resources"].update(resource_probe_path=str(runtime_path), resource_probe_at=runtime["observed_at"])
    shared["execution"].update(timeout_seconds=7200)
    shared["execution"]["launcher_source"] = {"path": str(entry), "sha256": pc.sha(entry)}
    shared["execution"]["wrapper_source"] = {"path": str(wrapper), "sha256": pc.sha(wrapper)}
    shared["execution"]["post_issue_binding_policy"] = "Fixed command executes run_bound_unit.py --binding <unit JSON>. Root creates and SHA-binds that JSON in a separate post-issue launch index after actual contract and execution-validation byte hashes exist. No own SHA is embedded in this contract. Resolved argv and clipped unit deadline retained by binding receipt."
    units = {}
    for row in draft_index["runs"]:
        key = (row["method_id"], row["split_id"], row["regime_id"], row["seed"])
        file, file_sha, spec = specs[key]
        if spec["max_epochs"] != 20 or spec["patience"] != 5 or spec["device"] != "cuda:0" or spec["cpu_threads"] != 2 or not spec.get("gpu_explicitly_authorized"):
            raise ValueError("Wrong frozen scientific/resource budget")
        if spec["candidates"] != [{"learning_rate": 0.001, "weight_decay": 0.0}, {"learning_rate": 0.0003, "weight_decay": 0.0}]:
            raise ValueError("Changed search candidates")
        proof = spec.get("launch_proof")
        if not isinstance(proof, dict) or proof["expected_hostname"] != "cihebi":
            raise ValueError("No actual cihebi launch proof")
        for asset in proof["files"]:
            source = local(asset["path"])
            if pc.sha(source) != asset["sha256"]:
                raise ValueError("Proof asset changed: " + str(source))
        for name in ("train_rows", "validation_rows"):
            if pc.sha(local(spec[name])) != spec[name + "_sha256"]:
                raise ValueError("Training/validation projection changed")
        if pc.sha(local(proof["runner_path"])) != proof["runner_sha256"]:
            raise ValueError("Actual runner changed after launch proof")
        command = [runtime["executable"], WSL + "/control/run_bound_unit.py", "--binding", WSL + "/control/unit-bindings-v4/" + row["run_id"] + ".json"]
        units[row["run_id"]] = {
            "execution": {"command": command, "stdout_path": args.pool_output_root + "/" + row["run_id"] + ".stdout.log", "stderr_path": args.pool_output_root + "/" + row["run_id"] + ".stderr.log", "launch_proof": copy.deepcopy(proof), "fit_spec": {"path": str(file), "sha256": file_sha}},
            "benchmark_metadata": {"candidate_fits": 2, "final_selections": 1, "max_epochs": 20, "patience": 5, "validation_scope": "same_as_regime", "fit_spec_sha256": file_sha, "input_encoding_audit": copy.deepcopy(adoption["methods"][row["method_id"]]["benchmark_metadata"]["input_encoding_audit"]), "launch_data_binding": {name: {"path": spec[name], "sha256": spec[name + "_sha256"]} for name in ("train_rows", "validation_rows")}},
        }
    adoption.update(is_template=False, units=units, freeze_state="actual_facts_joined_ready_for_authoritative_validator", do_not_start_reason=[], final_join={"created_at": pc.now(), "fit_index_path": str(fit_index_path), "fit_index_sha256": pc.sha(fit_index_path), "runtime_path": str(runtime_path), "runtime_sha256": pc.sha(runtime_path), "entry_path": str(entry), "entry_sha256": pc.sha(entry), "wrapper_path": str(wrapper), "wrapper_sha256": pc.sha(wrapper), "formal_output_planned": str(formal), "pool_output_root": args.pool_output_root, "actual_model_runs_started_by_this_script": 0})
    pc.write_new(destination, adoption)
    print(json.dumps({"adoption_path": str(destination), "units": len(units), "registered_papers": len(adoption["methods"]), "actual_models_launched": 0}, ensure_ascii=False))
