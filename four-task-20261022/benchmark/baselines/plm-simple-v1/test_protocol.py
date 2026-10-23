"""Semantic checks for raw coverage and the effect representation before any fitting."""
import csv
import importlib.util
import json
import sys
import unittest
from pathlib import Path
import hashlib
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import plm_features
import prepare_inputs
import verify_results

class ProtocolTests(unittest.TestCase):
    def test_independent_scoring_ties_and_constants(self):
        from scipy.stats import spearmanr
        from sklearn.metrics import mean_absolute_error, r2_score
        fixtures=[([1.,2.,2.,4.],[2.,2.,3.,1.]),([1.,2.,4.],[3.,3.,3.]),
                  ([1.,1.,1.],[1.,2.,3.]),([1.],[2.])]
        for y,p in fixtures:
            result=verify_results.metrics(y,p,False)
            self.assertAlmostEqual(result['mae'],mean_absolute_error(y,p),places=12)
            if len(y)>1 and max(y)>min(y):
                self.assertAlmostEqual(result['r2'],r2_score(y,p),places=12)
            else:self.assertIsNone(result['r2'])
            if len(y)>1 and max(y)>min(y) and max(p)>min(p):
                self.assertAlmostEqual(result['spearman'],spearmanr(y,p).statistic,places=12)
            else:self.assertIsNone(result['spearman'])

    def test_raw_identity_gate(self):
        self.assertIsNone(prepare_inputs.reason('ACDE'))
        for seq in ['aCDE','ACX','AC[pS]',' ACDE','ACDE\n']:
            self.assertEqual(prepare_inputs.reason(seq),'non_AA20_raw_symbol')
        self.assertIn('compute_budget',prepare_inputs.reason('A'*2049))

    def test_effect_uses_separate_inputs_and_same_target(self):
        vectors={'AC':np.ones(320,dtype=np.float32),'AD':np.full(320,3,dtype=np.float32),
                 'GH':np.full(320,7,dtype=np.float32)}
        cache={hashlib.sha256(k.encode()).hexdigest():v for k,v in vectors.items()}
        old=plm_features._CACHE
        try:
            plm_features._CACHE=(cache,'fake-cache','fake-receipt',{'model_sha256':'fake'})
            frame=pd.DataFrame([{'embedding_peptide_wt':'AC','embedding_peptide_mut':'AD','embedding_target':'GH','label':999}])
            a,_=plm_features.build_features(frame,'effect')
            frame['label']=-999
            b,_=plm_features.build_features(frame,'effect')
            np.testing.assert_array_equal(a,b)
            np.testing.assert_array_equal(a[0,:320],np.ones(320))
            np.testing.assert_array_equal(a[0,320:640],np.full(320,2))
            np.testing.assert_array_equal(a[0,640:],np.full(320,7))
        finally:
            plm_features._CACHE=old

    def test_coverage_preserves_frozen_labels_splits_and_raw_peptides(self):
        manifest=json.loads((HERE/'coverage-manifest.json').read_text(encoding='utf-8'))
        for view in manifest['views']:
            parent=HERE.parents[1]/'data'/(view['parent_view_id']+'.csv')
            with parent.open(encoding='utf-8-sig') as stream:
                original={r['row_id']:r for r in csv.DictReader(stream)}
            with Path(view['path']).open(encoding='utf-8-sig') as stream:
                derived=list(csv.DictReader(stream))
            for row in derived:
                self.assertEqual(row['split'],original[row['row_id']]['split'])
                self.assertEqual(row['label'],original[row['row_id']]['label'])
                if view['task']=='affinity':
                    self.assertEqual(row['embedding_peptide'],original[row['row_id']]['peptide_sequence_raw'])
            if view['task']=='effect':
                self.assertEqual(sum(r['split']=='test' for r in derived),129)

if __name__=='__main__':
    unittest.main(verbosity=2)
