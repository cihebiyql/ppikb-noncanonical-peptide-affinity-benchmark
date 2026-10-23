"""New administrative audit/recalculation; preserve every earlier audit and training artifact."""
import os
for _key in ("OMP_NUM_THREADS","MKL_NUM_THREADS","OPENBLAS_NUM_THREADS","NUMEXPR_NUM_THREADS"):
    os.environ[_key] = "1"
os.environ["CUDA_VISIBLE_DEVICES"] = ""

import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata
from sklearn.metrics import average_precision_score, roc_auc_score


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/"baselines"/"recovery-20261023"
REMOTE = "/data/qlyu/projects/peptide-four-task-benchmark-20261022"
TRAIN = ["cpu-v2","cpu-additional-v1","cpu-contact-v1","cpu-effect-v1","cpu-contact64-v1","cpu-molecular-v1"]
EXTERNAL = ["cpu-external-v1","cpu-effect-external-v1"]
POSTHOC = ["cpu-common-subset-v1"]
MODELS = {"constant","linear","random_forest","extra_trees","hist_gradient_boosting"}


def local(path):
    value = str(path)
    if value==REMOTE or value.startswith(REMOTE+"/"):
        return ROOT/Path(value[len(REMOTE):].lstrip("/"))
    return Path(value)


def sha(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""):
            result.update(block)
    return result.hexdigest()


def clean(value):
    return float(value) if value is not None and math.isfinite(float(value)) else None


def corr(a,b):
    if len(a)<2 or np.ptp(a)==0 or np.ptp(b)==0:
        return None
    ac,bc = a-np.mean(a),b-np.mean(b)
    return clean(np.dot(ac,bc)/math.sqrt(np.dot(ac,ac)*np.dot(bc,bc)))


