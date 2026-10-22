"""Complete only missing new-batch proposal after the observed outer-path error."""
import copy
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent; PROJECT = HERE.parent.parent; A1 = PROJECT / "administration/a1"
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
read = lambda path: json.loads(Path(path).read_text(encoding="utf-8"))
def local(value): return Path("D:/" + str(value)[len("/mnt/d/"):]) if str(value).startswith("/mnt/d/") else Path(value)
def ref(path): return {"path": str(path), "sha256": sha(path)}
def write(path, value):
    with Path(path).open("x", encoding="utf-8") as stream: json.dump(value, stream, ensure_ascii=False, indent=2); stream.write("\n")


exit_path = HERE / "archive.actual-exit.json"; exited = read(exit_path)
if exited["exit_code"] != 1: raise ValueError("Adapter only applies to the actual retained nonzero original archive process")
stderr = Path(exited["stderr"]["path"])
if sha(stderr) != exited["stderr"]["sha256"]: raise ValueError("Original failure stderr hash differs")
error = stderr.read_text(encoding="utf-8")
if "file.relative_to(PROJECT)" not in error or "summary-rows.json' is not in the subpath" not in error or "postjoint_issue_all.py" not in error: raise ValueError("Failure is not exclusively the diagnosed new-batch metadata path conversion")
if (A1 / "ARCHIVE-READY.json").exists() or (A1 / "five-paper-summary-rows.proposed.json").exists(): raise FileExistsError("Do not overwrite original success/proposal artifacts")
index_path = A1 / "standard-result-index.json"; index = read(index_path)
if index.get("root_result_archival_authorized") is not True or len(index["records"]) != 240: raise ValueError("Original actual240-record index required")
families, tasks, accepted = Counter(), Counter(), 0
for entry in index["records"]:
    result_path, contract_path = local(entry["result"]["path"]), local(entry["contract"]["path"])
    if sha(result_path) != entry["result"]["sha256"] or sha(contract_path) != entry["contract"]["sha256"]: raise ValueError("Original actual contract/result digest differs")
    result, contract = read(result_path), read(contract_path)
    report = read(result_path.parent / "accepted-central-validation.json")
    if result.get("review", {}).get("status") != "accepted" or result.get("lifecycle_status") != "succeeded" or result.get("incomplete_reasons") or report.get("valid_for_acceptance") is not True: raise ValueError("All original240 records must independently remain actually accepted before proposal repair")
    if result["contract_sha256"] != entry["contract"]["sha256"]: raise ValueError("Standard result/contract identity mismatch")
    accepted += 1; families[entry["family"]] += 1
    if entry["family"] == "NN": tasks[contract["task_id"]] += 1
if families != {"NN": 200, "RF": 40} or len(tasks) != 5 or set(tasks.values()) != {40}: raise ValueError("Actual five-paper200+RF40 coverage required")
batch_file = PROJECT.parent.parent / "复现/batches/peptide-binding-nc-benchmark-20261022/summary-rows.json"
if sha(batch_file) != "0a8dea4ad44a98e3dff9fb042fe585535bb8524c401a8b56827b662b5d0d6019": raise ValueError("New-batch original target changed; do not fabricate a stale proposal")
existing = read(batch_file)
if len(existing) != 5 or {row["task_id"] for row in existing} != set(tasks): raise ValueError("Only exact newbatch identities allowed")
decision = read(HERE / "archive-inputs.actual-v2.json")
if not decision["root_accept_reviewed_records"] or not decision["root_result_archival_authorized"]: raise PermissionError("Actual root acceptance authority absent")
proposed = copy.deepcopy(existing)
for row in proposed:
    row.update(status="succeeded", lifecycle_status="succeeded", reproduction_level="training", scope_coverage="partial_subset", review_status="accepted", summary="共同NC亲和力基准：该作者实现完成2面板×2训练口径×10种子，实际训练与三数据评分收据、独立重算均保留。", actual_results="80候选拟合、40验证选择、120评分收据；详细数值与每seed结果见本轮标准结果索引及独立审计。", differences="改变数据集与任务范围；原论文主表不作直接数值复现比较。蛋白前缀、化学表示限制、必要适配与统一预算均保留。", incomplete_reason=None, result_record_index=str(index_path), independent_NN_audit=decision["NN_independent_per_score_audit"], additional_classic_RF={"paper_count_contribution": 0, "units": 40, "scores": 120, "rows": 53160, "independent_audit": decision["RF_independent_per_score_audit"], "scope": "独立附加经典参照，不归给该作者模型或虚增论文数量"})
proposal = A1 / "five-paper-summary-rows.proposed.json"; write(proposal, proposed)
write(A1 / "new-batch-adoption-proposal.json", {"target_batch_summary": ref(batch_file), "proposed_summary": ref(proposal), "expected_existing_task_count": 5, "RF_paper_count_contribution": 0, "root_acceptance_requested": True, "root_must_review_then_apply": True, "actual_registry_files_written": 0, "old62_and_oldv4_unchanged": True, "metadata_path_recovery_adapter": ref(__file__), "retained_original_nonzero_archive_exit": ref(exit_path)})
receipt = {"schema": "explicit-proposal-only-metadata-path-recovery.v1", "completed_at": datetime.now(timezone.utc).isoformat(), "original_archive_exit": ref(exit_path), "original_archive_stderr": ref(stderr), "original240_record_index": ref(index_path), "original_records_independently_verified_accepted": accepted, "actual_families": dict(families), "actual_core_papers": len(tasks), "missing_proposal_completed": ref(proposal), "new_batch_proposal_metadata": ref(A1 / "new-batch-adoption-proposal.json"), "adapter_source": ref(__file__), "failure_scope": "Original assembler completed240 accepted records/index then failed only converting external batch summary metadata path; original process remains exit1 and original ARCHIVE-READY is not created", "scientific_or_record_archival_steps_rerun": 0, "original_sources_index_records_or_logs_modified": False, "actual_registry_updates": 0, "raw_model_gold_prediction_reads": 0}
write(A1 / "ARCHIVE-METADATA-RECOVERY-READY.json", receipt)
print(json.dumps({"original_records_verified_accepted": accepted, "actual_families": dict(families), "original_archive_exit_preserved": 1, "proposal_only_recovery": True}, indent=2))
