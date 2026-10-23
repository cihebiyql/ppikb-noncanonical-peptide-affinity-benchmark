"""Meaningful preparation guards, without loading a GPU or author model."""
import importlib.util
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent
def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class ProtocolTests(unittest.TestCase):
    def test_missing_chemical_identity_is_rejected(self):
        prepare = load('prepare_jobs')
        with self.assertRaises(ValueError):
            prepare.normalize({'row_id': 'r', 'label': 1, 'target_sequence': 'ACD', 'peptide_sequence': 'AAA'}, 'regression')

    def test_duplicate_original_observation_cannot_cross_splits(self):
        prepare = load('prepare_jobs')
        rows = [{'record_id': 'same', 'split': split} for split in ['train', 'validation', 'test']]
        with self.assertRaises(ValueError):
            prepare.partition(rows)

    def test_effect_needs_both_chemical_entities(self):
        prepare = load('prepare_jobs')
        with self.assertRaises(ValueError):
            prepare.normalize({'row_id': 'r', 'label': 1, 'target_sequence': 'ACD', 'smiles_wt': 'CC'}, 'effect')

    def test_native_batchnorm_singleton_handling_preserves_every_sample(self):
        train = load('train')
        chunks = train.minibatches(list(range(33)), 16)
        self.assertEqual([i for chunk in chunks for i in chunk], list(range(33)))
        self.assertGreater(len(chunks[-1]), 1)

if __name__ == '__main__':
    unittest.main()
