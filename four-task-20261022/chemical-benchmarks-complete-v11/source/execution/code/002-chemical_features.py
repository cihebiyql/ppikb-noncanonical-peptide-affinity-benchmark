"""Frozen full-SMILES encoder cache and separately declared protein representation."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from collections import Counter
from pathlib import Path

import numpy as np

AA = 'ACDEFGHIKLMNPQRSTVWY'


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def resolve(path, parent):
    path = Path(path)
    return path if path.is_absolute() else parent / path


def json_read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def raw_key(text):
    if not isinstance(text, str) or not text:
        raise ValueError('Nonempty complete source SMILES/sequence required; no repair or substitution')
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def load_table(path, expected_sha, ids_key, embedding_key):
    if sha(path) != expected_sha:
        raise ValueError(f'Feature cache SHA mismatch: {path}')
    with np.load(path, allow_pickle=False) as obj:
        keys = obj[ids_key].astype(str)
        matrix = np.asarray(obj[embedding_key], dtype=np.float32)
    if matrix.ndim != 2 or matrix.shape[0] != len(keys) or not np.isfinite(matrix).all():
        raise ValueError('Invalid cache shape or nonfinite embeddings')
    if len(set(keys)) != len(keys):
        raise ValueError('Duplicate raw-input keys in cache')
    return {key: matrix[index] for index, key in enumerate(keys)}, matrix.shape[1]


class ChemicalFeatures:
    def __init__(self, specification_path, *, allow_synthetic_fixture=False):
        self.specification_path = Path(specification_path).resolve()
        self.spec = json_read(self.specification_path)
        if self.spec.get('is_template') is not False:
            raise ValueError('An actual frozen feature specification with is_template=false is required')
        parent = self.specification_path.parent
        self.audit = {'specification_path': str(self.specification_path),
                      'specification_sha256': sha(self.specification_path),
                      'labels_used_for_features': False, 'new_encoder_fit': False}
        self.chemistry_mode = self.spec.get('chemistry_mode', 'cached_encoder')
        self.audit['chemistry_mode'] = self.chemistry_mode
        if self.chemistry_mode == 'cached_encoder':
            binding_path = resolve(self.spec['chemical_cache_manifest'], parent)
            binding = json_read(binding_path)
            if self.spec.get('chemical_cache_manifest_sha256') != sha(binding_path):
                raise ValueError('Chemical manifest must have an exact frozen SHA in feature specification')
            if binding.get('status') != 'succeeded':
                raise ValueError('Chemical feature extraction has not succeeded')
            if binding.get('keys_kind') != 'sha256_raw_smiles':
                raise ValueError('Only unaltered full source SMILES keys are accepted')
            if binding.get('no_truncation') is not True or binding.get('chemical_canary_passed') is not True:
                raise ValueError('No-truncation and actual chemical-canary evidence required')
            canary_path = resolve(binding.get('chemical_canary_receipt', 'canary.json'), binding_path.parent)
            if sha(canary_path) != binding.get('chemical_canary_receipt_sha256', binding.get('canary_sha256')):
                raise ValueError('Chemical canary receipt SHA mismatch')
            canary = json_read(canary_path)
            if canary.get('schema') == 'chemical-encoder.canary.v1':
                if canary.get('status') != 'succeeded' or any(canary.get(k) is not True for k in ('all_finite', 'no_unknown_tokens', 'no_truncation')):
                    raise ValueError('Native chemical canary did not succeed')
                if canary.get('model_identity') != binding.get('model_identity'):
                    raise ValueError('Canary and feature cache use different model assets')
                required = {('alanine_L','alanine_D'), ('serine','phosphoserine'),
                            ('alanine_L','aminobutyrate'), ('alanine_L','alaninamide')}
                passed = {(item['a'],item['b']) for item in canary.get('pairs', [])
                          if item.get('token_ids_differ') is True and item.get('max_abs_embedding_difference',0) > 1e-7}
                if not required.issubset(passed) or canary.get('repeat_max_abs_difference',1) > 1e-7:
                    raise ValueError('Native D/L, PTM, noncanonical or terminal distinction/reproducibility check failed')
            elif allow_synthetic_fixture and canary.get('scope') == 'synthetic_fixture_not_chemical_validation':
                if canary.get('passed') is not True:
                    raise ValueError('Chemical canary receipt did not pass')
                for test in ('chirality', 'ptm', 'noncanonical'):
                    if canary.get('tests', {}).get(test, {}).get('passed') is not True:
                        raise ValueError(f'Missing successful actual chemical canary: {test}')
            else:
                raise ValueError('Formal cached-encoder features require the actual native chemical-encoder.canary.v1 receipt')
            embedding_path = resolve(binding['embedding_file'], binding_path.parent)
            self.chemical, self.chemical_dimension = load_table(
                embedding_path, binding['embedding_sha256'], binding.get('ids_key', 'smiles_sha256'),
                binding.get('embedding_key', 'embeddings'))
            self.audit.update(chemical_cache_manifest_sha256=sha(binding_path),
                              chemical_embedding_sha256=binding['embedding_sha256'],
                              chemical_canary_receipt_sha256=sha(canary_path),
                              chemical_dimension=self.chemical_dimension,
                              model_identity=binding.get('model_identity'),
                              chemical_identity='complete source isomeric SMILES to extent actually supplied')
        elif self.chemistry_mode == 'chiral_morgan_rdkit':
            source = resolve(self.spec['molecular_source'], parent)
            if sha(source) != self.spec['molecular_source_sha256']:
                raise ValueError('Frozen existing molecular feature implementation SHA differs')
            module_spec = importlib.util.spec_from_file_location('frozen_chemical_morgan_source', source)
            self.molecular = importlib.util.module_from_spec(module_spec)
            module_spec.loader.exec_module(self.molecular)
            canary = self.molecular.chiral_canary()
            ser = self.molecular.chemical_features('N[C@@H](CO)C(=O)O')
            phosphoser = self.molecular.chemical_features('N[C@@H](COP(=O)(O)O)C(=O)O')
            ptm_passed = not np.array_equal(ser, phosphoser)
            if not canary['passed'] or not ptm_passed:
                raise ValueError('Existing chiral Morgan feature canary failed')
            self.chemical, self.chemical_dimension = {}, len(ser)
            self.audit.update(chemical_dimension=self.chemical_dimension, molecular_source_sha256=sha(source),
                              model_identity='chiral-Morgan-r2-2048-plus-10-RDKit-descriptors',
                              chirality_canary=canary, phosphate_canary_passed=ptm_passed,
                              chemical_identity='complete source isomeric SMILES to extent actually supplied')
        else:
            raise ValueError('Unknown chemistry_mode')
        self.protein_mode = self.spec['protein_mode']
        if self.protein_mode == 'frozen_esm2':
            target_binding_path = resolve(self.spec['protein_cache_binding'], parent)
            target_binding = json_read(target_binding_path)
            if sha(target_binding_path) != self.spec['protein_cache_binding_sha256']:
                raise ValueError('Protein cache binding SHA mismatch')
            directory = resolve(target_binding['directory'], target_binding_path.parent)
            receipt_path = directory / 'receipt.json'
            receipt = json_read(receipt_path)
            if sha(receipt_path) != target_binding['receipt_sha256']:
                raise ValueError('Protein cache receipt mismatch')
            if receipt.get('status') != 'succeeded' or receipt.get('canary'):
                raise ValueError('Protein embeddings are not a successful formal cache')
            self.protein, self.protein_dimension = load_table(
                directory / 'embeddings.npz', target_binding['embedding_sha256'], 'sequence_ids', 'embeddings')
            if self.protein_dimension != 320:
                raise ValueError('Expected frozen ESM2-t6-8M 320D protein vectors')
            self.audit.update(protein_dimension=320, protein_mode=self.protein_mode,
                              protein_embedding_sha256=target_binding['embedding_sha256'],
                              protein_model_sha256=receipt.get('model_sha256'))
        elif self.protein_mode == 'aac23':
            self.protein_dimension = 23
            self.protein = {}
            self.audit.update(protein_dimension=23, protein_mode=self.protein_mode,
                              protein_features='20AA composition, unknown fraction, log length, zero empty flag')
        else:
            raise ValueError('Explicit protein_mode must be frozen_esm2 or aac23; no fallback')

    def target(self, sequence):
        key = raw_key(sequence)
        if self.protein_mode == 'frozen_esm2':
            if not set(sequence).issubset(set(AA)):
                raise ValueError('Non-AA20 target not supported by frozen protein cache')
            if key not in self.protein:
                raise KeyError(f'Uncached protein sequence SHA: {key}')
            return self.protein[key]
        if key not in self.protein:
            n, counts = len(sequence), Counter(sequence)
            self.protein[key] = np.asarray([counts[aa] / n for aa in AA] +
                [sum(v for k, v in counts.items() if k not in AA) / n, math.log1p(n), 0.0], dtype=np.float32)
        return self.protein[key]

    def molecule(self, smiles):
        key = raw_key(smiles)
        if self.chemistry_mode == 'chiral_morgan_rdkit' and key not in self.chemical:
            self.chemical[key] = self.molecular.chemical_features(smiles)
        if key not in self.chemical:
            raise KeyError(f'Uncached complete source SMILES SHA: {key}')
        return self.chemical[key]

    def coverage_reason(self, row, task='affinity'):
        targets = [row.get('target_sequence') or row.get('target_wt_sequence')]
        smiles = [row.get('peptide_smiles') or row.get('smiles')]
        if task == 'effect':
            targets = [row.get('target_wt_sequence') or row.get('target_sequence')]
            if (row.get('target_mut_sequence') or targets[0]) != targets[0]:
                return 'unsupported_target_mutation'
            smiles = [row.get('smiles_wt'), row.get('smiles_mut')]
        if not all(smiles):
            return 'missing_actual_complete_smiles'
        if not all(targets):
            return 'missing_target_sequence'
        if self.chemistry_mode == 'cached_encoder' and any(raw_key(sm) not in self.chemical for sm in smiles):
            return 'chemical_cache_unavailable_or_unsupported_input'
        if self.protein_mode == 'frozen_esm2':
            if any(not set(sequence).issubset(set(AA)) for sequence in targets):
                return 'unsupported_target_alphabet'
            if any(raw_key(sequence) not in self.protein for sequence in targets):
                return 'target_embedding_cache_unavailable'
        return None

    def build(self, frame, task):
        values, zero_changes = [], 0
        for row in frame.to_dict('records'):
            if task == 'effect':
                target_wt = row.get('target_wt_sequence') or row.get('target_sequence')
                target_mut = row.get('target_mut_sequence') or target_wt
                if target_wt != target_mut:
                    raise ValueError('This chemical-head effect track covers same-target peptide changes only')
                reference, variant = self.molecule(row['smiles_wt']), self.molecule(row['smiles_mut'])
                change = variant - reference
                zero_changes += int(np.array_equal(reference, variant))
                values.append(np.concatenate([reference, change, self.target(target_wt)]))
            else:
                smiles = row.get('peptide_smiles') or row.get('smiles')
                values.append(np.concatenate([self.molecule(smiles), self.target(row['target_sequence'])]))
        matrix = np.asarray(values, dtype=np.float32)
        if not np.isfinite(matrix).all() or matrix.ndim != 2:
            raise ValueError('Nonfinite or invalid feature matrix')
        audit = dict(self.audit, shape=list(matrix.shape), task=task,
                     feature_sha256=hashlib.sha256(matrix.tobytes()).hexdigest(),
                     effect_zero_embedding_change_rows=zero_changes if task == 'effect' else None)
        return matrix, audit
