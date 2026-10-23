"""Verify unchanged manual features/grid and exact ESM row-level input coverage."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE))
import run_manual_controls as control
spec=importlib.util.spec_from_file_location('original_cpu',ROOT/'baselines/frozen-code/cpu-baselines-v2.py')
original=importlib.util.module_from_spec(spec);spec.loader.exec_module(original)
class ControlsTest(unittest.TestCase):
    def test_grid_and_solver_unchanged(self):
        self.assertEqual(control.models(False),original.models(False))
        for parameters in control.models(False)['linear']:
            self.assertEqual(control.make_model('linear',parameters,0,False)[1].solver,'auto')
    def test_features_exact_and_label_independent(self):
        manifest=json.loads((HERE/'coverage-manifest.json').read_text(encoding='utf-8'))
        for view in manifest['views']:
            frame=pd.read_csv(view['path'],keep_default_na=False,float_precision='round_trip')
            if view['task']=='effect':
                self.assertTrue((frame.peptide_wt_sequence==frame.embedding_peptide_wt).all())
                self.assertTrue((frame.peptide_mut_sequence==frame.embedding_peptide_mut).all())
            else:self.assertTrue((frame.peptide_sequence==frame.embedding_peptide).all())
            self.assertTrue((frame.target_sequence==frame.embedding_target).all())
            sampled=frame.head(44).copy()
            new,_=control.build_features(sampled,view['task']);old,_=original.build_features(sampled,view['task'])
            np.testing.assert_array_equal(new,old)
            sampled['label']=sampled['label']+12345
            altered,_=control.build_features(sampled,view['task'])
            np.testing.assert_array_equal(new,altered)
            self.assertEqual(new.shape[1],435 if view['task']=='effect' else 174)
if __name__=='__main__':unittest.main(verbosity=2)
