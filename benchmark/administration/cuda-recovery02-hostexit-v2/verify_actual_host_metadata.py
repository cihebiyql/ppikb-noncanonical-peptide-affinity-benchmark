"""Read approved actual host/probe/source metadata only; never archive/launch."""
import json
import recovery as r

proof_path = r.PROJECT / "control/old-v5-hostexit1-proof-v2.json"
proof = r.read(proof_path)
r.check_wait(proof, 2, r.POOL_SHA)
observation = r.verify_host_mapping(proof)
print(json.dumps({"status": "actual_host_metadata_verified_without_scientific_payload_access", "actual_root_proof": r.ref(proof_path), "observation": observation, "actual_archive_or_retry_or_model_gold_prediction_reads": 0}, ensure_ascii=False, indent=2))
