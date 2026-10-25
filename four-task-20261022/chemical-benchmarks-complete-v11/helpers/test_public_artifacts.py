"""Synthetic fixtures only; no biological data or trained weights."""
import csv
import importlib.util
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
def module(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value

p = module('public_artifacts')
c = module('collect_artifacts')
e = module('evaluate_saved_predictions')


def fixture_csv(source='PPIKB', value='1.5'):
    stream = io.StringIO(newline='')
    writer = csv.writer(stream, lineterminator='\n')
    writer.writerow(['row_id','source','split','group_id','global_group_id','endpoint','evaluation_stratum','label','prediction'])
    writer.writerow(['synthetic-1',source,'test','g','g','pKd','fixture','1',value])
    return stream.getvalue().encode()


class PublicPreparationTests(unittest.TestCase):
    def test_numeric_json_leaves_preserved(self):
        original = {'loss': 1.2345678901234567, 'seed': 9, 'epochs': [2,3], 'source': '/data/qlyu/projects/peptide-four-task-benchmark-20261022/runs/a'}
        cleaned, changes = p.sanitize_json(original)
        self.assertEqual([cleaned['loss'],cleaned['seed'],cleaned['epochs']], [original['loss'],9,[2,3]])
        self.assertTrue(changes)
        self.assertEqual(cleaned['source'], 'record-ref:project/runs/a')

    def test_secret_removed_mapping_contains_hash_only(self):
        secret = 'ghp_' + 'x' * 32
        cleaned, changes = p.sanitize_text('credential=' + secret)
        self.assertNotIn(secret, cleaned)
        self.assertNotIn(secret, json.dumps(changes))
        self.assertEqual(changes[0]['removed_text_sha256'], p.sha(secret.encode()))

    def test_unclassified_input_field_has_explicit_disposition(self):
        cleaned, changes = p.sanitize_json({'input_ids':[123,456],'history':[{'epoch':1,'loss':3.2}]})
        self.assertEqual(cleaned['history'], [{'epoch':1,'loss':3.2}])
        self.assertIn('withheld',cleaned['input_ids'])
        self.assertEqual(changes[0]['json_pointer'],'/input_ids')

    def test_private_paths_in_json_dictionary_keys_are_sanitized(self):
        cleaned,changes=p.sanitize_json({'/data/qlyu/projects/peptide-four-task-benchmark-20261022/model.py':{'sha':'fixture','n':12}})
        self.assertEqual(cleaned,{'record-ref:project/model.py':{'sha':'fixture','n':12}})
        self.assertNotIn('qlyu',json.dumps(changes))
        self.assertTrue(changes[0]['json_key'])

    def test_unrelated_process_identity_and_commands_removed_resource_numbers_kept(self):
        original={'user':'fixture-person','name':'/home/fixture-person/project/tool.py','cmdline':['private command','--secret','fixture'],'memory_mib':1234,'pid':5678,'uuid':'GPU-11111111-2222-3333-4444-555555555555'}
        cleaned,changes=p.sanitize_json(original)
        self.assertEqual((cleaned['memory_mib'],cleaned['pid']),(1234,5678))
        self.assertNotIn('fixture-person',json.dumps(cleaned))
        self.assertNotIn('private command',json.dumps(cleaned))
        self.assertTrue(cleaned['uuid'].startswith('gpu-ref:sha256:'))
        self.assertTrue(any(c['rule']=='unrelated_process_command_not_project_science' for c in changes))

    def test_other_private_home_path_masked_but_project_ref_preserved(self):
        cleaned,changes=p.sanitize_text('/home/fixture-person/env/bin/python')
        self.assertTrue(cleaned.startswith('record-ref:private-path#sha256:'))
        ref='record-ref:project/data/cohort.csv'
        self.assertEqual(p.sanitize_text(ref),(ref,[]))

    def test_prediction_original_bytes(self):
        data = fixture_csv()
        reviewed = p.inspect_prediction_csv(data,expected_rows=1,expected_ids=['synthetic-1'])
        self.assertEqual(reviewed['n'],1)
        self.assertEqual(p.prepare_bytes(data,'.csv'),(data,[]))

    def test_other_dataset_not_blanket_licensed(self):
        with self.assertRaises(ValueError):p.inspect_prediction_csv(fixture_csv('OTHER'))

    def test_nonfinite_prediction_rejected(self):
        with self.assertRaises(ValueError):p.inspect_prediction_csv(fixture_csv(value='nan'))

    def test_wrong_prediction_case_set_rejected(self):
        with self.assertRaises(ValueError):p.inspect_prediction_csv(fixture_csv(),expected_ids=['other'])

    def test_raw_input_log_requires_review(self):
        with self.assertRaises(ValueError):p.prepare_bytes(b'protein_sequence=synthetic fixture','.log')

    def test_symbolic_oom_traceback_preserved_but_not_token_array(self):
        log=b'hidden = self.encoder(input_ids=ids, attention_mask=mask, return_dict=True).last_hidden_state\n'
        self.assertEqual(p.prepare_bytes(log,'.log'),(log,[]))
        with self.assertRaises(ValueError):p.prepare_bytes(b'input_ids=[1,2,3]','.log')

    def test_traversal_and_windows_paths_rejected(self):
        for name in ('../bad','/absolute','C:/bad','a/./b','a//b','a\\b'):
            with self.subTest(name=name),self.assertRaises(ValueError):p.safe_relative(name)

    def test_collection_never_reads_binary(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);source=root/'input';source.mkdir()
            (source/'stdout.log').write_text('epoch=1 loss=0.25\n')
            (source/'candidate.joblib').write_bytes(b'not a real model')
            archive=root/'collected.tar.gz'
            result=c.collect(['fixture='+str(source)],archive)
            self.assertEqual((result['collected_files'],result['indexed_files']),(1,2))
            inventory=p.extract_checked(archive,root/'mirror')
            binary=next(x for x in inventory['files'] if x['relative_path']=='candidate.joblib')
            self.assertEqual(binary['disposition'],'not_collected_binary')
            self.assertNotIn('sha256',binary)

    def test_archives_deterministic(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw)
            first=p.deterministic_archive({'b.log':b'b','a.json':b'{}'},root/'first.gz')
            second=p.deterministic_archive({'a.json':b'{}','b.log':b'b'},root/'second.gz')
            self.assertEqual(first['sha256'],second['sha256'])

    def test_extract_rejects_symlinks(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);archive=root/'bad.tar.gz'
            with tarfile.open(archive,'w:gz') as writer:
                entry=tarfile.TarInfo('link');entry.type=tarfile.SYMTYPE;entry.linkname='outside';writer.addfile(entry)
            with self.assertRaises(ValueError):p.extract_checked(archive,root/'output')

    def test_refuse_collector_overwrite(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw);archive=root/'occupied.gz';archive.write_bytes(b'history')
            with self.assertRaises(FileExistsError):c.collect(['fixture='+str(root)],archive)
            self.assertEqual(archive.read_bytes(),b'history')

    def test_spearman_average_tie_ranks(self):
        self.assertEqual(e.ranks([3,1,1,2]),[4,1.5,1.5,3])

    def test_saved_metrics_and_undefined_correlations(self):
        result=e.metrics([{'label':'1','prediction':'2'},{'label':'3','prediction':'2'}])
        self.assertEqual((result['n'],result['mae'],result['rmse'],result['bias'],result['r2']),(2,1,1,0,0))
        self.assertIsNone(result['pearson']);self.assertIsNone(result['spearman'])
        self.assertIsNone(e.metrics([{'label':'1','prediction':'1'}])['r2'])

    def test_empty_and_nonfinite_saved_metrics(self):
        self.assertEqual(e.metrics([])['n'],0)
        with self.assertRaises(ValueError):e.metrics([{'label':'inf','prediction':'1'}])


if __name__ == '__main__':
    unittest.main()
