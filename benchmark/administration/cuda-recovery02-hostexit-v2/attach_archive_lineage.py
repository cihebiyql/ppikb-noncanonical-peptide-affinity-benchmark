"""Create a new copied result/index with explicit CUDA lineage; never overwrite."""
import argparse
import copy
import importlib.util
from pathlib import Path
import recovery as r


def local(path):
    value = str(path)
    if __import__("os").name == "nt" and value.startswith("/mnt/d/"): return Path("D:/" + value[len("/mnt/d/"):])
    return Path(value)


def attach(index_path, chain_path, output, authorized=False, root_accept=False):
    if authorized is not True: raise PermissionError("Explicit root final lineage archival authority required")
    source = r.read(index_path); chain = r.read(chain_path)
    if chain.get("scientific_unit_id") != r.UID or chain.get("extra_interrupted_attempts") != 2 or chain.get("valid_NN_fits") != 400 or chain.get("selected_NN_cells") != 200 or not chain.get("must_attach_to_final_standard_cell_result"): raise ValueError("Exact validated CUDA attempt-chain supplement required")
    output = local(output).resolve()
    if not output.is_relative_to(r.HERE.resolve()): raise ValueError("New owned archival output only")
    output.mkdir(exist_ok=False)
    changed = []
    for entry in source["records"]:
        contract = r.read(local(entry["contract"]["path"]))
        if contract["run_id"] != chain["evaluation_unit_id"]: continue
        if r.sha(local(entry["result"]["path"])) != entry["result"]["sha256"]: raise ValueError("Source standard result changed")
        result = r.read(local(entry["result"]["path"]))
        result.setdefault("stage_lineage", {})["cuda_recovery02"] = r.ref(chain_path)
        result.setdefault("differences", []).append({"category": "explicit_CUDA_unknown_error_same_namespace_retry", "description": "Original pool actual outer-tool exit1/199success1failed; native2 is inferred from frozen source and verified terminal, never directly observed and original candidate0CUDA unknown error are retained. Both failed output trees were atomically archived with complete path/SHA mapping before one explicit same-config same-path retry; retry pool exit0/200success0failed completed within original22:54:18.479676UTC ceiling. Two historical interrupted attempts remain separate from400 valid NN fits/200 cells.", "effect_on_comparison": "Identical spec/contract/seed/LR/epochs/scientific c7b3 index; no method/performance-based change or clock reset", "evidence_type": "source_fact", "evidence_paths": [str(chain_path)]})
        result.setdefault("artifacts", []).append({"role": "explicit_CUDA_attempt_chain", "path": str(chain_path), "location": "local", "available": True, "sha256": r.sha(chain_path), "notes": "Full original failure/archive/retry success lineage; required final scoped-cell supplement"})
        prior_review = copy.deepcopy(result.get("review"))
        if root_accept and (not prior_review or prior_review.get("status") != "accepted" or result.get("lifecycle_status") != "succeeded" or result.get("incomplete_reasons")):
            raise PermissionError("Lineage-only acceptance cannot replace the original full scoped-result review")
        result["review_before_CUDA_supplement"] = prior_review
        result["review"].update(status="accepted" if root_accept else "pending", reviewer="root explicit review of actual CUDA lineage supplement" if root_accept else None, reviewed_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat() if root_accept else None)
        path = output / "result-record.with-CUDA-lineage.json"; r.write(path, result)
        entry["result"] = r.ref(path); changed.append(contract["run_id"])
        validator = r.PROJECT.parent.parent / "复现/规范/validate_reproduction.py"
        spec = importlib.util.spec_from_file_location("central_CUDA_lineage_validator", validator)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        report = module.validate(contract, result, contract_bytes=local(entry["contract"]["path"]).read_bytes(), check_files=False)
        r.write(output / "central-validation.json", report)
        if not report["valid"] or (root_accept and not report["valid_for_acceptance"]): raise ValueError("Central result validation failed; retain copy and report, no adoption")
    if changed != [r.UID + "__evaluation_v1"]: raise ValueError("Exactly one actual affected standard evaluation cell must be augmented")
    source["cuda_lineage_supplement"] = r.ref(chain_path)
    source["source_standard_result_index"] = r.ref(index_path)
    source["root_reviewed_CUDA_supplement"] = root_accept
    r.write(output / "standard-result-index.with-CUDA-lineage.json", source)
    r.write(output / "ATTACHMENT-RECEIPT.json", {"source_index": r.ref(index_path), "chain": r.ref(chain_path), "new_index": r.ref(output / "standard-result-index.with-CUDA-lineage.json"), "changed_cells": changed, "actual_original_files_modified": 0, "root_acceptance_explicit": root_accept})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root-attach-final-lineage-authorized", action="store_true"); parser.add_argument("--root-review-accept-lineage", action="store_true")
    parser.add_argument("--index", required=True); parser.add_argument("--chain", required=True); parser.add_argument("--out", required=True)
    a = parser.parse_args(); attach(a.index, a.chain, a.out, a.root_attach_final_lineage_authorized, a.root_review_accept_lineage)
