"""Score existing held-out predictions on explicit shared test cohorts; never fit or forward."""
import os
for _name in ("OMP_NUM_THREADS","MKL_NUM_THREADS","OPENBLAS_NUM_THREADS","NUMEXPR_NUM_THREADS"):
    os.environ[_name]="1"
os.environ["CUDA_VISIBLE_DEVICES"]=""

import csv
import hashlib
import io
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata


ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"runs/common-prediction-comparison-v2"
INTER=ROOT/"methods/interaction"
REMOTE="/data/qlyu/projects/peptide-four-task-benchmark-20261022"
MODEL_NAMES=["constant","linear","random_forest","extra_trees","hist_gradient_boosting"]
INPUTS={}
CACHE={}
ERRORS=[]
ALIASES=[]
ENCODINGS={}


def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()


def locate(value):
    text=str(value)
    if text.startswith(REMOTE+"/"):
        path=ROOT/Path(text[len(REMOTE):].lstrip("/"))
    else:
        path=Path(text)
    if path.exists():
        return path
    # Some older DTA administrative CSV paths have a damaged display-only Windows root.
    # Resolve only the exact ASCII task-relative suffix; never rewrite scientific files.
    normalized=text.replace("\\","/")
    token="peptide-four-task-benchmark-20261022/"
    if token in normalized:
        candidate=ROOT/Path(normalized.split(token,1)[1])
        if candidate.exists():
            ALIASES.append({"original_reference":text,"verified_task_relative_alias":str(candidate)})
            return candidate
    return path


def track(path):
    path=locate(path)
    if str(path) not in INPUTS:
        INPUTS[str(path)]={"path":str(path),"sha256":sha(path),"bytes":path.stat().st_size}
    return path


def load(path):
    return json.loads(track(path).read_text(encoding="utf-8-sig"))


def read_rows(path):
    path=track(path)
    if str(path) not in CACHE:
        if path.suffix==".jsonl":
            with path.open(encoding="utf-8") as stream:
                data=[json.loads(line) for line in stream if line.strip()]
        else:
            with path.open(encoding="utf-8-sig",newline="") as stream:
                data=list(csv.DictReader(stream))
        indexed={}
        for row in data:
            key=row.get("row_id") or row.get("record_id")
            if not key or key in indexed:
                raise ValueError(f"missing/duplicate row_id in {path}")
            indexed[key]=row
        CACHE[str(path)]=indexed
    return CACHE[str(path)]


def check(condition,problem,**fields):
    if not condition:
        ERRORS.append({"problem":problem,**fields})


def add_provider(providers,method,panel,seed_paths,training_counts,route,source_refs,complete_expected=True):
    for seed,information in seed_paths.items():
        path=track(information["path"])
        if information.get("sha256"):
            check(INPUTS[str(path)]["sha256"]==information["sha256"],"input_prediction_hash_mismatch",method=method,seed=seed)
        information["path"]=str(path)
        information["format"]="jsonl" if path.suffix==".jsonl" else "csv"
        information["sha256"]=INPUTS[str(path)]["sha256"]
        information["rows"]=len(read_rows(path))
    if complete_expected:
        check(sorted(seed_paths)==list(range(10)),"expected_ten_seed_provider_incomplete",method=method,panel=panel,seeds=sorted(seed_paths))
    providers.append({"method":method,"panel":panel,"seeds":seed_paths,"training_counts":training_counts,"feature_route":route,
                      "source_refs":source_refs,"ten_seed_complete":sorted(seed_paths)==list(range(10))})


