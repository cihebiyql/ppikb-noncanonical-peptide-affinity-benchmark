"""Audit all prepared draft contracts with the unchanged authoritative validator."""
import importlib.util
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import prepare_campaign as pc

BASE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("authoritative_reproduction_validator", pc.STANDARD / "validate_reproduction.py")
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)

if __name__ == "__main__":
    index_path = BASE / "drafts-current-facts-v1" / "draft-index.json"
    index = pc.read(index_path)
    seed_groups = defaultdict(list)
    errors = []
    valid_structure = 0
    accidental_execution = []
    for row in index["runs"]:
        path = Path(row["contract_draft_path"])
        contract = pc.read(path)
        report = validator.validate(contract, allow_template=True, check_files=True, contract_directory=path.parent)
        if report["valid"]:
            valid_structure += 1
        else:
            errors.append({"run_id": row["run_id"], "errors": report["errors"]})
        if report["valid_for_execution"]:
            accidental_execution.append(row["run_id"])
        seed_groups[(row["method_id"], row["split_id"], row["regime_id"])].append(row["seed"])
    report = {
        "at": datetime.now(timezone.utc).isoformat(), "authoritative_validator_path": str(pc.STANDARD / "validate_reproduction.py"), "authoritative_validator_sha256": pc.sha(pc.STANDARD / "validate_reproduction.py"),
        "index_path": str(index_path), "index_sha256": pc.sha(index_path),
        "drafts": len(index["runs"]), "valid_template_structures": valid_structure,
        "distinct_verified_paper_keys": len({row["paper_identity_key"] for row in index["runs"]}),
        "seed_groups": len(seed_groups), "all_groups_exact_ten_seeds": all(sorted(seeds) == pc.SEEDS for seeds in seed_groups.values()),
        "unique_run_ids": len({row["run_id"] for row in index["runs"]}),
        "accidental_execution_eligible_drafts": accidental_execution, "errors": errors,
        "actual_model_runs": 0,
        "scope": "Unchanged authoritative validator, template mode only; all unknown freeze/launch facts remain unknown. No model execution.",
    }
    pc.write_new(BASE / "current-facts-v1-verification.json", report)
    print(json.dumps({key: report[key] for key in ("drafts", "valid_template_structures", "distinct_verified_paper_keys", "all_groups_exact_ten_seeds", "actual_model_runs", "accidental_execution_eligible_drafts")}, ensure_ascii=False))
    raise SystemExit(0 if not errors and not accidental_execution and report["all_groups_exact_ten_seeds"] else 1)
