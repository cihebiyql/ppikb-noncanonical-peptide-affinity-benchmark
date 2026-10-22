"""Administrative guard tests; all fixture identities are synthetic, no model executes."""
import copy
import unittest
from pathlib import Path

import prepare_campaign as pc


class AdministrativeGuards(unittest.TestCase):
    def setUp(self):
        self.config = {"seeds": list(range(10)), "methods": [], "splits": [], "training_regimes": []}

    def test_seed_coverage_cannot_be_silently_reduced(self):
        self.config["seeds"] = [0]
        with self.assertRaises(ValueError):
            pc.validate_plan(self.config)

    def test_output_cannot_escape_write_ownership(self):
        with self.assertRaises(ValueError):
            pc.inside_admin(pc.ADMIN.parent / "other-agent-owned.json")

    def test_duplicate_paper_variants_do_not_count_as_five_papers(self):
        self.config["methods"] = [{"method_id": f"synthetic_{n}", "paper_identity_key": "same-synthetic-paper"} for n in range(5)]
        gaps = pc.validate_plan(self.config)
        self.assertTrue(any("five distinct" in text for text in gaps))

    def test_seeds_preserve_the_method_clock_and_cannot_be_executable(self):
        method = {"method_id": "synthetic_guard_fixture", "task_id": "synthetic-only", "timing": {"first_substantive_started_at": "2000-01-01T00:00:00+00:00", "effective_deadline_at": "2000-01-01T10:00:00+00:00", "retry_resets_clock": True}}
        before = copy.deepcopy(method)
        for seed in range(10):
            draft = pc.build_contract(self.config, method, {"split_id": "synthetic"}, {"regime_id": "synthetic"}, seed, f"fixture{seed}", "2000-01-01T01:00:00+00:00")
            self.assertEqual(draft["timing"]["first_substantive_started_at"], before["timing"]["first_substantive_started_at"])
            self.assertEqual(draft["timing"]["effective_deadline_at"], before["timing"]["effective_deadline_at"])
            self.assertFalse(draft["timing"]["retry_resets_clock"])
            self.assertTrue(draft["is_template"])
            self.assertIsNone(draft["frozen_at"])
            self.assertEqual(draft["execution"]["seeds"], [seed])
        self.assertEqual(method, before)

    def test_stable_id_rejects_path_traversal(self):
        for bad in ("../escape", "path/slash", "", None):
            with self.assertRaises(ValueError):
                pc.slug(bad)


if __name__ == "__main__":
    unittest.main()
