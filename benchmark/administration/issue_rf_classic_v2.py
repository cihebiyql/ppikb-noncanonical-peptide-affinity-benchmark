"""Root-authorized RF metadata/contract issuance only. No fit or scoring launch."""
import copy
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import prepare_campaign as pc
import freeze_contracts

BASE = Path(__file__).resolve().parent
PROJECT = BASE.parent
RF = PROJECT / "auxiliary-rf-baseline"
CONTROL = PROJECT / "control"
LAUNCH = CONTROL / "rf-launch-v1"
WSL = "/mnt/d/work/科研工作台/research-tasks/peptide-binding-nc-benchmark-20261021"


def wsl(path):
    return WSL + "/" + str(Path(path).relative_to(PROJECT)).replace("\\", "/")


def local(value):
    return Path("D:/" + value[len("/mnt/d/"):]) if str(value).startswith("/mnt/d/") else Path(value)


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    source_path = RF / "SOURCE-FREEZE-v1.json"
    source = pc.read(source_path)
    if pc.sha(source_path) != "078c507e790140d66e3419246d01d18f6bb2fa785afdb6ef6075cec0df3998ab":
        raise ValueError("Root-reviewed final RF source-freeze identity differs")
    review_path = PROJECT / "review" / "auxiliary-RF-source-metadata-review-v4.json"
    review = pc.read(review_path)
    probe_path = CONTROL / "rf-live-resource-v1.json"
    probe = pc.read(probe_path)
    if probe["hostname"] != "cihebi" or probe["CUDA_VISIBLE_DEVICES"] != "" or not {4,5,6,7} <= set(probe["allowed_cpus"]):
        raise ValueError("Real root RF CPU/environment proof fails")
    for name, expected in source["source_sha256"].items():
        if pc.sha(RF / name) != expected:
            raise ValueError("Final RF source changed: " + name)
    launcher_freeze = pc.read(LAUNCH / "FROZEN-RF-LAUNCHER-v1.json")
    for name, expected in launcher_freeze["source_sha256"].items():
        if pc.sha(LAUNCH / name) != expected:
            raise ValueError("Final RF launcher changed")
    spec_index_path = RF / "specs-v1" / "task-spec-index.json"
    if pc.sha(spec_index_path) != source["artifact_sha256"]["specs-v1/task-spec-index.json"]:
        raise ValueError("RF40 metadata index changed")
    spec_index = pc.read(spec_index_path)
    units = spec_index["units"]
    if len(units) != 40:
        raise ValueError("Exactly40 RF units required")
    asset_path = RF / "installed-assets-v1.json"
    assets = pc.read(asset_path)
    code_paths = [RF / name for name in source["source_sha256"]] + [LAUNCH / name for name in ("rf_common.py", "rf_unit.py", "rf_pool.py")] + [PROJECT / "launch" / "common.py"]
    code_files = [{"path": wsl(path), "sha256": pc.sha(path)} for path in code_paths]
    out = BASE / "rf-classic-ready-v2"
    out.mkdir(exist_ok=False)
    archive = out / "rf-frozen-source-snapshot.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in code_paths + [source_path, asset_path, RF / "installed-binaries-v1.json"]:
            relative = str(path.relative_to(PROJECT)).replace("\\", "/")
            if relative not in bundle.namelist():
                bundle.write(path, relative)
    authorization_path = CONTROL / "rf-fit-authorization-v1.json"
    authorization = {"schema": "nc-root-auxiliary-RF-fit-authorization.v1", "root_real_RF_fit_authorized": True, "authority": "Explicit root same-thread instruction after independent299-check source review and actual live CPU/software proof; within user's authorized traditional baseline scope", "authorized_at": pc.now(), "allowed_spec_sha256": [unit["spec_sha256"] for unit in units], "source_sha256": source["source_sha256"], "deadline_unix": datetime.fromisoformat("2026-10-22T01:45:00+00:00").timestamp(), "resources": {"CPU_per_worker": 1, "max_workers": 4, "n_jobs": 1, "RSS_bytes_per_worker": 2*1024**3, "unit_timeout_seconds": 1800, "CUDA_VISIBLE_DEVICES": "", "allowed_cpu_ids": [4,5,6,7]}, "only_via_positive_central_private_CPU_pool": True, "review": {"path": wsl(review_path), "sha256": pc.sha(review_path)}, "live_cpu_proof": {"path": wsl(probe_path), "sha256": pc.sha(probe_path)}, "source_freeze": {"path": wsl(source_path), "sha256": pc.sha(source_path)}, "paper_count_contribution": 0, "NN200_400_600_protocol_unchanged": True, "real_holdout_scoring_authorized": False, "clock_reset": False}
    for unit in units:
        if pc.sha(local(unit["spec_path"])) != unit["spec_sha256"]:
            raise ValueError("RF frozen unit spec differs")
    write_new(authorization_path, authorization)
    anchors = pc.read(BASE / "issued-gpu-v4" / "freeze-index.json")["records"]
    anchor_map = {(r["split_id"], r["regime_id"], r["seed"]): r for r in anchors if r["method_id"] == "GraphDTA-GIN"}
    records = []
    stage_bindings = {}
    for unit in units:
        spec = pc.read(local(unit["spec_path"]))
        uid = unit["unit_id"]
        anchor = anchor_map[(unit["panel"], unit["regime"], unit["seed"])]
        parent = pc.read(anchor["contract_path"])
        contract = pc.read(pc.STANDARD / "task-contract.template.json")
        contract.update(task_id=parent["task_id"], run_id=uid, created_at=pc.now())
        for key in ("identity", "timing"):
            contract[key] = copy.deepcopy(parent[key])
        contract["identity"].update(administrative_anchor_only=True, administrative_identity_explanation="S299/GraphDTA is only this registered benchmark's administrative anchor; the extra RandomForest is not a GraphDTA author method or a reproduced paper.0 paper contribution.")
        contract["execution_scope"] = copy.deepcopy(parent["execution_scope"])
        contract["execution_scope"].update(objective="Fit and validate two fixed RandomForest classic-reference profiles, select by own-regime validation MAE; no holdout prediction and no author-paper claim", relation_to_prior_run="Additional classic reference preregistered before any holdout predictions; original5NN200/400/600 contract grid unchanged; S299 administrative anchor only; no old workflow or clock reset", intended_level="training", scope_coverage="partial_subset", prior_run_ids=[], excluded_claims=["Not a GraphDTA author method or published RF paper replication", "RF contributes0 predecessor papers", "No innovation model or sequence optimization", "No holdout access, test-based selection or scoring permission", "No original or local deadline reset"])
        contract["assets"]["datasets"] = [{"name": "RF fixed per-unit train/validation metadata specification", "version": "frozen specs-v1", "path": str(local(unit["spec_path"])), "sha256": unit["spec_sha256"], "manifest_sha256": unit["spec_sha256"], "sample_count": spec["train_n"] + spec["validation_n"], "statistical_unit": "own-regime prepared train/validation record", "integrity": "complete", "notes": "This exact metadata spec binds existing train/validation rows/IDs and fixed label-free2469-feature arrays. Worker verifies actual training/validation hashes; original full holdout-label container is prohibited and not opened by administrative issuance."}]
        contract["assets"]["code"] = [{"role": "task_classical_reference_and_private_CPU_launcher", "source_url": None, "path": str(archive), "archive_sha256": pc.sha(archive), "sha256": pc.sha(archive), "commit": None, "license": "Task source snapshot; sklearn dependencies retain installed source/license manifests", "checkout_status": "actual ZIP of exact frozen task/launcher source and installed-version metadata; no Git checkout claim", "integrity": "complete", "notes": "Frozen8 RF source/schema/version assets +actual3 CPU launcher files +frozen launch common; actual worker also verifies installed sklearn/tree native module hashes before fitting. Not a published author implementation.", "evidence_paths": [str(source_path), str(review_path)]}]
        contract["assets"]["models"] = [{"name": "RandomForestRegressor two fixed profiles", "path": None, "sha256": None, "integrity": "not_applicable", "notes": "No input model/pretraining; bothRF estimators are fresh future outputs. Full actual installed defaults are frozen in installed-assets-v1 and repeated in metadata."}]
        targets = []
        for label in ("candidate0_validation_MAE", "candidate1_validation_MAE", "selected_validation_MAE"):
            targets.append({"target_id": label, "paper_endpoint": "Generic extra classic reference own-validation endpoint; no author-paper endpoint", "required": True, "dataset_reference": "own-regime validation only", "comparison_endpoint": label, "metric": "MAE", "metric_definition": "mean(abs(predicted_pKd-observed_pKd)) on exact frozen own-regime validation IDs", "statistical_unit": "prepared validation measurement record", "denominator": spec["validation_n"], "unit": "pKd (-log10 molar Kd)", "paper_value": None, "paper_value_source": None, "checkpoint_selection": "minimum validation MAE; exact ties lower candidate index leaf2", "repetitions": 10, "tolerance": {"kind": "not_comparable", "absolute": None, "relative": None, "reason": "Classical reference stage, not a paper numerical reproduction"}, "evidence_paths": [str(source_path)]})
        contract["targets"] = targets
        contract["environment"].update(isolation="Existing generic WSL virtual environment and task source; CPU only; no installs or shared environment mutation", environment_path=parent["environment"]["environment_path"], lockfile_path=str(asset_path), lockfile_sha256=pc.sha(asset_path), runtime_versions=assets["versions"], shared_environment_modified=False)
        contract["environment"]["numerical_policy"].update(parameter_dtype="Not a neural parameter tensor; sklearn-tree implementation/defaults frozen", input_dtype="Xfloat32, supervised y/predictionfloat64; exact feature definitions frozen", autocast=False, determinism="Python/NumPy/sklearn random_state seed0–9; n_jobs1; actual effective constructor parameters recorded per candidate", notes="Morgan chirality-aware2048bits +AAC20+dipep400+effective1000prefix length =2469; no learned scaling, unknown residues remain in denominators; no Torch or visible CUDA inRF worker")
        contract["resources"].update(expected_hostname="cihebi", cpu_threads=1, data_loader_workers=0, memory_limit_bytes=2*1024**3, gpu_devices=[], gpu_memory_budget_bytes=None, allowed_cpu_ids=[4,5,6,7], resource_probe_path=str(probe_path), resource_probe_sha256=pc.sha(probe_path), resource_probe_at=probe["observed_at"], start_gate="Actual root liveCPU4–7/version/RSS proof; private RF pool re-probes CPU/load/available memory before startup and each launch, keeps1thread,2GiB/worker,≤4workers and≤8GiB pool; no preemption ofNN GPU jobs", budget_basis="Root explicit preregistered extra classic CPU-only reference; no holdout performance used; original01:45Z cutoff and complete1800-second slot required", no_preemption=True)
        binding_path = LAUNCH / "bindings" / (uid + ".json")
        receipt_root = WSL + "/control/rf-launch-v1/receipts/" + uid
        contract["execution"].update(command=[probe["python"], WSL + "/control/rf-launch-v1/rf_unit.py", "--binding", wsl(binding_path)], working_directory=WSL, seed_policy="Same frozen panels, own-regime validation only, exactly0–9, two fixed candidate profiles per seed", seeds=[unit["seed"]], timeout_seconds=1800, process_control={"platform": "Linux WSL", "mechanism": "Root-issued private single-CPU RF pool/session; independent1800-second/global-cutoff/RSS watchdog, actual wait/exit side-signature; failure retained no silent retry", "whole_tree_bounded": True}, stdout_path=WSL + "/control/rf-launch-v1/pool-runs/" + uid + ".stdout.log", stderr_path=WSL + "/control/rf-launch-v1/pool-runs/" + uid + ".stderr.log")
        stage = {"spec": {"path": unit["spec_path"], "sha256": unit["spec_sha256"]}, "authorization": {"path": wsl(authorization_path), "sha256": pc.sha(authorization_path)}, "live_cpu_proof": {"path": wsl(probe_path), "sha256": pc.sha(probe_path)}, "worker": {"path": WSL + "/auxiliary-rf-baseline/rf_runner.py", "sha256": source["source_sha256"]["rf_runner.py"]}, "code_files": code_files, "receipt_root": receipt_root}
        contract["rf_execution_stage"] = stage
        contract["benchmark_metadata"] = {"method_id": "RF-Classic", "worker_method_id": "RF-Morgan2-chiral-AAC-DP", "split_id": unit["panel"], "regime_id": unit["regime"], "seed": unit["seed"], "validation_scope": "same_as_regime", "test_used_for_selection": False, "external_used_for_selection": False, "paper_count_contribution": 0}
        contract["baseline_metadata"] = {"administrative_anchor_only": parent["task_id"], "author_model_reproduction": False, "feature_spec": {"path": str(RF / "feature-spec-v1.json"), "sha256": source["source_sha256"]["feature-spec-v1.json"]}, "feature_dimension": 2469, "actual_effective_candidate_parameters": [{**profile["effective_parameters_seed0"], "random_state": unit["seed"]} for profile in assets["candidate_profiles"]], "original_NN_protocol": {"fits": 400, "selections": 200, "scores": 600, "rows": 265800}, "extra_RF_protocol": {"fits": 80, "selections": 40, "scores": 120, "rows": 53160}, "root_joint_NN200_RF40_scoring_barrier_required": True, "fit_only_scoring_not_authorized": True}
        directory = out / "drafts" / uid
        directory.mkdir(parents=True)
        path = directory / "task-contract.draft.json"
        pc.write_new(path, contract)
        records.append({"run_id": uid, "method_id": "RF-Classic", "split_id": unit["panel"], "regime_id": unit["regime"], "seed": unit["seed"], "contract_draft_path": str(path)})
        stage_bindings[uid] = stage
    draft_index = out / "draft-index.json"
    pc.write_new(draft_index, {"runs": records, "paper_count_contribution": 0, "actual_models_launched": 0})
    adoption = out / "adoption.json"
    pc.write_new(adoption, {"draft_index_path": str(draft_index), "shared": {}, "methods": {}, "splits": {}, "units": {}, "root_authorization": {"path": str(authorization_path), "sha256": pc.sha(authorization_path)}})
    issued_dir = out / "issued"
    freeze_contracts.run(adoption, issued_dir, freeze=True)
    issued = pc.read(issued_dir / "freeze-index.json")
    if issued["frozen_units"] != 40 or issued["blocked_units"]:
        raise ValueError("RF central issuance failed; retain drafts/reports, do not launch or change gates")
    pool_units = []
    for item in issued["records"]:
        uid = item["run_id"]
        stage = stage_bindings[uid]
        binding = {"schema": "rf-unit-binding-v1", "issued": True, "unit_id": uid, "expected_hostname": "cihebi", "python": probe["python"], "PYTHONPATH": WSL + "/resources/local-gpu-route/vendor-dependencies", "CUDA_VISIBLE_DEVICES": "", "allowed_cpu_ids": [4,5,6,7], "deadline": "2026-10-22T01:45:00+00:00", "timeout_seconds": 1800, **stage, "central_contract": {"path": wsl(Path(item["contract_path"])), "sha256": item["contract_sha256"]}, "validation": {"path": wsl(Path(item["validation_binding_path"])), "sha256": item["validation_binding_sha256"]}, "entrypoint_sha256": launcher_freeze["source_sha256"]["rf_unit.py"], "pool_sha256": launcher_freeze["source_sha256"]["rf_pool.py"], "common_sha256": launcher_freeze["source_sha256"]["rf_common.py"]}
        file = LAUNCH / "bindings" / (uid + ".json")
        write_new(file, binding)
        pool_units.append({"unit_id": uid, "binding": {"path": wsl(file), "sha256": pc.sha(file)}})
    pool = {"schema": "rf-unit-index-v1", "issued": True, "expected_hostname": "cihebi", "python": probe["python"], "PYTHONPATH": WSL + "/resources/local-gpu-route/vendor-dependencies", "CUDA_VISIBLE_DEVICES": "", "allowed_cpu_ids": [4,5,6,7], "deadline": "2026-10-22T01:45:00+00:00", "max_concurrent": 4, "timeout_seconds": 1800, "launch_max_load_1min": 12.0, "output_root": WSL + "/control/rf-launch-v1/pool-runs", "entrypoint_sha256": launcher_freeze["source_sha256"]["rf_unit.py"], "pool_sha256": launcher_freeze["source_sha256"]["rf_pool.py"], "unit_sha256": launcher_freeze["source_sha256"]["rf_unit.py"], "supervisor_sha256": launcher_freeze["source_sha256"]["rf_pool.py"], "common_sha256": launcher_freeze["source_sha256"]["rf_common.py"], "units": pool_units}
    pool_path = CONTROL / "rf-unit-index-v1.json"
    write_new(pool_path, pool)
    ready = {"created_at": pc.now(), "authorization": {"path": str(authorization_path), "sha256": pc.sha(authorization_path)}, "central_freeze_index": {"path": str(issued_dir / "freeze-index.json"), "sha256": pc.sha(issued_dir / "freeze-index.json")}, "pool_index": {"path": str(pool_path), "sha256": pc.sha(pool_path)}, "actual_training_fits_started": 0, "raw_gold_prediction_model_cache_payload_reads": 0, "paper_count_contribution": 0, "unit_count": 40, "candidate_fits": 80, "pool_CLI": [probe["python"], WSL + "/control/rf-launch-v1/rf_pool.py", "--index", wsl(pool_path), "--index-sha256", pc.sha(pool_path)], "required_environment": {"CUDA_VISIBLE_DEVICES": "", "PYTHONPATH": WSL + "/resources/local-gpu-route/vendor-dependencies", "all_thread_environment_variables": "1"}}
    pc.write_new(out / "ROOT-RF-LAUNCH-READY.json", ready)
    print(json.dumps(ready, ensure_ascii=False))
