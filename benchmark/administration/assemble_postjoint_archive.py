"""Future root-authorized720-receipt metadata archive assembler; no raw data.

Two-pass: all600NN/120RF producer receipts, private-session exits and independent
600/120 audits must pass before any standard result record is emitted. Never
opens gold, predictions, caches or trained-model bytes. Does not adopt the batch.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import re
from collections import Counter
from pathlib import Path

import prepare_campaign as pc
import archive_stage_result
from postjoint_issue_all import read_ref, ref, local, wsl, write_new, candidate_grid

BASE = Path(__file__).resolve().parent
PROJECT = BASE.parent
DATASET_ROLE = {"source_test": "internal", "target_test": "internal", "internal-test": "internal", "PPIKB-internal": "internal", "external75": "external75", "external75-PTM-reference-view-v1": "external75", "PTM-external75": "external75", "supplement13": "supplement13", "postfreeze-supplement13-reference-view-v1": "supplement13", "IgG-supplement13": "supplement13"}


def audit_index(document, expected):
    if not isinstance(document, list) or len(document) != expected:
        raise ValueError("Exact independent600 or120 per-score audit list required")
    result = {}
    for row in document:
        if row.get("all_truths_match_frozen_gold") is not True or row.get("runner_metric_differences"):
            raise ValueError("Independent label/metric verification incomplete or disagrees")
        digest = row["score_receipt_sha256"]
        if digest in result:
            raise ValueError("Duplicate independent producer-receipt audit")
        result[digest] = row
    return result


def find_started(pool_root, uid, pid, binding_sha):
    if not re.fullmatch("[A-Za-z0-9_.-]+", uid):
        raise ValueError("Unsafe issued unit ID")
    paths = list(local(pool_root).glob("attempts/*/" + uid + ".started.json"))
    paths += list(local(pool_root).glob(uid + ".started.json"))
    matches = []
    for path in paths:
        body, actual = read_ref(str(path))
        if body.get("pid") == pid and body.get("binding_sha256", binding_sha) == binding_sha:
            matches.append(actual)
    if len(matches) != 1:
        raise ValueError("Actual immutable pool start/PID proof is absent or ambiguous")
    return matches[0]


def training_exit(parent, uid):
    if parent.get("rf_execution_stage"):
        return ref(parent["rf_execution_stage"]["receipt_root"] + "/pool-exit-verification.json")
    # OriginalNN pools preserve their actual terminal file in the actual outer
    # pool directory. Do not pretend it was written to the pre-registered alias.
    candidates = list((PROJECT / "launch").glob("pool-runs-*/" + uid + ".terminal.json"))
    matches = []
    for path in candidates:
        body, actual = read_ref(str(path))
        if body.get("unit_id") == uid and body.get("exit_code") == 0:
            matches.append(actual)
    if len(matches) != 1:
        raise ValueError("Exact actual originalNN training terminal evidence ambiguous/missing")
    return matches[0]


def gather(issuance, nn_review, rf_review):
    independent = {"NN": audit_index(nn_review, 600), "RF": audit_index(rf_review, 120)}
    collected, counts, rows = [], Counter(), Counter()
    seen = {"NN": set(), "RF": set()}
    coordinates = {"NN": [], "RF": []}
    for family in ("NN", "RF"):
        pool, _ = read_ref(issuance["pools"][family])
        for entry in pool["units"]:
            binding, binding_ref = read_ref(entry["binding"])
            contract, contract_ref = read_ref(binding["central_contract"])
            uid = contract["run_id"]
            cell = contract["benchmark_metadata"]
            coordinates[family].append((cell["split_id"], cell["regime_id"], cell["seed"]) if family == "RF" else (cell["method_id"], cell["split_id"], cell["regime_id"], cell["seed"]))
            unit, unit_ref = read_ref(binding["receipt_root"] + "/unit-complete.json")
            terminal, exit_ref = read_ref(binding["receipt_root"] + "/pool-exit-verification.json")
            if unit.get("status") != "complete" or unit.get("contract_sha256") != contract_ref["sha256"] or terminal.get("exit_code") != 0 or terminal.get("private_session_handles_absent") is not True:
                raise ValueError("Actual successful scored unit +pool exit proof not complete")
            if unit.get("binding_sha256") != binding_ref["sha256"] or terminal.get("binding_sha256") != binding_ref["sha256"]:
                raise ValueError("Scored unit/exit belong to another binding")
            start_ref = find_started(pool["output_root"], uid, unit["pid"], binding_ref["sha256"])
            if len(unit.get("scores", [])) != 3 or {score["role"] for score in unit["scores"]} != {"internal", "external75", "supplement13"}:
                raise ValueError("Exactlythree distinct original score receipts required")
            score_refs = []
            for score in unit["scores"]:
                actual_score, score_ref = read_ref({"path": score["complete_path"], "sha256": score["complete_sha256"]})
                normal = archive_stage_result.normalize_receipt(actual_score)
                expected = contract["benchmark_metadata"]
                if archive_stage_result.normalized_coordinate(normal) != (expected["method_id"], expected["split_id"], expected["regime_id"], expected["seed"]):
                    raise ValueError("Score scientific coordinate differs from issued unit")
                review = independent[family].get(score_ref["sha256"])
                if score_ref["sha256"] in seen[family]:
                    raise ValueError("Producer score receipt reused in more than one scored cell")
                seen[family].add(score_ref["sha256"])
                if not review or archive_stage_result.normalized_coordinate(review["identity"]) != archive_stage_result.normalized_coordinate(normal):
                    raise ValueError("Exact independent audit of this producer/coordinate absent")
                if DATASET_ROLE.get(review["identity"]["dataset_id"]) != score["role"]:
                    raise ValueError("Independent dataset role differs")
                score_refs.append({"role": score["role"], **score_ref})
                counts[family] += 1
                rows[family] += normal["n"]
            parent_ref = {"path": contract["evaluation_stage"]["training_contract_path"], "sha256": contract["evaluation_stage"]["training_contract_sha256"]}
            parent, actual_parent_ref = read_ref(parent_ref)
            parent_uid = parent["run_id"]
            receipts = parent.get("rf_execution_stage", {}).get("receipt_root") or parent["execution"]["launch_proof"]["receipt_root"]
            original_unit_ref = ref(receipts + "/unit-complete.json")
            original_exit_ref = training_exit(parent, parent_uid)
            evidence = {"root_result_archival_authorized": True, "global_barrier": issuance["NN_barrier"], "joint_barrier": issuance["joint_barrier"], "unit_receipt": unit_ref, "pool_exit_verification": exit_ref, "pool_started": start_ref, "score_receipts": score_refs, "execution": {}, "training_stage": {"contract": actual_parent_ref, "unit_receipt": original_unit_ref, "exit_verification": original_exit_ref}, "differences": []}
            if parent.get("recovery_metadata"):
                historical = parent["recovery_metadata"]
                evidence["historical_failed_attempt"] = {key: copy.deepcopy(historical[key]) for key in ("original_run_id", "original_contract", "original_fit_spec", "original_terminal", "original_unit_started_at", "original_absolute_unit_deadline", "original_global_effective_deadline")}
                evidence["differences"].append({"category": "explicit_original_interrupted_attempt_retained", "description": "PriorMGraph -15 interrupted I/O attempt is retained; same scientific cell recovered in isolated outputs under its original training absolute ceiling. No relabelled old success, no additional scientific cell or deadline reset.", "effect_on_comparison": "Same model/seed/data/hyperparameters; only output/receipt directories changed for explicit one-slot recovery", "evidence_type": "source_fact", "evidence_paths": [historical["original_terminal"]["path"]]})
            collected.append({"family": family, "contract_ref": contract_ref, "binding_ref": binding_ref, "evidence": evidence, "uid": uid})
    if counts != {"NN": 600, "RF": 120} or rows != {"NN": 265800, "RF": 53160} or len(collected) != 240:
        raise ValueError("Full actual720receipts/318960rows required before any standard result emission")
    candidate_grid(coordinates["NN"])
    candidate_grid(coordinates["RF"], rf=True)
    if any(seen[family] != set(independent[family]) for family in ("NN", "RF")):
        raise ValueError("Independent audits must cover exactly the actual600/120 producer receipts with no omissions/extras")
    return collected, {"producer_receipts": dict(counts), "prediction_rows": dict(rows), "actual_units": len(collected)}


def assemble(inputs, output):
    if inputs.get("root_result_archival_authorized") is not True:
        raise PermissionError("No actual root metadata archival authorization")
    issuance, issuance_ref = read_ref(inputs["issuance_index"])
    nn_review, nn_review_ref = read_ref(inputs["NN_independent_per_score_audit"])
    rf_review, rf_review_ref = read_ref(inputs["RF_independent_per_score_audit"])
    # All producers/audits/actual exit proofs are checked in a complete first pass.
    cells, inventory = gather(issuance, nn_review, rf_review)
    output = pc.inside_admin(output)
    if output.exists():
        raise FileExistsError("Preserve any earlier pending/accepted records; use a new archive revision")
    output.mkdir(parents=True)
    result_entries, accepted_count = [], 0
    accept = inputs.get("root_accept_reviewed_records") is True
    validator_spec = importlib.util.spec_from_file_location("central_result_validator", pc.STANDARD / "validate_reproduction.py")
    central = importlib.util.module_from_spec(validator_spec)
    validator_spec.loader.exec_module(central)
    for cell in cells:
        evidence = cell["evidence"]
        evidence["independent_review"] = nn_review_ref if cell["family"] == "NN" else rf_review_ref
        folder = output / cell["family"] / cell["uid"]
        folder.mkdir(parents=True)
        evidence_path = folder / "metadata-evidence.json"
        write_new(evidence_path, evidence)
        result_path = folder / "result-record.pending.json"
        report = archive_stage_result.fill(cell["contract_ref"]["path"], str(evidence_path), result_path)
        if not report["valid"]:
            raise ValueError("Standard scoped result rejected; preserve exact report, do not relax gates")
        if accept:
            result = pc.read(result_path)
            if result["lifecycle_status"] != "succeeded" or result["incomplete_reasons"]:
                raise ValueError("Root acceptance cannot promote partial or failed stage")
            result["review"].update(status="accepted", reviewer="root explicit postjoint review and independent720-receipt validation", reviewed_at=pc.now(), checks=[{"item": name, "passed": True, "reason": "Bound actual metadata/producer/independent reviewer evidence at scoped new-data level, not full paper"} for name in ("identity", "assets", "contract", "execution", "comparison", "claims", "preservation")], evidence_paths=[nn_review_ref["path"], rf_review_ref["path"]])
            accepted = folder / "result-record.accepted.json"
            write_new(accepted, result)
            contract = pc.read(local(cell["contract_ref"]["path"]))
            validation = central.validate(contract, result, contract_bytes=local(cell["contract_ref"]["path"]).read_bytes(), check_files=False)
            write_new(folder / "accepted-central-validation.json", validation)
            if not validation["valid_for_acceptance"]:
                raise ValueError("Actual central acceptance failed; never label it accepted in summaries")
            result_path = accepted
            accepted_count += 1
        result_entries.append({"contract": cell["contract_ref"], "result": ref(str(result_path)), "family": cell["family"]})
    index_path = output / "standard-result-index.json"
    write_new(index_path, {"root_result_archival_authorized": True, "records": result_entries})
    batch_file = PROJECT.parent.parent / "复现" / "batches" / "peptide-binding-nc-benchmark-20261022" / "summary-rows.json"
    existing_rows, batch_ref = read_ref(str(batch_file))
    if len(existing_rows) != 5:
        raise ValueError("New batch must contain exactlyfive actual predecessor papers; never alter old62")
    proposed = copy.deepcopy(existing_rows)
    core_by_task = Counter(pc.read(local(row["contract"]["path"]))["task_id"] for row in result_entries if row["family"] == "NN")
    if set(core_by_task.values()) != {40} or len(core_by_task) != 5:
        raise ValueError("Exactly40 core evaluation cells per original paper required")
    for row in proposed:
        if row["task_id"] not in core_by_task:
            raise ValueError("Actual registered new-paper identity changed")
        row.update(status="succeeded", lifecycle_status="succeeded", reproduction_level="training", scope_coverage="partial_subset", review_status="accepted" if accept else "pending", summary="共同NC亲和力基准：该作者实现完成2面板×2训练口径×10种子，实际训练与三数据评分收据、独立重算均保留。", actual_results="80候选拟合、40验证选择、120评分收据；详细数值与每seed结果见本轮标准结果索引及独立审计。", differences="改变数据集与任务范围；原论文主表不作直接数值复现比较。蛋白前缀、化学表示限制、必要适配与统一预算均保留。", incomplete_reason=None, result_record_index=str(index_path), independent_NN_audit=nn_review_ref, additional_classic_RF={"paper_count_contribution": 0, "units": 40, "scores": 120, "rows": 53160, "independent_audit": rf_review_ref, "scope": "独立附加经典参照，不归给该作者模型或虚增论文数量"})
    proposed_path = output / "five-paper-summary-rows.proposed.json"
    write_new(proposed_path, proposed)
    write_new(output / "new-batch-adoption-proposal.json", {"target_batch_summary": batch_ref, "proposed_summary": ref(str(proposed_path)), "expected_existing_task_count": 5, "RF_paper_count_contribution": 0, "root_acceptance_requested": accept, "root_must_review_then_apply": True, "actual_registry_files_written": 0, "old62_and_oldv4_unchanged": True})
    summary = {"schema": "postjoint-standard-archive240.v1", "created_at": pc.now(), "source_issuance": issuance_ref, "independent_reviews": {"NN": nn_review_ref, "RF": rf_review_ref}, "actual_inventory": inventory, "result_records": len(result_entries), "root_requested_acceptance": accept, "actual_centrally_accepted_records": accepted_count, "standard_result_index": ref(str(index_path)), "new_batch_summary_proposal": ref(str(proposed_path)), "raw_gold_model_prediction_array_reads": 0, "registry_changes": 0, "full_paper_claim": False}
    write_new(output / "ARCHIVE-READY.json", summary)
    print(json.dumps({"records": len(result_entries), "accepted": accepted_count, "raw_payload_reads": 0, "registry_changes": 0}))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    assemble(pc.read(args.inputs), args.out)
