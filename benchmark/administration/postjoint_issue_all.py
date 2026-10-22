"""Future root-only240-stage metadata issuer. Never launch a pool or load models.

Current preparation/synthetic tests do not invoke issue(). Real selected JSON is
read only after actual root authorizations and the fullNN200/RF40 joint proof.
All scientific payloads remain unopened; actual byte audits are root certificates.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import prepare_campaign as pc

BASE = Path(__file__).resolve().parent
PROJECT = BASE.parent
WSL = "/mnt/d/work/科研工作台/research-tasks/peptide-binding-nc-benchmark-20261021"
APPROVED_NN_INDEX = "c7b3bde68c9a741c0ac3f255a825e4a55dd7234e2b4e6d48f212fee8d5609ab1"
DEADLINE = "2026-10-22T01:45:00+00:00"
METHODS = {"GraphDTA-GIN", "MGraphDTA", "DGDTA-CL", "DeepNC-GEN", "GS-DTA"}
PANELS = {"source_peptide_dependency_cold", "target_reference_homology_cold"}


def local(value):
    value = str(value)
    return Path("D:/" + value[len("/mnt/d/"):]) if os.name == "nt" and value.startswith("/mnt/d/") else Path(value)


def wsl(value):
    file = Path(value).resolve()
    if os.name != "nt":
        return str(file)
    return WSL + "/" + str(file.relative_to(PROJECT)).replace("\\", "/")


def ref(value):
    supplied = value if isinstance(value, dict) else {"path": str(value)}
    path = local(supplied["path"])
    if path.suffix.lower() != ".json" or any(token in path.name.lower() for token in ("gold", "predictions")):
        raise PermissionError("Issuer only reads approved JSON metadata, never scientific payloads")
    actual = pc.sha(path)
    if supplied.get("sha256") is not None and supplied["sha256"] != actual:
        raise ValueError("Metadata digest differs: " + str(path))
    return {"path": wsl(path), "sha256": actual}


def read_ref(value):
    actual = ref(value)
    return pc.read(local(actual["path"])), actual


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def check_joint(joint, nn, rf, audit, references):
    if joint.get("status") != "all_200_NN_plus_40_RF_frozen" or (joint.get("NN_selections"), joint.get("RF_selections"), joint.get("NN_candidate_fits"), joint.get("RF_candidate_fits")) != (200, 40, 400, 80):
        raise ValueError("Actual fullNN200+RF40 joint barrier required")
    if nn.get("status") != "all_selections_frozen" or (nn.get("selection_count"), nn.get("candidate_fit_count")) != (200, 400) or len(nn.get("selections", [])) != 200:
        raise ValueError("Actual originalNN200/400 barrier incomplete")
    if rf.get("status") != "all_40_RF_selections_frozen" or (rf.get("selection_count"), rf.get("candidate_fit_count")) != (40, 80) or len(rf.get("selections", [])) != 40:
        raise ValueError("Actual auxiliaryRF40/80 barrier incomplete")
    if nn.get("execution_index_sha256") != APPROVED_NN_INDEX or joint.get("NN_execution_index_sha256") != APPROVED_NN_INDEX:
        raise ValueError("Joint gate does not bind approved recovery-awareNNv5 index")
    for name in ("NN", "RF"):
        if joint.get(name + "_barrier_sha256") != references[name + "_barrier"]["sha256"]:
            raise ValueError("Joint linked barrier hash mismatch")
    if audit.get("status") != "all_200_selections_and_checkpoints_verified" or len(audit.get("selections", [])) != 200 or audit.get("barrier_sha256") != references["NN_barrier"]["sha256"] or audit.get("execution_index_sha256") != APPROVED_NN_INDEX:
        raise ValueError("Authorized root fullNN checkpoint-byte audit missing/mismatched")


def candidate_grid(identities, rf=False):
    identities = list(identities)
    expected = {(p, r, s) for p in PANELS for r in ("NC_only", "standard_only") for s in range(10)}
    if not rf:
        expected = {(m, *cell) for m in METHODS for cell in expected}
    if len(identities) != len(expected) or set(identities) != expected:
        raise ValueError("Duplicate/incomplete exact200 or40 selected coordinate grid")


def binding_from_contract(contract, record, template, family, launcher_hashes):
    binding = copy.deepcopy(template)
    binding.update(issued=True, unit_id=contract["run_id"], deadline=DEADLINE, central_contract={"path": wsl(record["contract_path"]), "sha256": record["contract_sha256"]}, validation={"path": wsl(record["validation_path"]), "sha256": record["validation_sha256"]})
    if family == "NN":
        stage = contract["evaluation_stage"]
        binding.update(selection=stage["selection"], score_specs=[row["score_spec"] for row in stage["datasets"]], authorization=stage["root_score_authorization"], barrier=stage["root_barrier"], audit=stage["root_barrier_audit"], code_files=stage["code_files"], score_root=stage["score_root"], receipt_root=WSL + "/control/scoring-launch-v1/receipts/" + contract["run_id"], entrypoint_sha256=launcher_hashes["score_unit.py"], pool_sha256=launcher_hashes["score_pool.py"], common_sha256=launcher_hashes["score_common.py"])
    else:
        stage = contract["rf_score_execution_stage"]
        binding.update(copy.deepcopy(stage))
        binding.update(entrypoint_sha256=launcher_hashes["rf_score_unit.py"], pool_sha256=launcher_hashes["rf_score_pool.py"], common_sha256=launcher_hashes["rfs_common.py"])
    return binding


def issue(inputs, output):
    if inputs.get("root_postjoint_metadata_issuance_authorized") is not True:
        raise PermissionError("No current root issuance authority; examples and synthetic prep never issue")
    if os.name != "nt":
        raise RuntimeError("Use WindowsPython311 administrative issuer; actual pools use existingWSLPython. Immutable metadata only, no live progress reads.")
    if (datetime.fromisoformat(DEADLINE) - datetime.now(timezone.utc)).total_seconds() <= 1800:
        raise TimeoutError("Complete1800-second RF evaluation window cannot fit original global cutoff")
    # Root score permissions are read before any actual selected metadata.
    nn_auth, nn_auth_ref = read_ref(inputs["NN_score_authorization"])
    rf_auth, rf_auth_ref = read_ref(inputs["RF_score_authorization"])
    if nn_auth.get("root_scoring_authorized") is not True or "score" not in nn_auth.get("allowed_phases", []) or rf_auth.get("root_RF_holdout_score_authorized") is not True:
        raise PermissionError("Actual separately issued NN and RF score permissions required")
    nn, nn_ref = read_ref(inputs["NN_barrier"])
    rf, rf_ref = read_ref(inputs["RF_barrier"])
    joint, joint_ref = read_ref(inputs["joint_barrier"])
    audit, audit_ref = read_ref(inputs["NN_checkpoint_audit"])
    references = {"NN_barrier": nn_ref, "RF_barrier": rf_ref}
    check_joint(joint, nn, rf, audit, references)
    if nn_auth.get("barrier_sha256") != nn_ref["sha256"] or nn_auth.get("barrier_audit_sha256") != audit_ref["sha256"] or nn_auth.get("joint_barrier_sha256") != joint_ref["sha256"]:
        raise ValueError("NN root score authorization must additionally pin actual joint barrier; no frozen scorer change needed")
    if rf_auth.get("joint_barrier_sha256") != joint_ref["sha256"]:
        raise ValueError("RF root score authorization pins a different joint barrier")
    output = pc.inside_admin(output)
    if output.exists():
        raise FileExistsError("Use a new administrative revision; never overwrite issued contracts/bindings")
    nn_plan = pc.read(BASE / "evaluation-plan-eligible-v5.prebarrier.json")
    rf_plan = pc.read(BASE / "rf-postjoint-plan.prebarrier-v1.json")
    nn_specs = {s["sha256"] for unit in nn_plan["units"].values() for s in unit["score_specs"]}
    if set(nn_auth.get("allowed_score_spec_sha256", [])) != nn_specs or len(nn_specs) != 30:
        raise ValueError("NN auth must whitelist exactly original30 shared specs")
    rf_spec_index = pc.read(PROJECT / "auxiliary-rf-baseline/score-specs-v1/score-spec-index.json")
    rf_specs = {entry["score_spec_sha256"] for entry in rf_spec_index["entries"]}
    if set(rf_auth.get("allowed_score_spec_sha256", [])) != rf_specs or len(rf_specs) != 6:
        raise ValueError("RF auth must whitelist exactly frozen6 specs")
    nn_by_path = {entry["path"]: entry for entry in nn["selections"]}
    audit_by_path = {entry["path"]: entry for entry in audit["selections"]}
    rf_by_path = {entry["selection_path"]: entry for entry in rf["selections"]}
    expected_nn_paths = {unit["selection"]["path"] for unit in nn_plan["units"].values()}
    expected_rf_paths = {unit["selection"]["path"] for unit in rf_plan["units"].values()}
    if len(nn_by_path) != 200 or len(audit_by_path) != 200 or set(nn_by_path) != expected_nn_paths or set(audit_by_path) != expected_nn_paths or len(rf_by_path) != 40 or set(rf_by_path) != expected_rf_paths:
        raise ValueError("Full certified metadata path sets must match eligible199+recovery andRF40 before any selected metadata read")
    nn_ids, rf_ids = [], []
    for unit in nn_plan["units"].values():
        selection_ref = unit["selection"]
        source = nn_by_path.get(selection_ref["path"])
        certificate = audit_by_path.get(selection_ref["path"])
        if not source or not certificate or source["sha256"] != certificate["sha256"]:
            raise ValueError("NN selected path missing from exact full audit")
        selected, actual_ref = read_ref({"path": source["path"], "sha256": source["sha256"]})
        if selected.get("status") != "frozen" or selected.get("holdout_metrics_consulted") is not False or selected["checkpoint_sha256"] != certificate["checkpoint_sha256"]:
            raise ValueError("NN selected metadata does not match certified actual weights")
        nn_ids.append(tuple(selected[key] for key in ("method_id", "split_id", "regime", "seed")))
        unit.update(selection=actual_ref, checkpoint_path=selected["checkpoint"], checkpoint_sha256=selected["checkpoint_sha256"])
    for unit in rf_plan["units"].values():
        source = rf_by_path.get(unit["selection"]["path"])
        if not source:
            raise ValueError("RF selected path absent from actual40 barrier")
        selected, actual_ref = read_ref({"path": source["selection_path"], "sha256": source["selection_sha256"]})
        if selected.get("status") != "frozen" or selected.get("validation_only") is not True or selected.get("gold_reads") != 0 or selected["model_sha256"] != source["model_sha256"]:
            raise ValueError("RF selected metadata differs from root byte-verified certificate")
        rf_ids.append(tuple(selected[key] for key in ("panel", "regime", "seed")))
        unit.update(selection=actual_ref, model_path=selected["model_path"], model_sha256=selected["model_sha256"])
    candidate_grid(nn_ids)
    candidate_grid(rf_ids, rf=True)
    cpu, cpu_ref = read_ref(inputs["live_CPU_proof"])
    if cpu.get("hostname") != "cihebi" or not (cpu.get("observed_at") or cpu.get("at")):
        raise ValueError("Actual CPU identity/time proof missing")
    nn_plan.update(root_authorized_after_barrier=True, authorization=nn_auth_ref, barrier=nn_ref, barrier_audit=audit_ref, root_joint_barrier=joint_ref)
    rf_plan.update(root_postjoint_RF_scoring_authorized=True, authorization=rf_auth_ref, joint_barrier=joint_ref, NN_barrier=nn_ref, RF_barrier=rf_ref, live_cpu_proof=cpu_ref)
    for family, plan, subdir in (("NN", nn_plan, "scoring-launch-v1"), ("RF", rf_plan, "rf-score-launch-v1")):
        for uid in plan["units"]:
            if (PROJECT / "control" / subdir / "bindings" / (uid + "__evaluation_v1.json")).exists():
                raise FileExistsError("Postissue binding already exists; no overwrite/reissue")
        for source in plan["code_files"]:
            file = local(source["path"])
            if file.suffix not in (".py", ".json") or pc.sha(file) != source["sha256"]:
                raise ValueError("Fixed metadata/code proof changed")
    output.mkdir(parents=True)
    write_new(output / "NN-postjoint-plan.json", nn_plan)
    write_new(output / "RF-postjoint-plan.json", rf_plan)
    import prepare_evaluation_contracts
    import prepare_rf_score_contracts
    prepare_evaluation_contracts.generate(nn_plan, output / "NN200", issue=True)
    prepare_rf_score_contracts.generate(rf_plan, output / "RF40", issue=True)
    indices = {}
    for family, folder, index_name, common_name, unit_name, pool_name, freeze_name in (("NN", "scoring-launch-v1", "evaluation-contract-index.json", "score_common.py", "score_unit.py", "score_pool.py", "FROZEN-LAUNCHER-v1.json"), ("RF", "rf-score-launch-v1", "rf-score-contract-index.json", "rfs_common.py", "rf_score_unit.py", "rf_score_pool.py", "FROZEN-RF-SCORE-LAUNCHER-v1.json")):
        launcher = PROJECT / "control" / folder
        frozen = pc.read(launcher / freeze_name)
        source_hashes = frozen["source_sha256"]
        for name, expected in source_hashes.items():
            if pc.sha(launcher / name) != expected:
                raise ValueError("Actual score launcher mutated after freeze")
        stage_index = pc.read(output / ("NN200" if family == "NN" else "RF40") / index_name)
        template = pc.read(launcher / "binding.example.json")
        pool = pc.read(launcher / "index.example.json")
        pool.update(issued=True, supervisor_sha256=source_hashes[pool_name], unit_sha256=source_hashes[unit_name], common_sha256=source_hashes[common_name], units=[])
        for record in stage_index["records"]:
            contract = pc.read(record["contract_path"])
            binding = binding_from_contract(contract, record, template, family, source_hashes)
            binding_path = launcher / "bindings" / (record["run_id"] + ".json")
            write_new(binding_path, binding)
            pool["units"].append({"unit_id": record["run_id"], "binding": {"path": wsl(binding_path), "sha256": pc.sha(binding_path)}})
        pool_path = output / (family + "-score-pool-index.json")
        write_new(pool_path, pool)
        indices[family] = {"path": str(pool_path), "sha256": pc.sha(pool_path), "stage_contract_index": str(output / ("NN200" if family == "NN" else "RF40") / index_name), "CLI": [pool["python"], wsl(launcher / pool_name), "--index", wsl(pool_path), "--index-sha256", pc.sha(pool_path)], "required_environment": {"PYTHONPATH": pool["PYTHONPATH"], "CUDA_VISIBLE_DEVICES": pool.get("gpu_uuid", "")}}
    result = {"schema": "postjoint-240-stage-issuance.v1", "created_at": pc.now(), "root_input_metadata": copy.deepcopy(inputs), "NN_barrier": nn_ref, "RF_barrier": rf_ref, "joint_barrier": joint_ref, "NN_checkpoint_audit": audit_ref, "pools": indices, "stage_contracts": {"NN": 200, "RF": 40}, "postissue_bindings": 240, "future_producer_receipts": {"NN": 600, "RF": 120}, "models_or_scores_launched_by_issuer": 0, "raw_gold_model_prediction_array_bytes_read": 0, "actual_selected_metadata_files_checked_after_permission": 240, "historical_failed_NN_attempt_preserved": True}
    write_new(output / "POSTJOINT-ISSUANCE.json", result)
    print(json.dumps({"NN_index": indices["NN"]["sha256"], "RF_index": indices["RF"]["sha256"], "contracts": 240, "bindings": 240, "processes_launched": 0}))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    issue(pc.read(args.inputs), args.out)
