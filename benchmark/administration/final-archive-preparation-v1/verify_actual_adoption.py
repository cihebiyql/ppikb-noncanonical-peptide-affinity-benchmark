"""Final read-only verification of the actual scoped new-batch adoption."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent; PROJECT = HERE.parent.parent
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
read = lambda path: json.loads(Path(path).read_text(encoding="utf-8"))
def ref(path): return {"path": str(path), "sha256": sha(path)}

receipt_path = HERE / "ACTUAL-NEW-BATCH-ADOPTION.json"; receipt = read(receipt_path)
target = Path(receipt["target_summary_path"]); rows = read(target)
assert sha(target) == receipt["new_summary_sha256"] == receipt["adopted_proposal"]["sha256"]
assert sha(receipt["old_summary_backup"]["path"]) == receipt["old_summary_sha256"]
assert len(rows) == 5 and all(row["review_status"] == "accepted" and row["scope_coverage"] == "partial_subset" and row["full_paper_reproduction_claim"] is False for row in rows)
final_ref = receipt["final_result_index"]
assert sha(final_ref["path"]) == final_ref["sha256"]
assert all(row["result_record_index"] == final_ref["path"] and row["result_record_index_sha256"] == final_ref["sha256"] for row in rows)
summary = read(receipt["final_validation_summary"]["path"])
assert (summary["record_count"], summary["central_valid_count"], summary["central_accepted_count"], summary["distinct_core_papers"], summary["auxiliary_RF_paper_contribution"]) == (240, 240, 240, 5, 0) and summary["errors"] == []
adoption = read(receipt["final_adoption_validation"]["path"])
assert adoption["ready_for_root_adoption"] and adoption["full_extended_NN_plus_RF_grid_complete"]
assert read(HERE / "archive.actual-exit.json")["exit_code"] == 1
assert read(HERE / "attach.actual-exit.json")["exit_code"] == 0
assert read(HERE / "validate.actual-exit.json")["exit_code"] == 1
assert read(HERE / "VALIDATION-WINDOWS-PATH-RECOVERY.json")["actual_exit_code"] == 0
assert sha(PROJECT.parent.parent / "复现/batches/peptide-binding-nc-benchmark-20261022/campaign.json") == "8831981c5dbe6d43ac1b89e9f01663bf3ccbe1053c5d0708980c2acf0c533295"
handoff = {"schema": "actual-scoped-archive-and-new-batch-handoff.v1", "verified_at": datetime.now(timezone.utc).isoformat(), "adoption_receipt": ref(receipt_path), "new_batch_summary": ref(target), "old_summary_backup": receipt["old_summary_backup"], "final_actual_result_index": final_ref, "original_withCUDA_index_preserved": receipt["original_with_CUDA_index_before_path_alias"], "final_validator_summary": receipt["final_validation_summary"], "final_adoption_validation": receipt["final_adoption_validation"], "original_archive_actual_nonzero_exit": receipt["retained_original_archive_process"], "proposal_only_metadata_path_recovery": receipt["proposal_only_metadata_path_recovery"], "original_validator_actual_nonzero_exit": receipt["retained_original_validator_failure"], "actual_path_alias_revalidation": receipt["contract_path_alias_mapping_and_revalidation"], "actual_postscore_READY": receipt["actual_READY"], "actual_CUDA_chain": receipt["CUDA_chain"], "central_records": 240, "central_valid_records": 240, "central_accepted_records": 240, "core_NN_cells": 200, "auxiliary_RF_cells": 40, "core_papers": 5, "RF_paper_contribution": 0, "both_adoption_gates_true": True, "old_new_batch_campaign_identity_unchanged": True, "old62_merged_rows_and_registry_index_not_written_by_this_execution": True, "raw_model_gold_prediction_files_modified": False, "original_archive_and_original_validator_failures_preserved_not_relabelled": True}
with (HERE / "ACTUAL-ARCHIVE-HANDOFF.json").open("x", encoding="utf-8") as stream: json.dump(handoff, stream, ensure_ascii=False, indent=2); stream.write("\n")
print(json.dumps({"handoff_sha256": sha(HERE / "ACTUAL-ARCHIVE-HANDOFF.json"), "adoption_receipt_sha256": sha(receipt_path), "new_batch_summary_sha256": sha(target), "final_index_sha256": final_ref["sha256"], "central_accepted_records": 240, "papers": 5, "RF_paper_contribution": 0}, indent=2))
