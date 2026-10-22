"""Read-only independent administrative verification of200 issued contracts.

Does not load a model, labels, predictions, checkpoints or evaluation metrics.
It hashes train/validation input bytes solely for artifact identity.
"""
import importlib.util
import json
from collections import Counter, defaultdict
from pathlib import Path

import prepare_campaign as pc

BASE = Path(__file__).resolve().parent
PROJECT = BASE.parent
FROZEN = PROJECT / "data-protocol" / "frozen-v1"
WSL = "/mnt/d/work/科研工作台/research-tasks/peptide-binding-nc-benchmark-20261021"


def local(value):
    value = str(value)
    if value.startswith("/mnt/d/"):
        return Path("D:/" + value[len("/mnt/d/"):])
    return Path(value)


if __name__ == "__main__":
    started = pc.now()
    index_path = BASE / "issued-gpu-v4" / "freeze-index.json"
    index = pc.read(index_path)
    registered = pc.read(PROJECT / "control" / "registered-paper-map.json")
    module_spec = importlib.util.spec_from_file_location("authoritative_reproduction_validator", pc.STANDARD / "validate_reproduction.py")
    validator = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(validator)
    hashes = {}
    errors = []
    groups = defaultdict(list)
    seen_ids = set()
    model_counts = Counter()
    pending_bindings = []
    actual_binding_count = 0

    def check(ok, message):
        if not ok:
            errors.append(message)

    def checked(value, expected):
        file = local(value).resolve()
        key = str(file)
        if key not in hashes:
            hashes[key] = pc.sha(file)
        check(hashes[key] == expected, "SHA mismatch: " + key)
        return file

    for row in index["records"]:
        contract_path = checked(row["contract_path"], row["contract_sha256"])
        central_path = checked(row["validation_path"], row["validation_sha256"])
        envelope_path = checked(row["validation_binding_path"], row["validation_binding_sha256"])
        contract = pc.read(contract_path)
        central = pc.read(central_path)
        envelope = pc.read(envelope_path)
        meta = contract["benchmark_metadata"]
        method = meta["method_id"]
        expected = registered[method]
        check(contract["task_id"] == expected["task_id"], row["run_id"] + ": task registration differs")
        check(contract["identity"]["doi"].lower() == expected["doi"].lower(), row["run_id"] + ": DOI differs")
        checked(contract["identity"]["pdf"]["path"], expected["pdf_sha256"])
        check(contract["is_template"] is False and contract["contract_status"] == "frozen", row["run_id"] + ": contract is unissued")
        check(central["valid_for_execution"] is True and not central["errors"], row["run_id"] + ": stored central validation failed")
        check(envelope["valid_for_execution"] is True and envelope["contract_sha256"] == row["contract_sha256"] and envelope["central_validation_sha256"] == row["validation_sha256"], row["run_id"] + ": envelope binding differs")
        fresh = validator.validate(contract, check_files=False)
        check(fresh["valid_for_execution"] is True, row["run_id"] + ": fresh unchanged central validator does not permit execution")
        check(contract["timing"]["effective_deadline_at"] == "2026-10-22T01:45:00+00:00" and contract["timing"]["retry_resets_clock"] is False, row["run_id"] + ": deadline or clock changed")
        check(contract["execution"]["timeout_seconds"] == 7200, row["run_id"] + ": timeout differs")
        check(meta["input_encoding_audit"]["status"] == "verified", row["run_id"] + ": actual input audit not verified")
        check(meta["test_used_for_selection"] is False and meta["external_used_for_selection"] is False, row["run_id"] + ": selection boundary changed")
        check(contract["resources"]["cpu_threads"] == 2 and contract["resources"]["memory_limit_bytes"] == 4 * 1024**3 and contract["resources"]["gpu_memory_budget_bytes"] == 3 * 1024**3 and contract["resources"]["expected_hostname"] == "cihebi", row["run_id"] + ": resource budget differs")
        execution = contract["execution"]
        for name in ("launcher_source", "wrapper_source", "fit_spec"):
            checked(execution[name]["path"], execution[name]["sha256"])
        checked(contract["environment"]["lockfile_path"], contract["environment"]["lockfile_sha256"])
        fit = pc.read(local(execution["fit_spec"]["path"]))
        check((fit["method_id"], fit["split_id"], fit["regime"], fit["seed"]) == (method, meta["split_id"], meta["regime_id"], meta["seed"]), row["run_id"] + ": scientific fit-spec identity differs")
        check(fit["max_epochs"] == 20 and fit["patience"] == 5 and fit["validation_scope"] == "same_as_regime", row["run_id"] + ": training budget differs")
        check(fit["candidates"] == [{"learning_rate": 0.001, "weight_decay": 0.0}, {"learning_rate": 0.0003, "weight_decay": 0.0}], row["run_id"] + ": LR candidates differ")
        for key in ("train_rows", "validation_rows"):
            checked(fit[key], fit[key + "_sha256"])
        proof = fit["launch_proof"]
        checked(proof["runner_path"], proof["runner_sha256"])
        for item in proof["files"]:
            name = str(item["path"]).lower()
            check(not any(text in name for text in ("sealed-test", "test-inputs", "external-validation/gold")), row["run_id"] + ": holdout artifact in fit proof")
            checked(item["path"], item["sha256"])
        command = execution["command"]
        expected_command = ["/root/.venvs/peptide-omnipanel-v31-web311-20260723/bin/python", WSL + "/control/run_bound_unit.py", "--binding", WSL + "/control/unit-bindings-v4/" + row["run_id"] + ".json"]
        check(command == expected_command, row["run_id"] + ": actual fixed entry command differs")
        binding_file = local(command[-1])
        if binding_file.exists():
            actual_binding_count += 1
            binding = pc.read(binding_file)
            check(binding["unit_id"] == row["run_id"] and binding["contract_sha256"] == row["contract_sha256"] and binding["spec_sha256"] == execution["fit_spec"]["sha256"] and binding["validation_sha256"] == row["validation_binding_sha256"], row["run_id"] + ": existing post-issue binding differs")
        else:
            pending_bindings.append(row["run_id"])
        summary = pc.read(FROZEN / "splits" / meta["split_id"] / "summary.json")
        expected_n = {"all": summary["split_sizes"]["test"], **summary["strata_by_split"]["test"]}
        expected_n["NC_core"] = sum(n for key, n in summary["strata_by_split"]["test"].items() if key != "standard20_control")
        check(len(contract["targets"]) == 35, row["run_id"] + ": incomplete endpoint plan")
        for target in contract["targets"]:
            stratum, metric = target["target_id"].split(":")
            check(target["denominator"] == expected_n[stratum] and target["metric"] == metric and target["paper_value"] is None and target["tolerance"]["kind"] == "not_comparable", row["run_id"] + ": target denominator/comparability differs")
        result = pc.read(contract_path.parent / "result-record.template.json")
        check(result["task_id"] == expected["task_id"] and result["contract_sha256"] == row["contract_sha256"] and result["is_template"] is True and result["execution"]["performed"] is False, row["run_id"] + ": result template claims execution or wrong identity")
        check(all(item["actual_value"] is None for item in result["metric_comparisons"]), row["run_id"] + ": fabricated pre-run metrics")
        check(row["run_id"] not in seen_ids, "Duplicate run id")
        seen_ids.add(row["run_id"])
        groups[(method, meta["split_id"], meta["regime_id"])].append(meta["seed"])
        model_counts[method] += 1
    check(len(groups) == 20 and all(sorted(values) == list(range(10)) for values in groups.values()), "Incomplete paper×panel×regime×ten-seed matrix")
    check(len(seen_ids) == 200 and len(model_counts) == 5 and set(model_counts.values()) == {40}, "Incorrect distinct paper/unit count")
    warnings = []
    for integration_index in sorted((PROJECT / "control").glob("unit-index*integration*.json")):
        actual = pc.read(integration_index)
        if actual["output_root"] != WSL + "/launch/pool-runs-v4":
            warnings.append({"kind": "outer_pool_log_directory_differs_from_contract", "index_path": str(integration_index), "actual_output_root": actual["output_root"], "contract_output_root": WSL + "/launch/pool-runs-v4", "action": "Retain actual original outer-pool logs and state this administrative path difference in results; do not rewrite contract or rerun fits. Unit-internal frozen receipts remain separate."})
    report = {"schema": "nc-issued-contracts-independent-audit.v1", "started_at": started, "ended_at": pc.now(), "freeze_index_path": str(index_path), "freeze_index_sha256": pc.sha(index_path), "authoritative_validator_sha256": pc.sha(pc.STANDARD / "validate_reproduction.py"), "units_checked": len(seen_ids), "distinct_registered_papers": len(model_counts), "unit_counts_by_model": dict(model_counts), "seed_groups": len(groups), "seed_matrix_complete": len(groups) == 20 and all(sorted(values) == list(range(10)) for values in groups.values()), "unique_artifacts_hashed": len(hashes), "existing_post_issue_bindings_checked": actual_binding_count, "future_bindings_not_yet_created_count": len(pending_bindings), "errors": errors, "administrative_warnings": warnings, "passed": not errors, "workloads_launched_by_this_audit": 0, "metric_or_checkpoint_files_opened": 0, "scope": "Contract/assets/registration/seed/denominator administrative audit only; does not claim any completed fit or scientific metric"}
    pc.write_new(BASE / "issued-gpu-v4-independent-audit.json", report)
    print(json.dumps({key: report[key] for key in ("passed", "units_checked", "distinct_registered_papers", "seed_matrix_complete", "unique_artifacts_hashed", "existing_post_issue_bindings_checked", "future_bindings_not_yet_created_count", "errors")}, ensure_ascii=False))
    raise SystemExit(0 if not errors else 1)
