import unittest

import numpy as np
import pandas as pd

from molecular_features import build_features, chemical_features, chiral_canary
from run_molecular_baselines import make_model, models, predict


class MolecularTests(unittest.TestCase):
    def test_chiral_morgan_distinguishes_enantiomers(self):
        self.assertTrue(chiral_canary()["passed"])

    def test_equivalent_smiles_has_same_fingerprint(self):
        np.testing.assert_array_equal(chemical_features("CCO")[:2048],chemical_features("OCC")[:2048])

    def test_phosphorylation_changes_observable_molecular_features(self):
        unmodified = chemical_features("N[C@@H](CO)C(=O)O")
        phosphorylated = chemical_features("N[C@@H](COP(=O)(O)O)C(=O)O")
        self.assertFalse(np.array_equal(unmodified,phosphorylated))

    def test_labels_and_annotation_flags_do_not_enter_features(self):
        frame = pd.DataFrame({"peptide_smiles":["CCO","N[C@@H](C)C(=O)O"],"target_sequence":["ACDEFG","ACDEFG"],"label":[0.,1.],"evaluation_stratum":["PTM","standard20_control"]})
        a,_ = build_features(frame,"affinity")
        frame["label"] = [1e9,-1e9]
        frame["evaluation_stratum"] = ["standard20_control","PTM"]
        b,_ = build_features(frame,"affinity")
        np.testing.assert_array_equal(a,b)

    def test_effect_uses_molecular_difference_with_fixed_target(self):
        frame = pd.DataFrame({"smiles_wt":["N[C@@H](C)C(=O)O"],"smiles_mut":["N[C@H](C)C(=O)O"],"target_sequence":["ACDEFG"],"target_wt_sequence":["ACDEFG"],"target_mut_sequence":["ACDEFG"]})
        a,_ = build_features(frame,"effect")
        frame[["smiles_wt","smiles_mut"]] = frame[["smiles_mut","smiles_wt"]]
        b,_ = build_features(frame,"effect")
        np.testing.assert_array_equal(a[:,2058:4116],-b[:,2058:4116])
        self.assertGreater(np.count_nonzero(a[:,2058:4116]),0)

    def test_invalid_smiles_does_not_fall_back_to_sequence(self):
        with self.assertRaises(ValueError):
            build_features(pd.DataFrame({"peptide_smiles":["not-a-smiles"],"peptide_sequence":["AAAA"],"target_sequence":["ACDEFG"]}),"affinity")

    def test_all_classical_regression_candidates_fit_in_existing_runtime(self):
        rng = np.random.default_rng(7)
        x = rng.normal(size=(30,20)).astype(np.float32)
        y = rng.normal(size=30)
        for name, grid in models(False).items():
            for parameters in grid:
                model = make_model(name,parameters,0,False)
                model.fit(x[:24],y[:24])
                values = predict(model,x[24:],False)
                self.assertTrue(np.isfinite(values).all())


if __name__=="__main__":
    unittest.main()
