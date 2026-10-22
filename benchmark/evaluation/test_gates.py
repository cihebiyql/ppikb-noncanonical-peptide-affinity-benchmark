"""Synthetic metadata fixtures only: no real run/selection/gold/weights accessed."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import common
import score_cached

class Gates(unittest.TestCase):
    def test_denial_precedes_access_to_any_real_selection_or_weights(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'authorization.json'
            common.write_json(path,dict(root_scoring_authorized=False))
            with patch.object(common,'sha',side_effect=AssertionError('Unauthorized file hash/open')):
                with self.assertRaises(PermissionError):
                    score_cached.validate_gate(path,'not-opened-barrier','not-opened-audit','not-opened-selection','not-opened-spec')

    def test_label_free_input_rejects_even_zero_gold(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'input.jsonl'
            path.write_text('{"record_id":"fixture","pKd":0.0}\n')
            with self.assertRaises(ValueError):common.read_inputs(path)

    def test_method_input_and_code_are_all_in_cache_signature(self):
        identity=common.signature('MGraphDTA','a','b')
        self.assertNotEqual(identity,common.signature('GS-DTA','a','b'))
        self.assertNotEqual(identity,common.signature('MGraphDTA','different-input','b'))
        self.assertNotEqual(identity,common.signature('MGraphDTA','a','different-code'))

    def test_complete_grid_audit_and_partial_grid_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);checkpoint=root/'synthetic-bytes-only.bin';checkpoint.write_bytes(b'unit-fixture-not-trained-weights')
            entries=[];barrier_entries=[]
            for method in common.METHODS:
                for panel in ('fixture_panel_a','fixture_panel_b'):
                    for regime in ('NC_only','standard_only'):
                        for seed in range(10):
                            name=f'{method}-{panel}-{regime}-{seed}'
                            spec=root/(name+'.fit.json')
                            common.write_json(spec,dict(method_id=method,split_id=panel,regime=regime,seed=seed))
                            selection=root/(name+'.selection.json')
                            common.write_json(selection,dict(status='frozen',method_id=method,split_id=panel,regime=regime,seed=seed,
                                holdout_metrics_consulted=False,candidate_index=0,checkpoint=str(checkpoint),checkpoint_sha256=common.sha(checkpoint),
                                fit_spec_sha256=common.sha(spec),candidates=[dict(status='complete',candidate_index=i,
                                    best_validation_MAE=.1+i,checkpoint_sha256=common.sha(checkpoint)) for i in (0,1)]))
                            entries.append(dict(selection_path=str(selection),spec_path=str(spec)))
                            barrier_entries.append(dict(path=str(selection),sha256=common.sha(selection)))
            index=root/'index.json';common.write_json(index,dict(total_fits=400,total_selections=200,per_seed_selections=entries))
            barrier=root/'barrier.json';common.write_json(barrier,dict(status='all_selections_frozen',selection_count=200,
                candidate_fit_count=400,selections=barrier_entries,execution_index_sha256=common.sha(index)))
            auth=root/'unit-only-auth.json';common.write_json(auth,dict(root_scoring_authorized=True,allowed_phases=['barrier_audit'],
                evaluation_code_sha256=score_cached.code_hashes(),barrier_sha256=common.sha(barrier),execution_index_sha256=common.sha(index)))
            audit=score_cached.verify_barrier(auth,barrier,index,root/'audit.json')
            self.assertEqual(len(audit['selections']),200)
            self.assertEqual(audit['gold_reads'],0)
            partial=common.read_json(barrier);partial['selections']=partial['selections'][:-1]
            common.write_json(root/'partial.json',partial)
            modified=common.read_json(auth);modified['barrier_sha256']=common.sha(root/'partial.json')
            common.write_json(root/'partial-auth.json',modified)
            with self.assertRaises(ValueError):
                score_cached.verify_barrier(root/'partial-auth.json',root/'partial.json',index,root/'blocked-audit.json')

    def test_blind_file_and_receipt_must_exist_before_any_gold_byte_access(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);gold=root/'synthetic-unit-gold.jsonl'
            gold.write_text('{"record_id":"synthetic-a","pKd":2.0}\n')
            spec=dict(gold_rows=str(gold),gold_rows_sha256=common.sha(gold))
            blind=[dict(record_id='synthetic-a',pKd_pred=1.0)]
            original_sha=common.sha
            gold_hash_calls=[]
            def guarded_sha(path):
                if Path(path)==gold:
                    gold_hash_calls.append(path)
                    self.assertTrue((root/'blind-predictions.jsonl').is_file())
                    self.assertTrue((root/'blind-complete.json').is_file())
                return original_sha(path)
            with patch.object(common,'sha',guarded_sha):
                with self.assertRaises(FileNotFoundError):
                    score_cached._join_gold_after_blind(spec,root,[{'record_id':'synthetic-a'}],blind,'missing')
                self.assertEqual(gold_hash_calls,[])
                (root/'blind-predictions.jsonl').write_text('{"record_id":"synthetic-a","pKd_pred":1.0}\n')
                checksum=common.sha(root/'blind-predictions.jsonl')
                common.write_json(root/'blind-complete.json',dict(blind_predictions_sha256=checksum))
                labels,joined=score_cached._join_gold_after_blind(spec,root,[{'record_id':'synthetic-a'}],blind,checksum)
                self.assertEqual(labels,{'synthetic-a':2.0})
                self.assertEqual(joined[0]['pKd_pred'],1.0)
                self.assertEqual(joined[0]['residual'],-1.)
                self.assertEqual(len(gold_hash_calls),1)

if __name__=='__main__':unittest.main(verbosity=2)
