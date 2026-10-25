"""Explicit SPE-output adapter around the unchanged restricted 2025 loader."""
import hashlib
import importlib.util
import json
from pathlib import Path

ORIGINAL_LOADER_SHA = "2205c3f2de478f72a58f01fc16352ee86a372b792c5a563ce40dec3e972c1688"
ADAPTER_SHA = "18c93586978208d2772f9bc249066c9ecce6dfe58558bebca2f08d9502bc7bd2"
RECIPE_SHA = "0fe967597586337d3684c6c9de95560e70df1ea1efcd44a8db6f55870808e0d2"
METADATA_SHA = "55a3082b0b1fdd416db2724cbf1e9d37d0622de94146e1e2afa095c3224eb82d"
HERE = Path(__file__).resolve().parent
_BASE = None


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _import(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_identity():
    path = HERE / "NN-SOURCE-MANIFEST.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest["schema"] == "peptideclm2025.spefix-nn-source.v1"
    expected = {"extract_cpu_spefix.py", "load_peptideclm2025_spefix.py", "spefix_adapter.py", "recipe.json"}
    assert {row["name"] for row in manifest["files"]} == expected
    assert len(manifest["files"]) == len(expected)
    for row in manifest["files"]:
        file = HERE / row["name"]
        assert file.stat().st_size == row["bytes"] and sha(file) == row["sha256"], "NN source changed"
    assert sha(HERE / "spefix_adapter.py") == ADAPTER_SHA
    assert sha(HERE / "recipe.json") == RECIPE_SHA
    return sha(path)


def _original():
    global _BASE
    if _BASE is None:
        path = HERE.parent / "chemical-encoders-20261024-v1/load_peptideclm2025.py"
        assert sha(path) == ORIGINAL_LOADER_SHA
        _BASE = _import("unchanged_reviewed_2205_safe_loader", path)
    return _BASE


def verify(asset_root, tokenizer_dir):
    source_identity()
    return _original().verify(asset_root, tokenizer_dir)


def load_encoder(asset_root, tokenizer_dir):
    manifest_sha = source_identity()
    # Original helper performs weights_only=True, strict state_dict loading and asset SHA checks.
    tokenizer, encoder, identity = _original().load_encoder(asset_root, tokenizer_dir)
    adapter = _import("reviewed_2025_spe_cccc_adapter", HERE / "spefix_adapter.py")
    adapter.patch_tokenizer(tokenizer)
    identity = dict(identity, input_adapter=adapter.NAME, input_adapter_sha256=ADAPTER_SHA,
                    input_adapter_recipe_sha256=RECIPE_SHA, source_manifest_sha256=manifest_sha,
                    original_safe_loader_sha256=ORIGINAL_LOADER_SHA,
                    actual_metadata_coverage_sha256=METADATA_SHA,
                    tokenizer_identity="project_SPE_output_adapter_not_author_native")
    return tokenizer, encoder, identity


def tokenize_full(tokenizer, smiles):
    # Raw-string reconstruction, no UNK and 768 limit remain the original scientific gate.
    return _original().tokenize_full(tokenizer, smiles)


def pooled_features(encoder, input_ids, attention_mask):
    # Unchanged adapted masked mean; PAD excluded, CLS/SEP included.
    return _original().pooled_features(encoder, input_ids, attention_mask)
