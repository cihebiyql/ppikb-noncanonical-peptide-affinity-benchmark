"""Apply only the specifically authorized new five-paper summary after all gates."""
import argparse
import copy
import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent; PROJECT = HERE.parent.parent
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
read = lambda path: json.loads(Path(path).read_text(encoding="utf-8"))
def write(path, value):
    with Path(path).open("x", encoding="utf-8") as stream: json.dump(value, stream, ensure_ascii=False, indent=2); stream.write("\n")
def ref(path): return {"path": str(path), "sha256": sha(path)}


def main(authorized=False):
    if authorized is not True: raise PermissionError("Explicit root approval of this exact new-batch summary update required")
    if datetime.now(timezone.utc) >= datetime.fromisoformat("2026-10-22T01:45:00+00:00"): raise TimeoutError("Original cutoff unchanged")
    decision = read(HERE / "archive-inputs.actual-v2.json")
    if decision.get("root_result_archival_authorized") is not True or decision.get("root_accept_reviewed_records") is not True: raise PermissionError("Actual scoped archive acceptance missing")
    final_index = PROJECT / "administration/cuda-recovery02-hostexit-v2/f1/standard-result-index.with-CUDA.windows-paths.json"
    validation_root = PROJECT / "administration/v1/normalized-v2"
    validation = read(validation_root / "summary.json")
    adoption = read(validation_root / "batch-result-adoption-proposal.json")
    if validation.get("record_count") != 240 or validation.get("central_valid_count") != 240 or validation.get("central_accepted_count") != 240 or validation.get("errors") or validation.get("distinct_core_papers") != 5 or validation.get("auxiliary_RF_paper_contribution") != 0: raise ValueError("Actual all240 centrally accepted/five core papers/RF0 required")
    if validation.get("source_index_sha256") != sha(final_index): raise ValueError("Validator is not bound to actual finalwithCUDA index")
    if validation.get("stage_coverage", {}).get("evaluation", {}).get("complete200_matrix") is not True or validation.get("auxiliary_RF_coverage", {}).get("evaluation", {}).get("complete40_matrix") is not True: raise ValueError("Actual completeNN200/RF40 ten-seed matrices required")
    if adoption.get("ready_for_root_adoption") is not True or adoption.get("full_extended_NN_plus_RF_grid_complete") is not True or adoption.get("auxiliary_RF_complete_and_accepted") is not True: raise ValueError("Both actual adoption gates must pass")
    final = read(final_index)
    if len(final["records"]) != 240 or final.get("root_reviewed_CUDA_supplement") is not True: raise ValueError("Actual reviewedCUDA240 final index required")
    chain_path = Path(decision["CUDA_chain"]["path"])
    sidecar_path = Path(decision["CUDA_sidecar"]["path"])
    sidecar = read(sidecar_path)
    if sha(chain_path) != sidecar["cuda_attempt_chain"]["sha256"] or sha(chain_path) != "d2338c08ad35006eac485064767c56c95c0b818515a98e813273ac9b8f5b128f" or final["cuda_lineage_supplement"]["sha256"] != sha(chain_path): raise ValueError("Final chain must equal immutablei1 sidecar")
    affected = next(row for row in adoption["records"] if row["run_id"] == sidecar["scientific_evaluation_unit_id"])
    affected_path = Path(affected["result"]["path"])
    affected_result = read(affected_path)
    if affected_result["stage_lineage"]["cuda_recovery02"]["sha256"] != sha(chain_path) or affected_result["review"]["status"] != "accepted": raise ValueError("Affected actual accepted record lacksCUDA history")
    a1 = PROJECT / "administration/a1"
    original_proposal = read(a1 / "new-batch-adoption-proposal.json")
    proposed_source = a1 / "five-paper-summary-rows.proposed.json"
    if sha(proposed_source) != original_proposal["proposed_summary"]["sha256"]: raise ValueError("Original five-row proposal changed")
    batch = PROJECT.parent.parent / "复现/batches/peptide-binding-nc-benchmark-20261022"
    target = batch / "summary-rows.json"
    if target.resolve() != Path(original_proposal["target_batch_summary"]["path"]).resolve() or target.is_symlink(): raise ValueError("Only the named actual new-batch summary may change")
    before = sha(target)
    if before != original_proposal["target_batch_summary"]["sha256"]: raise ValueError("New-batch summary changed after original proposal; do not overwrite")
    ids = {"S299_ef670bb4eeb4", "S300_0a445649ae97", "S301_6cf263a8a267", "S302_401fdeeb8b77", "S303_725e257cf378"}
    old_rows = read(target); proposed = copy.deepcopy(read(proposed_source))
    if len(old_rows) != 5 or len(proposed) != 5 or {row["task_id"] for row in old_rows} != ids or {row["task_id"] for row in proposed} != ids: raise ValueError("Only exact five originally registered identities may be adopted")
    task_counts = Counter(row["task_id"] for row in adoption["records"] if row["family"] == "NN_core")
    if set(task_counts) != ids or set(task_counts.values()) != {40}: raise ValueError("Each core paper must have40 accepted evaluation cells")
    ready_ref = decision["actual_READY"]
    if sha(ready_ref["path"]) != ready_ref["sha256"]: raise ValueError("Actualv2 READY mutated")
    ready = read(ready_ref["path"])
    for row in proposed:
        row.update(result_record_index=str(final_index), result_record_index_sha256=sha(final_index), final_administrative_validation=ref(validation_root / "summary.json"), final_adoption_validation=ref(validation_root / "batch-result-adoption-proposal.json"), benchmark_CUDA_lineage_sidecar=ref(sidecar_path), benchmark_CUDA_attempt_chain=ref(chain_path), actual_independent_audit_pipeline=ready_ref, retained_prior_failed_audit_pipeline=ready["prior_failed_pipeline"], actual_RF_subgroup_audit_recovery=ready["RF_subgroup_audit_recovery_freeze"], training_hyperparameter_evidence=ref(PROJECT / "reporting/training-metadata-v1/FINAL-MANIFEST.json"), existing_epoch_budget_diagnostic=ref(PROJECT / "reporting/training-logs-v1/verification.json"), reproduction_level="training", scope_coverage="partial_subset", review_status="accepted", status="succeeded", lifecycle_status="succeeded", full_paper_reproduction_claim=False)
        if row["task_id"].startswith("S300_"):
            row["differences"] += " 两次技术中断分别为IO watchdog和CUDAunknown，原件/完整归档及同配置恢复链保留；旧池外层exit1与原生exit2推断分开，新retry实际native0。400有效NNfit/200格不因中断增计。"
    proposed_path = HERE / "five-paper-summary-rows.with-CUDA.proposed.json"; write(proposed_path, proposed)
    backup = HERE / "new-batch-summary.before-adoption.json"
    with backup.open("xb") as stream: stream.write(target.read_bytes())
    if sha(backup) != before: raise ValueError("Original summary backup bytes differ")
    if sha(target) != before: raise ValueError("Concurrent target change detected immediately before adoption")
    staging = HERE / "new-batch-summary.atomic-update.json"
    with staging.open("xb") as stream: stream.write(proposed_path.read_bytes())
    os.replace(staging, target)
    after = sha(target)
    if after != sha(proposed_path): raise ValueError("Applied summary bytes do not equal reviewed newproposal")
    receipt = {"schema": "actual-new-batch-scoped-adoption.v1", "adopted_at": datetime.now(timezone.utc).isoformat(), "root_explicit_update_authorized": True, "scope": "UnifiedPPIKB adapted author retraining partial reproduction only, not original-paper main table", "target_summary_path": str(target), "old_summary_sha256": before, "new_summary_sha256": after, "old_summary_backup": ref(backup), "adopted_proposal": ref(proposed_path), "final_result_index": ref(final_index), "final_validation_summary": ref(validation_root / "summary.json"), "final_adoption_validation": ref(validation_root / "batch-result-adoption-proposal.json"), "actual_READY": ready_ref, "CUDA_chain": ref(chain_path), "CUDA_sidecar": ref(sidecar_path), "central_valid_records": 240, "central_accepted_records": 240, "NN_selected_cells": 200, "RF_selected_cells": 40, "distinct_core_papers": 5, "auxiliary_RF_paper_contribution": 0, "retained_interrupted_attempts": 2, "actual_registry_files_written": [str(target)], "old62_campaign_merged_rows_and_registry_index_written": False, "scientific_sources_models_gold_predictions_modified": False, "original_deadline_unchanged": "2026-10-22T01:45:00+00:00"}
    receipt["retained_original_archive_process"] = ref(HERE / "archive.actual-exit.json")
    receipt["original_with_CUDA_index_before_path_alias"] = ref(PROJECT / "administration/cuda-recovery02-hostexit-v2/f1/standard-result-index.with-CUDA-lineage.json")
    receipt["contract_path_alias_mapping_and_revalidation"] = ref(HERE / "VALIDATION-WINDOWS-PATH-RECOVERY.json")
    receipt["retained_original_validator_failure"] = ref(HERE / "validate.actual-exit.json")
    recovery_ready = a1 / "ARCHIVE-METADATA-RECOVERY-READY.json"
    receipt["proposal_only_metadata_path_recovery"] = ref(recovery_ready) if recovery_ready.exists() else None
    write(HERE / "ACTUAL-NEW-BATCH-ADOPTION.json", receipt)
    print(json.dumps({key: receipt[key] for key in ("old_summary_sha256", "new_summary_sha256", "central_accepted_records", "distinct_core_papers", "auxiliary_RF_paper_contribution")}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--root-apply-new-batch-authorized", action="store_true"); args = parser.parse_args(); main(args.root_apply_new_batch_authorized)
