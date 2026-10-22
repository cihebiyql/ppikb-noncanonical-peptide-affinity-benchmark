"""Pure synthetic fitting fixtures; no scientific labels/model files accessed."""
from pathlib import Path
import json
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import numpy as np
import common
import features
import rf_runner
import rf_score

class Mechanics(unittest.TestCase):
    def test_feature_dimensions_prefix_unknown_and_short_sequences(self):
        row=dict(record_id='synthetic',canonical_isomeric_smiles='CC(=O)O',target_sequence='AXC')
        vector,audit=features.encode_record(row)
        self.assertEqual(vector.shape,(2469,));self.assertEqual(vector.dtype,np.float32)
        self.assertAlmostEqual(float(vector[2048:2068].sum()),2/3,places=6)
        self.assertEqual(float(vector[2068:2468].sum()),0.)
        self.assertEqual(vector[2468],3);self.assertEqual(audit['prefix_unknown_count'],1)
        one,_=features.encode_record(dict(row,target_sequence='A'))
        self.assertEqual(one[2468],1);self.assertEqual(float(one[2068:2468].sum()),0.)
        long,audit=features.encode_record(dict(row,target_sequence='A'*1001))
        self.assertEqual(long[2468],1000);self.assertEqual(audit['full_reference_length'],1001)
        self.assertTrue(audit['reference_truncated'])
        known,_=features.encode_record(dict(row,target_sequence='ACD'))
        self.assertEqual(known[2068+features.AA_INDEX['A']*20+features.AA_INDEX['C']],.5)
        self.assertEqual(known[2068+features.AA_INDEX['C']*20+features.AA_INDEX['D']],.5)

    def test_supplied_chirality_and_fragments_no_imputation(self):
        row=dict(record_id='synthetic',target_sequence='ACDE')
        left,_=features.encode_record(dict(row,peptide_smiles='N[C@@H](C)C(=O)O'))
        right,_=features.encode_record(dict(row,peptide_smiles='N[C@H](C)C(=O)O'))
        self.assertFalse(np.array_equal(left[:2048],right[:2048])) # synthetic example, not universal collision guarantee
        _,unknown=features.encode_record(dict(row,peptide_smiles='NC(C)C(=O)O'))
        self.assertEqual(unknown['specified_chiral_atoms'],0);self.assertFalse(unknown['inferred_stereochemistry'])
        salt,audit=features.encode_record(dict(row,peptide_smiles='[Na+].CC(=O)[O-]'))
        alone,_=features.encode_record(dict(row,peptide_smiles='CC(=O)[O-]'))
        self.assertEqual(audit['molecule_fragments'],2);self.assertFalse(np.array_equal(salt[:2048],alone[:2048]))

    def test_real_fit_denied_before_spec_or_label_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            auth=Path(tmp)/'authorization.json';common.write(auth,dict(root_real_RF_fit_authorized=False))
            with patch.object(common,'sha',side_effect=AssertionError('Unauthorized hashing/read')):
                with self.assertRaises(PermissionError):rf_runner.authorize_fit(auth,'not-opened-spec')

    def test_real_score_denied_before_joint_or_model_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            auth=Path(tmp)/'authorization.json';common.write(auth,dict(root_RF_holdout_score_authorized=False))
            with patch.object(common,'sha',side_effect=AssertionError('Unauthorized model/read')):
                with self.assertRaises(PermissionError):rf_score.authorize(auth,'not-opened-joint','not-opened-selection','not-opened-spec')

    def test_partial_joint_barrier_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);nn=root/'nn.json';rf=root/'rf.json'
            common.write(nn,dict(status='all_selections_frozen',selection_count=199,candidate_fit_count=400,selections=[]))
            common.write(rf,dict(status='all_40_RF_selections_frozen',selection_count=40,candidate_fit_count=80,selections=[]))
            with self.assertRaises(ValueError):rf_runner.validate_joint(nn,rf)

    def test_full_synthetic_joint_grid_preserves_original_NN_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);nn_entries=[];rf_entries=[]
            methods=['GraphDTA-GIN','MGraphDTA','DGDTA-CL','DeepNC-GEN','GS-DTA']
            for panel in common.PANELS:
                for regime in common.REGIMES:
                    for seed in range(10):
                        f=root/f'RF-{panel}-{regime}-{seed}.json'
                        common.write(f,dict(status='frozen',validation_only=True,gold_reads=0,panel=panel,regime=regime,seed=seed))
                        rf_entries.append(dict(selection_path=str(f),selection_sha256=common.sha(f),panel=panel,regime=regime,seed=seed))
                        for method in methods:
                            n=root/f'NN-{method}-{panel}-{regime}-{seed}.json'
                            common.write(n,dict(status='frozen',holdout_metrics_consulted=False,method_id=method,split_id=panel,regime=regime,seed=seed))
                            nn_entries.append(dict(path=str(n),sha256=common.sha(n)))
            index=root/rf_runner.NN_APPROVED_INDEX_RELATIVE
            common.write(index,dict(per_seed_selections=[dict(selection_path=entry['path']) for entry in nn_entries]))
            index_sha=common.sha(index)
            common.write(root/'NN.json',dict(status='all_selections_frozen',selection_count=200,candidate_fit_count=400,selections=nn_entries,
                                           execution_index_sha256=index_sha))
            common.write(root/'RF.json',dict(status='all_40_RF_selections_frozen',selection_count=40,candidate_fit_count=80,selections=rf_entries))
            before=common.sha(root/'NN.json')
            with patch.object(common,'PROJECT',root),patch.object(rf_runner,'NN_APPROVED_INDEX_SHA',index_sha):
                result=rf_runner.validate_joint(root/'NN.json',root/'RF.json')
            self.assertEqual(result['NN_selections'],200);self.assertEqual(result['RF_selections'],40)
            self.assertEqual(common.sha(root/'NN.json'),before)

    def test_real_sklearn_two_profile_synthetic_fit_seed_and_roundtrip(self):
        # 32 entirely synthetic molecule/reference records; labels generated below,
        # never read from TRAIN32, real affinity files or a holdout.
        smiles=['CC(=O)O','CCN','CCC','NCC(=O)O','C1CCCCC1','CCO','CC(=O)N','COC']
        vectors=[]
        for index in range(32):
            vector,_=features.encode_record(dict(record_id='synthetic-'+str(index),peptide_smiles=smiles[index%8],
                target_sequence=features.AA[index%20:]+features.AA[:index%20]+'A'*(index%7)))
            vectors.append(vector)
        X=np.asarray(vectors,dtype=np.float32);y=np.random.default_rng(91234).normal(size=32)
        assets=rf_runner.installed_assets(common.HERE/'installed-assets-v1.json')
        first=rf_runner.fit_array_candidates(X[:24],y[:24],X[24:],y[24:],assets,0)
        second=rf_runner.fit_array_candidates(X[:24],y[:24],X[24:],y[24:],assets,0,(0,))[0]
        self.assertEqual(len(first),2)
        for index,result in enumerate(first):
            self.assertEqual(result['parameters']['n_estimators'],200)
            self.assertEqual(result['parameters']['min_samples_leaf'],(2,5)[index])
            self.assertEqual(result['parameters']['max_features'],'sqrt')
            self.assertEqual(result['parameters']['n_jobs'],1)
            self.assertEqual(len(result['model'].estimators_),200)
        np.testing.assert_array_equal(first[0]['prediction'],second['prediction'])
        import joblib
        with tempfile.TemporaryDirectory() as tmp:
            model=Path(tmp)/'synthetic-model.joblib';joblib.dump(first[0]['model'],model)
            np.testing.assert_array_equal(joblib.load(model).predict(X[24:]),first[0]['prediction'])
        tie=[dict(candidate_index=1,validation_MAE=1.),dict(candidate_index=0,validation_MAE=1.)]
        self.assertEqual(min(tie,key=lambda row:(row['validation_MAE'],row['candidate_index']))['candidate_index'],0)

    def test_synthetic_full_fit_path_filters_own_regime_and_retains_both_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);panel=common.PANELS[0];data=root/'execution/prepared-panels-wsl-v3'/panel
            data.mkdir(parents=True)
            rows=[];vectors=[];audits=[]
            for index in range(32):
                row=dict(record_id='unit-synthetic-'+str(index),peptide_smiles='CCO' if index%3 else 'CCN',
                    target_sequence='ACDEFGHIKLMNPQRSTVWY'+'A'*(index%5),NC_core=index%2==0,
                    evaluation_stratum='PTM' if index%2==0 else 'standard20_control',
                    pKd=float(np.random.default_rng(555+index).normal()))
                vector,audit=features.encode_record(row);rows.append(row);vectors.append(vector);audits.append(audit)
            common.write_jsonl(data/'train.jsonl',rows[:24]);common.write_jsonl(data/'validation.jsonl',rows[24:])
            common.write(root/'train-ids.json',[row['record_id'] for row in rows[:24] if row['NC_core']])
            common.write(root/'val-ids.json',[row['record_id'] for row in rows[24:] if row['NC_core']])
            np.save(root/'synthetic-X.npy',np.asarray(vectors,dtype=np.float32),allow_pickle=False)
            common.write(root/'synthetic-X.ids.json',[row['record_id'] for row in rows])
            common.write_jsonl(root/'synthetic-X.audit.jsonl',audits)
            common.write(root/'synthetic-X-manifest.json',dict(entries=[dict(dataset_id='PPIKB9619',fixture=True,
                matrix_path=str(root/'synthetic-X.npy'),matrix_sha256=common.sha(root/'synthetic-X.npy'),
                record_ids_path=str(root/'synthetic-X.ids.json'),record_ids_sha256=common.sha(root/'synthetic-X.ids.json'),
                audit_path=str(root/'synthetic-X.audit.jsonl'),audit_sha256=common.sha(root/'synthetic-X.audit.jsonl'))]))
            spec=dict(method_id=common.METHOD,panel=panel,regime='NC_only',seed=0,
                train_rows=str(data/'train.jsonl'),validation_rows=str(data/'validation.jsonl'),
                train_ids=str(root/'train-ids.json'),validation_ids=str(root/'val-ids.json'),
                feature_manifest=str(root/'synthetic-X-manifest.json'),installed_assets=str(common.HERE/'installed-assets-v1.json'),
                output_root=str(root/'synthetic-output'))
            for key in ('train_rows','validation_rows','train_ids','validation_ids','feature_manifest','installed_assets'):
                spec[key+'_sha256']=common.sha(spec[key])
            common.write(root/'spec.json',spec)
            common.write(root/'synthetic-only-authorization.json',dict(root_real_RF_fit_authorized=True,fixture_only=True,
                allowed_spec_sha256=[common.sha(root/'spec.json')],source_sha256=rf_runner.source_hashes(),deadline_unix=time.time()+30))
            with patch.object(common,'PROJECT',root):
                selection=rf_runner.fit_unit(root/'spec.json',root/'synthetic-only-authorization.json')
            self.assertEqual(len(selection['candidates']),2)
            self.assertTrue(selection['validation_only'])
            self.assertEqual(selection['gold_reads'],0)
            self.assertEqual([row['train_n'] for row in selection['candidates']],[12,12])
            self.assertEqual([row['validation_n'] for row in selection['candidates']],[4,4])
            self.assertTrue((root/'synthetic-output/complete.json').exists())
            for index in (0,1):
                self.assertTrue((root/f'synthetic-output/candidate-{index}/model.joblib').exists())
                self.assertTrue((root/f'synthetic-output/candidate-{index}/validation-predictions.jsonl').exists())

    def test_atomic_transient_sharing_conflict_retries_and_unique_tmp(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);target=root/'status.json';original=Path.replace;names=[]
            def flaky(source,destination):
                names.append(source.name)
                if len(names)==1:raise PermissionError(13,'synthetic transient sharing conflict')
                return original(source,destination)
            with patch.object(Path,'replace',flaky):common.write(target,dict(status='done'))
            self.assertEqual(common.read(target),dict(status='done'))
            self.assertNotEqual(names[0],target.name+'.tmp')
            self.assertIn(str(__import__('os').getpid()),names[0])

    def test_atomic_persistent_failure_is_bounded_and_preserves_tmp(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'status.json'
            with patch.object(Path,'replace',side_effect=PermissionError(13,'synthetic persistent conflict')) as replace,patch.object(time,'sleep') as sleep:
                with self.assertRaises(PermissionError):common.write(target,dict(status='not-committed'))
            self.assertEqual(replace.call_count,7);self.assertEqual(sleep.call_count,6)
            self.assertFalse(target.exists());self.assertEqual(len(list(Path(tmp).glob('*.tmp'))),1)

    def test_independent_budget_ticks_continue_during_write_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            stop=threading.Event();ticks=[];original=Path.replace;attempts=[]
            def monitor():
                while not stop.wait(.005):ticks.append(time.monotonic())
            def sharing(source,target):
                attempts.append(1)
                if len(attempts)<3:raise PermissionError(13,'synthetic sharing delay')
                return original(source,target)
            observer=threading.Thread(target=monitor);observer.start()
            try:
                with patch.object(Path,'replace',sharing):common.write(Path(tmp)/'heartbeat.json',dict(status='written'))
            finally:stop.set();observer.join()
            self.assertGreater(len(ticks),10)

if __name__=='__main__':unittest.main(verbosity=2)
