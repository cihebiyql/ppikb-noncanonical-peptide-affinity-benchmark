"""Pinned CLM2 input-only ring adapter. Imports no model or torch."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

RECIPE_SHA256 = '0cd5d5e04a6503af84033c72b2723e2c19e66e8a74db2315dbf0db037d955a17'
BASE_TOKENIZER_SHA256 = 'd7cfeefb9290fb094430641a53dcfeba580efc60b64bb4a84225366d7dc75d98'
HERE = Path(__file__).resolve().parent


def file_sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def load_recipe():
    path = HERE / 'ringfix-recipe.json'
    if file_sha(path) != RECIPE_SHA256:
        raise ValueError('Ringfix recipe changed')
    recipe = json.loads(path.read_text(encoding='utf-8'))
    if recipe['schema'] != 'chemical-encoder.tokenizer-ringfix.v2':
        raise ValueError('Unexpected recipe schema')
    if recipe['base_tokenizer_sha256'] != BASE_TOKENIZER_SHA256:
        raise ValueError('Unexpected base tokenizer')
    if recipe['new_regex'] != recipe['old_regex'][:-1] + '|%[0-9]{2}|[0-9])':
        raise ValueError('Only the reviewed percent-preserving ring-digit change is supported')
    if recipe['weights_modified'] or recipe['smiles_modified'] or not recipe['vocabulary_unchanged']:
        raise ValueError('Recipe changes weights/chemistry/vocabulary')
    return recipe


def augmented_identity(base_identity):
    load_recipe()
    if base_identity['asset_sha256']['tokenizer.json'] != BASE_TOKENIZER_SHA256:
        raise ValueError('Model identity has a different original tokenizer')
    adapter = {'name': 'ringfix-v2-percent-preserving', 'recipe_sha256': RECIPE_SHA256,
               'adapter_source_sha256': file_sha(Path(__file__)),
               'base_tokenizer_sha256': BASE_TOKENIZER_SHA256,
               'weights_unchanged': True, 'vocabulary_unchanged': True,
               'smiles_unchanged': True}
    if 'tokenizer_adapter' in base_identity:
        raise ValueError('Expected native asset identity before augmentation')
    return dict(base_identity, tokenizer_adapter=adapter)


def apply_ringfix(tokenizer):
    """Modify only the loaded tokenizer object's pre-tokenizer; no file mutation."""
    recipe = load_recipe()
    backend = getattr(tokenizer, 'backend_tokenizer', tokenizer)
    before = json.loads(backend.to_str())
    part = before['pre_tokenizer']
    if part != {'type': 'Split', 'pattern': {'Regex': recipe['old_regex']},
                'behavior': 'Isolated', 'invert': False}:
        raise ValueError('Tokenizer is already modified or differs from native policy')
    from tokenizers import Regex, pre_tokenizers
    backend.pre_tokenizer = pre_tokenizers.Split(Regex(recipe['new_regex']), behavior='isolated', invert=False)
    after = json.loads(backend.to_str())
    a, b = dict(before), dict(after)
    a.pop('pre_tokenizer'); b.pop('pre_tokenizer')
    if a != b or backend.get_vocab() != before['model']['vocab']:
        raise ValueError('Ringfix changed vocabulary or another tokenizer component')
    return {'recipe_sha256': RECIPE_SHA256, 'adapter_source_sha256': file_sha(Path(__file__)),
            'other_components_unchanged': True, 'vocabulary_unchanged': True,
            'new_regex_sha256': hashlib.sha256(recipe['new_regex'].encode()).hexdigest()}
