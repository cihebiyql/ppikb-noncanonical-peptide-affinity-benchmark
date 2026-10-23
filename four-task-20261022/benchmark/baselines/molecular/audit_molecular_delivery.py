"""Audit real molecular runs, fingerprints via a second RDKit API, and seed completeness."""
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from rdkit import Chem, DataStructs, RDLogger
from rdkit.Chem import AllChem


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT/"runs"/"cpu-molecular-v1"
IDS = ["ppikb_kd_source_cold_scope_v2","ppikb_kd_target_cold_scope_v2","ppikb_effect_metadata_silver_source_cold"]
MODELS = {"constant","linear","random_forest","extra_trees","hist_gradient_boosting"}


def sha(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b""):
            value.update(chunk)
    return value.hexdigest()


def legacy_fingerprint(smiles):
    molecule = Chem.MolFromSmiles(smiles)
    if molecule is None:
        raise ValueError("frozen SMILES failed independent parse")
    bitvector = AllChem.GetMorganFingerprintAsBitVect(molecule,2,nBits=2048,useChirality=True,useBondTypes=True)
    result = np.zeros(2048,dtype=np.float32)
    DataStructs.ConvertToNumpyArray(bitvector,result)
    return result


def main():
    RDLogger.DisableLog("rdApp.warning")
    errors, views, receipts, candidates = [], [], 0, 0
    checked_fingerprints = 0
    ridge_iterations = []
    for identifier in IDS:
        view_root = RUN/identifier
        contract = json.loads((view_root/"task-contract.json").read_text())
        if sha(contract["input_path"]) != contract["input_sha256"]:
            errors.append({"view":identifier,"problem":"source_input_changed"})
        if sha(ROOT/"baselines/molecular/run_molecular_baselines.py") != contract["code_sha256"]:
            errors.append({"view":identifier,"problem":"execution_code_changed"})
        if sha(ROOT/"baselines/molecular/molecular_features.py") != contract["feature_code_sha256"]:
            errors.append({"view":identifier,"problem":"feature_code_changed"})
        frame = pd.read_csv(contract["input_path"],keep_default_na=False,float_precision="round_trip")
        cache = np.load(view_root/"features.npz",allow_pickle=False)
        x = cache["features"]
        if cache["row_ids"].tolist() != frame.row_id.tolist():
            errors.append({"view":identifier,"problem":"feature_row_order_changed"})
        if hashlib.sha256(x.tobytes()).hexdigest()!=contract["feature_audit"]["feature_matrix_sha256"]:
            errors.append({"view":identifier,"problem":"feature_matrix_sha_mismatch"})
        indices = []
        for _, group in frame.groupby("evaluation_stratum",sort=True):
            indices.extend(group.index[:12].tolist())
        effect = identifier.startswith("ppikb_effect")
        for i in indices:
            row = frame.iloc[i]
            if effect:
                reference,variant = legacy_fingerprint(row.smiles_wt),legacy_fingerprint(row.smiles_mut)
                if not np.array_equal(x[i,:2048],reference) or not np.array_equal(x[i,2058:4106],variant-reference):
                    errors.append({"view":identifier,"row_id":row.row_id,"problem":"independent_effect_fingerprint_mismatch"})
                checked_fingerprints += 2
            else:
                expected = legacy_fingerprint(row.peptide_smiles or row.smiles)
                if not np.array_equal(x[i,:2048],expected):
                    errors.append({"view":identifier,"row_id":row.row_id,"problem":"independent_chiral_fingerprint_mismatch"})
                checked_fingerprints += 1
        model_seeds = {}
        for path in sorted(view_root.glob("*/seed-*/result.json")):
            record = json.loads(path.read_text())
            if record["contract_sha256"]!=sha(view_root/"task-contract.json"):
                errors.append({"path":str(path),"problem":"contract_hash_mismatch"})
            model_seeds.setdefault(record["model"],[]).append(record["seed"])
            grid = json.loads((path.parent/"candidates.json").read_text())
            if len(grid)!=2:
                errors.append({"path":str(path),"problem":"not_two_validation_candidates"})
            for value in grid:
                weights = path.parent/f"candidate-{value['candidate']}.joblib"
                if sha(weights)!=value["model_sha256"]:
                    errors.append({"path":str(weights),"problem":"model_sha_mismatch"})
                if record["model"]=="linear":
                    estimator = joblib.load(weights)[-1]
                    iterations = np.asarray(estimator.n_iter_).reshape(-1).tolist()
                    ridge_iterations.append({"view":identifier,"seed":record["seed"],"candidate":value["candidate"],"iterations":iterations,
                                             "at_iteration_cap":any(int(v)>=1000 for v in iterations)})
                candidates += 1
            for split,item in record["splits"].items():
                if sha(item["prediction_path"])!=item["prediction_sha256"]:
                    errors.append({"path":item["prediction_path"],"problem":"prediction_sha_mismatch"})
            receipts += 1
        if set(model_seeds)!=MODELS or any(sorted(values)!=list(range(10)) for values in model_seeds.values()):
            errors.append({"view":identifier,"problem":"five_models_ten_seed_coverage_missing"})
        views.append({"view":identifier,"rows":len(frame),"features":list(x.shape),"splits":frame.split.value_counts().to_dict(),
                      "evaluation_strata":frame.evaluation_stratum.value_counts().to_dict(),"feature_audit":contract["feature_audit"]})
    process = json.loads((RUN/"process-receipt.json").read_text())
    if process["exit_code"] or not process["worker_pid_absent"] or process["termination_reason"]:
        errors.append({"problem":"supervised_process_not_clean_success","receipt":process})
    result = {"passed":not errors,"errors":errors,"selected_results":receipts,"candidate_fits":candidates,
              "independent_fingerprint_checks":checked_fingerprints,"views":views,"process":process,
              "ridge_iterations":ridge_iterations,"ridge_at_iteration_cap_count":sum(item["at_iteration_cap"] for item in ridge_iterations),
              "validation_selection_only":True,"new_dependencies":False,"new_gpu_use":False,
              "chemical_identity_limit":"source SMILES can encode stereo/PTM; source graph/annotation conflicts are retained, not corrected by fingerprinting"}
    (RUN/"molecular-delivery-audit.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    print(json.dumps({key:result[key] for key in ("passed","errors","selected_results","candidate_fits","independent_fingerprint_checks","ridge_at_iteration_cap_count")}))
    return 0 if result["passed"] else 2


if __name__=="__main__":
    raise SystemExit(main())
