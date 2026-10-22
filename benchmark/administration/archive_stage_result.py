"""Fill a standard result record from authorized metadata receipts, never raw data.

Preparation never executes this against live scientific results. Later root use
requires explicit archival authorization, a full200 selection barrier and actual
pool exit side-signature. Gold/prediction/checkpoint/cache bytes are never opened.
"""
import argparse
import copy
import importlib.util
import json
import math
from pathlib import Path

import prepare_campaign as pc

REVIEW_GROUPS = {"primary67": "external_primary67", "conditional8": "external_conditional_sensitivity8", "target_reference_cold2": "external_reference_target_cold2"}
REVIEW_DATASETS = {"internal": "PPIKB-internal", "external75": "PTM-external75", "supplement13": "IgG-supplement13"}


def normalize_receipt(receipt):
    """Explicit metadata-only RF schema alias; original files/SHA stay unchanged."""
    result = copy.deepcopy(receipt)
    if receipt.get("method_id") == "RF-Morgan2-chiral-AAC-DP":
        result.update(worker_method_id=receipt["method_id"], method_id="RF-Classic", split_id=receipt["panel"], checkpoint_sha256=receipt["selected_model_sha256"], no_parameter_updates=receipt.get("parameter_updates") == 0, true_gold_used_only_after_blind_file=receipt.get("blind_before_gold") is True, administrative_schema_alias="RF panel→split_id,selected_model_sha256→checkpoint_sha256,parameter_updates0→no_updates; no source receipt changed")
    return result


def normalized_coordinate(row):
    method = row.get("method_id")
    return ("RF-Classic" if method == "RF-Morgan2-chiral-AAC-DP" else method, row.get("split_id", row.get("panel")), row.get("regime"), row.get("seed"))


def local(value):
    value = str(value)
    return Path("D:/" + value[len("/mnt/d/"):]) if value.startswith("/mnt/d/") else Path(value)


def metadata(ref):
    path = local(ref["path"])
    if path.suffix.lower() != ".json" or any(token in path.name.lower() for token in ("gold", "prediction", "checkpoint", "cache")):
        raise PermissionError("Archival tool only opens metadata receipts, never scientific data/weights")
    if pc.sha(path) != ref["sha256"]:
        raise ValueError("Metadata receipt changed: " + str(path))
    return pc.read(path)


def actual_execution(unit, pool, evidence, contract, unit_ref, pool_ref):
    terminal = pool.get("execution", {})
    actual_exit = pool.get("exit_code", terminal.get("exit_code"))
    actual_absence = pool.get("handles_absent_verified_at", terminal.get("handles_absent_verified_at"))
    if not isinstance(actual_exit, int) or isinstance(actual_exit, bool):
        raise ValueError("Actual pool terminal exit must be independently present; never trust unit self-exit")
    if not actual_absence:
        raise ValueError("Actual pool process-tree exit signature absent")
    if pool.get("private_session_handles_absent") is not True:
        raise ValueError("Pool did not verify the actual private process tree absent")
    execution = copy.deepcopy(unit.get("execution", {}))
    for key in ("hostname", "pid", "pgid", "started_at", "ended_at", "stdout_path", "stderr_path", "command"):
        if key not in execution and key in unit:
            execution[key] = copy.deepcopy(unit[key])
    execution.update(copy.deepcopy(pool.get("execution", {})))
    execution.update(copy.deepcopy(evidence.get("execution", {})))
    if evidence.get("pool_started"):
        launch = metadata(evidence["pool_started"])
        if launch.get("pid") != execution.get("pid") or launch.get("pgid") != execution.get("pgid"):
            raise ValueError("Actual pool launch and unit process identity differ")
        execution["command"] = launch["argv"]
    execution.update(exit_code=actual_exit, handles_absent_verified_at=actual_absence)
    # The exited unit cannot certify its own exit. These terminal facts must come
    # from the supervising pool's actual wait/exit-verification side-signature.
    for key in ("exit_code", "timed_out", "handles_absent_verified_at", "stdout_path", "stderr_path", "ended_at"):
        if key in pool:
            execution[key] = pool[key]
    if not isinstance(execution.get("exit_code"), int):
        raise ValueError("Actual pool-wait terminal exit code absent; never infer0 from unit-complete")
    if not execution.get("handles_absent_verified_at"):
        raise ValueError("Actual private process-tree exit verification absent")
    for key in ("hostname", "pid", "started_at", "ended_at", "stdout_path", "stderr_path"):
        if execution.get(key) is None:
            raise ValueError("Missing actual execution field: " + key)
    execution.update(performed=True, receipt_path=unit_ref["path"], receipt_sha256=unit_ref["sha256"], exit_verification_path=pool_ref["path"], exit_verification_sha256=pool_ref["sha256"], working_directory=execution.get("working_directory", contract["execution"]["working_directory"]), environment_path=contract["environment"]["environment_path"], effective_deadline_at=contract["timing"]["effective_deadline_at"], timeout_seconds=contract["execution"]["timeout_seconds"], seeds=contract["execution"]["seeds"])
    if not execution.get("command"):
        raise ValueError("Actual resolved command must be supplied by unit/pool receipt, not copied from expectation")
    return execution