def providers_and_references():
    providers=[]
    references=[]
    review_path=ROOT/"baselines/interaction-component-audit-20261023/COMPONENT-REVIEW-RECEIPT.revision2.json"
    review=load(review_path)
    check(review["passed_integrity_and_component_checks"],"head_component_review_not_passed")
    for panel in ("source","target"):
        view=f"ppikb_kd_{panel}_cold_scope_v2"
        for run_id,prefix,route in (("cpu-v2","sequence","manual sequence"),("cpu-molecular-v1","morgan","chiral Morgan+RDKit+protein AAC")):
            contract=load(ROOT/"runs"/run_id/view/"task-contract.json")
            counts=contract["data_audit"]["split_counts"]
            for name in MODEL_NAMES:
                seeds={}
                for seed in range(10):
                    result_path=ROOT/"runs"/run_id/view/name/f"seed-{seed:02d}"/"result.json"
                    result=load(result_path)
                    seeds[seed]={"path":result["splits"]["test"]["prediction_path"],"sha256":result["splits"]["test"]["prediction_sha256"],
                                 "result_path":str(result_path),"result_sha256":INPUTS[str(result_path)]["sha256"]}
                add_provider(providers,f"{prefix}__{name}",panel,seeds,counts,route,[str(ROOT/"runs"/run_id/view/"task-contract.json")])
        for family in (f"standard_{panel}",f"backbone_ablation_{panel}"):
            information=next(item for item in review["head_components"]["families"] if item["family"]==family)
            data_path=locate(information["data_path"])
            data=read_rows(data_path)
            reference_id=f"{'standard2919' if family.startswith('standard') else 'backbone6336'}__{panel}"
            reference={key:row for key,row in data.items() if row["split"]=="test"}
            references.append({"id":reference_id,"panel":panel,"family":family,"path":str(data_path),"input_sha256":INPUTS[str(data_path)]["sha256"],
                               "rows_all_splits":len(data),"test_ids":list(reference),"test_n":len(reference),
                               "strata":dict(Counter(row["evaluation_stratum"] for row in reference.values()))})
            selected=[item for item in review["head_components"]["candidate_index"] if item["family"]==family and item["selected"]]
            seeds={item["seed"]:{"path":str(locate(item["head_path"]).parent.parent/"test-predictions.csv"),"adopted_component_review":str(review_path)} for item in selected}
            method="PepInter_cached_native_head" if family.startswith("standard") else "PepInter_backbone_ablation_native_head"
            add_provider(providers,method,panel,seeds,information["split_counts"],information["claim"],[str(review_path),str(data_path)])
    # Source GraphDTA uses the owner's exact ten-seed adoption table, not a filesystem winner search.
    graph_index=ROOT/"methods/dta/source-GraphDTA-ten-seed-confirmed/per-seed.csv"
    raw=track(graph_index).read_bytes()
    try:
        graph_text=raw.decode("utf-8-sig")
        encoding="utf-8-sig"
    except UnicodeDecodeError:
        graph_text=raw.decode("gb18030")
        encoding="gb18030"
        if graph_text.encode("gb18030")!=raw:
            raise ValueError("DTA path-index encoding did not round-trip exactly")
    ENCODINGS[str(graph_index)]=encoding
    graph_rows=list(csv.DictReader(io.StringIO(graph_text,newline="")))
    graph_seeds={}
    graph_counts=None
    for row in graph_rows:
        complete_path=locate(row["path"])
        complete=load(complete_path)
        check(complete["status"]=="complete" and complete["endpoint"]=="pKd" and complete["stage"]=="formal","invalid_graph_source_adoption",path=str(complete_path))
        graph_seeds[int(row["seed"]) ]={"path":str(complete_path.parent/"test-predictions.jsonl"),"sha256":complete["prediction_sha256"],
                                      "result_path":str(complete_path),"runtime_stratum":row.get("runtime_stratum")}
        graph_counts=complete["sample_counts"]
    add_provider(providers,"GraphDTA-GIN","source",graph_seeds,graph_counts,"author graph architecture; own feature/stereo/prefix limitations retained",[str(graph_index)])
    census=load(ROOT/"methods/dta/common-formal-census-20261023T013530Z.json")
    target_seeds={}
    target_counts=None
    for source in census["source_censuses"]:
        snapshot=load(source)
        for row in snapshot["records"]:
            if row["view"]!="ppikb_kd_target_cold_scope_v2" or row["method"]!="GraphDTA-GIN":
                continue
            complete_path=locate(row["path"])
            complete=load(complete_path)
            seed=int(row["seed"])
            item={"path":str(complete_path.parent/"test-predictions.jsonl"),"sha256":complete["prediction_sha256"],"result_path":str(complete_path)}
            if seed in target_seeds:
                check(target_seeds[seed]["sha256"]==item["sha256"],"conflicting_graph_target_seed",seed=seed)
            else:
                target_seeds[seed]=item
            target_counts=complete["sample_counts"]
    add_provider(providers,"GraphDTA-GIN","target",target_seeds,target_counts,"partial author-graph target panel; not a ten-seed ranking",[str(ROOT/"methods/dta/common-formal-census-20261023T013530Z.json")],False)
    return providers,references


def regression(rows):
    n=len(rows)
    if not n:
        return {"n":0,"mae":None,"rmse":None,"bias":None,"r2":None,"pearson":None,"spearman":None}
    y=np.asarray([float(row["label"]) for row in rows])
    p=np.asarray([float(row["prediction"]) for row in rows])
    error=p-y
    total=float(np.dot(y-y.mean(),y-y.mean()))
    variable=n>1 and np.ptp(y)>0 and np.ptp(p)>0
    return {"n":n,"mae":float(np.mean(np.abs(error))),"rmse":float(np.sqrt(np.mean(error**2))),"bias":float(error.mean()),
            "r2":float(1-np.dot(error,error)/total) if n>1 and np.ptp(y)>0 else None,
            "pearson":float(np.corrcoef(y,p)[0,1]) if variable else None,
            "spearman":float(np.corrcoef(rankdata(y),rankdata(p))[0,1]) if variable else None}


