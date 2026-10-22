"""Prepare40 honest classical-reference stage drafts; not a sixth paper.

S299 identifies the existing benchmark's administrative anchor only. No RF paper
identity, published score or author-method replication is invented. No fitting.
"""
import copy
import json
from pathlib import Path

import prepare_campaign as pc

BASE = Path(__file__).resolve().parent
PROJECT = BASE.parent


if __name__ == "__main__":
    train_index = pc.read(BASE / "issued-gpu-v4" / "freeze-index.json")
    anchors = [row for row in train_index["records"] if row["method_id"] == "GraphDTA-GIN"]
    if len(anchors) != 40:
        raise ValueError("Expected2panels×2regimes×10seeds administrative anchors")
    output = BASE / "rf-classic-drafts-v1"
    output.mkdir(exist_ok=False)
    records = []
    for original in anchors:
        parent = pc.read(original["contract_path"])
        uid = "RF-Classic__" + original["split_id"] + "__" + original["regime_id"] + "__seed" + str(original["seed"]).zfill(2)
        contract = pc.read(pc.STANDARD / "task-contract.template.json")
        contract.update(task_id=parent["task_id"], run_id=uid, created_at=pc.now(), is_template=True, contract_status="draft")
        for key in ("identity", "timing"):
            contract[key] = copy.deepcopy(parent[key])
        contract["identity"]["administrative_anchor_only"] = True
        contract["identity"]["administrative_identity_explanation"] = "S299/GraphDTA is the registered benchmark anchor, not the source or paper identity of this RandomForest baseline. This stage contributes0 predecessor papers."
        contract["execution_scope"] = copy.deepcopy(parent["execution_scope"])
        contract["execution_scope"].update(objective="Additional pre-holdout preregistered RandomForest classical affinity reference; two fixed candidates selected by validation MAE only; not an author method", relation_to_prior_run="Auxiliary classic comparison within same user-authorized NC benchmark and original clock; no change to five-paper NN200/400/600 protocol", prior_run_ids=[parent["run_id"]], intended_level="training", scope_coverage="partial_subset", excluded_claims=["RF is not GraphDTA or a published author implementation", "RF contributes0 to the required five predecessor papers", "No original-paper numerical replication claim", "No novel model or targeted peptide optimization", "No reset of original clock or previously restricted workflows", "No RF continuation or model choice based on holdout performance"])
        contract["assets"]["datasets"] = copy.deepcopy(parent["assets"]["datasets"])
        contract["assets"]["code"] = [{"role": "auxiliary_classical_reference_implementation", "path": str(PROJECT / "auxiliary-rf-baseline"), "commit": None, "archive_sha256": None, "integrity": "partial", "notes": "Actual RF implementation, explicit sklearn defaults and environment source hashes are being prepared by assigned RF agent; not frozen or executed by this administrative draft. No GraphDTA author code is used by the RF method."}]
        contract["assets"]["models"] = [{"name": "sklearn RandomForestRegressor classic reference", "path": None, "sha256": None, "integrity": "not_applicable", "notes": "No pretrained input weights. Fresh RF is fitted twice per seed using preregistered leaf2/leaf5; trained estimator artifacts will be actual future outputs."}]
        contract["targets"] = copy.deepcopy(parent["targets"])
        for target in contract["targets"]:
            target["paper_endpoint"] = "New common-data classical reference benchmark; no corresponding RF paper endpoint"
            target["paper_value"] = None
            target["paper_value_source"] = None
            target["tolerance"]["reason"] = "Generic classical RF reference, not an author-paper reproduction; S299 paper is an administrative anchor only."
        contract["environment"]["isolation"] = "Existing generic WSL sklearn/RDKit runtime, task-owned source/data; no shared environment changes"
        contract["environment"]["environment_path"] = parent["environment"]["environment_path"]
        contract["environment"]["numerical_policy"]["notes"] = "Actual sklearn/RDKit/NumPy/SciPy versions, complete effective RF get_params and numeric feature dtype receipt required before any real issuance; no Torch/GPU path used by RF."
        contract["resources"].update(expected_hostname="cihebi", cpu_threads=1, data_loader_workers=0, memory_limit_bytes=2 * 1024**3, gpu_devices=[], gpu_memory_budget_bytes=None, resource_probe_path=None, resource_probe_at=None, start_gate="Pending actual live CPU/memory capacity. At most4 CPU-only workers with1thread and2GiB RSS each; coexistence must not preempt original NN jobs; lower concurrency if live reservation unavailable", budget_basis="Root preregistered extra classical comparison before any holdout predictions; bounded optional auxiliary stage must not block five core methods", no_preemption=True)
        contract["execution"].update(command=None, working_directory=None, seed_policy="Exactly0–9; same fixed NN cohort-wide partitions; one RF seed per unit and two fixed leaf candidates; validation only", seeds=[original["seed"]], timeout_seconds=1800, process_control={"platform": "Linux WSL", "mechanism": "Pending actual CPU private-PGID supervisor; four workers max, whole-tree RSS and original deadline guard", "whole_tree_bounded": None}, stdout_path=None, stderr_path=None)
        contract["benchmark_metadata"] = {"method_id": "RF-Classic", "split_id": original["split_id"], "regime_id": original["regime_id"], "seed": original["seed"], "test_used_for_selection": False, "external_used_for_selection": False, "validation_scope": "same_as_regime", "paper_count_contribution": 0}
        contract["baseline_metadata"] = {"identity_role": "auxiliary_generic_classic_comparison_not_predecessor_paper", "administrative_anchor": parent["task_id"], "anchor_contract": {"path": original["contract_path"], "sha256": original["contract_sha256"]}, "features": {"peptide": "Morgan radius2/2048bits/useChirality=true on full ligand graph", "target": "first1000 amino acids; AAC20 +dipeptide400 +length; exact numeric definitions/dtypes frozen by actual code before fitting"}, "candidate_definitions": [{"n_estimators": 200, "max_features": "sqrt", "min_samples_leaf": leaf, "n_jobs": 1, "random_state": original["seed"]} for leaf in (2, 5)], "all_other_effective_parameters": "Must be explicitly captured from the actual installed sklearn regressor; defaults are not guessed here", "selection": "minimum validation MAE; fixed candidate order leaf2 then5 breaks exact ties; no test-based decision", "expected_total_units": 40, "expected_total_fits": 80, "expected_future_score_receipts": 120, "expected_future_prediction_rows": 53160, "joint_holdout_policy": "Root high-level scoring authorization additionally requires RF40 frozen or a preregistered resource/asset failure terminal decision; original NN200 scorer gate remains unchanged", "optional_failure_policy": "Record bounded preparation/fit failures and actual resource/asset reason; do not hold five core methods hostage or choose RF inclusion using holdout scores", "stage_status": "draft_only_no_actual_fit"}
        directory = output / uid
        directory.mkdir()
        path = directory / "task-contract.draft.json"
        pc.write_new(path, contract)
        records.append({"run_id": uid, "task_id": parent["task_id"], "method_id": "RF-Classic", "split_id": original["split_id"], "regime_id": original["regime_id"], "seed": original["seed"], "contract_path": str(path), "contract_sha256": pc.sha(path), "issued": False, "paper_count_contribution": 0})
    pc.write_new(output / "rf-classic-contract-index.json", {"schema": "nc-auxiliary-rf-classic-contract-drafts.v1", "created_at": pc.now(), "issued": False, "units": 40, "candidate_fits": 80, "future_score_receipts": 120, "future_prediction_rows": 53160, "predecessor_paper_count_contribution": 0, "original_NN_protocol_unchanged": True, "actual_models_fitted": 0, "gold_prediction_selection_checkpoint_reads": 0, "records": records})
    print(json.dumps({"draft_units": len(records), "expected_candidate_fits": 80, "paper_count_contribution": 0, "actual_fits": 0}))
