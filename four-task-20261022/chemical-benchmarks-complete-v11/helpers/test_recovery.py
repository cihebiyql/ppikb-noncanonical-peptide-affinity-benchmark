"""Public recovery security fixtures. No models, biological records or weights."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('v11_recovery',HERE/'restore_project_tree.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)


def bundle(path,data=b'x = 1\n',original=None,relative='example/worker.py',policy=None):
    path.mkdir();(path/'code').mkdir()
    public='code/worker.json' if relative.endswith('.json') else 'code/worker.py'
    (path/public).write_bytes(data)
    entry={'source_ref':'record-ref:project/'+relative,'source_sha256':hashlib.sha256(original if original is not None else data).hexdigest(),'public_path':public,'public_sha256':hashlib.sha256(data).hexdigest(),'pinned_original_bytes':relative.endswith('.json')}
    if policy:entry['restore_policy']=policy
    (path/'SOURCE-MAPPING.json').write_text(json.dumps({'entries':[entry]}))


class RecoveryTests(unittest.TestCase):
    def test_exact_original_CRLF_recovered(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);bundle(root/'bundle',original=b'x = 1\r\n')
            receipt=r.restore([root/'bundle'],root/'project')
            self.assertEqual((root/'project/example/worker.py').read_bytes(),b'x = 1\r\n')
            self.assertTrue(receipt['restored_files'][0]['original_source_bytes_restored'])

    def test_overwrite_different_bytes_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);bundle(root/'bundle');(root/'project/example').mkdir(parents=True)
            (root/'project/example/worker.py').write_bytes(b'keep original history')
            with self.assertRaises(ValueError):r.restore([root/'bundle'],root/'project')
            self.assertEqual((root/'project/example/worker.py').read_bytes(),b'keep original history')

    def test_traversal_source_reference_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);bundle(root/'bundle',relative='../outside.py')
            with self.assertRaises(ValueError):r.restore([root/'bundle'],root/'project')

    def test_public_bytes_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);bundle(root/'bundle');(root/'bundle/code/worker.py').write_bytes(b'x = 2\n')
            with self.assertRaises(ValueError):r.restore([root/'bundle'],root/'project')

    def test_pinned_JSON_reformat_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);bundle(root/'bundle',data=b'{"value":1}\n',original=b'{ "value": 1 }\n',relative='example/recipe.json')
            with self.assertRaises(ValueError):r.restore([root/'bundle'],root/'project')

    def test_portable_adapter_disclosed_not_original(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);bundle(root/'bundle',data=b'x = "portable"\n',original=b'x = "historical"\n',policy='public_portable_path_adapter')
            receipt=r.restore([root/'bundle'],root/'project')
            self.assertFalse(receipt['restored_files'][0]['original_source_bytes_restored'])
            self.assertIn('provenance only',receipt['restored_files'][0]['transform'])


if __name__=='__main__':unittest.main()