def recompute(frame, stored):
    y,p = frame.label.to_numpy(),frame.prediction.to_numpy()
    if "mae" in stored:
        residual = p-y
        squared = float(np.dot(residual,residual))
        variance = float(np.dot(y-y.mean(),y-y.mean()))
        result = {"mae":clean(np.mean(np.abs(residual))),"rmse":clean(math.sqrt(squared/len(y))),"bias":clean(np.mean(residual)),
                  "pearson":corr(y,p),"spearman":corr(rankdata(y),rankdata(p)),"r2":clean(1-squared/variance) if len(y)>1 and np.ptp(y)>0 else None}
        if "direction_accuracy_nonzero" in stored:
            nonzero = y!=0
            result["direction_accuracy_nonzero"] = clean(np.mean(np.sign(y[nonzero])==np.sign(p[nonzero]))) if np.any(nonzero) else None
            result["nonzero_effect_n"] = int(sum(nonzero))
        return result
    binary = p>=frame.threshold.to_numpy()
    tp,tn = int(sum(binary&(y==1))),int(sum(~binary&(y==0)))
    fp,fn = int(sum(binary&(y==0))),int(sum(~binary&(y==1)))
    two = len(np.unique(y))==2
    denominator = (tp+fp)*(tp+fn)*(tn+fp)*(tn+fn)
    return {"brier":clean(np.mean((p-y)**2)),"f1":clean(2*tp/(2*tp+fp+fn)) if 2*tp+fp+fn else 0.,
            "mcc":clean((tp*tn-fp*fn)/math.sqrt(denominator)) if denominator else (0. if two else None),
            "balanced_accuracy":clean((tp/(tp+fn)+tn/(tn+fp))/2) if two else None,
            "auroc":clean(roc_auc_score(y,p)) if two else None,"auprc":clean(average_precision_score(y,p)) if two else None}


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    errors, files, contracts, coverage, summary_frames = [],[],{},defaultdict(list),[]
    candidate_count, metric_checks, prediction_rows = 0,0,0
    training_results, external_results, posthoc_results = 0,0,0
    per_run = []
    code_snapshots = {}
    for path in (ROOT/"baselines").rglob("*.py"):
        code_snapshots.setdefault(sha(path),str(path))
    for run_id in TRAIN+EXTERNAL+POSTHOC:
        base = ROOT/"runs"/run_id
        category = "training" if run_id in TRAIN else "fixed_external" if run_id in EXTERNAL else "fixed_common_subset"
        current = {"run_id":run_id,"category":category,"selected_results":0,"candidate_fits":0,"prediction_files":0,"prediction_rows":0,"metric_checks":0}
        for path in sorted(base.glob("*/*/seed-*/result.json")):
            result = json.loads(path.read_text(encoding="utf-8"))
            if result.get("status")!="succeeded":
                errors.append({"path":str(path),"problem":"not_succeeded"})
                continue
            coverage[(run_id,result["view_id"],result["model"])].append(result["seed"])
            cp = path.parent.parent.parent/"task-contract.json"
            cp_sha = sha(cp)
            if result["contract_sha256"]!=cp_sha:
                errors.append({"path":str(path),"problem":"contract_hash_changed"})
            if str(cp) not in contracts:
                contract = json.loads(cp.read_text(encoding="utf-8"))
                input_path = contract.get("input_path") or contract.get("reference_csv_path")
                input_sha = contract.get("input_sha256") or contract.get("reference_csv_sha256")
                if input_path and sha(local(input_path))!=input_sha:
                    errors.append({"path":str(cp),"problem":"frozen_input_hash_changed"})
                if contract.get("code_sha256") not in code_snapshots:
                    errors.append({"path":str(cp),"problem":"matching_execution_code_snapshot_missing"})
                if contract.get("feature_code_sha256") and sha(local(contract["feature_code_path"]))!=contract["feature_code_sha256"]:
                    errors.append({"path":str(cp),"problem":"molecular_feature_source_hash_changed"})
                contracts[str(cp)]={"path":str(cp),"sha256":cp_sha,"input_path_local":str(local(input_path)) if input_path else None,
                                    "matching_code_snapshot":code_snapshots.get(contract.get("code_sha256"))}
            if run_id in TRAIN:
                grid = json.loads((path.parent/"candidates.json").read_text(encoding="utf-8"))
                if len(grid)!=2:
                    errors.append({"path":str(path),"problem":"two_validation_candidates_missing"})
                for item in grid:
                    weights = path.parent/f"candidate-{item['candidate']}.joblib"
                    if sha(weights)!=item["model_sha256"]:
                        errors.append({"path":str(weights),"problem":"candidate_weight_hash_changed"})
                    candidate_count += 1
                    current["candidate_fits"] += 1
                training_results += 1
            elif run_id in EXTERNAL:
                external_results += 1
            else:
                posthoc_results += 1
            current["selected_results"] += 1
            for split,values in result["splits"].items():
                prediction = local(values["prediction_path"])
                actual_sha = sha(prediction)
                if actual_sha!=values["prediction_sha256"]:
                    errors.append({"path":str(prediction),"problem":"prediction_hash_changed"})
                frame = pd.read_csv(prediction,float_precision="round_trip",keep_default_na=False)
                if len(frame)!=values["metrics"]["n"]:
                    errors.append({"path":str(prediction),"problem":"prediction_denominator_changed"})
                recalculated = recompute(frame,values["metrics"])
                for metric,actual in recalculated.items():
                    expected = values["metrics"][metric]
                    metric_checks += 1
                    current["metric_checks"] += 1
                    if (actual is None)!=(expected is None) or (actual is not None and abs(actual-expected)>1e-10):
                        errors.append({"path":str(prediction),"metric":metric,"stored":expected,"recomputed":actual})
                files.append({"run_id":run_id,"category":category,"path":str(prediction),"sha256":actual_sha,"rows":len(frame)})
                prediction_rows += len(frame)
                current["prediction_files"] += 1
                current["prediction_rows"] += len(frame)
        per_run.append(current)
        summary = base/"mean-sd-metrics.csv"
        if summary.exists():
            table = pd.read_csv(summary)
            table.insert(0,"run_id",run_id)
            table.insert(1,"analysis_category",category)
            table.insert(2,"feature_route","chiral_morgan_rdkit_protein_AAC" if run_id=="cpu-molecular-v1" else "manual_sequence")
            summary_frames.append(table)
    for key,seeds in coverage.items():
        if sorted(seeds)!=list(range(10)):
            errors.append({"group":key,"problem":"seed_set_not_0_to_9","seeds":seeds})
    views = defaultdict(set)
    for run_id,view,model in coverage:
        views[(run_id,view)].add(model)
    for key,present in views.items():
        if present!=MODELS:
            errors.append({"view":key,"problem":"five_model_set_incomplete","present":sorted(present)})
    molecule = json.loads((ROOT/"runs/cpu-molecular-v1/molecular-delivery-audit.json").read_text(encoding="utf-8"))
    process = json.loads((ROOT/"runs/cpu-molecular-v1/process-receipt.json").read_text(encoding="utf-8"))
    mirror = json.loads((ROOT/"baselines/molecular/local-mirror-receipt.json").read_text(encoding="utf-8"))
    for name,receipt in (("molecular_native_audit",molecule),("molecular_local_mirror",mirror)):
        if not receipt.get("passed"):
            errors.append({"problem":name+"_failed"})
    if process["exit_code"] or not process["worker_pid_absent"] or process["surviving_owned_group_pids_before_cleanup"]:
        errors.append({"problem":"molecular_process_was_not_clean_completed"})
    contact = json.loads((ROOT/"runs/cpu-contact64-v1/independent-complex-macro-verification.json").read_text(encoding="utf-8"))
    if not contact["passed"] or contact["test_complex_count"]!=12:
        errors.append({"problem":"contact64_complex_verification_failed"})
    if summary_frames:
        pd.concat(summary_frames,ignore_index=True).to_csv(OUT/"all-results-mean-sd.csv",index=False)
    excluded = ROOT/"runs/cpu-v1/DIAGNOSTIC_ONLY.json"
    result = {"schema":"four-task.cpu-recovery-audit.v1","completed_at":datetime.now(timezone.utc).isoformat(),
              "passed":not errors,"errors":errors,"selected_training_results":training_results,"candidate_fits":candidate_count,
              "fixed_external_applications":external_results,"fixed_common_subset_evaluations":posthoc_results,
              "training_view_feature_conditions":sum(run in TRAIN for run,_ in views),
              "distinct_input_training_view_ids":len({view for run,view in views if run in TRAIN}),
              "prediction_files_including_posthoc_common":len(files),"prediction_rows_including_posthoc_common":prediction_rows,
              "fresh_metric_cells_recomputed":metric_checks,"new_fits_during_recovery":0,"new_predictions_during_recovery":0,
              "per_run":per_run,"seed_coverage":[{"run_id":key[0],"view_id":key[1],"model":key[2],"seeds":sorted(values)} for key,values in coverage.items()],
              "contracts":list(contracts.values()),"prediction_files":files,"molecular_native_fingerprint_checks":molecule["independent_fingerprint_checks"],
              "molecular_ridge_at_iteration_cap_count":molecule["ridge_at_iteration_cap_count"],"molecular_process":process,
              "molecular_local_mirror":mirror,"contact64_macro_verification":contact,
              "old_diagnostic_preserved":{"path":str(excluded),"sha256":sha(excluded),"included_in_training_count":False},
              "counts_are_compute_records_not_independent_biological_samples":True,
              "scope":"traditional sequence and molecular CPU baselines only; DTA/SWING/UniAIR native lanes are audited separately",
              "old_audits_overwritten":False,"code_sha256":sha(__file__)}
    (OUT/"CPU-RECOVERY-AUDIT.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    print(json.dumps({key:result[key] for key in ("passed","errors","selected_training_results","candidate_fits","fixed_external_applications","fixed_common_subset_evaluations","training_view_feature_conditions","distinct_input_training_view_ids","prediction_files_including_posthoc_common","prediction_rows_including_posthoc_common","fresh_metric_cells_recomputed","new_fits_during_recovery")},ensure_ascii=False))
    return 0 if result["passed"] else 2


if __name__=="__main__":
    raise SystemExit(main())
