import unittest
from stopping_rules import validate_stopping
def logs(scores,n=10):
    best=float('inf');out=[]
    for i,s in enumerate(scores):
        good=s<best;best=min(best,s);out.append({'epoch':i,'train_n':n,'validation':{'MAE':s},'improved':good})
    return out
class StoppingRuleTests(unittest.TestCase):
    def test_patience_can_end_before_cap(self):
        r=validate_stopping(logs([1,2,2,2,2,2]),0,10);self.assertTrue(r['patience_exhausted']);self.assertFalse(r['epoch_bound_reached'])
    def test_all_twenty_improving_is_bounded_not_patience(self):
        r=validate_stopping(logs(list(range(20,0,-1))),19,10);self.assertTrue(r['epoch_bound_without_patience'])
    def test_premature_saved_candidate_cannot_pass(self):
        with self.assertRaises(ValueError):validate_stopping(logs([2,1,1]),1,10)
    def test_ties_are_not_improvements(self):
        r=logs([1,1,1,1,1,1]);r[-1]['improved']=True
        with self.assertRaises(ValueError):validate_stopping(r,0,10)
    def test_cannot_train_past_patience(self):
        with self.assertRaises(ValueError):validate_stopping(logs([1]*7),0,10)
    def test_each_epoch_uses_all_observations(self):
        r=logs([1]*6);r[3]['train_n']=9
        with self.assertRaises(ValueError):validate_stopping(r,0,10)
if __name__=='__main__':unittest.main(verbosity=2)