def fill(contract_path, evidence_path, output):
    evidence = pc.read(evidence_path)
    if evidence.get("root_result_archival_authorized") is not True:
        raise PermissionError("Root authorized metadata archival is required")
    barrier = metadata(evidence["global_barrier"])
    if barrier.get("status") != "all_selections_frozen" or barrier.get("selection_count") != 200 or barrier.get("candidate_fit_count") != 400:
        raise ValueError("Full global selection barrier absent")
    contract_path = local(contract_path)
    contract = pc.read(contract_path)
    unit = metadata(evidence["unit_receipt"])
    pool = metadata(evidence["pool_exit_verification"])
    if contract["is_template"] or contract["contract_status"] != "frozen":
        raise ValueError("Cannot archive a template as a real result")
    if unit.get("contract_sha256") != pc.sha(contract_path):
        raise ValueError("Actual unit receipt is not bound to this exact evaluation contract")
    expected_parent = contract.get("evaluation_stage", {}).get("training_run_id", contract["run_id"])
    prior_training_exit = None
    if "evaluation_stage" in contract:
        training = evidence.get("training_stage", {})
        if not all(key in training for key in ("contract", "unit_receipt", "exit_verification")):
            raise ValueError("Evaluation result must preserve exact original training contract, unit receipt and exit evidence")
        original_contract = metadata(training["contract"])
        original_unit = metadata(training["unit_receipt"])
        original_exit = metadata(training["exit_verification"])
        prior_training_exit = original_exit.get("exit_code", original_exit.get("execution", {}).get("exit_code"))
        if not isinstance(prior_training_exit, int) or isinstance(prior_training_exit, bool):
            raise ValueError("Actual original training terminal exit is required, never inferred from completion file")
        if original_contract["run_id"] != expected_parent or training["contract"]["sha256"] != contract["evaluation_stage"]["training_contract_sha256"]:
            raise ValueError("Training lineage contract differs")
        if original_unit.get("status") != "complete" or original_unit.get("contract_sha256") != training["contract"]["sha256"]:
            raise ValueError("Actual original training receipt does not match the preserved contract")
    coordinate = contract["benchmark_metadata"]
    if coordinate["method_id"] == "RF-Classic":
        if not evidence.get("joint_barrier"):
            raise ValueError("RF evaluation archival requires the actual root NN200+RF40 joint barrier")
        joint = metadata(evidence["joint_barrier"])
        if joint.get("status") != "all_200_NN_plus_40_RF_frozen" or (joint.get("NN_selections"), joint.get("RF_selections")) != (200, 40):
            raise ValueError("Incomplete actual root joint barrier")
    scores = {}
    for ref in evidence["score_receipts"]:
        receipt = normalize_receipt(metadata(ref))
        expected = (coordinate["method_id"], coordinate["split_id"], coordinate["regime_id"], coordinate["seed"])
        actual = tuple(receipt[key] for key in ("method_id", "split_id", "regime", "seed"))
        if actual != expected or ref["role"] in scores:
            raise ValueError("Duplicate/wrong scientific score identity")
        if receipt.get("status") != "complete" or receipt.get("no_parameter_updates") is not True or receipt.get("true_gold_used_only_after_blind_file") is not True:
            raise ValueError("Score did not certify frozen no-update blind-first protocol")
        if coordinate["method_id"] == "RF-Classic":
            if receipt.get("joint_barrier_sha256") != evidence["joint_barrier"]["sha256"]:
                raise ValueError("Actual RF score belongs to a different joint barrier")
        elif receipt.get("barrier_sha256") != evidence["global_barrier"]["sha256"]:
            raise ValueError("Actual NN score belongs to a different all200 barrier")
        if contract.get("evaluation_stage"):
            dataset_plan = [row for row in contract["evaluation_stage"]["datasets"] if row["role"] == ref["role"]]
            if len(dataset_plan) != 1 or receipt.get("score_spec_sha256") != dataset_plan[0]["score_spec"]["sha256"]:
                raise ValueError("Actual scoring spec differs from the preregistered dataset role")
        scores[ref["role"]] = (receipt, ref)
    if set(scores) != {"internal", "external75", "supplement13"}:
        raise ValueError("All three separate score receipts required; partial failures use explicit blocked/partial archival")
    if len({r[0]["selection_sha256"] for r in scores.values()}) != 1 or len({r[0]["checkpoint_sha256"] for r in scores.values()}) != 1:
        raise ValueError("Three scores do not reuse the same unchanged selected model")
    review = metadata(evidence["independent_review"]) if evidence.get("independent_review") else []
    comparisons, missing = [], []
    for target in contract["targets"]:
        binding = target.get("metric_binding")
        if not binding:
            group, metric = target["target_id"].rsplit(":", 1)
            binding = {"dataset_role": "internal", "group": group, "metric": metric, "source": "score"}
        role, group, metric = binding["dataset_role"], binding["group"], binding["metric"]
        receipt, ref = scores[role]
        metrics = receipt["metrics"]
        paths = [ref["path"]]
        if binding["source"] == "review":
            matches = [row for row in review if row.get("identity", {}).get("dataset_id") == REVIEW_DATASETS[role] and normalized_coordinate(row["identity"]) == normalized_coordinate(receipt)]
            if len(matches) == 1:
                if matches[0].get("runner_metric_differences"):
                    raise ValueError("Independent metric disagreement must be resolved and preserved before acceptance")
                metrics = matches[0]["metrics"]
                paths.append(evidence["independent_review"]["path"])
                group = REVIEW_GROUPS.get(group, group)
            else:
                metrics = {}
        actual = metrics.get(group, {}).get(metric)
        known_group = group in metrics and metric in metrics[group]
        if known_group and metrics[group].get("n") != target["denominator"]:
            raise ValueError("Frozen endpoint denominator differs: " + target["target_id"])
        if actual is not None and (isinstance(actual, bool) or not isinstance(actual, (int, float)) or not math.isfinite(actual)):
            raise ValueError("Non-finite/invalid metric in actual receipt")
        if not known_group:
            missing.append(target["target_id"])
        comparison = {key: copy.deepcopy(target.get(key)) for key in ("target_id", "paper_endpoint", "metric", "metric_definition", "statistical_unit", "denominator", "unit", "paper_value")}
        comparison.update(actual_value=actual, baseline_value=None, absolute_difference=None, relative_difference=None, comparability="not_comparable", tolerance_reference=target["tolerance"], passed=None, reason=("Group metric mathematically undefined; stored null retained. " if known_group and actual is None else "") + ("Independent subgroup calculation not yet supplied. " if not known_group else "") + "Published original-paper value is not comparable on this changed dataset.", evidence_paths=paths)
        comparisons.append(comparison)
    execution = actual_execution(unit, pool, evidence, contract, evidence["unit_receipt"], evidence["pool_exit_verification"])
    result = pc.read(pc.STANDARD / "result-record.template.json")
    result.update(is_template=False, task_id=contract["task_id"], run_id=contract["run_id"], contract_path=str(contract_path), contract_sha256=pc.sha(contract_path), recorded_at=pc.now(), lifecycle_status="succeeded" if execution["exit_code"] == 0 and not missing and prior_training_exit in (None, 0) else "partial", reproduction_level=contract["execution_scope"]["intended_level"], scope_coverage=contract["execution_scope"]["scope_coverage"], execution=execution, metric_comparisons=comparisons)
    result["assets_integrity"] = {name: {"status": "partial", "scope": "Actual bounded common-data stage, linked author/source/runtime metadata; no full-paper replication claim", "evidence_paths": [evidence["unit_receipt"]["path"], evidence["pool_exit_verification"]["path"]], "notes": "Scientific data bytes are not re-opened by this archival tool; producer and independent reviewer evidence retained"} for name in ("datasets", "code", "models", "environment")}
    for category in ("datasets", "code", "models"):
        entries = contract["assets"][category]
        if entries and all(item["integrity"] in ("complete", "not_applicable") for item in entries):
            result["assets_integrity"][category]["status"] = "complete"
            result["assets_integrity"][category]["notes"] = "Frozen scoped assets and actual producer/root-audit receipt integrity support availability; no new raw-payload read or full-paper claim by this metadata archival tool"
    result["claims"] = [{"text": "Recorded actual scoped " + contract["execution_scope"]["intended_level"] + " execution and available bound metrics", "evidence_type": "source_fact", "evidence_paths": [evidence["unit_receipt"]["path"]], "limitations": "Missing required endpoints remain partial. Original-paper metrics non-comparable; historical failures and chemistry/external-scope limits remain. No full-paper replication claim."}]
    result["incomplete_reasons"] = [{"code": "required_subgroup_metric_not_available", "description": "Required independent subgroup metric absent", "affected_targets": missing, "evidence_paths": [], "next_action": "Complete authorized independent post-hoc review from the same saved predictions; do not regenerate/reselect models"}] if missing else []
    if execution["exit_code"] != 0:
        result["incomplete_reasons"].append({"code": "actual_stage_nonzero_exit", "description": "Original failed terminal process retained", "affected_targets": [], "evidence_paths": [evidence["pool_exit_verification"]["path"]], "next_action": "Preserve outputs/failure and report partial scope; no silent retry"})
    if prior_training_exit not in (None, 0):
        result["incomplete_reasons"].append({"code": "prior_training_stage_nonzero_exit_preserved", "description": "Prior training stage terminal failure remains an actual failure; later score success does not rewrite it", "affected_targets": [], "evidence_paths": [evidence["training_stage"]["exit_verification"]["path"]], "next_action": "Keep the complete cross-stage record partial and explain scope; never relabel the parent exit"})
    result["differences"] = evidence.get("differences", [])
    result["stage_lineage"] = {"training_run_id": expected_parent, "training_stage": evidence.get("training_stage"), "evaluation_unit_receipt": evidence["unit_receipt"], "pool_exit_verification": evidence["pool_exit_verification"], "score_receipts": evidence["score_receipts"], "global_barrier": evidence["global_barrier"], "independent_review": evidence.get("independent_review"), "historical_failed_attempt": evidence.get("historical_failed_attempt")}
    result["artifacts"] = [{"role": "metadata_receipt", "path": ref["path"], "location": "remote" if str(ref["path"]).startswith("/") else "local", "available": True, "sha256": ref["sha256"], "notes": "Exact metadata file checked; scientific payload hashes remain producer/independent-review references"} for ref in [evidence["unit_receipt"], evidence["pool_exit_verification"], *evidence["score_receipts"], evidence["global_barrier"]]]
    result["scientific_output_hashes_from_receipts"] = {role: {key: receipt.get(key) for key in ("predictions_sha256", "blind_predictions_sha256", "gold_source_sha256", "selection_sha256", "checkpoint_sha256")} for role, (receipt, ref) in scores.items()}
    result["review"].update(status="pending", reviewer=None, reviewed_at=None)
    output = pc.inside_admin(output)
    pc.write_new(output, result)
    module_spec = importlib.util.spec_from_file_location("authoritative_reproduction_validator", pc.STANDARD / "validate_reproduction.py")
    validator = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(validator)
    # A training contract references raw labels/weights. --check-files would open
    # those bytes indirectly, contrary to this task's metadata-only preparation.
    # Root may separately authorize the full artifact-hash pass at final review.
    report = validator.validate(contract, result, contract_bytes=contract_path.read_bytes(), check_files=False, contract_directory=contract_path.parent, result_directory=output.parent)
    report["administrative_metadata_integrity"] = "Exact metadata receipt hashes were checked by this tool; raw scientific payloads were deliberately not re-opened. This is not a --check-files artifact audit."
    pc.write_new(output.with_name(output.stem + ".central-validation.json"), report)
    print(json.dumps({"result_path": str(output), "central_valid": report["valid"], "lifecycle_status": result["lifecycle_status"], "review_status": "pending", "raw_gold_prediction_checkpoint_reads": 0}))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    report = fill(args.contract, args.evidence, args.out)
    raise SystemExit(0 if report["valid"] else 2)
