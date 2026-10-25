"""Exact approved expanded-data identity; no model or framework imports."""
import hashlib
from pathlib import Path

MANIFEST_SHA = "93cdc000433e3c0babd7a5b7e183acd2fbe25649f4d2e7d5d95f5f0ad5aacae4"
CSV_SHA = "c3d8f4e42600f0c762bb9d2d24595a32c8f13de7a1f5018d59047d241dd8525a"
SPEC_SHA = "8b126e2c28f26e466b8efe0da6e8a12ba96842885e4864f5339a8b611efed74b"
PARENT_GLOBAL_SHA = "971a1feaafeae45e0e4f29092b80405419d8d47100b0a3e5e936c82ecc0e44c0"
MODEL_ADAPTER_SHA = "d935cd85f8009e8c243fb42550c24dbe08f22e55a77fe8efbc6d81f35052fc27"
FRAME_SPLITS = {"train": 531, "validation": 570, "test": 685, "external": 0}
DECLARED_SPLITS = {"fine_train": 531, "validation": 570, "test": 685}
REMOTE_MANIFEST = "/data/qlyu/projects/peptide-four-task-benchmark-20261022/runs/protein-cache-expanded-v3/attempt--20261024T234819/artifacts/cohort/frozen-manifest.json"
REMOTE_SPEC = "/data/qlyu/projects/peptide-four-task-benchmark-20261022/protocol/feature-specs-expanded-v3/attempt--20261024T234819/peptideclm2025-spefix-frozen-esm320-v3.json"
REMOTE_CSV = "/data/qlyu/projects/peptide-four-task-benchmark-20261022/runs/protein-cache-expanded-v3/attempt--20261024T234819/artifacts/cohort/ppikb_kd_target_global_firewall_v1.csv"


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def validate_hashes(manifest_sha, spec_sha, csv_sha, split_counts=None):
    if manifest_sha != MANIFEST_SHA:
        raise ValueError("Expanded case requires approved93cdc manifest, never original e2/963")
    if spec_sha != SPEC_SHA:
        raise ValueError("Expanded case requires approved8b126 spec and merged5206 protein cache")
    if csv_sha != CSV_SHA:
        raise ValueError("Expanded case requires c3d8 CSV, never original4f469")
    if split_counts is not None and split_counts != FRAME_SPLITS:
        raise ValueError("Expanded case requires531/570/685 with no external rows")


def validate_frozen_files(manifest_path, spec_path):
    validate_hashes(sha(manifest_path), sha(spec_path), CSV_SHA)


def validate_target_view(view, actual_csv_sha):
    validate_hashes(MANIFEST_SHA, SPEC_SHA, actual_csv_sha)
    if view.get("id") != "ppikb_kd_target_global_firewall_v1" or view.get("sha256") != CSV_SHA:
        raise ValueError("Wrong expanded target view or mixed old CSV")
    if view.get("split_counts") != DECLARED_SPLITS:
        raise ValueError("Expanded view declares the wrong role counts")


def validate_plan(plan):
    if plan.get("schema") != "peptideclm2025.expanded-fullfine-plan.v1":
        raise ValueError("Wrong expanded plan schema")
    dataset = plan["dataset"]
    validate_hashes(dataset["manifest_sha256"], dataset["feature_spec_sha256"], dataset["csv_sha256"], dataset["frame_split_counts"])
    if dataset["manifest_path"] != REMOTE_MANIFEST or dataset["feature_spec_path"] != REMOTE_SPEC or dataset["csv_path"] != REMOTE_CSV:
        raise ValueError("Plan paths must come from the approved builder artifact index")
    if plan.get("model_adapter_sha256") != MODEL_ADAPTER_SHA:
        raise ValueError("Expanded preparation must retain unchanged d935 model adapter")
    candidates = plan["candidates"]
    if len(candidates) != 20 or {(r["seed"], r["candidate"]) for r in candidates} != {(s, c) for s in range(10) for c in (0, 1)}:
        raise ValueError("Exactly one new20-candidate case required")
    for row in candidates:
        if row["learning_rate"] != (1e-5, 3e-5)[row["candidate"]]:
            raise ValueError("Unexpected learning-rate candidate")
        if row["manifest_path"] != REMOTE_MANIFEST or row["feature_spec_path"] != REMOTE_SPEC:
            raise ValueError("A candidate mixes original and expanded inputs")
    tests = plan["selected_tests"]
    if len(tests) != 10 or {r["seed"] for r in tests} != set(range(10)):
        raise ValueError("Exactly10 post-selection TEST runs required")
    if any(r["candidate_indices_required"] != [0, 1] or r["selection"] != "validation_mae_only" for r in tests):
        raise ValueError("Both candidates and validation-only selection required")
    expected = {"batch_size": 8, "max_epochs": 30, "patience": 5, "weight_decay": 0.01,
                "gradient_clip_norm": 1.0, "dtype": "float32", "tf32": False,
                "head": [1088, 256, 1], "dropout": 0.1, "max_tokens_including_special": 768}
    if plan["training_settings"] != expected:
        raise ValueError("Data-only adaptation cannot change the training algorithm")
    return True
