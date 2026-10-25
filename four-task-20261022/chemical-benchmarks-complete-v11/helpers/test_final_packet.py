"""No biological fixtures: prevent pending results becoming a final packet."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import build_final_packet as final
from public_artifacts import sha


class FinalGateTests(unittest.TestCase):
    def test_wrong_intake_schema_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);intake=tmp/'intake.json';intake.write_text('{}')
            with self.assertRaises(ValueError):final.build(intake,tmp/'output')
            self.assertFalse((tmp/'output').exists())

    def test_project_source_traversal_refused(self):
        with self.assertRaises(ValueError):final.read_bound({'project_relative_path':'../outside.json','sha256':'0'*64})

    def test_final_raw_test_29_refused(self):
        self.reject_raw_count(29)

    def test_pending_raw_test_refused(self):
        self.reject_raw_count(30,status='pending')

    def reject_raw_count(self,count,status='passed'):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);comparison={'status':'passed','model_seed_units':230,'fullfine30_models_fresh_raw_audited':30,'groups':155}
            raw={'status':status,'raw_selected_models_recomputed':count,'test_n':685,'validation_n':570}
            spec={'schema':'public-v11.final-accepted-inputs.v1'}
            for name,value in [('comparison',comparison),('raw30_audit',raw)]:
                data=json.dumps(value).encode();(root/(name+'.json')).write_bytes(data)
                spec[name]={'project_relative_path':name+'.json','sha256':sha(data)}
            intake=root/'intake.json';intake.write_text(json.dumps(spec))
            with patch.object(final,'ROOT',root):
                with self.assertRaises(ValueError):final.build(intake,root/'output')
            self.assertFalse((root/'output').exists())


if __name__=='__main__':unittest.main()
