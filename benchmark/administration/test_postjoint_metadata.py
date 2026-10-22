"""Pure synthetic tests only; no actual selected/model/gold/prediction reads."""
import copy
import unittest
from unittest.mock import patch

import assemble_postjoint_archive as archive
import postjoint_issue_all as issuer


class PostjointMetadataTests(unittest.TestCase):
    def test_issuer_requires_authority_before_metadata(self):
        with patch.object(issuer, "read_ref", side_effect=AssertionError("No real metadata read")):
            with self.assertRaises(PermissionError):
                issuer.issue({"root_postjoint_metadata_issuance_authorized": False}, "unused")

    def test_archiver_requires_authority_before_metadata(self):
        with patch.object(archive, "read_ref", side_effect=AssertionError("No real metadata read")):
            with self.assertRaises(PermissionError):
                archive.assemble({"root_result_archival_authorized": False}, "unused")

    def joint(self):
        joint = {"status": "all_200_NN_plus_40_RF_frozen", "NN_selections": 200, "RF_selections": 40, "NN_candidate_fits": 400, "RF_candidate_fits": 80, "NN_execution_index_sha256": issuer.APPROVED_NN_INDEX, "NN_barrier_sha256": "nn", "RF_barrier_sha256": "rf"}
        nn = {"status": "all_selections_frozen", "selection_count": 200, "candidate_fit_count": 400, "selections": [{} for _ in range(200)], "execution_index_sha256": issuer.APPROVED_NN_INDEX}
        rf = {"status": "all_40_RF_selections_frozen", "selection_count": 40, "candidate_fit_count": 80, "selections": [{} for _ in range(40)]}
        audit = {"status": "all_200_selections_and_checkpoints_verified", "selections": [{} for _ in range(200)], "barrier_sha256": "nn", "execution_index_sha256": issuer.APPROVED_NN_INDEX}
        references = {"NN_barrier": {"sha256": "nn"}, "RF_barrier": {"sha256": "rf"}}
        return joint, nn, rf, audit, references

    def test_complete_joint(self):
        issuer.check_joint(*self.joint())

    def test_joint_rejects_wrong_recovery_source(self):
        values = self.joint()
        values[0]["NN_execution_index_sha256"] = "superseded-v4"
        with self.assertRaises(ValueError):
            issuer.check_joint(*values)

    def test_joint_rejects_missing_actual_candidate_fits(self):
        values = self.joint()
        del values[0]["RF_candidate_fits"]
        with self.assertRaises(ValueError):
            issuer.check_joint(*values)

    def test_joint_rejects_wrong_linked_hash(self):
        values = self.joint()
        values[0]["RF_barrier_sha256"] = "different"
        with self.assertRaises(ValueError):
            issuer.check_joint(*values)

    def test_joint_rejects_partial_checkpoint_audit(self):
        values = self.joint()
        values[3]["selections"].pop()
        with self.assertRaises(ValueError):
            issuer.check_joint(*values)

    def grid(self, rf=False):
        cells = [(p, r, s) for p in issuer.PANELS for r in ("NC_only", "standard_only") for s in range(10)]
        return cells if rf else [(m, *c) for m in issuer.METHODS for c in cells]

    def test_exact_nn200_grid(self):
        issuer.candidate_grid(self.grid())

    def test_exact_rf40_grid(self):
        issuer.candidate_grid(self.grid(True), rf=True)

    def test_grid_rejects_duplicate_seed(self):
        grid = self.grid()
        grid[-1] = grid[0]
        with self.assertRaises(ValueError):
            issuer.candidate_grid(grid)

    def test_grid_rejects_extra_recovery_as_201st_cell(self):
        with self.assertRaises(ValueError):
            issuer.candidate_grid(self.grid() + [self.grid()[0]])

    def test_binding_nn_matches_issued_stage(self):
        stage = {"selection": {"path": "synthetic-selected.json", "sha256": "sel"}, "datasets": [{"score_spec": {"path": f"spec-{i}.json", "sha256": str(i)}} for i in range(3)], "root_score_authorization": {"path": "auth.json", "sha256": "a"}, "root_barrier": {"path": "barrier.json", "sha256": "b"}, "root_barrier_audit": {"path": "audit.json", "sha256": "c"}, "code_files": [], "score_root": "synthetic-score-root"}
        original = copy.deepcopy(stage)
        record = {"contract_path": "contract.json", "contract_sha256": "contract", "validation_path": "validation.json", "validation_sha256": "validation"}
        with patch.object(issuer, "wsl", side_effect=str):
            binding = issuer.binding_from_contract({"run_id": "synthetic-unit", "evaluation_stage": stage}, record, {"issued": False, "timeout_seconds": 1200}, "NN", {"score_unit.py": "u", "score_pool.py": "p", "score_common.py": "c"})
        self.assertTrue(binding["issued"])
        self.assertEqual(binding["selection"], stage["selection"])
        self.assertEqual(binding["score_specs"], [row["score_spec"] for row in stage["datasets"]])
        self.assertEqual(binding["deadline"], issuer.DEADLINE)
        self.assertEqual(stage, original)

    def test_binding_rf_preserves_exact_11_stage_fields(self):
        names = ("selection", "score_specs", "authorization", "joint_barrier", "NN_barrier", "RF_barrier", "live_cpu_proof", "worker", "code_files", "receipt_root", "score_root")
        stage = {name: [name] if name in ("score_specs", "code_files") else {"synthetic": name} for name in names}
        record = {"contract_path": "contract.json", "contract_sha256": "c", "validation_path": "validation.json", "validation_sha256": "v"}
        with patch.object(issuer, "wsl", side_effect=str):
            binding = issuer.binding_from_contract({"run_id": "synthetic-rf", "rf_score_execution_stage": stage}, record, {"issued": False, "timeout_seconds": 1800}, "RF", {"rf_score_unit.py": "u", "rf_score_pool.py": "p", "rfs_common.py": "c"})
        self.assertEqual({name: binding[name] for name in names}, stage)
        self.assertEqual(binding["timeout_seconds"], 1800)

    def audits(self, n):
        return [{"all_truths_match_frozen_gold": True, "runner_metric_differences": [], "score_receipt_sha256": f"synthetic-{i}"} for i in range(n)]

    def test_independent_exact_nn600_and_rf120(self):
        self.assertEqual(len(archive.audit_index(self.audits(600), 600)), 600)
        self.assertEqual(len(archive.audit_index(self.audits(120), 120)), 120)

    def test_independent_rejects_duplicate_producer(self):
        rows = self.audits(120)
        rows[-1]["score_receipt_sha256"] = rows[0]["score_receipt_sha256"]
        with self.assertRaises(ValueError):
            archive.audit_index(rows, 120)

    def test_independent_rejects_metric_disagreement(self):
        rows = self.audits(120)
        rows[0]["runner_metric_differences"] = [{"metric": "MAE", "synthetic_disagreement": True}]
        with self.assertRaises(ValueError):
            archive.audit_index(rows, 120)

    def test_independent_rejects_partial_verification(self):
        rows = self.audits(120)
        rows[0]["all_truths_match_frozen_gold"] = False
        with self.assertRaises(ValueError):
            archive.audit_index(rows, 120)

    def test_payloads_rejected_before_open(self):
        with patch.object(issuer.pc, "sha", side_effect=AssertionError("No payload hash read")):
            for name in ("synthetic-model.pt", "synthetic-array.pkl", "synthetic-gold.json", "synthetic-predictions.jsonl"):
                with self.assertRaises(PermissionError):
                    issuer.ref(name)


if __name__ == "__main__":
    unittest.main()
