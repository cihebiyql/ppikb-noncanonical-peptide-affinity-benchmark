"""Synthetic only: no actual producer, selection, weight, gold or prediction reads."""
import copy
import unittest
from unittest.mock import patch

import root_postjoint as windows
import wsl_prepare as wsl


class RootPostjointTests(unittest.TestCase):
    def terminal(self):
        return {"status": "complete", "reason": None, "pending": 0, "active": [], "failed_count": 0, "failed_units": [], "cleanup_errors": [], "complete_count": 200, "completed_units": ["synthetic-" + str(i) for i in range(200)], "index_sha256": wsl.POOL_INDEX_SHA, "deadline": wsl.DEADLINE}

    def test_complete_exact_terminal(self):
        body = self.terminal()
        wsl.check_terminal(body, body["completed_units"])

    def test_reject_running_partial_failed_or_wrong_source(self):
        for change in ({"status": "running"}, {"complete_count": 199}, {"active": ["synthetic-active"]}, {"failed_count": 1}, {"index_sha256": "old-v4"}, {"cleanup_errors": ["synthetic"]}, {"deadline": "later-reset-deadline"}):
            body = self.terminal()
            body.update(change)
            with self.subTest(change=change), self.assertRaises((PermissionError, ValueError)):
                wsl.check_terminal(body, self.terminal()["completed_units"])

    def test_duplicate_completed_units_are_rejected(self):
        body = self.terminal()
        body["completed_units"][-1] = body["completed_units"][0]
        with self.assertRaises(ValueError):
            wsl.check_terminal(body, self.terminal()["completed_units"])

    def exit(self):
        return {"exit_code": 0, "pool_pid": 123456, "index_sha256": wsl.POOL_INDEX_SHA, "observed_at": "synthetic-time", "source": "synthetic actual-wait fixture", "root_observed_actual_wait": True}

    def test_actual_wait_evidence_shape(self):
        wsl.check_exit(self.exit())

    def test_missing_wait_or_nonzero_exit_rejected(self):
        for change in ({"exit_code": False}, {"exit_code": -15}, {"pool_pid": 0}, {"index_sha256": "wrong"}, {"root_observed_actual_wait": False}, {"source": ""}):
            body = self.exit()
            body.update(change)
            with self.subTest(change=change), self.assertRaises(PermissionError):
                wsl.check_exit(body)

    def test_full1800_reserve_does_not_reset_clock(self):
        wsl.reserve(wsl.CUTOFF - 1801)
        with self.assertRaises(TimeoutError):
            wsl.reserve(wsl.CUTOFF - 1800)

    def test_windows_explicit_flag_precedes_all_file_reads(self):
        with patch.object(windows, "sha", side_effect=AssertionError("No file reads")):
            with self.assertRaises(PermissionError):
                windows.root_execute("unused.json", "unused", "unused", authorized=False)

    def test_wsl_explicit_flag_precedes_all_file_reads(self):
        with patch.object(wsl, "read", side_effect=AssertionError("No file reads")):
            with self.assertRaises(PermissionError):
                wsl.prepare("unused", "unused.json", "unused", authorized=False)

    def test_scientific_runner_has_no_score_command(self):
        # Source-only inspection, no import of runner/Torch or execution.
        source = (wsl.HERE / "wsl_prepare.py").read_text(encoding="utf-8")
        self.assertNotIn('"score", "--', source)
        self.assertNotIn('"fit", "--', source)
        self.assertIn('"audit-barrier"', source)

    def test_inputs_not_mutated_by_pure_guards(self):
        body = self.terminal()
        original = copy.deepcopy(body)
        wsl.check_terminal(body, body["completed_units"])
        self.assertEqual(body, original)


if __name__ == "__main__":
    unittest.main()
