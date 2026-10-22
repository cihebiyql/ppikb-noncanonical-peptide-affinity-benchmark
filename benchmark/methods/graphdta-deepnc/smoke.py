"""Bounded synthetic-input CPU checks; never runs the full benchmark."""
import hashlib
import inspect
import json
import os
import pickle
import platform
import resource
import time
from pathlib import Path

import numpy as np
import rdkit
import torch
import torch_geometric
from torch_geometric.nn import GENConv

import adapter


def main():
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch.manual_seed(0)
    started = time.time()
    rows = [
        {"record_id": "smoke-chemical-a", "canonical_isomeric_smiles": "N[C@@H](C)C(=O)O", "target_sequence": "ACDEFGHIKLMNPQRSTVWY" * 63, "pKd": 5.0},
        {"record_id": "smoke-chemical-b", "peptide_smiles": "NCC(=O)O", "target_sequence": "YWVTSRQPNMLKIHGFEDCA" * 7, "pKd": 6.0},
    ]
    items = [adapter.encode_record(row) for row in rows]
    assert items[0]["audit"]["target_truncated"]
    assert items[0]["audit"]["target_effective_length"] == 1000
    assert not items[1]["audit"]["target_truncated"]
    assert pickle.loads(pickle.dumps(items))[0]["audit"] == items[0]["audit"]
    other_features = adapter._load("nc_deepnc_features_smoke", "deepnc_gen_features.py")
    for row, item in zip(rows, items):
        n, x, e = other_features.smile_to_graph(row.get("canonical_isomeric_smiles") or row["peptide_smiles"])
        assert n == len(item["x"])
        np.testing.assert_array_equal(np.asarray(x, np.float32), item["x"])
        np.testing.assert_array_equal(np.asarray(e, np.int64).reshape(-1, 2).T, item["edge_index"])
        np.testing.assert_array_equal(other_features.seq_cat(row["target_sequence"]), item["target"])
    # Show the known author-feature limitation rather than inventing a repair.
    stereo = dict(rows[0], record_id="smoke-stereo", canonical_isomeric_smiles="N[C@H](C)C(=O)O")
    stereo_item = adapter.encode_record(stereo)
    assert items[0]["audit"]["graph_feature_sha256"] == stereo_item["audit"]["graph_feature_sha256"]
    empty_edges = adapter.encode_record(dict(rows[0], record_id="smoke-isolated-atom", canonical_isomeric_smiles="[Na+]"))
    assert empty_edges["edge_index"].shape == (2, 0)
    long_molecule = adapter.encode_record(dict(rows[0], record_id="smoke-no-atom-cap", canonical_isomeric_smiles="C" * 600))
    assert long_molecule["audit"]["molecule_atoms_original"] == long_molecule["audit"]["molecule_atoms_effective"] == 600
    methods = []
    for method_id in adapter.METHOD_IDS:
        model = adapter.build_model(method_id, {})
        model.train()
        losses = []
        for size in (1, 2):
            model.zero_grad(set_to_none=True)
            batch = adapter.collate(items[:size])
            pred = adapter.predict(model, batch, "cpu")
            y = adapter.batch_targets(batch)
            assert pred.shape == y.shape == (size,)
            assert torch.isfinite(pred).all()
            loss = torch.nn.functional.mse_loss(pred, y)
            loss.backward()
            gradients = [p.grad for p in model.parameters() if p.grad is not None]
            assert gradients and all(torch.isfinite(g).all() for g in gradients)
            assert any(torch.count_nonzero(g).item() for g in gradients)
            losses.append(float(loss.detach()))
        model.eval()
        with torch.no_grad():
            forward = adapter.predict(model, adapter.collate(items), "cpu")
            reverse = adapter.predict(model, adapter.collate(items[::-1]), "cpu").flip(0)
            singles = torch.cat([adapter.predict(model, adapter.collate([item]), "cpu") for item in items])
        torch.testing.assert_close(forward, reverse, atol=1e-5, rtol=1e-5)
        torch.testing.assert_close(forward, singles, atol=1e-5, rtol=1e-5)
        metadata = adapter.method_metadata(method_id)
        metadata.update({"batch_sizes_forward_backward": [1, 2], "finite_gradients": True,
                         "batch_permutation_invariance": True,
                         "batch_partition_invariance": True,
                         "maximum_permutation_abs_error": float((forward - reverse).abs().max()),
                         "maximum_partition_abs_error": float((forward - singles).abs().max()),
                         "synthetic_mse_smoke_only": losses})
        if method_id == "DeepNC-GEN":
            metadata["GENConv_aggregators"] = [{"type": type(layer.aggr_module).__name__, "semi_grad": layer.aggr_module.semi_grad, "t": float(layer.aggr_module.t)} for layer in (model.conv1, model.conv2, model.conv3)]
            assert all(x["semi_grad"] for x in metadata["GENConv_aggregators"])
        methods.append(metadata)
    source = inspect.getsource(GENConv.__init__)
    Path("smoke-results.json").write_text(json.dumps({
        "scope": "CPU synthetic component smoke only, no benchmark training or performance estimate",
        "host": platform.node(), "torch": torch.__version__, "torch_geometric": torch_geometric.__version__,
        "rdkit": rdkit.__version__, "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "cpu_affinity": sorted(os.sched_getaffinity(0)), "torch_threads": torch.get_num_threads(),
        "elapsed_seconds": time.time() - started,
        "max_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "tests": {"pickle_CPU_roundtrip": True, "both_author_preprocessing_agree": True,
                  "target_truncation_audit": [x["audit"] for x in items],
                  "D_L_feature_collision_confirmed_limitation": True,
                  "empty_edge_graph_encoded": True, "600_atom_graph_uncapped": True},
        "pyg_GENConv_constructor_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "pyg_GENConv_softmax_sg_compatibility": "native semi_grad=True compatibility path; no model patch needed",
        "methods": methods}, indent=2) + "\n")


if __name__ == "__main__":
    main()
