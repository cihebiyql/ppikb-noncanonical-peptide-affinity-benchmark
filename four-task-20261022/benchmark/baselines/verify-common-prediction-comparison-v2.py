"""Independent stdlib-only identity, extraction and regression check for common comparisons."""
import csv
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"runs/common-prediction-comparison-v2"
CACHE={}


def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""):
            h.update(block)
    return h.hexdigest()


def read(path):
    path=Path(path)
    if str(path) not in CACHE:
        with path.open(encoding="utf-8-sig",newline="") as stream:
            content=[json.loads(line) for line in stream if line.strip()] if path.suffix==".jsonl" else list(csv.DictReader(stream))
        CACHE[str(path)]={row.get("row_id") or row["record_id"]:row for row in content}
    return CACHE[str(path)]


def ranks(values):
    order=sorted(range(len(values)),key=values.__getitem__)
    result=[0.]*len(values)
    start=0
    while start<len(order):
        end=start+1
        while end<len(order) and values[order[end]]==values[order[start]]:
            end+=1
        for i in range(start,end):
            result[order[i]]=(start+1+end)/2
        start=end
    return result


def correlation(a,b):
    if len(a)<2 or max(a)==min(a) or max(b)==min(b):
        return None
    am,bm=math.fsum(a)/len(a),math.fsum(b)/len(b)
    aa=[v-am for v in a];bb=[v-bm for v in b]
    return math.fsum(x*y for x,y in zip(aa,bb))/math.sqrt(math.fsum(x*x for x in aa)*math.fsum(y*y for y in bb))


def score(rows):
    n=len(rows)
    if not n:
        return {"n":0,"mae":None,"rmse":None,"bias":None,"r2":None,"pearson":None,"spearman":None}
    y=[float(row["label"]) for row in rows];p=[float(row["prediction"]) for row in rows]
    squared=math.fsum((a-b)**2 for a,b in zip(y,p))
    mean=math.fsum(y)/n
    denom=math.fsum((value-mean)**2 for value in y)
    return {"n":n,"mae":math.fsum(abs(a-b) for a,b in zip(y,p))/n,"rmse":math.sqrt(squared/n),
            "bias":math.fsum(b-a for a,b in zip(y,p))/n,"r2":1-squared/denom if n>1 and max(y)>min(y) else None,
            "pearson":correlation(y,p),"spearman":correlation(ranks(y),ranks(p))}


def stratum_match(row,tag):
    value=row["evaluation_stratum"]
    return tag=="all" or tag=="NC_all_including_PTM" and value!="standard20_control" or tag=="PTM_any_including_mixed" and value in {"PTM","synthetic_and_PTM"} or value==tag


def main():
    receipt=json.loads((OUT/"COMPARISON-RECEIPT.json").read_text(encoding="utf-8"))
    contract=json.loads((OUT/"task-contract.json").read_text(encoding="utf-8"))
    errors=[]
    source_checks=0
    for item in receipt["source_input_files"]:
        if sha(item["path"])!=item["sha256"]:
            errors.append({"problem":"source_sha_changed","path":item["path"]})
        source_checks+=1
    row_checks=0
    metric_checks=0
    seed_sets={}
    for record in receipt["prediction_receipts"]:
        source=read(record["source_prediction_path"])
        reference=read(record["reference_csv"])
        selected=read(record["selected_prediction_path"])
        if sha(record["selected_prediction_path"])!=record["selected_prediction_sha256"]:
            errors.append({"problem":"selected_prediction_sha_changed","path":record["selected_prediction_path"]})
        if record["main_ranking_eligible"]:
            expected={key for key,row in reference.items() if row["split"]=="test"}
            if set(selected)!=expected:
                errors.append({"problem":"main_same_test_set_not_equal","cohort":record["cohort"],"method":record["method"],"seed":record["seed"]})
            seed_sets.setdefault((record["cohort"],record["method"]),[]).append(record["seed"])
        for key,row in selected.items():
            original=source[key];gold=reference[key]
            if float(row["label"])!=float(gold["label"]) or float(row["label"])!=float(original["label"]) or float(row["prediction"])!=float(original["prediction"]) or row["endpoint"]!=gold["endpoint"] or row["endpoint"]!=original["endpoint"]:
                errors.append({"problem":"row_label_endpoint_or_prediction_changed","row_id":key,"method":record["method"]})
            row_checks+=1
        for stored in record["stratum_metrics"]:
            actual=score([row for row in selected.values() if stratum_match(row,stored["stratum"])])
            for metric,value in actual.items():
                wanted=stored[metric]
                if (value is None)!=(wanted is None) or value is not None and not math.isclose(value,wanted,abs_tol=1e-10,rel_tol=1e-10):
                    errors.append({"problem":"metric_mismatch","cohort":record["cohort"],"method":record["method"],"seed":record["seed"],"stratum":stored["stratum"],"metric":metric,"actual":value,"stored":wanted})
                metric_checks+=1
    for key,seeds in seed_sets.items():
        if sorted(seeds)!=list(range(10)):
            errors.append({"problem":"main_not_ten_seeds","key":key,"seeds":seeds})
    partial_graph=[item for item in contract["coverage"] if item["method"]=="GraphDTA-GIN" and item["panel"]=="target"]
    if any(item["main_ranking_eligible"] for item in partial_graph):
        errors.append({"problem":"partial_target_graph_included_in_ten_seed_main"})
    result={"passed":not errors,"errors":errors,"source_files_sha_verified":source_checks,"selected_rows_identity_checked":row_checks,
            "metric_cells_recomputed":metric_checks,"main_method_cohort_conditions":len(seed_sets),"main_conditions_all_ten_seeds":all(sorted(v)==list(range(10)) for v in seed_sets.values()),
            "partial_target_graph_excluded_from_main":True,"new_fits":0,"new_model_forward":0,"new_model_predictions":0,
            "implementation":"independent csv/JSON parser, builtin float64, average tied ranks, math.fsum; no ML adapter imported",
            "code_sha256":sha(__file__)}
    (OUT/"INDEPENDENT-VERIFICATION.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    print(json.dumps({key:result[key] for key in ("passed","errors","source_files_sha_verified","selected_rows_identity_checked","metric_cells_recomputed","main_method_cohort_conditions","new_fits")},ensure_ascii=False))
    return 0 if not errors else 2


if __name__=="__main__":
    raise SystemExit(main())
