"""Offline 2025 PeptideCLM loading helpers. Importing this file loads no model.

Resource owner must separately authorize and bound actual calls to load_encoder.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


def sha(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024*1024), b''):
            result.update(block)
    return result.hexdigest()


def verify(asset_root, tokenizer_dir):
    asset_root, tokenizer_dir = Path(asset_root), Path(tokenizer_dir)
    receipt_path = asset_root / 'ASSET-RECEIPT.actual.json'
    receipt = json.loads(receipt_path.read_text())
    audit = json.loads((asset_root / 'STATIC-RUNTIME-AUDIT.actual.json').read_text())
    if receipt['status'] != 'succeeded' or receipt['revision'] != 'a0847d8231d236645a2c4f629590118716c6fdda':
        raise ValueError('Unexpected or partial 2025 assets')
    if sha(receipt_path) != audit['asset_receipt_sha256']:
        raise ValueError('Asset audit/receipt mismatch')
    for item in receipt['files']:
        path = asset_root / item['relative_path']
        if sha(path) != item['sha256']:
            raise ValueError('Changed original model asset ' + item['relative_path'])
    for item in audit['vendor_files']:
        if sha(asset_root/item['relative_path']) != item['sha256']:
            raise ValueError('Changed private tokenizer dependency')
    for item in audit['source_files']:
        path = tokenizer_dir / Path(item['path']).name
        if sha(path) != item['sha256']:
            raise ValueError('Changed author tokenizer source/vocabulary')
    return receipt, audit


def load_encoder(asset_root, tokenizer_dir):
    """Load only through torch's restricted weights-only unpickler, never fallback."""
    asset_root, tokenizer_dir = Path(asset_root), Path(tokenizer_dir)
    receipt, audit = verify(asset_root, tokenizer_dir)
    vendor = (asset_root/'vendor').resolve()
    sys.path.insert(0, str(vendor))
    # Private reviewed package overlay, no shared installation or source modification.
    import SmilesPE
    if not Path(SmilesPE.__file__).resolve().is_relative_to(vendor):
        raise ValueError('A different previously imported SmilesPE is active')
    spec = importlib.util.spec_from_file_location('reviewed_peptideclm2025_tokenizer', tokenizer_dir/'my_tokenizers.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tokenizer = module.SMILES_SPE_Tokenizer(str(tokenizer_dir/'new_vocab.txt'), str(tokenizer_dir/'new_splits.txt'), model_max_length=768)
    import torch
    from transformers import RoFormerConfig, RoFormerForMaskedLM
    config = RoFormerConfig(**json.loads((asset_root/'model/config.json').read_text()))
    # No weights_only=False, custom globals allowlisting, remote code or executable pickle fallback.
    state = torch.load(asset_root/'model/pytorch_model.bin', map_location='cpu', weights_only=True)
    if not isinstance(state, dict) or not all(isinstance(k,str) and isinstance(v,torch.Tensor) for k,v in state.items()):
        raise ValueError('Expected a tensor-only state_dict')
    model = RoFormerForMaskedLM(config)
    model.load_state_dict(state, strict=True)
    encoder = model.roformer.eval().requires_grad_(False)
    return tokenizer, encoder, {'model':receipt['model'],'revision':receipt['revision'],
        'weights_sha256':next(x['sha256'] for x in receipt['files'] if x['relative_path']=='model/pytorch_model.bin'),
        'pooling':'adapted_masked_mean_including_cls_sep', 'embedding_dimension':768,
        'max_tokens_including_special':768, 'pretrained_corpus_test_entity_exposure':'unknown'}


def tokenize_full(tokenizer, smiles):
    if not smiles or any(x.isspace() for x in smiles):
        raise ValueError('Empty or whitespace SMILES')
    tokens = tokenizer.tokenize(smiles)
    # SmilesPE's regex may otherwise drop an unsupported character silently.
    if ''.join(tokens) != smiles:
        raise ValueError('Tokenizer did not preserve the entire original chemical string')
    encoded = tokenizer(smiles, add_special_tokens=True, truncation=False, padding=False)
    if len(encoded['input_ids']) > 768:
        raise ValueError('Token budget exceeded; no truncation permitted')
    if tokenizer.unk_token_id in encoded['input_ids']:
        raise ValueError('Unknown chemical token')
    return encoded


def pooled_features(encoder, input_ids, attention_mask):
    """Explicit adaptation; released 2025 backbone has no native pooled output."""
    import torch
    with torch.inference_mode():
        hidden = encoder(input_ids=input_ids, attention_mask=attention_mask, return_dict=True).last_hidden_state
        mask = attention_mask.unsqueeze(-1).to(hidden.dtype)
        result = (hidden*mask).sum(1)/mask.sum(1).clamp(min=1)
    if result.shape[-1] != 768 or not torch.isfinite(result).all():
        raise ValueError('Unexpected or nonfinite embedding')
    return result
