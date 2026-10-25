"""Migration fixtures reject original4f/e2 inputs and mixed candidate plans."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from dataset_binding import (MANIFEST_SHA, SPEC_SHA, CSV_SHA, FRAME_SPLITS,
                             validate_hashes, validate_frozen_files, validate_target_view, validate_plan)

HERE = Path(__file__).resolve().parent
TORCH_WAS_IMPORTED = "torch" in sys.modules


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads((HERE / "PLAN.actual.json").read_text(encoding="utf-8"))

    def test_actual_approved_metadata_and_plan(self):
        validate_frozen_files(HERE / "inputs/approved-manifest.json", HERE / "inputs/approved-feature-spec.json")
        manifest = json.loads((HERE / "inputs/approved-manifest.json").read_text(encoding="utf-8"))
        view, = [v for v in manifest["views"] if v["id"] == "ppikb_kd_target_global_firewall_v1"]
        validate_target_view(view, CSV_SHA)
        self.assertTrue(validate_plan(self.plan))

    def test_original_e2_manifest_rejected(self):
        with self.assertRaises(ValueError):
            validate_hashes("e2deb8ee4d3533c33d87401f8df35eb0ea5a3c366e06a6f46d662772bc729190", SPEC_SHA, CSV_SHA)

    def test_original4f_csv_rejected(self):
        with self.assertRaises(ValueError):
            validate_hashes(MANIFEST_SHA, SPEC_SHA, "4f4694b8937c6e3bd2e5b1091faf948fd66ecc57180b09d0ff5c236cded83c60")

    def test_original9cde_protein_spec_rejected(self):
        with self.assertRaises(ValueError):
            validate_hashes(MANIFEST_SHA, "9cde3fd5d87e5e4d597393f640a5b8eb9ede702f853e9511e88841414e682db7", CSV_SHA)

    def test_original_partition_counts_rejected(self):
        with self.assertRaises(ValueError):
            validate_hashes(MANIFEST_SHA, SPEC_SHA, CSV_SHA, {"train": 497, "validation": 495, "test": 656, "external": 0})
        validate_hashes(MANIFEST_SHA, SPEC_SHA, CSV_SHA, FRAME_SPLITS)

    def test_plan_cannot_mix_one_original_candidate(self):
        plan = copy.deepcopy(self.plan)
        plan["candidates"][7]["manifest_path"] = "/old/e2deb/frozen-manifest.json"
        with self.assertRaises(ValueError):
            validate_plan(plan)

    def test_plan_cannot_change_training_budget(self):
        for name, value in [("batch_size", 4), ("max_epochs", 31), ("head", [832, 256, 1])]:
            plan = copy.deepcopy(self.plan)
            plan["training_settings"][name] = value
            with self.assertRaises(ValueError):
                validate_plan(plan)
        plan = copy.deepcopy(self.plan)
        plan["candidates"].pop()
        with self.assertRaises(ValueError):
            validate_plan(plan)

    def test_production_prepare_calls_data_guards_and_model_is_unchanged(self):
        source = (HERE / "train_finetune.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        prepare, = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "prepare"]
        self.assertEqual(prepare.body[0].value.func.id, "validate_frozen_files")
        calls = [n.func.id for n in ast.walk(prepare) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)]
        self.assertIn("validate_target_view", calls)
        self.assertEqual(hashlib.sha256((HERE / "model_adapter.py").read_bytes()).hexdigest(),
                         "d935cd85f8009e8c243fb42550c24dbe08f22e55a77fe8efbc6d81f35052fc27")
        self.assertEqual("torch" in sys.modules, TORCH_WAS_IMPORTED)


if __name__ == "__main__":
    unittest.main(verbosity=2)
