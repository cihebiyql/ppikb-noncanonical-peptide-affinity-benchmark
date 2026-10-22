import json
import unittest
import numpy as np
import metrics_stable as metrics

class StableMetrics(unittest.TestCase):
    def test_repeated_decimal_constant_is_undefined(self):
        result=metrics.numeric_metrics([.1]*3,[.2,.3,.4])
        self.assertIsNone(result['Pearson']);self.assertIsNone(result['Spearman']);self.assertIsNone(result['R2'])
        json.dumps(result,allow_nan=False)
    def test_constant_predictions_and_constant_both(self):
        result=metrics.numeric_metrics([1,2,3],[.1]*3)
        self.assertIsNone(result['Pearson']);self.assertIsNone(result['Spearman']);self.assertIsNotNone(result['R2'])
        both=metrics.numeric_metrics([.1]*3,[.1]*3)
        self.assertEqual(both['MAE'],0.);self.assertEqual(both['RMSE'],0.);self.assertIsNone(both['R2'])
    def test_exactly_distinct_near_constant_not_collapsed(self):
        values=np.array([.1,np.nextafter(.1,1.)])
        result=metrics.numeric_metrics(values,values)
        self.assertEqual(result['R2'],1.)
        self.assertAlmostEqual(result['Pearson'],1.)
        self.assertAlmostEqual(result['Spearman'],1.)
    def test_small_empty_invalid_and_ties(self):
        for y,p in [([],[]),([.1],[.2])]:
            result=metrics.numeric_metrics(y,p)
            self.assertIsNone(result['Pearson']);self.assertIsNone(result['Spearman']);self.assertIsNone(result['R2'])
        with self.assertRaises(ValueError):metrics.numeric_metrics([1],[float('nan')])
        self.assertAlmostEqual(metrics.numeric_metrics([1,1,2],[2,2,3])['Spearman'],1.)
    def test_group_constant_and_discordance_preserve_same_prediction(self):
        rows=[dict(pKd=.1,NC_core=True,evaluation_stratum='PTM',residue_class_graph_discordance=i==0) for i in range(3)]
        result=metrics.grouped_metrics(rows,[.1,.2,.3])
        self.assertIsNone(result['PTM']['R2']);self.assertIsNone(result['exclude_discordant:PTM']['Pearson'])
        self.assertEqual(result['exclude_discordant_sensitivity']['n'],2)
        json.dumps(result,allow_nan=False)
if __name__=='__main__':unittest.main(verbosity=2)
