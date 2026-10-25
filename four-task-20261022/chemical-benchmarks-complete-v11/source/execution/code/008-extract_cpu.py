"""Offline, frozen PeptideCLM-2 features; resource owner launches this worker.

Default pooling is the author's native mean_pool (PAD excluded, CLS/SEP included).
No SMILES canonicalization, chemistry projection, fitting, or silent truncation.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import importlib
import json
import os
import random
import sys
import time
import types
from datetime import datetime, timezone
from pathlib import Path

CANARIES = {
    'alanine_L': 'N[C@@H](C)C(=O)O',
    'alanine_D': 'N[C@H](C)C(=O)O',
    'serine': 'N[C@@H](CO)C(=O)O',
    'phosphoserine': 'N[C@@H](COP(=O)(O)O)C(=O)O',
    'aminobutyrate': 'N[C@@H](CC)C(=O)O',
    'alaninamide': 'N[C@@H](C)C(=O)N',
}
PAIRS = [('alanine_L', 'alanine_D'), ('serine', 'phosphoserine'),
         ('alanine_L', 'aminobutyrate'), ('alanine_L', 'alaninamide')]


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def verify_assets(model_dir, receipt_path):
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    assert receipt['status'] == 'succeeded', 'Incomplete asset receipt'
    name = 'aaronfeller/' + model_dir.name
    entries = [x for x in receipt['files'] if x['repository'] == name and x['kind'] == 'model_asset']
    assert len(entries) == 9, 'Unexpected model asset closure'
    checked = {}
    for item in entries:
        path = model_dir / item['relative_path']
        assert path.is_file() and path.stat().st_size == item['bytes'], 'Missing/changed asset ' + path.name
        actual = sha_file(path)
        assert actual == item['sha256'], 'Changed asset ' + path.name
        checked[path.name] = actual
    assert 'model.safetensors' in checked and 'ChemPepMTR.py' in checked
    return {'repository': name, 'revision': entries[0]['revision'], 'asset_sha256': checked,
            'asset_receipt_sha256': sha_file(receipt_path)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model-dir', required=True, type=Path)
    parser.add_argument('--asset-receipt', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--input-csv', type=Path)
    parser.add_argument('--smiles-column', default='smiles')
    parser.add_argument('--canary-only', action='store_true')
    parser.add_argument('--max-tokens', type=int, default=768)
    parser.add_argument('--batch-size', type=int, default=4)
    parser.add_argument('--threads', type=int, default=2)
    parser.add_argument('--wall-seconds', type=int, default=180)
    parser.add_argument('--pooling', choices=['native_mean_pool', 'mean_content_pool'], default='native_mean_pool')
    args = parser.parse_args()
    assert 1 <= args.threads <= 8 and 1 <= args.batch_size <= 16
    assert args.canary_only or args.input_csv, 'input-csv required for features'
    assert not args.output_dir.exists(), 'Unique new output directory required'
    args.output_dir.mkdir(parents=True)
    started = time.monotonic()
    os.environ['CUDA_VISIBLE_DEVICES'] = ''
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    os.environ['OMP_NUM_THREADS'] = str(args.threads)
    os.environ['MKL_NUM_THREADS'] = str(args.threads)
    provenance = verify_assets(args.model_dir, args.asset_receipt)
    write_json(args.output_dir / 'run-status.json', {'status': 'initializing', 'model_identity': provenance})
    import numpy as np
    import torch
    import transformers
    from transformers import PreTrainedTokenizerFast
    torch.set_num_threads(args.threads)
    torch.set_num_interop_threads(1)
    torch.manual_seed(0)
    random.seed(0)
    np.random.seed(0)
    # Import reviewed files from a local package; never execute downloaded code via a remote URL.
    package_name = 'reviewed_chemical_encoder_' + provenance['asset_sha256']['ChemPepMTR.py'][:12]
    package = types.ModuleType(package_name)
    package.__path__ = [str(args.model_dir.resolve())]
    sys.modules[package_name] = package
    module = importlib.import_module(package_name + '.ChemPepMTR')
    config_module = importlib.import_module(package_name + '.config')
    config_data = json.loads((args.model_dir / 'config.json').read_text())
    tokenizer_config = json.loads((args.model_dir / 'tokenizer_config.json').read_text())
    assert 2 < args.max_tokens <= min(config_data['max_seq_len'], tokenizer_config['model_max_length'])
    tokenizer = PreTrainedTokenizerFast(tokenizer_file=str(args.model_dir / 'tokenizer.json'),
        pad_token='[PAD]', unk_token='[UNK]', cls_token='[CLS]', sep_token='[SEP]', mask_token='[MASK]',
        model_max_length=tokenizer_config['model_max_length'])
    config = config_module.model_config(**config_data)
    model, loading = module.MLM_model.from_pretrained(str(args.model_dir), config=config,
        local_files_only=True, use_safetensors=True, output_loading_info=True)
    assert not loading.get('missing_keys') and not loading.get('unexpected_keys') and not loading.get('mismatched_keys'), loading
    model = model.to(device='cpu', dtype=torch.float32).eval()
    model.requires_grad_(False)

    def token_info(smiles):
        if not smiles or any(x.isspace() for x in smiles):
            return None, 'empty_or_whitespace_smiles'
        encoded = tokenizer(smiles, truncation=False, padding=False, add_special_tokens=True,
                            return_offsets_mapping=True, return_special_tokens_mask=True)
        ids = encoded['input_ids']
        if len(ids) > args.max_tokens:
            return {'token_count': len(ids)}, 'token_budget_exceeded'
        if tokenizer.unk_token_id in ids:
            return {'token_count': len(ids)}, 'unknown_token'
        covered = [False] * len(smiles)
        for (a, b), special in zip(encoded['offset_mapping'], encoded['special_tokens_mask']):
            if not special:
                covered[a:b] = [True] * (b-a)
        if not all(covered):
            return {'token_count': len(ids)}, 'uncovered_input_characters'
        return {'token_count': len(ids), 'input_ids': ids}, None

    def encode(smiles_list):
        batch = tokenizer(smiles_list, return_tensors='pt', truncation=False, padding=True,
                          add_special_tokens=True, return_special_tokens_mask=True)
        special_mask = batch.pop('special_tokens_mask')
        with torch.inference_mode():
            outputs = model(input_ids=batch['input_ids'], attention_mask=batch['attention_mask'])
            if args.pooling == 'native_mean_pool':
                pooled = outputs.mean_pool
            else:
                mask = (batch['attention_mask'].bool() & ~special_mask.bool()).unsqueeze(-1)
                pooled = (outputs.last_hidden_state * mask).sum(1) / mask.sum(1).clamp(min=1)
        array = pooled.detach().cpu().numpy().astype(np.float32, copy=False)
        assert array.shape == (len(smiles_list), config_data['embed_dim']) and np.isfinite(array).all()
        return array

    canary_tokens = {}
    for name, smiles in CANARIES.items():
        token, error = token_info(smiles)
        assert not error, ('Canary tokenizer failure', name, error)
        canary_tokens[name] = token
    values = encode(list(CANARIES.values()))
    repeated = encode(list(CANARIES.values()))
    repeat_max = float(np.abs(values-repeated).max())
    assert repeat_max <= 1e-7, ('Nondeterministic canary', repeat_max)
    pairs = []
    names = list(CANARIES)
    for a, b in PAIRS:
        diff = float(np.abs(values[names.index(a)]-values[names.index(b)]).max())
        distinct = canary_tokens[a]['input_ids'] != canary_tokens[b]['input_ids']
        assert distinct and diff > 1e-7, ('Chemical distinction lost', a, b, diff)
        pairs.append({'a': a, 'b': b, 'token_ids_differ': distinct, 'max_abs_embedding_difference': diff})
    canary = {'schema': 'chemical-encoder.canary.v1', 'status': 'succeeded',
              'model_identity': provenance, 'pooling': args.pooling, 'max_tokens_including_special': args.max_tokens,
              'tokenizer_model_max_length': tokenizer_config['model_max_length'],
              'architecture_max_seq_len': config_data['max_seq_len'], 'embedding_dim': config_data['embed_dim'],
              'parameter_count': sum(p.numel() for p in model.parameters()),
              'repeat_max_abs_difference': repeat_max, 'pairs': pairs, 'tokenizations': canary_tokens,
              'all_finite': True, 'no_unknown_tokens': True, 'no_truncation': True,
              'scientific_scope': 'Chemical representations differ; no binding-affinity accuracy claim.',
              'runtime': {'torch': torch.__version__, 'transformers': transformers.__version__,
                          'device': 'cpu', 'threads': args.threads, 'dtype': 'float32'}}
    write_json(args.output_dir / 'canary.json', canary)
    np.savez_compressed(args.output_dir / 'canary-embeddings.npz', embeddings=values,
                        ids=np.asarray(names, dtype='U32'))
    if args.canary_only:
        write_json(args.output_dir / 'run-status.json', {'status': 'succeeded', 'scope': 'canary_only',
                   'elapsed_seconds': time.monotonic()-started, 'model_identity': provenance})
        print(json.dumps({'status': 'succeeded', 'scope': 'canary_only', 'embedding_dim': config_data['embed_dim'],
                          'pairs': pairs, 'elapsed_seconds': time.monotonic()-started}))
        return 0

    unique = {}
    with args.input_csv.open(encoding='utf-8-sig', newline='') as handle:
        for row in csv.DictReader(handle):
            smiles = row[args.smiles_column]
            key = sha_bytes(smiles.encode('utf-8'))
            assert key not in unique or unique[key] == smiles
            unique[key] = smiles
    accepted, rejected = [], []
    for key, smiles in sorted(unique.items()):
        info, error = token_info(smiles)
        if error:
            rejected.append({'smiles_sha256': key, 'reason': error, **(info or {})})
        else:
            accepted.append((key, smiles, info['token_count']))
    assert accepted, 'No accepted molecule'
    accepted.sort(key=lambda x: (x[2], x[0]))
    matrix, keys = [], []
    chunk_dir = args.output_dir / 'chunks'
    chunk_dir.mkdir()
    for offset in range(0, len(accepted), args.batch_size):
        assert time.monotonic()-started < args.wall_seconds, 'Feature extraction wall budget reached; chunks retained'
        batch = accepted[offset:offset+args.batch_size]
        array = encode([x[1] for x in batch])
        ids = np.asarray([x[0] for x in batch], dtype='U64')
        np.savez_compressed(chunk_dir / f'{offset:07d}.npz', embeddings=array, smiles_sha256=ids)
        matrix.append(array)
        keys.extend(ids.tolist())
        write_json(args.output_dir / 'run-status.json', {'status': 'running', 'molecules_completed': len(keys),
                   'molecules_total_accepted': len(accepted), 'elapsed_seconds': time.monotonic()-started})
    feature_file = args.output_dir / 'embeddings.npz'
    np.savez_compressed(feature_file, embeddings=np.concatenate(matrix), smiles_sha256=np.asarray(keys, dtype='U64'))
    write_json(args.output_dir / 'coverage.json', {'unique_raw_smiles': len(unique), 'accepted': len(accepted),
               'rejected': rejected, 'max_tokens_including_special': args.max_tokens, 'silent_truncation': False})
    manifest = {'schema': 'chemical-encoder.cache.v1', 'status': 'succeeded', 'model_identity': provenance,
                'embedding_file': str(feature_file.resolve()), 'embedding_sha256': sha_file(feature_file),
                'embedding_key': 'embeddings', 'ids_key': 'smiles_sha256', 'keys_kind': 'sha256_raw_smiles',
                'rows': len(keys), 'dimensions': config_data['embed_dim'], 'dtype': 'float32', 'allow_pickle': False,
                'pooling': args.pooling, 'no_truncation': True, 'chemical_canary_passed': True,
                'input_csv_sha256': sha_file(args.input_csv), 'extractor_sha256': sha_file(Path(__file__)),
                'canary_sha256': sha_file(args.output_dir / 'canary.json'),
                'supervised_labels_used': False, 'elapsed_seconds': time.monotonic()-started}
    write_json(args.output_dir / 'cache-manifest.json', manifest)
    write_json(args.output_dir / 'run-status.json', {'status': 'succeeded', 'scope': 'feature_extraction',
               'molecules_completed': len(keys), 'elapsed_seconds': time.monotonic()-started})
    print(json.dumps({'status': 'succeeded', 'scope': 'feature_extraction', 'rows': len(keys),
                      'excluded': len(rejected), 'embedding_sha256': manifest['embedding_sha256'],
                      'elapsed_seconds': manifest['elapsed_seconds']}))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'status': 'failed', 'error': type(error).__name__ + ': ' + str(error)}), file=sys.stderr)
        raise
