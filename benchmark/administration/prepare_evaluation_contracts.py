"""Prepare200 evaluation-stage contracts, each binding three future score calls.

Metadata/code files only: never open gold, predictions, caches or checkpoints.
Actual issuance requires the root's complete-barrier scoring plan and unchanged
central validator. No command is executed by this generator.
"""
import argparse
import copy
import importlib.util
import json
from pathlib import Path

import prepare_campaign as pc

BASE = Path(__file__).resolve().parent
PROJECT = BASE.parent
WSL = "/mnt/d/work/科研工作台/research-tasks/peptide-binding-nc-benchmark-20261021"
SCORE_ROOT = WSL + "/formal-runs-gpu-v4/scores"
METRICS = {"MAE": "mean(abs(predicted-observed))", "RMSE": "sqrt(mean((predicted-observed)^2))", "Pearson": "Pearson correlation; null for undefined groups", "Spearman": "Pearson correlation of average-tied ranks; null for undefined groups", "R2": "1-SSE/SST; null when observed variance is zero or group undersized"}


def local(value):
    value = str(value)
    return Path("D:/" + value[len("/mnt/d/"):]) if value.startswith("/mnt/d/") else Path(value)


def metadata(ref):
    file = local(ref["path"])
    if pc.sha(file) != ref["sha256"]:
        raise ValueError("Metadata hash differs: " + str(file))
    return pc.read(file)


def supplemental_target(role, group, count, metric, metric_source="score"):
    return {"target_id": role + "::" + group + ":" + metric, "paper_endpoint": "New PPIKB NC benchmark post-selection holdout inference", "required": True, "dataset_reference": role + "/" + group, "comparison_endpoint": "exact held-out experimental pKd", "metric": metric, "metric_definition": METRICS[metric], "statistical_unit": "measurement record; dependency grouping and external eligibility remain those frozen before model scoring", "denominator": count, "unit": "pKd (-log10 molar Kd)" if metric in ("MAE", "RMSE") else "dimensionless", "paper_value": None, "paper_value_source": None, "baseline": "same selected model; no post-test model selection", "checkpoint_selection": "unchanged validation-only selection frozen before all holdout predictions", "repetitions": 10, "tolerance": {"kind": "not_comparable", "absolute": None, "relative": None, "rule": None, "reason": "New dataset and frozen common-data transfer benchmark; original paper table scores are not comparable."}, "evidence_paths": [], "metric_binding": {"dataset_role": role, "group": group, "metric": metric, "source": metric_source}}


def targets(parent):
    result = []
    for original in parent["targets"]:
        item = copy.deepcopy(original)
        group, metric = item["target_id"].rsplit(":", 1)
        item["target_id"] = "internal::" + item["target_id"]
        item["metric_binding"] = {"dataset_role": "internal", "group": group, "metric": metric, "source": "score"}
        result.append(item)
    for group, count, source in (("all", 75, "score"), ("primary67", 67, "review"), ("conditional8", 8, "review"), ("target_reference_cold2", 2, "review")):
        result.extend(supplemental_target("external75", group, count, metric, source) for metric in METRICS)
    for group, count in (("all", 13), ("synthetic_D_backbone", 8), ("standard20_control", 5)):
        result.extend(supplemental_target("supplement13", group, count, metric) for metric in METRICS)
    return result


