"""Public recovery/recipe smoke tests; standard library only, no models or real data."""
import hashlib, importlib.util, json
from pathlib import Path
import tempfile, unittest
import restore_project_tree as recovery

HERE=Path(__file__).resolve().parent

class RecoveryTests(unittest.TestCase):
    def bundle(self,base,ref='record-ref:project/code/demo.py',body=b'x=1\n'):
        bundle=base/'bundle';(bundle/'code').mkdir(parents=True)
        (bundle/'code/demo.py').write_bytes(body)
        entry={'source_ref':ref,'public_path':'code/demo.py','public_sha256':recovery.digest(body),'source_sha256':recovery.digest(body)}
        (bundle/'SOURCE-MAPPING.json').write_text(json.dumps({'entries':[entry]}));return bundle

    def test_idempotence_and_different_existing_bytes_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            p=Path(name);b=self.bundle(p);out=p/'out'
            self.assertEqual(recovery.restore([b],out),recovery.restore([b],out))
            (out/'code/demo.py').write_bytes(b'changed')
            with self.assertRaises(ValueError):recovery.restore([b],out)

    def test_source_ref_traversal_and_absolute_rejected(self):
        for ref in ['record-ref:project/../outside.py','record-ref:project//tmp/a.py','record-ref:project/'+'C'+chr(58)+'/x.py','record-ref:project/code\\x.py']:
            with self.assertRaises(ValueError):recovery.relative_ref(ref)

    def test_tampered_public_bytes_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            p=Path(name);b=self.bundle(p);(b/'code/demo.py').write_bytes(b'x=2\n')
            with self.assertRaises(ValueError):recovery.restore([b],p/'out')
            self.assertFalse((p/'out').exists())

    def test_original_newline_source_sha_recovered(self):
        with tempfile.TemporaryDirectory() as name:
            p=Path(name);b=self.bundle(p,body=b'x=1\r\r\n')
            m=json.loads((b/'SOURCE-MAPPING.json').read_text());m['entries'][0]['source_sha256']=recovery.digest(b'x=1\n');(b/'SOURCE-MAPPING.json').write_text(json.dumps(m))
            r=recovery.restore([b],p/'out');self.assertEqual(r['restored_files'][0]['restored_sha256'],recovery.digest(b'x=1\n'))

    def test_actual_disclosed_ringfix_recipe_loads(self):
        # Standalone public bundle layout is sufficient for actual stdlib load_recipe.
        path=HERE/'code/ringfix-v2/ringfix_adapter.py'
        spec=importlib.util.spec_from_file_location('public_ring_adapter',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        recipe=module.load_recipe()
        self.assertEqual(module.file_sha(path.with_name('ringfix-recipe.json')),module.RECIPE_SHA256)
        self.assertEqual(recipe['schema'],'chemical-encoder.tokenizer-ringfix.v2')
        self.assertTrue(recipe['vocabulary_unchanged'])

    def test_actual_disclosed_adapter_identity_is_pure(self):
        path=HERE/'code/ringfix-v2/ringfix_adapter.py';s=importlib.util.spec_from_file_location('public_ring_identity',path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
        base={'asset_sha256':{'tokenizer.json':m.BASE_TOKENIZER_SHA256}}
        value=m.augmented_identity(base);self.assertNotIn('tokenizer_adapter',base)
        self.assertEqual(value['tokenizer_adapter']['recipe_sha256'],m.RECIPE_SHA256)
        with self.assertRaises(ValueError):m.augmented_identity(value)

if __name__=='__main__':unittest.main(verbosity=2)
