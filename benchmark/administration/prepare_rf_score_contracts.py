"""Prepare/issue40 CPU RF post-joint evaluation contracts, never run scores.

Only metadata/code read; no selections, models, arrays, gold or predictions opened.
Root supplies actual post-joint model/selection references when issuing.
"""
import argparse
import copy
import importlib.util
import json
from pathlib import Path

import prepare_campaign as pc
from prepare_evaluation_contracts import metadata, targets

BASE = Path(__file__).resolve().parent
PROJECT = BASE.parent
RF = PROJECT / "auxiliary-rf-baseline"
WSL = "/mnt/d/work/科研工作台/research-tasks/peptide-binding-nc-benchmark-20261021"
SCORE_ROOT = WSL + "/auxiliary-rf-baseline/rf-scores-v1"


def generate(plan, out, issue=False):
    out = pc.inside_admin(out)
    if out.exists():
        raise FileExistsError("Preserve prior RF evaluation contracts and failures")
    joint = None
    if issue:
        if plan.get("root_postjoint_RF_scoring_authorized") is not True:
            raise PermissionError("RF postjoint authorization absent")
        auth = metadata(plan["authorization"])
        joint = metadata(plan["joint_barrier"])
        if auth.get("root_RF_holdout_score_authorized") is not True or auth["joint_barrier_sha256"] != plan["joint_barrier"]["sha256"]:
            raise PermissionError("Wrong root RF scoring authorization")
        if joint.get("status") != "all_200_NN_plus_40_RF_frozen" or (joint.get("NN_selections"), joint.get("RF_selections")) != (200, 40):
            raise ValueError("Actual NN200+RF40 joint gate missing")
        nn, rf = metadata(plan["NN_barrier"]), metadata(plan["RF_barrier"])
        if nn.get("selection_count") != 200 or rf.get("selection_count") != 40:
            raise ValueError("Actual linked barrier counts differ")
        for source in plan["code_files"]:
            file = Path(str(source["path"]).replace("/mnt/d/", "D:/", 1))
            if file.suffix not in (".py", ".json") or "gold" in file.name.lower() or "prediction" in file.name.lower():
                raise ValueError("Code proof must not open scientific data")
            if pc.sha(file) != source["sha256"]:
                raise ValueError("RF scorer code changed after root freeze")
        normalized = {str(source["path"]).replace("\\", "/") for source in plan["code_files"]}
        required = ["/control/rf-score-launch-v1/" + name for name in ("rfs_common.py", "rf_score_unit.py", "rf_score_pool.py")] + ["/control/rf-launch-v1/rf_common.py", "/launch/common.py", "/evaluation/metrics_stable.py"] + ["/auxiliary-rf-baseline/" + name for name in ("features.py", "common.py", "rf_runner.py", "rf_score.py", "feature-spec-v1.json", "protocol-v1.json", "installed-assets-v1.json", "installed-binaries-v1.json")]
        if any(not any(path.endswith(suffix) for path in normalized) for suffix in required):
            raise ValueError("Frozen actual RF postjoint launcher/worker/metrics proof incomplete")
    out.mkdir(parents=True)
    source_index = BASE / "rf-classic-ready-v2" / "issued" / "freeze-index.json"
    training = pc.read(source_index)
    nn_training = pc.read(BASE / "issued-gpu-v4" / "freeze-index.json")
    anchor = {(r["split_id"], r["regime_id"], r["seed"]): r for r in nn_training["records"] if r["method_id"] == "GraphDTA-GIN"}
    spec_index_path = RF / "score-specs-v1" / "score-spec-index.json"
    entries = pc.read(spec_index_path)["entries"]
    by_spec = {(entry["panel"], entry["dataset_id"]): entry for entry in entries}
    validator_spec = importlib.util.spec_from_file_location("central_reproduction_validator", pc.STANDARD / "validate_reproduction.py")
    validator = importlib.util.module_from_spec(validator_spec)
    validator_spec.loader.exec_module(validator)
    records, total_rows = [], 0
    for old in training["records"]:
        parent = pc.read(old["contract_path"])
        cell = (old["split_id"], old["regime_id"], old["seed"])
        neural = pc.read(anchor[cell]["contract_path"])
        uid = old["run_id"] + "__evaluation_v1"
        own = plan.get("units", {}).get(old["run_id"], {})
        contract = pc.read(pc.STANDARD / "task-contract.template.json")
        contract.update(task_id=parent["task_id"], run_id=uid, is_template=not issue, contract_status="frozen" if issue else "draft", created_at=pc.now(), frozen_at=pc.now() if issue else None)
        for name in ("identity", "timing", "environment", "resources"):
            contract[name] = copy.deepcopy(parent[name])
        contract["execution_scope"] = copy.deepcopy(parent["execution_scope"])
        contract["execution_scope"].update(objective="Post-joint fixed selected RF inference on internal test, external75 and separate supplement13; CPU only; no fitting/selection/parameter updates", intended_level="independent_inference", prior_run_ids=[parent["run_id"]], relation_to_prior_run="RF evaluation stage of same non-paper auxiliary reference; original RF training/raw exit logs retained and global clock unchanged")
        contract["assets"]["code"] = copy.deepcopy(parent["assets"]["code"])
        certified = False
        if issue and own.get("model_path") and own.get("model_sha256"):
            matched = [entry for entry in joint["RF_selection_entries"] if (entry["panel"], entry["regime"], entry["seed"]) == cell]
            if len(matched) != 1 or matched[0]["model_sha256"] != own["model_sha256"] or matched[0]["selection_sha256"] != own["selection"]["sha256"]:
                raise ValueError("RF root-byte-audited model reference differs")
            certified = True
        contract["assets"]["models"] = [{"name": "Same validation-selected classical RF estimator", "version": "No refit or parameter update", "path": own.get("model_path") if certified else None, "sha256": own.get("model_sha256"), "location": "remote", "integrity": "complete" if certified else "partial", "notes": "Actual selected model/path/SHA is certified by root's actual joint RF40 byte audit; this metadata generator does not open estimator bytes." if certified else "Postjoint selected-model metadata is not populated yet; no claim that trained models are missing."}]
        internal_data = "source_test" if old["split_id"] == "source_peptide_dependency_cold" else "target_test"
        internal_n = next(t["denominator"] for t in neural["targets"] if t["target_id"] == "all:MAE")
        refs, datasets = [], []
        for role, data, count in (("internal", internal_data, internal_n), ("external75", "external75", 75), ("supplement13", "supplement13", 13)):
            entry = by_spec[(old["split_id"], data)]
            ref = {"path": entry["score_spec_path"], "sha256": entry["score_spec_sha256"]}
            spec = metadata(ref)
            if spec["panel"] != old["split_id"] or spec["dataset_id"] != data or spec["output_root"] != SCORE_ROOT:
                raise ValueError("Frozen RF scoring dataset/panel/root differs")
            refs.append(ref)
            datasets.append({"role": role, "dataset_id": data, "n": count, "score_spec": ref})
            total_rows += count
        contract["assets"]["datasets"] = [{"name": row["role"], "path": row["score_spec"]["path"], "sha256": row["score_spec"]["sha256"], "manifest_sha256": row["score_spec"]["sha256"], "sample_count": row["n"], "statistical_unit": "held-out measurement record", "integrity": "complete", "notes": "Frozen metadata spec only; actual gold/array/model bytes first read by authorized worker under joint gate and blind-before-gold protocol."} for row in datasets]
        contract["targets"] = targets(neural)
        for target in contract["targets"]:
            target["paper_endpoint"] = "Generic auxiliary RF postjoint holdout comparison; not a GraphDTA author-paper endpoint"
            target["tolerance"]["reason"] = "Additional classical reference on new common data; not a published-paper numerical reproduction"
        contract["benchmark_metadata"] = copy.deepcopy(parent["benchmark_metadata"])
        stage = {"selection": own.get("selection"), "score_specs": refs, "authorization": plan.get("authorization"), "joint_barrier": plan.get("joint_barrier"), "NN_barrier": plan.get("NN_barrier"), "RF_barrier": plan.get("RF_barrier"), "live_cpu_proof": plan.get("live_cpu_proof"), "worker": {"path": WSL + "/auxiliary-rf-baseline/rf_score.py", "sha256": pc.sha(RF / "rf_score.py")}, "code_files": plan.get("code_files", []), "receipt_root": WSL + "/control/rf-score-launch-v1/receipts/" + uid, "score_root": SCORE_ROOT}
        contract["rf_score_execution_stage"] = stage
        contract["evaluation_stage"] = {"training_run_id": parent["run_id"], "training_contract_path": old["contract_path"], "training_contract_sha256": old["contract_sha256"], "expected_score_receipts": 3, "expected_prediction_rows": sum(row["n"] for row in datasets), "datasets": datasets, "root_joint_barrier": plan.get("joint_barrier"), "score_root": SCORE_ROOT, "no_training_or_parameter_updates": True, "paper_count_contribution": 0}
        contract["execution"].update(command=[parent["execution"]["command"][0], WSL + "/control/rf-score-launch-v1/rf_score_unit.py", "--binding", WSL + "/control/rf-score-launch-v1/bindings/" + uid + ".json"], working_directory=WSL, seeds=[old["seed"]], seed_policy="Same frozenRF seed/winner, no refit/reselection; score all three fixed datasets once", timeout_seconds=1800, process_control={"platform": "Linux WSL", "mechanism": "Private CPU4–7 sessions, CPU1/RSS2GiB each,≤4workers/8GiB, whole-tree1800sec/original-global watchdog; actual exit side-signatures", "whole_tree_bounded": True}, stdout_path=WSL + "/control/rf-score-launch-v1/pool-runs/" + uid + ".stdout.log", stderr_path=WSL + "/control/rf-score-launch-v1/pool-runs/" + uid + ".stderr.log")
        folder = out / uid
        folder.mkdir()
        report = validator.validate(contract, allow_template=not issue, check_files=issue, contract_directory=folder)
        pc.write_new(folder / "central-validator-report.json", report)
        if issue and not report["valid_for_execution"]:
            contract.update(is_template=True, contract_status="draft", frozen_at=None)
            pc.write_new(folder / "task-contract.unissued-draft.json", contract)
            raise ValueError("Root RF scoring contract not centrally executable")
        path = folder / ("task-contract.json" if issue else "task-contract.draft.json")
        pc.write_new(path, contract)
        record = {"run_id": uid, "training_run_id": old["run_id"], "task_id": parent["task_id"], "method_id": "RF-Classic", "split_id": old["split_id"], "regime_id": old["regime_id"], "seed": old["seed"], "contract_path": str(path), "contract_sha256": pc.sha(path), "issued": issue, "valid_for_execution": report["valid_for_execution"], "paper_count_contribution": 0}
        if issue:
            central = folder / "central-validator-report.json"
            envelope = {"valid_for_execution": True, "contract_sha256": record["contract_sha256"], "central_validation_path": str(central), "central_validation_sha256": pc.sha(central), "validated_at": pc.now()}
            pc.write_new(folder / "execution-validation.json", envelope)
            record.update(validation_path=str(folder / "execution-validation.json"), validation_sha256=pc.sha(folder / "execution-validation.json"))
        records.append(record)
    if len(records) != 40 or total_rows != 53160:
        raise ValueError("Exact RF40/120/53160 grid required")
    result = {"schema": "auxiliary-RF-postjoint-scoring-contracts.v1", "issued": issue, "units": 40, "expected_score_receipts": 120, "expected_prediction_rows": total_rows, "paper_count_contribution": 0, "raw_gold_prediction_selection_model_array_reads": 0, "actual_score_processes_launched": 0, "records": records}
    pc.write_new(out / "rf-score-contract-index.json", result)
    print(json.dumps({key: result[key] for key in ("issued", "units", "expected_score_receipts", "expected_prediction_rows", "actual_score_processes_launched")}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan")
    parser.add_argument("--out", required=True)
    parser.add_argument("--issue", action="store_true")
    args = parser.parse_args()
    generate(pc.read(args.plan) if args.plan else {}, args.out, args.issue)
