"""Synthetic administrative guards only; no real scientific result files read."""
import unittest

import archive_stage_result as archive
import prepare_evaluation_contracts as contracts


class EvaluationAdministrationGuards(unittest.TestCase):
    def test_issuance_requires_root_postbarrier_authorization(self):
        with self.assertRaises(PermissionError):
            contracts.readiness({"root_authorized_after_barrier": False})

    def test_raw_payload_refs_are_rejected_before_any_file_open(self):
        for name in ("gold75.jsonl", "blind-predictions.jsonl", "best.pt", "cache.pkl", "checkpoint.json", "gold13.json"):
            with self.assertRaises(PermissionError):
                archive.metadata({"path": "D:/synthetic-never-open/" + name, "sha256": "0" * 64})

    def test_unit_cannot_certify_its_own_zero_exit(self):
        with self.assertRaises(ValueError):
            archive.actual_execution({"execution": {"exit_code": 0, "handles_absent_verified_at": "synthetic"}}, {}, {}, {}, {}, {})

    def test_pool_actual_exit_and_absence_both_required(self):
        with self.assertRaises(ValueError):
            archive.actual_execution({}, {"exit_code": 0}, {}, {}, {}, {})

    def test_all_three_dataset_target_boundaries_are_preserved(self):
        synthetic_parent = {"targets": [{"target_id": group + ":" + metric, "denominator": 999} for group in ("all", "synthetic_D_backbone", "PTM", "synthetic_and_PTM", "other_NC", "standard20_control", "NC_core") for metric in contracts.METRICS]}
        endpoints = contracts.targets(synthetic_parent)
        self.assertEqual(len(endpoints), 70)
        self.assertEqual(len({r["target_id"] for r in endpoints}), 70)
        for role, expected in (("external75", {75, 67, 8, 2}), ("supplement13", {13, 8, 5})):
            self.assertEqual({r["denominator"] for r in endpoints if r["metric_binding"]["dataset_role"] == role}, expected)
        reviews = [r for r in endpoints if r["metric_binding"]["source"] == "review"]
        self.assertEqual(len(reviews), 15)
        self.assertTrue(all(r["paper_value"] is None and r["tolerance"]["kind"] == "not_comparable" for r in endpoints[35:]))

    def test_RF_schema_alias_is_explicit_and_does_not_mutate_receipt(self):
        original = {"method_id": "RF-Morgan2-chiral-AAC-DP", "panel": "synthetic-panel", "regime": "NC_only", "seed": 9, "selected_model_sha256": "a" * 64, "parameter_updates": 0, "blind_before_gold": True}
        result = archive.normalize_receipt(original)
        self.assertEqual(result["method_id"], "RF-Classic")
        self.assertEqual(result["checkpoint_sha256"], original["selected_model_sha256"])
        self.assertTrue(result["no_parameter_updates"])
        self.assertTrue(result["true_gold_used_only_after_blind_file"])
        self.assertNotIn("checkpoint_sha256", original)
        self.assertEqual(archive.normalized_coordinate(original), archive.normalized_coordinate(result))


if __name__ == "__main__":
    unittest.main()
