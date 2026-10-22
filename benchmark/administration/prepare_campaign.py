"""Prepare immutable administrative drafts; never run a model or freeze a contract.

The authoritative reproduction templates/validator remain under 复现/规范.
This tool only adds benchmark planning metadata and clones those templates.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import itertools
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ADMIN = Path(__file__).resolve().parent
WORKSPACE = ADMIN.parents[2]
STANDARD = WORKSPACE / "复现" / "规范"
SEEDS = list(range(10))


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def inside_admin(path):
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(ADMIN):
        raise ValueError("Output must stay inside this campaign administration directory")
    return resolved


def write_new(path, document):
    path = inside_admin(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(document, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def slug(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value):
        raise ValueError("Stable IDs must contain only letters, numbers, underscores, dots, hyphens")
    return value


def validate_plan(config):
    if config.get("seeds") != SEEDS:
        raise ValueError("This campaign requires exactly seeds 0 through 9 in order")
    for group, key in (("methods", "method_id"), ("splits", "split_id"), ("training_regimes", "regime_id")):
        ids = [slug(item[key]) for item in config.get(group, [])]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate " + group + " IDs")
    methods = config.get("methods", [])
    paper_ids = [m.get("paper_identity_key") for m in methods]
    actual_ids = [p for p in paper_ids if p]
    missing = []
    if len(set(actual_ids)) < 5:
        missing.append("At least five distinct verified predecessor papers are required; adapters/heads/seeds do not count as papers")
    if not config.get("splits"):
        missing.append("No frozen split identity is registered yet")
    if not config.get("training_regimes"):
        missing.append("No training regime is registered yet")
    for method in methods:
        for key in ("task_id", "paper_identity_key", "identity", "prior_run_ids", "timing", "code", "input_encoding_audit"):
            if key not in method:
                missing.append(method["method_id"] + ": missing " + key)
        if method.get("input_encoding_audit", {}).get("status") != "verified":
            missing.append(method["method_id"] + ": noncanonical input handling is not yet verified")
    return missing


def build_contract(config, method, split, regime, seed, run_id, created_at):
    contract = read(STANDARD / "task-contract.template.json")
    contract.update(task_id=method.get("task_id"), run_id=run_id, created_at=created_at)
    # Drafts must remain explicitly non-executable, even if the supplied config is complete.
    contract.update(is_template=True, contract_status="draft", frozen_at=None)
    contract["identity"] = copy.deepcopy(method.get("identity", contract["identity"]))
    scope = contract["execution_scope"]
    scope.update(
        objective="PPIKB noncanonical peptide–protein Kd benchmark with standard-residue controls; stratified non-natural/PTM evaluation",
        authorization_reference=config.get("authorization_reference"),
        relation_to_prior_run=method.get("relation_to_prior_run"),
        prior_run_ids=method.get("prior_run_ids", []),
        intended_level="training", scope_coverage="partial_subset",
        excluded_claims=["No novel model", "No claim to reproduce original paper tables on the changed dataset", "No PepLand or PepLand-derived binding input"],
    )
    scope["restriction_check"] = copy.deepcopy(method.get("restriction_check", scope["restriction_check"]))
    contract["timing"].update(copy.deepcopy(method.get("timing", {})))
    # This same method timing is copied to every split/seed. Never manufacture a new clock.
    contract["timing"]["retry_resets_clock"] = False
    contract["assets"]["datasets"] = copy.deepcopy(split.get("datasets", contract["assets"]["datasets"]))
    contract["assets"]["code"] = copy.deepcopy(method.get("code", contract["assets"]["code"]))
    contract["assets"]["models"] = copy.deepcopy(method.get("models", contract["assets"]["models"]))
    contract["targets"] = copy.deepcopy(split.get("contract_targets", config.get("targets", contract["targets"])))
    contract["environment"].update(copy.deepcopy(method.get("environment", {})))
    contract["resources"].update(copy.deepcopy(method.get("resources", {})))
    contract["execution"].update(copy.deepcopy(method.get("execution", {})))
    contract["execution"].update(seeds=[seed], seed_policy="One model-fit seed per run; frozen split and all hyperparameter-search candidates retained; seeds 0–9 all reported")
    contract["benchmark_metadata"] = {
        "schema": "peptide-binding.nc-benchmark.plan.v1",
        "method_id": method["method_id"], "split_id": split["split_id"],
        "regime_id": regime["regime_id"], "seed": seed,
        "training_regime": copy.deepcopy(regime),
        "input_encoding_audit": copy.deepcopy(method.get("input_encoding_audit", {})),
        "evaluation_strata": config.get("evaluation_strata", []),
        "test_used_for_selection": False,
        "external_used_for_selection": False,
    }
    return contract


def prepare(config_path, output_path):
    config = read(config_path)
    gaps = validate_plan(config)
    output_path = inside_admin(output_path)
    if output_path.exists():
        raise FileExistsError("Use a new draft revision; existing administrative evidence is immutable")
    output_path.mkdir(parents=True)
    created_at = now()
    sources = [Path(__file__), Path(config_path), STANDARD / "task-contract.template.json", STANDARD / "result-record.template.json", STANDARD / "validate_reproduction.py"]
    matrix = []
    for method, split, regime, seed in itertools.product(config.get("methods", []), config.get("splits", []), config.get("training_regimes", []), SEEDS):
        run_id = "__".join([method["method_id"], split["split_id"], regime["regime_id"], f"seed{seed:02d}"])
        directory = output_path / run_id
        contract = build_contract(config, method, split, regime, seed, run_id, created_at)
        write_new(directory / "task-contract.draft.json", contract)
        result = read(STANDARD / "result-record.template.json")
        result.update(task_id=method.get("task_id"), run_id=run_id)
        result["benchmark_metadata"] = copy.deepcopy(contract["benchmark_metadata"])
        # Binding is intentionally absent: there is no frozen or executed contract yet.
        write_new(directory / "result-record.template.json", result)
        matrix.append({"run_id": run_id, "method_id": method["method_id"], "paper_identity_key": method.get("paper_identity_key"), "split_id": split["split_id"], "regime_id": regime["regime_id"], "seed": seed, "status": "not_run", "contract_draft_path": str(directory / "task-contract.draft.json"), "execution_receipt_path": None, "metrics_path": None})
    index = {
        "schema": "peptide-binding.nc-benchmark.administration.v1", "created_at": created_at,
        "status": "draft_only", "executable": False, "actual_runs": 0,
        "source_config_path": str(Path(config_path).resolve()),
        "source_config_sha256": sha(config_path),
        "sources": [{"path": str(p.resolve()), "sha256": sha(p)} for p in sources],
        "method_count": len(config.get("methods", [])),
        "verified_distinct_paper_count": len({m.get("paper_identity_key") for m in config.get("methods", []) if m.get("paper_identity_key")}),
        "planned_run_rows": len(matrix), "readiness_gaps": gaps,
        "runs": matrix,
        "freeze_gate": "Root must fill real facts and obtain valid_for_execution=true from the authoritative validator immediately before launch. This tool never freezes, executes, or registers a batch.",
    }
    write_new(output_path / "draft-index.json", index)
    return index


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    index = prepare(args.config, args.out)
    print(json.dumps({key: index[key] for key in ("status", "executable", "actual_runs", "method_count", "planned_run_rows", "readiness_gaps")}, ensure_ascii=False))
