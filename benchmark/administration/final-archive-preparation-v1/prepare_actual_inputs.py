"""Materialize root's actual final archival decision from verified READY metadata."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent; PROJECT = HERE.parent.parent
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
read = lambda path: json.loads(Path(path).read_text(encoding="utf-8"))
ready_path = PROJECT / "review/postscore-driver-v2/runs/actual-v2/POSTSCORE-AUDIT-READY.json"
assert sha(ready_path) == "c9c5ae22449822aef294ba281f44915adfad73b46f469d6ebc4d7d2735062480"
ready = read(ready_path)
assert ready["status"] == "complete_postscore_independent_pipeline"
assert ready["source_issuance"]["sha256"] == "47089749c55431a5305b954940a5584f6654ec3fb0f4ea6b35ccfc398139cb5d"
sidecar_path = PROJECT / "administration/i1/POSTJOINT-CUDA-LINEAGE.json"
sidecar = read(sidecar_path)
chain_path = Path(sidecar["cuda_attempt_chain"]["path"])
assert sha(chain_path) == sidecar["cuda_attempt_chain"]["sha256"] == "d2338c08ad35006eac485064767c56c95c0b818515a98e813273ac9b8f5b128f"
for key in ("source_issuance", "NN_independent_per_score_audit", "RF_independent_per_score_audit"):
    assert sha(ready[key]["path"]) == ready[key]["sha256"]
decision = {"root_result_archival_authorized": True, "root_accept_reviewed_records": True, "issuance_index": ready["source_issuance"], "NN_independent_per_score_audit": ready["NN_independent_per_score_audit"], "RF_independent_per_score_audit": ready["RF_independent_per_score_audit"], "actual_READY": {"path": str(ready_path), "sha256": sha(ready_path)}, "CUDA_sidecar": {"path": str(sidecar_path), "sha256": sha(sidecar_path)}, "CUDA_chain": {"path": str(chain_path), "sha256": sha(chain_path)}, "root_review_decision_scope": "Explicit root authorization of actual unified PPIKB adapted retraining partial reproduction, 240 records; original-paper main-table reproduction is not claimed. Root separately reviewed actual NN600/RF120 zero-difference audits, v6/unchanged-prediction diagnostics and pool native0/tree absence proofs. Preserve v1 failure and v2 repair/reused-NN provenance.", "recorded_at": datetime.now(timezone.utc).isoformat(), "deadline_unchanged": "2026-10-22T01:45:00+00:00"}
output = HERE / "archive-inputs.actual-v2.json"
with output.open("x", encoding="utf-8") as stream: json.dump(decision, stream, ensure_ascii=False, indent=2); stream.write("\n")
print(json.dumps({"actual_input": str(output), "sha256": sha(output), "root_actual_archive_and_acceptance_decision_recorded": True, "scientific_processes_started": 0}, indent=2))
