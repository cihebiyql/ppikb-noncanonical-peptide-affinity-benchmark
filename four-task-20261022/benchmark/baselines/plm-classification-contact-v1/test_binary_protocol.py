"""Independent binary-score fixtures and sequence-only residue-feature semantics."""
import hashlib
from pathlib import Path
import sys
import unittest
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score,balanced_accuracy_score,brier_score_loss,f1_score,matthews_corrcoef,roc_auc_score

HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
import plm_binary_features as feature
import verify_heads

class BinaryProtocol(unittest.TestCase):
    def test_independent_scores_ties_constants_and_degenerate_truth(self):
        rng=np.random.default_rng(73)
        fixtures=[([0,1,1,0],[.5,.5,.2,.1]),([0,1,0,1],[.3,.3,.3,.3]),
                  ([1,1],[.1,.9]),([0,0],[.1,.9]),([1],[.2]),
                  (rng.integers(0,2,300).tolist(),np.round(rng.random(300),2).tolist())]
        for y,p in fixtures:
            result=verify_heads.scores(y,p,.5);classes=np.asarray(p)>=.5;two=len(set(y))==2
            self.assertAlmostEqual(result['brier'],brier_score_loss(y,p),places=12)
            self.assertAlmostEqual(result['f1'],f1_score(y,classes,zero_division=0),places=12)
            if two:
                self.assertAlmostEqual(result['auroc'],roc_auc_score(y,p),places=12)
                self.assertAlmostEqual(result['auprc'],average_precision_score(y,p),places=12)
                self.assertAlmostEqual(result['mcc'],matthews_corrcoef(y,classes),places=12)
                self.assertAlmostEqual(result['balanced_accuracy'],balanced_accuracy_score(y,classes),places=12)
                threshold=max(np.linspace(.1,.9,17),key=lambda t:(matthews_corrcoef(y,np.asarray(p)>=t),-abs(t-.5)))
                check=verify_heads.threshold_check(y,p,float(threshold))
                self.assertTrue(check['mcc_optimal_to_1e12']);self.assertTrue(check['selected_on_grid'])
            else:self.assertIsNone(result['auroc']);self.assertIsNone(result['auprc']);self.assertIsNone(result['mcc'])
    def test_contact_residue_is_1based_and_does_not_use_labels_or_geometry(self):
        peptide,target='GH','ACD';pk=hashlib.sha256(peptide.encode()).hexdigest();tk=hashlib.sha256(target.encode()).hexdigest()
        binding={'model_sha256':'unit-fixture-only'}
        proof={'unit-row':{'target_sequence_id':tk,'peptide_sequence_id':pk,'residue_index1':2,'target_residue_aa':'C'}}
        old=feature._CACHE;old_res=feature._RESIDUES
        try:
            feature._CACHE=(binding,{pk:np.full(320,10,dtype=np.float32)},proof,'unit-binding')
            feature._RESIDUES={tk:np.asarray([np.full(320,i,dtype=np.float32) for i in [1,2,3]])}
            frame=pd.DataFrame([{'row_id':'unit-row','embedding_peptide':peptide,'embedding_target':target,
                'residue_index':2,'target_residue_aa':'C','sequence_index_mapping_verified':True,
                'label':0,'minimum_heavyatom_distance_A':999.,'observed_target':'NOT_A_FEATURE'}])
            x,audit=feature.build_features(frame,'contact')
            np.testing.assert_array_equal(x[0,:320],np.full(320,2));np.testing.assert_array_equal(x[0,320:],np.full(320,10))
            frame['label']=1;frame['minimum_heavyatom_distance_A']=0.;frame['observed_target']='ALTERED'
            changed,_=feature.build_features(frame,'contact');np.testing.assert_array_equal(x,changed)
            self.assertFalse(audit['label_or_geometry_used']);self.assertFalse(audit['observed_region_mask_used'])
            frame['residue_index']=3
            with self.assertRaises(AssertionError):feature.build_features(frame,'contact')
        finally:feature._CACHE=old;feature._RESIDUES=old_res
if __name__=='__main__':unittest.main(verbosity=2)