def strata(rows):
    result={"all":rows,"NC_all_including_PTM":[r for r in rows if r["evaluation_stratum"]!="standard20_control"],
            "PTM_any_including_mixed":[r for r in rows if r["evaluation_stratum"] in {"PTM","synthetic_and_PTM"}]}
    for value in ("synthetic_D_backbone","PTM","synthetic_and_PTM","other_NC","standard20_control"):
        result[value]=[r for r in rows if r["evaluation_stratum"]==value]
    return result


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    if (OUT/"COMPARISON-RECEIPT.json").exists():
        raise ValueError("comparison-v2 is frozen; use a new revision for new predictions")
    providers,references=providers_and_references()
    reference_map={ref["id"]:{key:read_rows(ref["path"])[key] for key in ref["test_ids"]} for ref in references}
    coverage=[]
    for ref in references:
        gold=reference_map[ref["id"]]
        for provider in providers:
            if provider["panel"]!=ref["panel"]:
                continue
            overlaps=[]
            ids_all=set(gold)
            for seed,item in provider["seeds"].items():
                frame=read_rows(item["path"])
                overlap=set(gold)&set(frame)
                ids_all &= set(frame)
                mismatched=[]
                for row_id in overlap:
                    observed,expected=frame[row_id],gold[row_id]
                    if float(observed["label"])!=float(expected["label"]) or observed.get("endpoint")!=expected["endpoint"] or expected["endpoint"]!="pKd":
                        mismatched.append(row_id)
                    if not math.isfinite(float(observed["prediction"])):
                        mismatched.append(row_id)
                check(not mismatched,"canonical_label_endpoint_or_finite_prediction_mismatch",cohort=ref["id"],method=provider["method"],seed=seed,row_ids=mismatched[:20])
                overlaps.append({"seed":seed,"input_prediction_rows":len(frame),"common_rows":len(overlap),"mismatched_rows":len(mismatched)})
            eligible=provider["ten_seed_complete"] and len(ids_all)==len(gold)
            coverage.append({"cohort":ref["id"],"panel":ref["panel"],"method":provider["method"],"reference_test_n":len(gold),
                             "available_seed_ids":sorted(provider["seeds"]),"ten_seed_complete":provider["ten_seed_complete"],
                             "minimum_overlap_all_available_seeds":len(ids_all),"full_cohort_covered_by_all_10_seeds":eligible,
                             "main_ranking_eligible":eligible,"reason":"eligible_same_test_denominator" if eligible else "incomplete_seed_set" if not provider["ten_seed_complete"] else "partial_test_coverage_only",
                             "per_seed_coverage":overlaps,"training_counts":provider["training_counts"],"feature_route":provider["feature_route"]})
    if ERRORS:
        (OUT/"pre-score-errors.json").write_text(json.dumps(ERRORS,ensure_ascii=False,indent=2),encoding="utf-8")
        raise ValueError("canonical ID/label/endpoint pre-score checks failed; no comparison scores adopted")
    contract={"prepared_at":datetime.now(timezone.utc).isoformat(),"references":references,"providers":providers,"coverage":coverage,
              "main_inclusion_rule":"all seeds0-9 complete and every reference test ID covered in all seeds; fixed by coverage before looking at comparison metrics",
              "non_eligible_policy":"keep coverage and separately score available exact overlaps, never include partial target in ten-seed ranking",
              "canonical_label_policy":"raw frozen reference CSV Python float64 by row_id; require source labels/endpoints identical; no float32 scoring",
              "training_coverage_aligned":False,"all_eight_methods_common_subset":False,"new_fits":0,"new_model_forward":0,
              "source_inputs":list(INPUTS.values()),"path_aliases":ALIASES,"source_text_encodings":ENCODINGS,"code_sha256":sha(__file__)}
    (OUT/"task-contract.json").write_text(json.dumps(contract,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    metrics=[]
    partial=[]
    prediction_receipts=[]
    cohorts=[]
    for ref in references:
        gold=reference_map[ref["id"]]
        eligible={item["method"] for item in coverage if item["cohort"]==ref["id"] and item["main_ranking_eligible"]}
        common=set(gold)
        for provider in providers:
            if provider["panel"]==ref["panel"] and provider["method"] in eligible:
                for item in provider["seeds"].values():
                    common &= set(read_rows(item["path"]))
        order=[row_id for row_id in ref["test_ids"] if row_id in common]
        check(len(order)==ref["test_n"],"qualified_shared_intersection_changed_declared_cohort",cohort=ref["id"])
        cohorts.append({"id":ref["id"],"test_n":len(order),"eligible_methods":sorted(eligible),"stratum_counts":dict(Counter(gold[key]["evaluation_stratum"] for key in order))})
        cohort_root=OUT/ref["id"]
        cohort_root.mkdir(exist_ok=True)
        pd.DataFrame([{"row_id":key,"label":float(gold[key]["label"]),"endpoint":gold[key]["endpoint"],"group_id":gold[key]["group_id"],"evaluation_stratum":gold[key]["evaluation_stratum"]} for key in order]).to_csv(cohort_root/"common-reference.csv",index=False,float_format="%.17g")
        for provider in providers:
            if provider["panel"]!=ref["panel"]:
                continue
            main=provider["method"] in eligible
            for seed,item in sorted(provider["seeds"].items()):
                original=read_rows(item["path"])
                selected=[{"row_id":key,"label":float(gold[key]["label"]),"prediction":float(original[key]["prediction"]),"endpoint":"pKd",
                           "group_id":gold[key]["group_id"],"evaluation_stratum":gold[key]["evaluation_stratum"]} for key in order if key in original]
                records=[]
                for stratum,members in strata(selected).items():
                    record={"cohort":ref["id"],"panel":ref["panel"],"method":provider["method"],"seed":seed,"stratum":stratum,
                            "main_ranking_eligible":main,"available_seed_count":len(provider["seeds"]),"reference_test_n":len(gold),
                            "source_prediction_sha256":item["sha256"],**regression(members)}
                    (metrics if main else partial).append(record)
                    records.append(record)
                run=cohort_root/provider["method"]/f"seed-{seed:02d}"
                run.mkdir(parents=True,exist_ok=True)
                pd.DataFrame(selected).to_csv(run/"common-test-predictions.csv",index=False,float_format="%.17g")
                receipt={"cohort":ref["id"],"method":provider["method"],"seed":seed,"main_ranking_eligible":main,
                         "source_prediction_path":item["path"],"source_prediction_sha256":item["sha256"],"reference_csv":ref["path"],
                         "reference_sha256":ref["input_sha256"],"selected_prediction_path":str(run/"common-test-predictions.csv"),
                         "selected_prediction_sha256":sha(run/"common-test-predictions.csv"),"n":len(selected),"training_counts":provider["training_counts"],
                         "training_coverage_aligned":False,"new_fit":False,"new_forward":False,"stratum_metrics":records}
                (run/"result.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
                prediction_receipts.append(receipt)
    pd.DataFrame(metrics).to_csv(OUT/"per-seed-metrics.csv",index=False,float_format="%.17g")
    pd.DataFrame(partial).to_csv(OUT/"unranked-coverage-only-per-seed-metrics.csv",index=False,float_format="%.17g")
    pd.DataFrame([{key:value for key,value in item.items() if key not in {"per_seed_coverage","training_counts"}} for item in coverage]).to_csv(OUT/"coverage-per-method.csv",index=False)
    table=pd.DataFrame(metrics).melt(id_vars=["cohort","panel","method","seed","stratum","n","main_ranking_eligible"],value_vars=["mae","rmse","bias","r2","pearson","spearman"],var_name="metric",value_name="value")
    table.groupby(["cohort","panel","method","stratum","metric"],dropna=False).agg(mean=("value","mean"),sd=("value","std"),seed_count=("seed","nunique"),valid_seed_count=("value","count"),n=("n","first")).reset_index().to_csv(OUT/"mean-sd-metrics.csv",index=False,float_format="%.17g")
    changed=[item["path"] for item in INPUTS.values() if sha(item["path"])!=item["sha256"]]
    check(not changed,"original_inputs_changed_during_comparison",paths=changed)
    result={"schema":"four-task.common-fixed-prediction-comparison.v2","completed_at":datetime.now(timezone.utc).isoformat(),"passed":not ERRORS,"errors":ERRORS,
            "new_fits":0,"new_model_forward":0,"new_model_predictions":0,"cohorts":cohorts,"main_model_seed_conditions":len(metrics)//8,
            "unranked_model_seed_conditions":len(partial)//8,"main_metric_rows":len(metrics),"unranked_metric_rows":len(partial),
            "source_input_files":list(INPUTS.values()),"original_inputs_unchanged":not changed,"prediction_receipts":prediction_receipts,
            "training_coverage_aligned":False,"all_eight_methods_common_subset":False,"old_CPU_common_subset_v1_modified":False}
    (OUT/"COMPARISON-RECEIPT.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    print(json.dumps({key:result[key] for key in ("passed","errors","new_fits","main_model_seed_conditions","unranked_model_seed_conditions","cohorts")},ensure_ascii=False))
    return 0 if not ERRORS else 2


if __name__=="__main__":
    raise SystemExit(main())