def readiness(plan):
    if plan.get("root_authorized_after_barrier") is not True:
        raise PermissionError("Root post-barrier scoring plan is not issued")
    authorization = metadata(plan["authorization"])
    if authorization.get("root_scoring_authorized") is not True or "score" not in authorization.get("allowed_phases", []):
        raise PermissionError("Real scoring authorization absent")
    barrier = metadata(plan["barrier"])
    if barrier.get("status") != "all_selections_frozen" or barrier.get("selection_count") != 200 or barrier.get("candidate_fit_count") != 400:
        raise ValueError("Full400-fit/200-selection barrier incomplete")
    audit = metadata(plan["barrier_audit"])
    if audit.get("status") != "all_200_selections_and_checkpoints_verified" or len(audit.get("selections", [])) != 200:
        raise ValueError("Root checkpoint audit incomplete; this generator never reads weights")
    for source in plan["code_files"]:
        name = str(source["path"]).lower()
        if any(token in name for token in ("gold", "predictions", "checkpoint", ".pt", ".pkl")):
            raise ValueError("Code manifest must not include scientific data artifacts")
        file = local(source["path"])
        if pc.sha(file) != source["sha256"]:
            raise ValueError("Scoring code changed after root freeze")
    normalized = {str(source["path"]).replace("\\", "/") for source in plan["code_files"]}
    mandatory_suffixes = ("/control/scoring-launch-v1/score_unit.py", "/control/scoring-launch-v1/score_pool.py", "/control/scoring-launch-v1/score_common.py", "/evaluation/common.py", "/evaluation/feature_cache.py", "/evaluation/score_cached.py", "/evaluation/metrics_stable.py", "/execution/runner.py")
    if any(not any(name.endswith(suffix) for name in normalized) for suffix in mandatory_suffixes):
        raise ValueError("Actual frozen score launcher/scorer/runner code proof incomplete")
    return authorization, barrier, audit


