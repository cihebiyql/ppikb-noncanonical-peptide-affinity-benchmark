"""Adapters for frozen GraphDTA-GIN and DeepNC-GEN author architectures.

No peptide atom cap. Original 1000-residue target prefix and original 78 atom
features are retained. Chirality, bond order and stereochemistry are NOT encoded.
"""
import hashlib
import importlib.util
from pathlib import Path

import numpy as np
import torch
from rdkit import Chem
from torch_geometric.data import Batch, Data

METHOD_IDS = ["GraphDTA-GIN", "DeepNC-GEN"]
HERE = Path(__file__).resolve().parent


def _load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / "vendor" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_gin = _load("nc_graphdta_gin_author", "graphdta_gin.py")
_gen = _load("nc_deepnc_gen_author", "deepnc_gen.py")
_features = _load("nc_graphdta_features_author", "graphdta_gin_features.py")


def _sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def encode_record(row):
    """Return a CPU-only pickleable dictionary with complete truncation audit.

    row.pKd is an already harmonized regression target. No endpoint conversion,
    data-fitted normalization, entity substitution, or record dropping occurs.
    """
    smiles = row.get("canonical_isomeric_smiles") or row.get("peptide_smiles")
    if not isinstance(smiles, str) or not smiles:
        raise ValueError(f"{row.get('record_id')}: missing peptide SMILES")
    sequence = row.get("target_sequence")
    if not isinstance(sequence, str) or not sequence:
        raise ValueError(f"{row.get('record_id')}: missing target sequence")
    mol = Chem.MolFromSmiles(smiles)
    if mol is None or mol.GetNumAtoms() == 0:
        raise ValueError(f"{row.get('record_id')}: invalid/empty molecular graph")
    n_atoms, atom_features, author_edges = _features.smile_to_graph(smiles)
    x = np.asarray(atom_features, dtype=np.float32)
    if x.shape != (n_atoms, 78):
        raise ValueError(f"unexpected author feature shape {x.shape}")
    edge_index = np.asarray(author_edges, dtype=np.int64).reshape(-1, 2).T.copy()
    target = _features.seq_cat(sequence).astype(np.int64)
    effective = sequence[:1000]
    audit = {
        "record_id": row["record_id"],
        "target_original_length": len(sequence),
        "target_effective_length": len(effective),
        "target_truncated": len(sequence) > 1000,
        "target_coverage": len(effective) / len(sequence),
        "target_full_sha256": _sha(sequence),
        "target_effective_sha256": _sha(effective),
        "target_encoded_sha256": hashlib.sha256(target.tobytes()).hexdigest(),
        "smiles_sha256": _sha(smiles),
        "molecule_atoms_original": mol.GetNumAtoms(),
        "molecule_atoms_effective": n_atoms,
        "molecule_truncated": False,
        "directed_edges": edge_index.shape[1],
        "graph_feature_sha256": hashlib.sha256(x.tobytes() + edge_index.tobytes()).hexdigest(),
        "atom_chirality_encoded": False,
        "bond_order_encoded": False,
    }
    return {"record_id": row["record_id"], "x": x, "edge_index": edge_index,
            "target": target, "y": np.float32(row["pKd"]), "audit": audit}


def collate(items):
    graphs = [Data(x=torch.as_tensor(item["x"], dtype=torch.float32),
                   edge_index=torch.as_tensor(item["edge_index"], dtype=torch.long),
                   target=torch.as_tensor(item["target"], dtype=torch.long).reshape(1, 1000),
                   y=torch.as_tensor([item["y"]], dtype=torch.float32),
                   record_id=item["record_id"])
              for item in items]
    return Batch.from_data_list(graphs)


def build_model(method_id, config=None):
    if method_id not in METHOD_IDS:
        raise ValueError(f"unsupported method {method_id!r}")
    # Training hyperparameters (LR, batch size, epoch count) belong to the common
    # runner; keep all author architecture defaults here, including dropout 0.2.
    model = _gin.GINConvNet() if method_id == "GraphDTA-GIN" else _gen.GEN()
    model.method_id = method_id
    return model


def predict(model, batch, device):
    return model(batch.to(device)).reshape(-1)


def batch_targets(batch):
    return batch.y.reshape(-1)


def method_metadata(method_id):
    model = build_model(method_id)
    return {"method_id": method_id,
            "parameter_count": sum(p.numel() for p in model.parameters()),
            "atom_feature_dim": 78,
            "target_alphabet": _features.seq_voc,
            "target_token_length": 1000,
            "target_view": "author first-1000-residue prefix; every record carries coverage and hashes",
            "molecule_atom_cap": None,
            "atom_feature_normalization": "per atom feature / sum(feature), original author",
            "pooling": "global_add_pool (both methods; DeepNC misleading source comment says max)",
            "chirality_encoded": False, "bond_order_encoded": False,
            "stereochemistry_limitation": "D/L stereoisomers can have identical input graphs; no novel features added",
            "pretraining": False,
            "architecture_defaults_preserved": True,
            "default_dropout": 0.2,
            "constructor_patch": "undefined GEN_Conv -> GEN" if method_id == "DeepNC-GEN" else None}
