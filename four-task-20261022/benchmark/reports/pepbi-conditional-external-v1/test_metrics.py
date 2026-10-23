"""Numerical fixtures for independent metric calculations, including degeneracy and ties."""
import unittest
from run_fixed import metrics as production
from verify_fixed import metrics as independent

class MetricFixtures(unittest.TestCase):
    def test_independent_scores_match_existing_library_conventions(self):
        fixtures=[([1.,2.,2.,4.],[1.1,2.5,2.5,3.]),([2.,2.,2.],[1.,2.,3.]),
            ([1.,2.,4.],[2.,2.,2.]),([1.],[2.]),([1.,2.,3.],[3.,2.,1.])]
        for y,p in fixtures:
            left=production(y,p);right=independent(y,p)
            for key in left:
                if left[key] is None:self.assertIsNone(right[key])
                else:self.assertAlmostEqual(left[key],right[key],places=12)

if __name__=='__main__':unittest.main()
