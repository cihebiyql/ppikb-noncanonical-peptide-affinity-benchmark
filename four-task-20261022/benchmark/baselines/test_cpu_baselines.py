import unittest
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from run_cpu_baselines import audit_frame, build_features, is_binary, metrics, seq_features, make_model, models, predict, save_predictions


class ProtocolTests(unittest.TestCase):
    def frame(self):
        return pd.DataFrame({"row_id": ["a", "b", "c"], "split": ["train", "validation", "test"],
                             "group_id": ["g1", "g2", "g3"], "peptide_sequence": ["ACD", "ACy", "DED"],
                             "target_sequence": ["ALW", "ALW", "ALW"], "label": [0., 1., 0.]})

    def test_groups_cannot_cross_frozen_splits(self):
        frame = self.frame()
        frame.loc[1, "group_id"] = "g1"
        with self.assertRaisesRegex(ValueError, "dependency groups"):
            audit_frame(frame, "classification")

    def test_features_do_not_read_labels(self):
        frame = self.frame()
        actual, _ = build_features(frame, "classification")
        frame["label"] = [12., 87., -3.]
        changed, _ = build_features(frame, "classification")
        np.testing.assert_array_equal(actual, changed)

    def test_lowercase_ptm_is_not_changed_to_standard_tyrosine(self):
        ptm = seq_features("AAy")
        standard = seq_features("AAY")
        self.assertGreater(ptm[20], 0)
        self.assertEqual(standard[20], 0)
        self.assertFalse(np.array_equal(ptm, standard))

    def test_single_class_auc_and_constant_correlations_are_undefined(self):
        self.assertIsNone(metrics(np.array([0, 0]), np.array([.1, .2]), True)["auroc"])
        self.assertIsNone(metrics(np.array([1., 2.]), np.array([1., 1.]), False)["pearson"])

    def test_contact_coordinates_and_gold_never_enter_features(self):
        frame = self.frame()
        frame["residue_index"] = [1, 2, 3]
        frame["distance"] = [1., 50., 60.]
        first, _ = build_features(frame, "contact")
        frame["distance"] = [100., 1., 0.]
        frame["label"] = [1., 0., 1.]
        second, _ = build_features(frame, "contact")
        np.testing.assert_array_equal(first, second)
        self.assertTrue(is_binary("binding_site"))

    def test_effect_uses_mutation_inputs(self):
        frame = self.frame()
        frame["peptide_wt_sequence"] = "AAA"
        frame["peptide_mut_sequence"] = ["AAC", "AAD", "AAE"]
        first, _ = build_features(frame, "effect")
        frame["peptide_mut_sequence"] = "AAA"
        second, _ = build_features(frame, "effect")
        self.assertFalse(np.array_equal(first, second))

    def test_all_candidate_estimators_fit_and_predict(self):
        rng = np.random.default_rng(42)
        x = rng.normal(size=(30, 12)).astype(np.float32)
        for binary in (False, True):
            y = np.asarray([0, 1] * 15) if binary else rng.normal(size=30)
            for name, grid in models(binary).items():
                for params in grid:
                    model = make_model(name, params, 0, binary)
                    model.fit(x[:24], y[:24])
                    result = predict(model, x[24:], binary)
                    self.assertEqual(result.shape, (6,))
                    self.assertTrue(np.isfinite(result).all())

    def test_prediction_float_csv_roundtrip_preserves_rank_ties(self):
        frame = self.frame()
        frame["label"] = [3.123456789012345, 3.123456789012345, 7.903089986991944]
        predicted = np.asarray([2.123456789012345, 5.123456789012345, 6.903089986991944])
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "predictions.csv"
            save_predictions(path, frame, predicted, 0.5, False)
            loaded = pd.read_csv(path, float_precision="round_trip")
        np.testing.assert_array_equal(loaded.label.to_numpy(), frame.label.to_numpy())
        np.testing.assert_array_equal(loaded.prediction.to_numpy(), predicted)


if __name__ == "__main__":
    unittest.main()
