"""Ordinary differentiable RoFormer + frozen ESM-vector regression adapter."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import torch
from torch import nn

ROOT = Path(__file__).resolve().parents[2]
METHOD = ROOT / "methods/chemical-encoders-20261025-v3-peptideclm2025-spefix"
TOKENIZER_DIR = ROOT / "methods/chemical-encoders-20261024-v1/sources/PeptideCLM/tokenizer"
SAFE_HELPER_SHA = "900827f3778996544572360606c7303deaedcce4964faeba01b57b97cf109807"
NN_MANIFEST_SHA = "c1541420d34a09a642d3390011a3e4419b011ad01cb5a77e65e2b6a743a0f914"
FIXED_NAME = "encoder.embed_positions.weight"
FIXED_TYPE = "transformers.models.roformer.modeling_roformer.RoFormerSinusoidalPositionalEmbedding"
FIXED_SHAPE = (768, 64)
EXPECTED_IDENTITY = {
    "model": "aaronfeller/PeptideCLM-23M-all",
    "revision": "a0847d8231d236645a2c4f629590118716c6fdda",
    "weights_sha256": "b0c76524025a560bc429f50591dbf5555f638a977dcf79a55f52965ddec88669",
    "pooling": "adapted_masked_mean_including_cls_sep",
    "embedding_dimension": 768, "max_tokens_including_special": 768,
    "pretrained_corpus_test_entity_exposure": "unknown",
    "input_adapter": "peptideclm2025_spe_cccc_to_cc_cc_v1",
    "input_adapter_sha256": "18c93586978208d2772f9bc249066c9ecce6dfe58558bebca2f08d9502bc7bd2",
    "input_adapter_recipe_sha256": "0fe967597586337d3684c6c9de95560e70df1ea1efcd44a8db6f55870808e0d2",
    "source_manifest_sha256": NN_MANIFEST_SHA,
    "original_safe_loader_sha256": "2205c3f2de478f72a58f01fc16352ee86a372b792c5a563ce40dec3e972c1688",
    "actual_metadata_coverage_sha256": "55a3082b0b1fdd416db2724cbf1e9d37d0622de94146e1e2afa095c3224eb82d",
    "tokenizer_identity": "project_SPE_output_adapter_not_author_native",
}
COUNTS = {"encoder_total": 43029504, "encoder_learnable": 42980352,
          "native_fixed_sinusoidal": 49152, "head": 279041,
          "total": 43308545, "trainable": 43259393}


def sha(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def import_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def safe_helper():
    path = METHOD / "load_peptideclm2025_spefix.py"
    if sha(path) != SAFE_HELPER_SHA:
        raise ValueError("Reviewed2025 safe helper changed")
    helper = import_path("reviewed2025_fullfine_safe_helper", path)
    if helper.source_identity() != NN_MANIFEST_SHA:
        raise ValueError("The frozen SPEfix source identity changed")
    return helper


def restore_native_fixed_position_table(encoder):
    """Unfreeze learnable backbone; whitelist only the exact official fixed table."""
    encoder.requires_grad_(True)
    module = dict(encoder.named_modules()).get("encoder.embed_positions")
    if module is None or module.__class__.__module__ + "." + module.__class__.__name__ != FIXED_TYPE:
        raise ValueError("Unexpected fixed-position module type")
    parameters = dict(encoder.named_parameters())
    weight = parameters.get(FIXED_NAME)
    if weight is not module.weight or tuple(weight.shape) != FIXED_SHAPE:
        raise ValueError("Unexpected fixed-position full parameter name or shape")
    weight.requires_grad_(False)
    frozen = {name for name, parameter in encoder.named_parameters() if not parameter.requires_grad}
    if frozen != {FIXED_NAME}:
        raise ValueError("Unapproved encoder parameters remain frozen")


class PairRegressor(nn.Module):
    def __init__(self, encoder):
        super().__init__()
        self.encoder = encoder
        restore_native_fixed_position_table(self.encoder)
        self.head = nn.Sequential(nn.Linear(1088, 256), nn.ReLU(), nn.Dropout(0.1), nn.Linear(256, 1))

    def encode_chemical(self, ids, mask):
        # This path is differentiable: do not call original inference_mode pooled_features.
        hidden = self.encoder(input_ids=ids, attention_mask=mask, return_dict=True).last_hidden_state
        weights = mask.unsqueeze(-1).to(hidden.dtype)
        return (hidden * weights).sum(1) / weights.sum(1).clamp(min=1)

    def forward(self, ids, mask, protein):
        chemical = self.encode_chemical(ids, mask)
        if chemical.shape[-1] != 768 or protein.shape[-1] != 320 or protein.requires_grad:
            raise ValueError("Expected differentiable768D chemistry and frozen320D ESM")
        return self.head(torch.cat((chemical, protein), dim=1)).squeeze(-1)


def load_pair_model(asset_root, identity, device):
    helper = safe_helper()
    _, encoder, actual = helper.load_encoder(asset_root, TOKENIZER_DIR)
    if actual != identity or actual != EXPECTED_IDENTITY:
        raise ValueError("Full encoder and cache use different chemistry/adapter identity")
    model = PairRegressor(encoder).to(device=device, dtype=torch.float32)
    counts = {"encoder_total": sum(p.numel() for p in model.encoder.parameters()),
              "encoder_learnable": sum(p.numel() for p in model.encoder.parameters() if p.requires_grad),
              "native_fixed_sinusoidal": sum(p.numel() for p in model.encoder.parameters() if not p.requires_grad),
              "head": sum(p.numel() for p in model.head.parameters()),
              "total": sum(p.numel() for p in model.parameters()),
              "trainable": sum(p.numel() for p in model.parameters() if p.requires_grad)}
    if counts != COUNTS:
        raise ValueError("Unexpected actual parameter counts: " + str(counts))
    return model


def prepare_tokenizer(asset_root, asset_receipt, identity):
    if Path(asset_receipt).resolve() != (Path(asset_root) / "ASSET-RECEIPT.actual.json").resolve():
        raise ValueError("The original2025 asset receipt must be used")
    helper = safe_helper()
    helper.verify(asset_root, TOKENIZER_DIR)
    if identity != EXPECTED_IDENTITY:
        raise ValueError("Full encoder and common-cohort cache identities differ")
    vendor = (Path(asset_root) / "vendor").resolve()
    sys.path.insert(0, str(vendor))
    import SmilesPE
    if not Path(SmilesPE.__file__).resolve().is_relative_to(vendor):
        raise ValueError("Unexpected tokenizer dependency")
    author = import_path("reviewed2025_fullfine_author_tokenizer", TOKENIZER_DIR / "my_tokenizers.py")
    tokenizer = author.SMILES_SPE_Tokenizer(str(TOKENIZER_DIR / "new_vocab.txt"),
                                          str(TOKENIZER_DIR / "new_splits.txt"), model_max_length=768)
    adapter = import_path("reviewed2025_fullfine_spefix", METHOD / "spefix_adapter.py")
    adapter.patch_tokenizer(tokenizer)
    return tokenizer, dict(identity)


def tokenize_safely(tokenizer, smiles):
    return safe_helper().tokenize_full(tokenizer, smiles)


def chemical_canary(model, tokenizer, device):
    original = ROOT / "methods/chemical-encoders-20261024-v1/peptideclm2025_worker.py"
    if sha(original) != "fa8b5060cc30dc5595d904e4d1c07f6a95a330619e2d7acc064c1994a04c850d":
        raise ValueError("Original fixed chemical fixtures changed")
    fixtures = import_path("reviewed2025_fullfine_canary_fixtures", original)
    encoded = {name: tokenize_safely(tokenizer, raw) for name, raw in fixtures.CANARIES.items()}
    length = max(len(x["input_ids"]) for x in encoded.values())
    ids = torch.zeros((len(encoded), length), dtype=torch.long, device=device)
    mask = torch.zeros_like(ids)
    for i, row in enumerate(encoded.values()):
        values = row["input_ids"]
        ids[i, :len(values)] = torch.tensor(values, device=device)
        mask[i, :len(values)] = 1
    model.eval()
    with torch.no_grad():
        values = model.encode_chemical(ids, mask)
        repeat = model.encode_chemical(ids, mask)
    if values.shape != (8, 768) or not torch.isfinite(values).all():
        raise ValueError("Invalid differentiable-pooling preflight output")
    difference = float((values - repeat).abs().max())
    if difference > 1e-7:
        raise ValueError("Preflight repeat changed")
    names = list(encoded)
    pairs = []
    for a, b in fixtures.PAIRS:
        delta = float((values[names.index(a)] - values[names.index(b)]).abs().max())
        if encoded[a]["input_ids"] == encoded[b]["input_ids"] or delta <= 1e-7:
            raise ValueError("Preflight lost chemical distinction")
        pairs.append({"a": a, "b": b, "max_abs_embedding_difference": delta})
    return {"schema": "peptideclm2025.fullfine-preflight-canary.v1", "status": "succeeded",
            "model_identity": EXPECTED_IDENTITY, "rows": 8, "dimensions": 768, "pairs": pairs,
            "repeat_max_abs_difference": difference, "pooling": EXPECTED_IDENTITY["pooling"],
            "scope": "Untrained differentiable pooling preflight; no affinity accuracy claim"}
