"""Verify existing control/batch metadata only. No actual archive/adoption/score."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent.parent
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
read = lambda path: json.loads(Path(path).read_text(encoding="utf-8"))
chain = PROJECT / "administration/cuda-recovery02-hostexit-v2/postjoint-v2-execution1/CUDA-ATTEMPT-CHAIN.json"
sidecar = PROJECT / "administration/i1/POSTJOINT-CUDA-LINEAGE.json"
issuance = PROJECT / "administration/i1/POSTJOINT-ISSUANCE.json"
bound = read(sidecar)
assert sha(chain) == bound["cuda_attempt_chain"]["sha256"] == "d2338c08ad35006eac485064767c56c95c0b818515a98e813273ac9b8f5b128f"
assert sha(issuance) == bound["issuance"]["sha256"] == "47089749c55431a5305b954940a5584f6654ec3fb0f4ea6b35ccfc398139cb5d"
assert bound["scientific_evaluation_unit_id"] == "MGraphDTA__target_reference_homology_cold__standard_only__seed06__evaluation_v1"
batch = PROJECT.parent.parent / "复现/batches/peptide-binding-nc-benchmark-20261022"
campaign, rows = read(batch / "campaign.json"), read(batch / "summary-rows.json")
ids = {row["task_id"] for row in campaign["tasks"]}
assert ids == {"S299_ef670bb4eeb4", "S300_0a445649ae97", "S301_6cf263a8a267", "S302_401fdeeb8b77", "S303_725e257cf378"} == {row["task_id"] for row in rows}
sources = [PROJECT / name for name in ("administration/assemble_postjoint_archive.py", "administration/archive_stage_result.py", "administration/validate_stage_result_index.py", "administration/cuda-recovery02-hostexit-v2/attach_archive_lineage.py", "review/postscore-driver-v1/driver.py")]
receipt = {"schema": "final-archive-metadata-preparation-verification.v1", "verified_at": datetime.now(timezone.utc).isoformat(), "existing_issuance": {"path": str(issuance), "sha256": sha(issuance)}, "existing_CUDA_sidecar": {"path": str(sidecar), "sha256": sha(sidecar)}, "existing_CUDA_chain": {"path": str(chain), "sha256": sha(chain)}, "actual_chain_equals_i1_sidecar": True, "new_batch_campaign": {"path": str(batch / "campaign.json"), "sha256": sha(batch / "campaign.json")}, "new_batch_summary_before_any_adoption": {"path": str(batch / "summary-rows.json"), "sha256": sha(batch / "summary-rows.json")}, "exact_new_batch_task_ids": sorted(ids), "source_interfaces": [{"path": str(path), "sha256": sha(path)} for path in sources], "actual_archive_or_acceptance_or_registry_actions": 0, "actual_scientific_score_or_model_gold_prediction_reads": 0, "POSTSCORE_ready_or_actual_per_score_audits_read": False}
with (HERE / "verification.json").open("x", encoding="utf-8") as stream: json.dump(receipt, stream, ensure_ascii=False, indent=2); stream.write("\n")
print(json.dumps(receipt, ensure_ascii=False, indent=2))
