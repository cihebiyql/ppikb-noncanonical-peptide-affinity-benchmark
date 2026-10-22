"""Synthetic fixtures and pure guards only; never actual scientific outputs."""
import copy
import os
import time
import unittest
from pathlib import Path
from unittest.mock import patch
import recovery as r
import postjoint_gate_v2 as g
import postjoint_v2 as p
import attach_archive_lineage as a


class RecoveryTests(unittest.TestCase):
    def ids(self): return [r.UID] + ["synthetic-" + str(i) for i in range(199)]
    def old(self): return {"status": "complete", "reason": None, "pending": 0, "active": [], "cleanup_errors": [], "complete_count": 199, "failed_count": 1, "completed_units": self.ids()[1:], "failed_units": [{"unit_id": r.UID, "reason": "wrapper_exit_1"}], "index_sha256": r.POOL_SHA, "deadline": r.GLOBAL}
    def retry(self): return {"status": "complete", "reason": None, "pending": 0, "active": [], "cleanup_errors": [], "complete_count": 200, "failed_count": 0, "completed_units": self.ids(), "failed_units": [], "index_sha256": "synthetic-retry-index", "deadline": r.CEILING}
    def wait(self, code, digest):
        value = {"exit_code": 1 if code == 2 else code, "pool_pid": 12345, "index_sha256": digest, "root_observed_actual_wait": True, "observed_at": "synthetic-time", "source": "synthetic actual wait fixture", "native_exit_directly_observed": code != 2, "native_exit_code": code}
        if code == 2: value.update(outer_tool_exit_code=1, native_expected_exit_from_verified_terminal=2, normalization_probe={"path": "synthetic-probe.json", "sha256": "synthetic"})
        return value

    def test_old199failed1_is_honestly_accepted(self): r.check_old_terminal(self.old(), self.ids())
    def test_old200_success_is_not_this_recovery(self):
        body = self.old(); body.update(complete_count=200, failed_count=0)
        with self.assertRaises(PermissionError): r.check_old_terminal(body, self.ids())
    def test_old_different_failure_is_rejected(self):
        body = self.old(); body["failed_units"][0]["unit_id"] = "different-unit"
        with self.assertRaises(ValueError): r.check_old_terminal(body, self.ids())
    def test_old_still_active_is_rejected(self):
        body = self.old(); body["active"] = ["running"]
        with self.assertRaises(PermissionError): r.check_old_terminal(body, self.ids())
    def test_old_wrong_source_rejected(self):
        body = self.old(); body["index_sha256"] = "old-v4"
        with self.assertRaises(ValueError): r.check_old_terminal(body, self.ids())
    def test_actual_exit2_and_exit0_shapes(self):
        r.check_wait(self.wait(2, r.POOL_SHA), 2, r.POOL_SHA)
        r.check_wait(self.wait(0, "retry"), 0, "retry")
    def test_old_exit2_cannot_be_relabelled_exit0(self):
        with self.assertRaises(PermissionError): r.check_wait(self.wait(0, r.POOL_SHA), 2, r.POOL_SHA)
    def test_no_fabricated_original_native2_receipt(self):
        value = self.wait(2, r.POOL_SHA); value.update(exit_code=2, native_exit_directly_observed=True)
        with self.assertRaises(PermissionError): r.check_wait(value, 2, r.POOL_SHA)
    def test_no_original_direct_native_observation_claim(self):
        value = self.wait(2, r.POOL_SHA); value["native_exit_directly_observed"] = True
        with self.assertRaises(PermissionError): r.check_wait(value, 2, r.POOL_SHA)
    def test_missing_normalization_evidence_rejected(self):
        value = self.wait(2, r.POOL_SHA); del value["normalization_probe"]
        with self.assertRaises(PermissionError): r.check_wait(value, 2, r.POOL_SHA)
    def test_future_retry_requires_direct_native0(self):
        value = self.wait(0, "retry"); value["native_exit_directly_observed"] = False
        with self.assertRaises(PermissionError): r.check_wait(value, 0, "retry")
    def test_boolean_exit_is_not_integer_wait(self):
        with self.assertRaises(PermissionError): r.check_wait(self.wait(False, "retry"), 0, "retry")
    def test_retry_full200_with_original_ceiling(self): g.retry_terminal(self.retry(), self.ids(), "synthetic-retry-index")
    def test_retry_global_deadline_would_reset_window(self):
        body = self.retry(); body["deadline"] = r.GLOBAL
        with self.assertRaises(ValueError): g.retry_terminal(body, self.ids(), "synthetic-retry-index")
    def test_retry_second_failure_is_terminal(self):
        body = self.retry(); body.update(complete_count=199, failed_count=1)
        with self.assertRaises(PermissionError): g.retry_terminal(body, self.ids(), "synthetic-retry-index")
    def test_binding_only_two_permitted_changes(self):
        old = {"deadline": r.GLOBAL, "binding_receipt": "old-receipt.json", "spec": "original-spec.json", "spec_sha256": r.SPEC_SHA, "contract_sha256": r.CONTRACT_SHA}
        before = copy.deepcopy(old); new = r.retry_binding(old, "new-isolated-receipt.json")
        self.assertEqual(old, before); self.assertEqual(new["deadline"], r.CEILING)
        self.assertEqual({key for key in old if old[key] != new[key]}, {"deadline", "binding_receipt"})
    def test_preparation_execute_false_reads_nothing(self):
        with patch.object(r, "read", side_effect=AssertionError("No real reads")):
            with self.assertRaises(PermissionError): r.execute("unused", "unused", "unused", False)
    def test_postjoint_v2_false_reads_nothing(self):
        with patch.object(p, "load_original_utility", side_effect=AssertionError("No external source loaded")):
            with self.assertRaises(PermissionError): p.execute("unused", "unused", "unused", "unused", "unused", False)
    def test_gate_false_reads_nothing(self):
        with patch.object(r, "read", side_effect=AssertionError("No real reads")):
            with self.assertRaises(PermissionError): g.gate("unused", "unused", "unused", "unused", "unused", False)
    def test_archive_attachment_false_reads_nothing(self):
        with patch.object(r, "read", side_effect=AssertionError("No real reads")):
            with self.assertRaises(PermissionError): a.attach("unused", "unused", "unused", False)
    def fixture(self):
        folder = r.HERE / ("synthetic-fixture-" + str(time.time_ns())); folder.mkdir()
        source = folder / "source"; source.mkdir(); (source / "child").mkdir(); (source / "child" / "synthetic.bin").write_bytes(b"synthetic preserved bytes")
        scope = folder / "archives"; scope.mkdir()
        return folder, source, scope
    def test_fixture_inventory_and_atomic_rename_preserve_all_bytes(self):
        folder, source, scope = self.fixture(); source, target = r.safe_target(source, scope / "archived", project=folder, scope=scope)
        rows = r.inventory(source, target); r.assert_inventory(source, rows); os.rename(source, target); r.assert_inventory(target, rows, archived=True)
        self.assertFalse(source.exists()); self.assertEqual((target / "child/synthetic.bin").read_bytes(), b"synthetic preserved bytes")
    def test_fixture_changed_bytes_rejected(self):
        folder, source, scope = self.fixture(); rows = r.inventory(source, scope / "archived"); (source / "child/synthetic.bin").write_bytes(b"changed")
        with self.assertRaises(ValueError): r.assert_inventory(source, rows)
    def test_existing_archive_path_rejected(self):
        folder, source, scope = self.fixture(); target = scope / "exists"; target.mkdir()
        with self.assertRaises(ValueError): r.safe_target(source, target, project=folder, scope=scope)
    def test_source_outside_project_rejected(self):
        folder, source, scope = self.fixture()
        with self.assertRaises(ValueError): r.safe_target(r.HERE, scope / "archived", project=folder, scope=scope)
    def test_new_index_cannot_add_new_scientific_coordinates(self):
        original = self.ids(); reordered = [r.UID] + [uid for uid in original if uid != r.UID]
        self.assertEqual(len(reordered), 200); self.assertEqual(set(original), set(reordered)); self.assertNotIn(r.ATTEMPT, reordered)


if __name__ == "__main__": unittest.main()
