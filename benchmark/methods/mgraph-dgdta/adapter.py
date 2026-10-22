"""Author MGraphDTA / DGDTA-CL adapters for a shared affinity trainer.

No peptide atoms are truncated. Both native graph representations OMIT atom
chirality; DGDTA also omits bond order. Protein prefixes follow the originals.
This is configuration/bug-fix adapted transfer evaluation, not paper-metric replication.
"""
from pathlib import Path
import hashlib
import importlib.util
import math
import numpy as np
import torch
from torch_geometric.data import Batch, Data
from rdkit import Chem

METHOD_IDS = ['MGraphDTA', 'DGDTA-CL']
HERE = Path(__file__).resolve().parent
_MODULES = {}

def _load(name):
    if name not in _MODULES:
        spec = importlib.util.spec_from_file_location('nc_benchmark_' + name, HERE / 'patched-author' / (name + '.py'))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _MODULES[name] = module
    return _MODULES[name]

def encode_record(row, method_id=None):
    if method_id is None:
        return {name: encode_record(row, name) for name in METHOD_IDS}
    if method_id not in METHOD_IDS:
        raise ValueError(method_id)
    smiles = row.get('canonical_isomeric_smiles') or row.get('peptide_smiles')
    if not smiles:
        raise ValueError('No chemical identity SMILES for ' + str(row.get('record_id')))
    mol = Chem.MolFromSmiles(smiles)
    if mol is None or mol.GetNumAtoms() == 0:
        raise ValueError('Invalid SMILES for ' + str(row.get('record_id')))
    sequence = row.get('target_sequence')
    if not isinstance(sequence, str) or not sequence:
        raise ValueError('No target sequence for ' + str(row.get('record_id')))
    value = float(row['pKd'])
    if not math.isfinite(value):
        raise ValueError('Non-finite pKd')
    cap = 1200 if method_id == 'MGraphDTA' else 1000
    effective = sequence[:cap]
    if method_id == 'MGraphDTA':
        prep = _load('mgraph_preprocessing')
        # Do not call dataset __init__: its only purpose here is unchanged graph methods.
        graph_builder = object.__new__(prep.GNNDataset)
        x, edges, edge_attr = graph_builder.mol2graph(mol)
        span = x.max() - x.min()
        if not torch.isfinite(span) or float(span) == 0:
            raise ValueError('Degenerate native per-graph minmax')
        x = (x - x.min()) / span
        encoded = prep.seqs2int(effective)
        target = torch.zeros((1, cap), dtype=torch.long)
        target[0, :len(encoded)] = torch.tensor(encoded, dtype=torch.long)
    else:
        prep = _load('dgdta_preprocessing')
        _, features, edge_list = prep.convert_smile_to_graph(smiles)
        x = torch.tensor(np.asarray(features), dtype=torch.float32)
        edges = torch.tensor(edge_list, dtype=torch.long).reshape(-1, 2).T.contiguous()
        edge_attr = None
        target = torch.tensor(prep.encode_sequence(sequence), dtype=torch.long).reshape(1, cap)
    if x.shape[0] != mol.GetNumAtoms():
        raise AssertionError('Atom truncation or count mismatch')
    graph = Data(x=x, edge_index=edges, y=torch.tensor([value], dtype=torch.float32), target=target)
    if edge_attr is not None:
        graph.edge_attr = edge_attr
    return {
        'method_id': method_id, 'graph': graph, 'record_id': str(row['record_id']),
        'effective_target_sha256': hashlib.sha256(effective.encode()).hexdigest(),
        'full_target_sha256': hashlib.sha256(sequence.encode()).hexdigest(),
        'target_original_length': len(sequence), 'target_effective_length': len(effective),
        'target_coverage': len(effective) / len(sequence),
        'target_truncated': len(sequence) > cap, 'protein_cap': cap,
        'atom_count': mol.GetNumAtoms(), 'atom_chirality_encoded': False,
    }

def collate(items):
    if not items:
        raise ValueError('Empty batch')
    method_ids = {item['method_id'] for item in items}
    if len(method_ids) != 1:
        raise ValueError('Mixed native graph representations')
    # Clone each cached CPU item. Author code is allowed to mutate this fresh batch.
    batch = Batch.from_data_list([item['graph'].clone() for item in items])
    return {'graph': batch, 'record_ids': [item['record_id'] for item in items], 'method_id': items[0]['method_id']}

def build_model(method_id, config=None):
    config = config or {}
    if method_id == 'MGraphDTA':
        return _load('mgraph_model').MGraphDTA(3, 26, 128, 32, 1)
    if method_id == 'DGDTA-CL':
        return _load('dgdta_model').GATv2GCNModel(dropout_rate=float(config.get('dropout_rate', 0.2)))
    raise ValueError(method_id)

def predict(model, batch, device):
    # Batch.to mutates its container, so clone to keep reusable batches device neutral.
    graph = batch['graph'].clone().to(device)
    return model(graph).reshape(-1)

def batch_targets(batch):
    return batch['graph'].y.reshape(-1)
