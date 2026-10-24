"""Recipe/source invariants only; no chemical model loading or fitting."""
from __future__ import annotations
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import ringfix_adapter as adapter


def node(path, name):
    tree = ast.parse(path.read_text(encoding='utf-8'))
    for value in ast.walk(tree):
        if isinstance(value, (ast.FunctionDef, ast.ClassDef)) and value.name == name:
            return value
        if isinstance(value, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in value.targets):
            return value.value
    raise KeyError(name)


class PreparationTests(unittest.TestCase):
    def test_exact_reviewed_recipe_and_components(self):
        recipe = adapter.load_recipe()
        self.assertEqual(hashlib.sha256((HERE/'ringfix-recipe.json').read_bytes()).hexdigest(), adapter.RECIPE_SHA256)
        self.assertEqual(recipe['new_regex'], recipe['old_regex'][:-1]+'|%[0-9]{2}|[0-9])')
        self.assertTrue(recipe['vocabulary_unchanged'])

    def test_identity_adds_recipe_and_source_without_mutating_base(self):
        base = {'repository':'fixture','revision':'fixture','asset_sha256':{'tokenizer.json':adapter.BASE_TOKENIZER_SHA256}}
        before = copy.deepcopy(base)
        identity = adapter.augmented_identity(base)
        self.assertEqual(base, before)
        self.assertEqual(identity['tokenizer_adapter']['recipe_sha256'], adapter.RECIPE_SHA256)
        self.assertEqual(identity['tokenizer_adapter']['adapter_source_sha256'], adapter.file_sha(HERE/'ringfix_adapter.py'))
        with self.assertRaises(ValueError): adapter.augmented_identity(identity)

    def test_different_base_tokenizer_rejected(self):
        with self.assertRaises(ValueError):
            adapter.augmented_identity({'asset_sha256':{'tokenizer.json':'wrong'}})

    def test_fullfine_settings_and_science_functions_unchanged(self):
        old = ROOT/'baselines/chemical-encoder-finetune-20261024-v1/train_finetune.py'
        new = HERE/'train_finetune_ringfix.py'
        self.assertEqual(ast.literal_eval(node(old,'SETTINGS')), ast.literal_eval(node(new,'SETTINGS')))
        for name in ['PairRegressor','seed_all','rng_state','restore_rng','load_model','batch_values','predict',
                     'atomic_checkpoint','train_candidate','select_test','cost_gate']:
            self.assertEqual(ast.dump(node(old,name),include_attributes=False),ast.dump(node(new,name),include_attributes=False),name)

    def test_extractor_feature_and_pooling_functions_unchanged(self):
        old=ROOT/'methods/chemical-encoders-20261024-v1/extract_cpu.py'
        new=HERE/'extract_cpu_ringfix.py'
        for name in ['sha_bytes','sha_file','write_json','token_info','encode']:
            self.assertEqual(ast.dump(node(old,name),include_attributes=False),ast.dump(node(new,name),include_attributes=False),name)

    def test_old_source_bytes_preserved(self):
        self.assertEqual(adapter.file_sha(ROOT/'methods/chemical-encoders-20261024-v1/extract_cpu.py'),
                         '73b8e2d5e6e6e460f960dae55930175d9febc7fb961764f2a175bdd82bfa9a55')
        self.assertEqual(adapter.file_sha(ROOT/'baselines/chemical-encoder-finetune-20261024-v1/train_finetune.py'),
                         '1e3a84d0d0b67f1ffdc77a6618a5053b78ce479055df3ed10c6720887f7a7e65')

    @unittest.skipIf(importlib.util.find_spec('tokenizers') is None,'Local metadata tokenizer package absent; actual Node23 forward will verify adapter')
    def test_real_tokenizer_matches_the_actual_metadata_snapshot(self):
        from tokenizers import Tokenizer
        base=ROOT/'resources/chemical-encoders-20261024-v1/models/peptideclm-2-hybrid-small/tokenizer.json'
        tokenizer=Tokenizer.from_file(str(base))
        adapter.apply_ringfix(tokenizer)
        expected=json.loads((HERE/'collected-actual/artifacts--tokenizer.ringfix.json').read_text())
        self.assertEqual(json.loads(tokenizer.to_str()), expected)
        with self.assertRaises(ValueError):adapter.apply_ringfix(tokenizer)


if __name__=='__main__':unittest.main(verbosity=2)
