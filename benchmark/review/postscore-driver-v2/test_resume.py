import copy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('resume_driver', Path(__file__).with_name('driver.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


class ResumeTests(unittest.TestCase):
    def fixture(self):
        source = {'path':'SYNTHETIC_ISSUANCE','sha256':'SYNTHETIC_SHA'}
        files = {n:{'path':str(Path('/SYNTHETIC_NN')/n),'sha256':'SYNTHETIC_SHA'} for n in (
            'independent-audit-manifest.json','independent-matched-target-ten-seed-summary.json',
            'independent-ten-seed-summary.json','per-score-audit.json')}
        manifest = dict(evaluator_sha256='SYNTHETIC_SHA',real_score_tasks_audited=600,
            complete600_scores_265800_rows=True,metric_difference_count=0,all_predictions_true_labels_match=True)
        inputs = dict(issuance=source,prior_failed_pipeline={'path':'SYNTHETIC_FAILED'},
            prior_NN_task_map={'path':'SYNTHETIC_OLD_MAP'},prior_NN_audit_files=files)
        data = {'SYNTHETIC_FAILED':dict(status='failed_preserved_no_retry',source_issuance=source,
            completed_steps=[dict(name='02-NN600-independent',exit_code=0),dict(name='03-RF120-independent',exit_code=1)]),
            'SYNTHETIC_OLD_MAP':[{'score':'SYNTHETIC_SCORE'}]}
        for entry in files.values():data[entry['path']] = {}
        data[files['independent-audit-manifest.json']['path']] = manifest
        return inputs,data

    def call(self, inputs, data):
        with patch.object(d,'bound',lambda r:data[r['path']]), patch.object(d,'read',lambda p:[{'score':'SYNTHETIC_SCORE'}]), patch.object(d,'sha',lambda p:'SYNTHETIC_SHA'):
            return d.reuse_nn_audit(inputs,{'path':'SYNTHETIC_NEW_MAP'})

    def test_same_completed_audit_is_reused(self):
        inputs,data=self.fixture()
        self.assertEqual(self.call(inputs,data)[1]['real_score_tasks_audited'],600)

    def test_other_failure_rejected(self):
        inputs,data=self.fixture();data['SYNTHETIC_FAILED']['completed_steps'][1]['exit_code']=0
        with self.assertRaises(ValueError):self.call(inputs,data)

    def test_other_task_map_rejected(self):
        inputs,data=self.fixture();data['SYNTHETIC_OLD_MAP']=[]
        with self.assertRaises(ValueError):self.call(inputs,data)

    def test_missing_artifact_rejected(self):
        inputs,data=self.fixture();inputs['prior_NN_audit_files'].pop('per-score-audit.json')
        with self.assertRaises(ValueError):self.call(inputs,data)

    def test_metric_disagreement_rejected(self):
        inputs,data=self.fixture();data[inputs['prior_NN_audit_files']['independent-audit-manifest.json']['path']]['metric_difference_count']=1
        with self.assertRaises(ValueError):self.call(inputs,data)

    def test_other_issuance_rejected(self):
        inputs,data=self.fixture();data['SYNTHETIC_FAILED']['source_issuance']={'path':'OTHER'}
        with self.assertRaises(ValueError):self.call(inputs,data)


if __name__=='__main__':unittest.main()