def generate(plan, output, issue=False):
    output = pc.inside_admin(output)
    if output.exists():
        raise FileExistsError("Use a new evaluation-stage revision")
    audit_metadata = None
    if issue:
        _, _, audit_metadata = readiness(plan)
    output.mkdir(parents=True)
    default_training_index = BASE / "io-recovery01" / "eligible-training-freeze-index-v5.json"
    if plan.get("training_index"):
        training = metadata(plan["training_index"])
        training_index_reference = copy.deepcopy(plan["training_index"])
    elif default_training_index.exists():
        training = pc.read(default_training_index)
        training_index_reference = {"path": str(default_training_index), "sha256": pc.sha(default_training_index)}
    elif not issue:
        legacy_index = BASE / "issued-gpu-v4" / "freeze-index.json"
        training = pc.read(legacy_index)
        training_index_reference = {"path": str(legacy_index), "sha256": pc.sha(legacy_index)}
    else:
        raise ValueError("Actual eligible training source index is required; do not issue from the superseded v4 roster")
    source = pc.STANDARD / "validate_reproduction.py"
    spec = importlib.util.spec_from_file_location("authoritative_reproduction_validator", source)
    validator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(validator)
    records = []
    created = pc.now()
    rows_total = 0
    for old in training["records"]:
        parent = pc.read(old["contract_path"])
        if pc.sha(old["contract_path"]) != old["contract_sha256"]:
            raise ValueError("Immutable training contract changed")
        uid = old["run_id"] + "__evaluation_v1"
        own = plan.get("units", {}).get(old["run_id"], {})
        requested = own.get("score_specs", [])
        if issue and (len(requested) != 3 or {r["role"] for r in requested} != {"internal", "external75", "supplement13"}):
            raise ValueError("Exactly three independently bounded dataset specs required")
        contract = pc.read(pc.STANDARD / "task-contract.template.json")
        contract.update(task_id=parent["task_id"], run_id=uid, created_at=created, frozen_at=created if issue else None, is_template=not issue, contract_status="frozen" if issue else "draft")
        for key in ("identity", "timing", "environment", "resources"):
            contract[key] = copy.deepcopy(parent[key])
        evaluation_clock_basis = None
        if parent.get("recovery_metadata"):
            # The recovery's20:09 cap bounds that interrupted training slot only.
            # Evaluation is a separately contracted stage under the original
            # unchanged paper clock/global01:45, as explicitly directed by root.
            original_global = metadata(parent["recovery_metadata"]["original_contract"])
            contract["timing"] = copy.deepcopy(original_global["timing"])
            evaluation_clock_basis = {"original_global_contract": copy.deepcopy(parent["recovery_metadata"]["original_contract"]), "training_recovery_absolute_deadline": parent["timing"]["effective_deadline_at"], "evaluation_global_deadline": original_global["timing"]["effective_deadline_at"], "rule": "Different stages retain original project clock; no recovery-training extension or reset. Actual recovery must already have completed within its20:09 cap before global all200 selection freeze."}
        scope = copy.deepcopy(parent["execution_scope"])
        scope.update(objective="Post-freeze independent inference on internal test, external75 and separate supplement13; no training or model selection", relation_to_prior_run="New evaluation stage of the same authorized benchmark; original training, clocks, logs and failures retained", prior_run_ids=[parent["run_id"]], intended_level="independent_inference", scope_coverage="partial_subset")
        contract["execution_scope"] = scope
        contract["assets"]["code"] = copy.deepcopy(parent["assets"]["code"])
        weight_path, weight_sha = own.get("checkpoint_path"), own.get("checkpoint_sha256")
        certified = False
        if issue and weight_path and weight_sha:
            matches = [row for row in audit_metadata["selections"] if (row["method_id"], row["split_id"], row["regime"], row["seed"]) == (old["method_id"], old["split_id"], old["regime_id"], old["seed"])]
            if len(matches) != 1 or matches[0]["checkpoint_sha256"] != weight_sha or matches[0]["sha256"] != own["selection"]["sha256"] or matches[0]["path"] != own["selection"]["path"]:
                raise ValueError("Selected checkpoint metadata differs from root's full-grid byte verification")
            certified = True
        contract["assets"]["models"] = [{"name": old["method_id"] + " validation-selected trained weights", "version": "same frozen winner; no parameter updates", "path": weight_path if certified else None, "sha256": weight_sha, "location": "remote", "integrity": "complete" if certified else "partial", "notes": "Actual WSL checkpoint bytes and exact SHA certified by the authorized root full200-grid barrier audit; remote reference is not re-opened by this Windows administrative generator." if certified else "Administrative plan has not yet populated the actual selected-checkpoint path/hash/audit linkage; this does not assert weights are missing. No weights are opened during preparation.", "evidence_paths": [plan["barrier_audit"]["path"]] if certified else []}]
        contract["assets"]["datasets"] = []
        score_metadata = []
        internal_n = next(target["denominator"] for target in parent["targets"] if target["target_id"] == "all:MAE")
        for role, count in (("internal", internal_n), ("external75", 75), ("supplement13", 13)):
            matches = [r for r in requested if r["role"] == role]
            reference = matches[0] if len(matches) == 1 else None
            dataset_id = None
            if reference:
                score_spec = metadata(reference)
                dataset_id = score_spec["dataset_id"]
                if score_spec["output_root"] != SCORE_ROOT or score_spec["method_id"] != old["method_id"]:
                    raise ValueError("Wrong frozen score-root/method")
                if issue and score_spec.get("selection_split_id") not in (None, old["split_id"]):
                    raise ValueError("Scoring panel identity differs")
                # Never dereference score_spec['gold_rows'], cache or checkpoint references.
                score_metadata.append({"role": role, "dataset_id": dataset_id, "n": count, "score_spec": {"path": reference["path"], "sha256": reference["sha256"]}})
            else:
                score_metadata.append({"role": role, "dataset_id": None, "n": count, "score_spec": None})
            contract["assets"]["datasets"].append({"name": role, "version": "frozen pre-scoring cohort", "path": reference["path"] if reference else None, "manifest_sha256": reference["sha256"] if reference else None, "sha256": reference["sha256"] if reference else None, "sample_count": count, "statistical_unit": "held-out measurement record", "integrity": "complete" if reference else "partial", "notes": "This references only a frozen metadata score specification. Gold is first opened by the scorer after persisted blind predictions. External75 remains separate from supplement13; primary67/conditional8/cold2 are reported from independent review."})
            rows_total += count
        contract["targets"] = targets(parent)
        contract["resources"].update(cpu_threads=2, data_loader_workers=0, memory_limit_bytes=4 * 1024**3, gpu_memory_budget_bytes=3 * 1024**3, budget_basis="Same generic local WSL runtime/UUID, one scoring worker, CPU2/RSS4GiB/allocator3GiB; original global deadline retained")
        contract["execution"] = {"command": [parent["execution"]["command"][0], WSL + "/control/scoring-launch-v1/score_unit.py", "--binding", WSL + "/control/scoring-launch-v1/bindings/" + uid + ".json"], "working_directory": WSL, "seed_policy": "Use this unchanged frozen selected seed; no resampling/refitting/selection", "seeds": [old["seed"]], "timeout_seconds": 1200, "process_control": {"platform": "Linux WSL", "mechanism": "Root-scoring private PGID, one worker, whole-tree RSS/deadline watchdog; actual launcher code frozen before issue", "whole_tree_bounded": True}, "stdout_path": plan.get("pool_output_root", WSL + "/control/scoring-launch-v1/pool-runs") + "/" + uid + ".stdout.log", "stderr_path": plan.get("pool_output_root", WSL + "/control/scoring-launch-v1/pool-runs") + "/" + uid + ".stderr.log"}
        contract["benchmark_metadata"] = copy.deepcopy(parent["benchmark_metadata"])
        contract["evaluation_stage"] = {"training_run_id": parent["run_id"], "training_contract_path": old["contract_path"], "training_contract_sha256": old["contract_sha256"], "eligible_training_index": training_index_reference, "scientific_execution_index": copy.deepcopy(plan.get("scientific_execution_index")), "stage_clock_basis": evaluation_clock_basis, "expected_score_receipts": 3, "expected_prediction_rows": sum(r["n"] for r in score_metadata), "score_root": SCORE_ROOT, "datasets": score_metadata, "root_barrier": copy.deepcopy(plan.get("barrier")), "root_barrier_audit": copy.deepcopy(plan.get("barrier_audit")), "root_score_authorization": copy.deepcopy(plan.get("authorization")), "selection": copy.deepcopy(own.get("selection")), "code_files": copy.deepcopy(plan.get("code_files", [])), "no_training_or_parameter_updates": True, "global_matrix": "200selected units ×3datasets =600 independent score receipts; no gold/prediction/weight bytes read during administrative preparation"}
        folder = output / uid
        folder.mkdir()
        path = folder / ("task-contract.json" if issue else "task-contract.draft.json")
        report = validator.validate(contract, allow_template=not issue, check_files=issue, contract_directory=folder)
        pc.write_new(folder / "central-validator-report.json", report)
        if issue and not report["valid_for_execution"]:
            contract.update(is_template=True, contract_status="draft", frozen_at=None)
            pc.write_new(folder / "task-contract.unissued-draft.json", contract)
            raise ValueError("Real scoring contract did not pass central validator: " + uid)
        pc.write_new(path, contract)
        record = {"run_id": uid, "training_run_id": old["run_id"], "task_id": contract["task_id"], "method_id": old["method_id"], "split_id": old["split_id"], "regime_id": old["regime_id"], "seed": old["seed"], "contract_path": str(path), "contract_sha256": pc.sha(path), "issued": issue, "valid_for_execution": report["valid_for_execution"], "expected_score_receipts": 3}
        if issue:
            central = folder / "central-validator-report.json"
            envelope = {"valid_for_execution": True, "contract_sha256": record["contract_sha256"], "central_validation_path": str(central), "central_validation_sha256": pc.sha(central), "validated_at": created}
            pc.write_new(folder / "execution-validation.json", envelope)
            record.update(validation_path=str(folder / "execution-validation.json"), validation_sha256=pc.sha(folder / "execution-validation.json"))
        records.append(record)
    if len(records) != 200 or rows_total != 265800:
        raise ValueError("Wrong planned200/600/265800 matrix")
    summary = {"schema": "nc-evaluation-stage-contracts.v1", "created_at": created, "issued": issue, "units": 200, "expected_score_receipts": 600, "expected_prediction_rows": rows_total, "gold_reads": 0, "prediction_reads": 0, "checkpoint_reads": 0, "models_launched": 0, "authoritative_validator_sha256": pc.sha(source), "records": records}
    pc.write_new(output / "evaluation-contract-index.json", summary)
    print(json.dumps({key: summary[key] for key in ("issued", "units", "expected_score_receipts", "expected_prediction_rows", "gold_reads", "checkpoint_reads", "models_launched")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan")
    parser.add_argument("--out", required=True)
    parser.add_argument("--issue", action="store_true")
    args = parser.parse_args()
    generate(pc.read(args.plan) if args.plan else {}, args.out, args.issue)
