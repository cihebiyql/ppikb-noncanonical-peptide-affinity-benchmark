"""Summarize frozen evidence only. Never fit models or generate predictions."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/delivery-20261023"


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def link(path: Path, title: str | None = None):
    return f"[{title or path.name}](<{path.as_posix()}>)"


def write_csv(name: str, fields: list[str], rows: list[dict]):
    with (OUT / name).open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def fmt(d: dict, metric: str = "mae"):
    value = d.get(metric) or d.get(metric.upper())
    if not value or value.get("mean") is None:
        return "—"
    sd = value.get("sd")
    return f"{value['mean']:.4f} ± {sd:.4f}" if sd is not None else f"{value['mean']:.4f}"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    at = datetime.now(timezone.utc).isoformat()
    paths = {
        "views": ROOT / "data/view_manifest.json",
        "eligibility": ROOT / "data/source_task_matrix.json",
        "methods": ROOT / "protocol/method_registry.json",
        "cpu": ROOT / "baselines/recovery-20261023/CPU-RECOVERY-AUDIT.json",
        "dta": sorted((ROOT / "methods/dta").glob("common-formal-census-*.json"))[-1],
        "dta_artifacts": sorted((ROOT / "methods/dta").glob("final-success-artifact-audit-*.json"))[-1],
        "interaction": ROOT / "methods/interaction/status.interaction.v3.json",
        "data_audit": ROOT / "reports/independent-data-readback.json",
    }
    accepted_pointer = ROOT / "methods/dta/accepted-details-current.json"
    if accepted_pointer.is_file():
        pointer = read(accepted_pointer)
        accepted_path = Path(pointer["path"])
        assert sha(accepted_path) == pointer["sha256"], "Accepted DTA snapshot changed"
        paths["dta"] = accepted_path
    authorization = ROOT / "protocol/continuation-20261023/user-authorization.json"
    if authorization.is_file():
        paths["continuation_authorization"] = authorization
    for key, rel in {
        "hu_external": "reports/profaff-HU-external/STATUS.json",
        "pepbi_conditional_external": "reports/pepbi-conditional-external-v1/DELIVERY-RECEIPT.json",
        "profaff_expansion": "data/profaff-expansion-20261023/additional-manifest.json",
        "rde_canary": "runs/uniair-rde-SI-canary-continuation-v3/artifacts/result.json",
        "rde_canary_exit": "runs/uniair-rde-SI-canary-continuation-v3/process-receipt.json",
        "rde_full_progress": "runs/uniair-rde-SI-full-continuation-v1/artifacts/progress.json",
        "rde_joined": "methods/uniair/continuation-20261023/native419-joined-audit-v1/independent-audit.json",
        "rde_formal_progress": "methods/uniair/continuation-20261023/native-rde-status-fresh.json",
        "rde_ten_seed_summary": "methods/uniair/continuation-20261023/rde-ten-seed-report-v1/summary.json",
        "generic_aggregation_audit": "reports/root-generic-aggregation-independent-v1/DELIVERY-RECEIPT.json",
        "uniair_continuation": "methods/uniair/continuation-20261023/continuation-status-v2.json",
        "interaction_continuation": "methods/interaction/status.interaction.continuation.v1.json",
        "her2_strict_baselines": "reports/her2-strict-local/STATUS.json",
        "plm_simple": "baselines/plm-simple-v1/DELIVERY-RECEIPT.json",
        "plm_matched_controls": "baselines/plm-simple-v1/controls/DELIVERY-RECEIPT.json",
        "plm_binary": "baselines/plm-classification-contact-v1/FINAL-LOCAL-RECEIPT.json",
        "plm_binary_primary": "baselines/plm-classification-contact-v1/DELIVERY-RECEIPT.json",
        "generic_endpoint_declarations": "reports/root-generic-aggregation-independent-v1/view-endpoint-map.json",
        "species_audit": "reports/source-species-audit-v1/reported-species.json",
    }.items():
        if (ROOT / rel).is_file():
            paths[key] = ROOT / rel
    source = {key: read(path) for key, path in paths.items()}
    manifest, cpu, dta, interaction = (source[key] for key in ("views", "cpu", "dta", "interaction"))
    hu_external = source.get("hu_external", {})
    rde_canary = source.get("rde_canary", {})
    rde_exit = source.get("rde_canary_exit", {})
    rde_canary_complete = (rde_canary.get("strict_official_state_dict_load") is True and
        rde_exit.get("exit_code") == 0 and rde_exit.get("worker_pid_absent") is True)
    rde_rows = rde_canary.get("rows", 0) if rde_canary_complete else 0
    rde_progress = source.get("rde_full_progress", {})
    rde_joined = source.get("rde_joined", {})
    rde_formal = source.get("rde_formal_progress", {})
    rde_finished = [r for r in rde_formal.get("rows", [])
        if r.get("scientific_result_exists") and r.get("owned_terminal_success")]
    assert len(rde_finished) == rde_formal.get("formal_successful_seeds", 0)
    assert len({r["seed"] for r in rde_finished}) == len(rde_finished)
    assert all(r.get("real_candidate_fits") == 2 and r.get("test_evaluated") is True
        and not r.get("running_pids") and r.get("phase") == "formal" for r in rde_finished)
    rde_nseed = len(rde_finished)
    rde_summary = source.get("rde_ten_seed_summary", {})
    rde_ten_complete = bool(rde_summary.get("all_ten_genuine_training_seeds_audited"))
    if rde_ten_complete:
        assert rde_nseed == 10 and rde_summary["selected_RDE_models"] == 10
        assert rde_summary["real_RDE_candidate_fits"] == 20
        assert rde_summary["distinct_initial_trainable_states_verified"] == 10
        for proof in rde_summary["sources"]:
            assert sha(Path(proof["path"])) == proof["sha256"], "RDE comparison source changed"
    her2_baselines = source.get("her2_strict_baselines", {})
    plm_simple = source.get("plm_simple", {})
    plm_controls = source.get("plm_matched_controls", {})
    plm_binary = source.get("plm_binary", {})
    if plm_binary:
        assert plm_binary.get("passed") is True and plm_binary.get("numeric_errors") == 0
        assert sha(paths["plm_binary_primary"]) == plm_binary["primary_delivery_receipt_sha256"]
        assert source["plm_binary_primary"]["all_source_artifacts_local_verified"] is True
    continuation = source.get("interaction_continuation", {})
    swing_new = continuation.get("methods", {}).get("SWING", {}).get("controlled_hash0_classification", {})
    pep_new = continuation.get("methods", {}).get("PepInter", {}).get("new_native_classification_component", {})
    for panel, actual, audited, local in [
        (swing_new, "result_complete_seeds", "independently_audited_seeds", "local_complete_rehashed_seeds"),
        (pep_new, "result_complete_feature_chunks", "independently_audited_feature_chunks", "local_complete_rehashed_feature_chunks"),
        (pep_new, "result_complete_head_seeds", "independently_audited_head_seeds", "local_complete_rehashed_head_seeds"),
    ]:
        assert set(panel.get(local, [])).issubset(panel.get(audited, []))
        assert set(panel.get(audited, [])).issubset(panel.get(actual, []))
    swing_audited = len(swing_new.get("independently_audited_seeds", []))
    swing_local = len(swing_new.get("local_complete_rehashed_seeds", []))
    pep_chunks = len(pep_new.get("independently_audited_feature_chunks", []))
    pep_head_audited = len(pep_new.get("independently_audited_head_seeds", []))
    if plm_simple:
        assert plm_simple.get("status") == "complete" and plm_simple.get("independent_differences") == 0
    selected_total = (cpu["selected_training_results"] + her2_baselines.get("new_selected_training_results", 0)
        + plm_simple.get("selected_scientific_runs", 0) + plm_controls.get("additional_selected_scientific_runs", 0)
        + plm_binary.get("selected_conditions", 0))
    candidate_total = (cpu["candidate_fits"] + her2_baselines.get("new_candidate_fits", 0)
        + plm_simple.get("scientific_candidate_fits", 0) + plm_controls.get("additional_candidate_fits", 0)
        + plm_binary.get("candidate_fits", 0))
    rde_total_rows = rde_joined.get("coverage", rde_progress.get("rows_completed", 0))
    if rde_joined:
        assert rde_joined["missing"] == 0 and rde_joined["duplicates"] == 0
        assert sha(Path(rde_joined["predictions"]["path"])) == rde_joined["predictions"]["sha256"]
    if rde_canary_complete:
        assert sha(ROOT / "runs/uniair-rde-SI-canary-continuation-v3/artifacts/predictions.csv") == rde_canary["prediction_sha256"]
    remaining_dta = 150 - dta["complete_logical_units"]
    assert len(manifest["views"]) == 13
    assert cpu["passed"] is True and not cpu["errors"]
    assert len(source["methods"]["methods"]) == 8
    assert len(dta["groups"]) == 15 and not dta["duplicate_conflicts"]
    keys = {(r["view"], r["method"], r["seed"]) for r in dta["records"]}
    assert len(keys) == len(dta["records"]) == dta["complete_logical_units"]
    assert all(r["prediction_hash_valid"] for r in dta["records"])

    traditional = []
    for run in cpu["per_run"]:
        path = ROOT / "runs" / run["run_id"] / "mean-sd-metrics.csv"
        if not path.is_file():
            continue
        with path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                row.update(run_id=run["run_id"], category=run["category"], evidence=str(path))
                traditional.append(row)
    assert traditional, "No completed metric tables found"
    write_csv("traditional-metrics-all-panels.csv", ["run_id", "category", "view_id", "task", "model", "split", "metric", "mean", "sd", "valid_seed_count", "seed_count", "n", "evidence"], traditional)
    for row in traditional:
        if row.get("split") == "test" and row.get("seed_count"):
            assert int(row["seed_count"]) == 10

    generic = [dict(row) for row in traditional if row["category"] == "training"]
    metric_sources = []
    for run_id, category, rel in [
        ("her2-strict-local-baselines-v1", "HER2 strict local manual features", "runs/her2-strict-local-baselines-v1/ten-seed-mean-sd.csv"),
        ("plm-simple-v1", "Frozen ESM2-t6-8M", "runs/plm-simple-v1/heads/mean-sd-metrics.csv"),
        ("plm-cohort-manual-controls-v1", "Manual features on identical ESM cohorts", "runs/plm-cohort-manual-controls-v1/mean-sd-metrics.csv"),
        ("plm-classification-contact-v1", "Frozen ESM2-t6-8M classification and residue contact", "runs/plm-classification-contact-v1/heads/mean-sd-metrics.csv"),
    ]:
        path = ROOT / rel
        if not path.is_file():
            continue
        with path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        for row in rows:
            row.update(run_id=run_id, category=category, evidence=str(path))
            if not row.get("task"):
                row["task"] = "affinity" if row.get("endpoint") == "pKd" else "effect"
            assert int(row["seed_count"]) == 10
            generic.append(row)
        metric_sources.append(dict(path=str(path), sha256=sha(path), rows=len(rows)))
    endpoint_source = paths["generic_endpoint_declarations"]
    endpoint_map = source["generic_endpoint_declarations"]["by_view_id"]
    endpoint_source_sha = sha(endpoint_source)
    endpoint_filled = 0
    for row in generic:
        declared = endpoint_map[row["view_id"]]
        assert row["run_id"] in declared["run_ids"]
        assert row["task"] == declared["task"], "Declared task differs from original contract"
        if row.get("endpoint"):
            assert row["endpoint"] == declared["endpoint"], "Declared endpoint conflicts with existing label"
        else:
            row["endpoint"] = declared["endpoint"]
            endpoint_filled += 1
        assert row["endpoint"] and declared["endpoint_inferred_from_metrics"] is False
        for proof in declared["evidence"]:
            assert sha(Path(proof["path"])) == proof["sha256"], "Endpoint contract changed"
        row["endpoint_declaration_ref"] = str(endpoint_source)
        row["endpoint_declaration_sha256"] = endpoint_source_sha
    generic_groups = {(r["run_id"], r["view_id"], r["model"]) for r in generic}
    assert len(generic_groups) * 10 == selected_total, "Generic summary coverage differs from delivered fit receipts"
    generic_keys = [(r["run_id"], r["view_id"], r["model"], r["split"], r["metric"]) for r in generic]
    assert len(set(generic_keys)) == len(generic_keys), "Duplicate aggregate metric identity"
    write_csv("generic-completed-metrics-all-panels.csv", ["run_id", "category", "view_id", "task", "endpoint", "model", "split", "metric", "mean", "sd", "valid_seed_count", "seed_count", "n", "evidence", "endpoint_declaration_ref", "endpoint_declaration_sha256"], generic)
    generic_audit = source.get("generic_aggregation_audit", {})
    if generic_audit:
        assert generic_audit["passed"] is True and generic_audit["numeric_errors"] == 0
        assert sha(OUT / "generic-completed-metrics-all-panels.csv") == generic_audit["repaired_snapshot_sha256"]

    dta_rows = []
    for row in dta["records"]:
        for metric, value in row["metrics"].items():
            if metric not in {"n", "direction_n"}:
                dta_rows.append(dict(view=row["view"], method=row["method"], seed=row["seed"],
                    metric=metric, value=value, test_n=row["n"]["test"], evidence=row["path"],
                    prediction_sha256=row["prediction_sha256"],
                    runtime=json.dumps(row.get("runtime", {}), ensure_ascii=False, sort_keys=True)))
    write_csv("dta-existing-seed-metrics.csv", ["view", "method", "seed", "metric", "value", "test_n", "evidence", "prediction_sha256", "runtime"], dta_rows)
    write_csv("dta-completion-groups.csv", ["view", "method", "n_seed", "completed_seeds", "missing_seeds", "ten_seed_complete"],
        [dict(view=r["view"], method=r["method"], n_seed=len(r["seeds"]),
            completed_seeds=",".join(map(str, r["seeds"])), missing_seeds=",".join(map(str, r["missing_seeds"])),
            ten_seed_complete=r["ten_seed_complete"]) for r in dta["groups"]])
    write_csv("source-task-eligibility.csv", ["source", "task", "status", "qualification"], source["eligibility"]["cells"])

    completed_pep = [r for r in interaction["panels"] if r["id"].startswith("PepInter") and "ProfAff" not in r["id"]]
    swing = next(r for r in interaction["panels"] if r["id"].startswith("SWING"))
    assert len(completed_pep) == 4 and all(r["seeds"] == list(range(10)) for r in completed_pep)
    unresolved = [
        f"Five DTA common-data tracks: {remaining_dta} of150 logical seed tasks remain uncompleted in this timestamped census.",
        f"Controlled-hash SWING classification has {swing_audited}/10 independently audited results, {swing_local}/10 fully rehashed local deliveries; affinity adaptations separate.",
        f"PepInter native classification has {pep_chunks}/8 independently audited feature chunks and {pep_head_audited}/10 audited heads; full-data allparameter finetuning not complete.",
        "Full UniAIR/MoFPE and ten-seed native training are not complete; native RDE component progress is recorded separately.",
        "Strict chemically/experimentally certified mutation-effect gold and new-family independent external validation remain unavailable.",
        "Eight-method supervised contact prediction is not supported by their native outputs; manual-feature and frozen-ESM2 contact classifiers were executed.",
    ]
    status = dict(schema="fourtask.delivery-evidence.v2", at=at, full_requested_objective_complete=False,
        scientific_batch_status="continuation_in_progress_original_batch_retained" if authorization.is_file() else "closed_at_original_deadline",
        original_scientific_deadline="2026-10-23T01:31:20+00:00",
        deadline_source="C:/Users/ciheb/.codex/skills/paper-reproduction/SKILL.md; not a user-specified budget",
        continued_scientific_authorization_status="explicit direct human reply: 取消总时限，继续直到全部完成" if authorization.is_file() else "pending; no new authorization receipt inferred",
        campaign_total_wall_clock_cap_cancelled=authorization.is_file(),
        administrative_only_snapshot=True, new_fits=0, new_model_predictions=0,
        data_views=[{k: r.get(k) for k in ("id", "task", "endpoint", "rows", "split_counts")} for r in manifest["views"]],
        traditional={k: cpu[k] for k in ("selected_training_results", "candidate_fits", "fixed_external_applications", "fixed_common_subset_evaluations", "fresh_metric_cells_recomputed")},
        generic_formal_training_totals=dict(selected_results=selected_total, candidate_fits=candidate_total,
            runtime_canaries_counted=False, original_cpu_selected=cpu["selected_training_results"],
            her2_strict_selected=her2_baselines.get("new_selected_training_results", 0),
            frozen_plm_selected=plm_simple.get("selected_scientific_runs", 0),
            matched_manual_control_selected=plm_controls.get("additional_selected_scientific_runs", 0),
            frozen_plm_classification_contact_selected=plm_binary.get("selected_conditions", 0)),
        dta=dict(completed_logical_seed_units=len(keys), expected_logical_seed_units=150,
            groups=dta["groups"], complete_ten_seed_groups=sum(g["ten_seed_complete"] for g in dta["groups"])),
        interaction_panels=interaction["panels"], asset_transfers=interaction.get("transfers", []),
        interaction_continuation=continuation,
        official_checkpoint_local_transfer=interaction.get("official_checkpoint_local_transfer"),
        uniair=dict(full_UniAIR_MoFPE_native_inference_completed=False, full_framework_ten_seed_training_completed=False,
            rde_canary_completed=rde_canary_complete, rde_canary_prediction_rows=rde_rows,
            original_419_phase_progress=rde_progress, joined_419_inference=rde_joined,
            continuation_evidence_index=source.get("uniair_continuation", {}),
            native_RDE_ten_seed_training_completed=rde_ten_complete,
            native_RDE_ten_seed_summary=rde_summary,
            native_rde_formal_progress=rde_formal, native_rde_execution_successful_seeds=rde_nseed,
            partial_seed_metrics_not_aggregated=True,
            fixed_inference_is_not_ten_seed_training=True),
        additional_external=hu_external,
        additional_pepbi_candidate_external=source.get("pepbi_conditional_external", {}),
        additional_her2_strict_baselines=her2_baselines,
        additional_frozen_plm=plm_simple,
        additional_matched_manual_controls=plm_controls,
        additional_frozen_plm_classification_contact=plm_binary,
        generic_metric_aggregation_independent_audit=generic_audit,
        completed_generic_metric_table=dict(path=str(OUT / "generic-completed-metrics-all-panels.csv"),
            metric_rows=len(generic), model_view_groups=len(generic_groups), selected_training_results=10 * len(generic_groups),
            missing_endpoints=0, endpoint_cells_filled_from_original_contracts=endpoint_filled,
            endpoint_declaration_path=str(endpoint_source), endpoint_declaration_sha256=endpoint_source_sha,
            added_metric_sources=metric_sources),
        unresolved=unresolved,
        evidence_inputs={k: dict(path=str(p), sha256=sha(p)) for k, p in paths.items()},
        caveats=["Prepared jobs are not completed fits.", "View counts, seed results and derived contrasts are not additive independent biological samples.",
            "DTA aggregate SD mixes execution environments; backend-specific analysis is required.",
            "Transfer status is the timestamped owner snapshot; .part files are not completed local assets."])
    (OUT / "STATUS.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    previous = OUT / "previous-root-STATUS-v1.json"
    if (ROOT / "STATUS.json").is_file() and not previous.exists():
        shutil.copyfile(ROOT / "STATUS.json", previous)
    shutil.copyfile(OUT / "STATUS.json", ROOT / "STATUS.json")

    lines = ["# 四来源、四任务基准：阶段结果与未完成清单", "", f"生成时间：{at}。本报告读取冻结输入、既有预测和执行收据；本次汇总新增拟合与模型预测均为0。", "",
        f"已完成13个原始数据视图及16个来源—任务资格登记，另附ProfAff HU条件外测扩展。通用基线正式累计{selected_total}个选中结果、{candidate_total}次候选拟合：原CPU {cpu['selected_training_results']}、HER2严格局部 {her2_baselines.get('new_selected_training_results', 0)}、冻结ESM2亲和力/效应 {plm_simple.get('selected_scientific_runs', 0)}、其对齐手工对照 {plm_controls.get('additional_selected_scientific_runs', 0)}及冻结ESM2分类/接触 {plm_binary.get('selected_conditions', 0)}个。五个DTA迁移对照累计通过验收{len(keys)}/150个正式逻辑种子任务。PepInter四个冻结骨干组件面板各10种子完成；SWING新hash0分类独审{swing_audited}/10，旧9种子保留。UniAIR原生RDE固定推理累计{rde_total_rows}/419条；新严格局部划分已有{rde_nseed}/10个种子真实成功退出，权重/指标独立复核另列，完整框架继续推进。**用户要求的八方法完整流程尚未完成。**", "",
        "## 数据与任务", "", "|来源/视图|实际规模|训练/验证/测试|端点与用途|", "|---|---:|---|---|"]
    display = {
        "ppikb_kd_source_cold_scope_v2": ("PPIKB来源/肽依赖冷", "pKd主任务"),
        "ppikb_kd_target_cold_scope_v2": ("PPIKB参考靶标同源冷", "同一9,116观测的另一个划分"),
        "pepinter_classification_target_cold": ("PepInter分类", "结构阳性/作者构造负例"),
        "pepaff_mixed_target_cold": ("PepAffDB", "作者mixed pAffinity，单独诊断"),
        "ppikb_effect_metadata_silver_source_cold": ("PPIKB改动效应", "同来源元数据匹配的silver ΔpKd"),
        "profaff_pKd_domain_backbone_all162_external": ("ProfAff外测", "直接FP pKd；112标准骨架+50PTM"),
        "profaff_PTM_delta_pKd_external": ("ProfAff PTM效应外测", "42对共享68观测、2骨架17域"),
        "uniair_her2_effect_local_variant_diagnostic": ("UniAIR HER2局部诊断", "作者DDG；Kd升高对应正值，物理单位未认证"),
        "uniair_her2_pKd_protein_extension_external": ("UniAIR HER2蛋白扩展外测", "同419观测；H120/L107抗体变量域输入"),
        "ppikb_contact_experimental_64complex_dependency_cold_v2": ("PPIKB实验接触", "64复合物、8,625已观察残基、1,155接触"),
    }
    for v in manifest["views"]:
        if v["id"] not in display:
            continue
        name, note = display[v["id"]]
        splits = v["split_counts"]
        split = "/".join(str(splits[k]) for k in ("train", "validation", "test")) if "train" in splits else f"外测 {splits.get('external_test')}"
        lines.append(f"|{name}|{v['rows']:,}|{split}|{note}|")
    lines += ["", "PPIKB共9,116条：7,120条标准、1,996条按注释NC；NC细分为633条非天然/D/骨架、1,000条PTM、265条混合、98条其他。原21,845条与旧9,619条范围输入保留。568条结构—注释冲突保留标记并另有固定预测敏感性分析。", "",
        "各视图共享原始观测，数量按生物测量去重解释：PPIKB两套pKd拆分不相加；ProfAff112是162的子集；HER2多个视图共享419行；64个实验结构包含旧3结构pilot。几何接触定义为5Å重原子距离，仅为已观察残基生成标签。", "",
        "亲和力报告MAE、RMSE、R²、Pearson/Spearman与bias；效应另报告方向及依赖组结果；分类/接触报告AUROC、AUPRC、F1、MCC、balanced accuracy与Brier。接触另按复合物宏平均。十种子的±为拟合种子样本标准差；同一固定拆分上的十次训练不等于十个独立生物体系。", "",
        "## 八篇前人方法的实际执行", "", "|方法|来源冷 pKd /10|靶标冷 pKd /10|silver效应 /10|执行层级|", "|---|---:|---:|---:|---|"]
    by = {(g["view"], g["method"]): g for g in dta["groups"]}
    views = ["ppikb_kd_source_cold_scope_v2", "ppikb_kd_target_cold_scope_v2", "ppikb_effect_metadata_silver_source_cold"]
    for method in ["GraphDTA-GIN", "MGraphDTA", "DGDTA-CL", "DeepNC-GEN", "GS-DTA"]:
        counts = [len(by[(view, method)]["seeds"]) for view in views]
        lines.append(f"|{method}|{counts[0]}|{counts[1]}|{counts[2]}|原作者网络在肽分子数据重训；DTA迁移对照|")
    lines += [f"|PepInter|组件10+10|组件10+10|ProfAff派生诊断|标准2919与骨架6336单列；新原生分类独审{pep_head_audited}/10，全数据整骨干微调未完成|",
        f"|SWING|0|0|0|旧分类9种子保留；新hash0分类独审{swing_audited}/10，本地全保全{swing_local}/10|",
        f"|UniAIR|0|0|RDE执行成功{rde_nseed}/10|严格局部293/63/63；419条固定推理另列，完整MoFPE未完成|", "",
        "五个DTA属于分子—蛋白亲和力架构。共同数据训练保留作者网络及已披露修正；DGDTA原文第7页明确采用MSE，DGDTA-CL仅是旧运行标识，不代表另一个对比学习模型。旧报告中关于缺失对比预训练的说法已纠正，依据见dgdta-identity-correction.json。各方法无原生监督接触输出，attention或界面输入不作为接触位点模型验收。", "",
        f"正式DTA累计通过验收{len(keys)}/150，齐10的主组合数为{sum(g['ten_seed_complete'] for g in dta['groups'])}。GraphDTA来源冷pKd十种子MAE1.5481±0.0439，test=1,014。原批次59个单元/118候选完整审计保持；累计表优先读取accepted-details指针，新增单元的候选权重、验证/测试预测和实际退出证据已逐项核验，最终另做整表审计。另有633条非天然化学子任务GraphDTA十种子与五方法smoke，独立归档。CPU/GPU、Torch/RDKit与MGraph无cuDNN兼容后端差异随收据保留；DTA合并SD包含环境差异。", "",
        "## 传统与冻结表征基线", "", "常数/类别先验、Ridge或LogisticRegression、RandomForest、ExtraTrees、HistGradientBoosting共五族；每族两个预定候选，验证集选优，种子0–9。序列手工特征和带手性Morgan2048+10分子描述符+蛋白AAC分别成轨。", "",
        "|特征及模型|来源冷pKd MAE，test1,014|靶标冷pKd MAE，test1,383|", "|---|---:|---:|"]
    for run, feature, model in [("cpu-v2", "序列手工", "constant"), ("cpu-v2", "序列手工", "random_forest"),
        ("cpu-v2", "序列手工", "extra_trees"), ("cpu-molecular-v1", "手性Morgan", "random_forest"),
        ("cpu-molecular-v1", "手性Morgan", "extra_trees")]:
        vals = []
        for view in views[:2]:
            row = next((r for r in traditional if r["run_id"] == run and r.get("view_id") == view and r.get("model") == model and r.get("split") == "test" and r.get("metric") == "mae"), None)
            vals.append(f"{float(row['mean']):.4f} ± {float(row['sd']):.4f}" if row else "—")
        lines.append(f"|{feature} / {model}|{vals[0]}|{vals[1]}|")
    lines += ["", "全部550个选中结果和1,100个候选拟合权重已保留；另有250次固定外部模型应用及100次固定共同子集评分。传统基线9,400项主要指标独立复算零差异；64结构接触另有2,600项宏指标检查。原先scope_v1排除错误、训练失败和不利结果均保留。", "",
        "PepInter冻结监督骨干+原生回归头的实际面板如下，测试分母不同，应按覆盖解释：", "", "|组件面板|覆盖观测|测试数|pKd MAE，10种子|", "|---|---:|---:|---:|"]
    for panel in completed_pep:
        lines.append(f"|{panel['id']}|{panel['coverage_rows']:,}|{panel['test_rows']}|{fmt(panel['mean_sd'])}|")
    lines += ["", "标准2919面板全部是标准残基；骨架6336面板含5,931标准+405注释NC，输入仅接受原样20AA字符，编码器不辨任意非天然残基/PTM化学。骨架面板来源冷测试683条中60NC，靶标冷946条中88NC。四面板的80个候选头及1个保留副本均已本地校验，选中模型40个。", "",
        f"SWING分类实际test=2,362，9个有效种子AUROC {fmt(swing['mean_sd'], 'auroc')}，AUPRC {fmt(swing['mean_sd'], 'auprc')}。原seed0虽完成16轮训练，测试超时；重载原验证概率最大偏差0.22843，超过预注册1e-7，所以恢复测试在门槛前停止。没有把失败种子计入均值，也没有静默修改推理随机机制。", "",
        f"续行批次在进程启动前固定Python hash状态，沿用16轮训练、16轮推理和72维Doc2Vec。新分类已独审{swing_audited}/10，完全本地回流并重哈希{swing_local}/10；与旧9种子分开。PepInter新原生2304→1152→1分类头及Focal损失有{pep_chunks}/8个特征块独审、{pep_head_audited}/10个正式头独审。单步全参可行性测试单列，不计完整基准。", "",
        "## 外部验证与数据暴露", "", "ProfAff162按有条件domain/backbone外测使用。与当前PPIKB精确序列对与DOI交集0，但62条存在目标域包含关系；它衡量来源/域视图变化，不能作为全新家族测试。四个PepInter面板各10个固定头已外测。原监督PepInter骨干曾接触公开PepAff训练记录，本轮PepAff测试520条中498条精确命中公开训练表，该检查点在此测试上的结果存在直接暴露。", "",
        "ProfAff42个PTM对照由68个原观测构成。序列骨架模型在每对上有效输入相同，从实际已保存预测相减得到全部Δ预测0；MAE0.4413，十种子SD0。这是模型对化学差异不敏感的诊断结果。", "",
        f"新增HU外测已完成{hu_external.get('fixed_model_applications', 0)}次固定序列模型应用，覆盖16,806条测量情境、16,772个独特输入对、218个域和419个肽名称，训练与调参新增0。全部384,600项指标独立复算零差异。它是holdup校准换算pKd，与直接FP分轨；排序相关性接近零，全部R²负，保留原结果。此数据来自已使用过FP的来源，属于条件性assay-shift外测。", "",
        "新增PEPBI候选外测完成100次固定模型应用，覆盖27个独特输入、13个构建体、5个结合组和4篇ITC来源，保留2,700行计算结果。20,480项数值与逐组文件核对零差异，新增训练/调参为0。两套PPIKB训练面板全部模型微R²均为负；实验化学/缓冲条件与同源预训练暴露尚未完全认证，定位为来源去重后的条件外测，认证独立集仍为0。", "",
        "## 正在补齐的工作", "",
        f"- 五DTA主轨尚缺{remaining_dta}个逻辑种子；完整八方法共同任务没有完成。",
        f"- SWING新hash0分类独审{swing_audited}/10，本地全文件重哈希{swing_local}/10；两套pKd适配按冻结队列运行，旧失败保留。",
        f"- PepInter新原生Focal分类头独审{pep_head_audited}/10；全数据整骨干微调与全部新产物的本地回流另行核验。",
        f"- UniAIR原生RDE正式执行成功{rde_nseed}/10；完整MoFPE训练继续推进。正文访问缺口单列，合法官方补充PDF以真实角色支撑明确组件范围。",
        "- 严格同条件化学认证的改动效应金标、新家族独立外部集与更多原生接触模型仍是数据/方法缺口。", "",
        ("原科学批次已按既有合同在2026-10-23 01:31:20 UTC结束，旧进程已核验终态。用户随后明确回复“取消总时限，继续直到全部完成”，本轮现按新延续合同继续补齐。原科学合同、起止、失败和超时保留；每个新作业仍有独立timeout、进程组和资源预算。上表整合原批次及本次续行的已核证据，准备任务单列。" if authorization.is_file() else "科学批次已按既有合同在2026-10-23 01:31:20 UTC结束，自有科学进程核验为空。这个10小时总上限来自本机paper-reproduction技能，而非用户预算；取消此上限的用户选择仍待回复。现阶段继续既有结果复算与纯归档，原科学合同、起止、失败和超时不改写。"), "",
        "## 可检查的文件", "",
        f"- {link(ROOT / 'data/view_manifest.json', '13视图、固定分区与源路径')}。",
        f"- {link(ROOT / 'data/source_task_matrix.json', '16来源—任务资格')}。",
        f"- {link(paths['dta'], 'DTA逐种子收据及缺失种子')}。",
        f"- {link(paths['dta_artifacts'], 'DTA59成功单元/118候选本地完整性核验')}。",
        f"- {link(ROOT / 'methods/interaction/REPORT.interaction.md', 'PepInter/SWING完整结果与暴露核查')}。",
        f"- {link(ROOT / 'baselines/recovery-20261023/CPU-RECOVERY-AUDIT.json', '传统基线完整审计')}。",
        f"- {link(ROOT / 'reports/profaff-HU-external/REPORT.zh-CN.md', '新增ProfAff HU十种子条件外测')}。",
        f"- {link(ROOT / 'baselines/common-prediction-comparison-v2.md', '相同测试ID的固定预测比较')}。",
        f"- {link(ROOT / 'reports/her2-strict-local/REPORT.zh-CN.md', 'HER2严格局部DDG及pKd十种子传统对照')}。",
        f"- {link(ROOT / 'baselines/plm-simple-v1/RESULTS.md', '冻结小型ESM2三视图十种子基准')}，运行时canary另计。",
        f"- {link(ROOT / 'baselines/plm-simple-v1/controls/RESULTS.md', '完全对齐训练/验证/测试ID的手工特征对照')}。",
        f"- {link(ROOT / 'baselines/plm-classification-contact-v1/RESULTS.md', '冻结ESM2分类和接触位点十种子完整结果')}，100个选中结果/200候选，全文件本地校验；微指标与12复合物宏指标分别报告。",
        f"- {link(ROOT / 'data/pepbi-external-audit-20261023/REPORT.zh-CN.md', 'PEPBI329行的副本、测量与外测资格审计')}，27个条件候选另列，已认证独立集仍为0。",
        f"- {link(ROOT / 'reports/pepbi-conditional-external-v1/REPORT.zh-CN.md', 'PEPBI27候选的100个固定模型外测结果')}，包含全部不利结果、逐来源/结合组宏指标与本地保全收据。",
        f"- {link(ROOT / 'reports/root-generic-aggregation-independent-v1/REPORT.zh-CN.md', '通用基准汇总的独立验收')}：41,850项字段检查无错误，原1,190个缺失端点由冻结合同补齐，数值保持不变。",
        f"- {link(ROOT / 'reports/dgdta-identity-correction.json', 'DGDTA原文MSE定义与旧运行名称校正')}。",
        f"- {link(ROOT / 'protocol/DATA_SCOPE_ADDENDUM-20261023.md', 'PPIKB物种范围与原始来源标注核查')}。",
        f"- {link(ROOT / 'reports/figures-v1/report.pdf', '六页传统结果图及完整图注')}；该PDF为图报告，叙述说明以本文件为准。",
        f"- {link(ROOT / 'reports/contact-site-gallery-v3/README.zh-CN.md', '全部12个留出复合物的接触预测图')}，含逐残基十种子均值、SD和原阈值判定比例，独审527项无差异。",
        f"- {link(ROOT / 'literature/systematic-2021-2026/REPORT.zh-CN.md', '近五年前作目录与作者资源实物核查')}，包含用户参考清单逐项补差与来源重叠证据。",
        f"- {link(OUT / 'traditional-metrics-all-panels.csv', '传统基线完整指标表')}，{link(OUT / 'dta-existing-seed-metrics.csv', 'DTA已有逐种子指标表')}，{link(OUT / 'STATUS.json', '可机读阶段状态')}。", ""]
    lines += [f"- {link(OUT / 'generic-completed-metrics-all-panels.csv', '全部已交付通用基准的统一指标表')}：{len(generic_groups)}个模型—视图组合，各10种子，合计{selected_total}个选中结果。不同测试覆盖、端点与表征保留原标签，表格合并不改变可比性。", ""]
    if rde_ten_complete:
        rde_row = next(row for row in rde_summary["summary"] if row["model"] == "native_RDE")
        et_row = next(row for row in rde_summary["summary"] if row["model"] == "extra_trees")
        lines += ["## HER2严格局部任务：RDE十种子完成", "",
            f"原生RDE组件在固定63条测试记录上的MAE为{rde_row['MAE_mean']:.6f} ± {rde_row['MAE_sample_SD']:.6f}，RMSE为{rde_row['RMSE_mean']:.6f} ± {rde_row['RMSE_sample_SD']:.6f}，Spearman为{rde_row['Spearman_mean']:.6f} ± {rde_row['Spearman_sample_SD']:.6f}。同一测试ID的ExtraTrees手工对照MAE为{et_row['MAE_mean']:.6f} ± {et_row['MAE_sample_SD']:.6f}。", "",
            "20个真实候选拟合、10个不同初始化、验证集选参及全部终态均已独立核验。数值采用author_DDG标量；均值与样本SD反映同一固定拆分上的训练种子变化，任务包含一个抗体—靶标背景。该结果是RDE组件适配，完整四专家MoFPE另行推进。", "",
            f"详见{link(paths['rde_ten_seed_summary'].parent / 'mean-and-sample-SD.csv', 'RDE与五类传统对照的十种子指标表')}。", ""]
    (OUT / "阶段结果与未完成清单.md").write_text("\n".join(lines), encoding="utf-8")
    receipt = dict(at=at, administrative_only=True, new_fits=0, new_model_predictions=0,
        inputs=status["evidence_inputs"], outputs={p.name: dict(bytes=p.stat().st_size, sha256=sha(p))
            for p in OUT.iterdir() if p.is_file() and p.name != "build-receipt.json"},
        completed=False, checks=dict(data_views=13, registered_methods=8, dta_unique_complete=len(keys),
            dta_groups=15, traditional_selected=cpu["selected_training_results"], pepinter_ten_seed_panels=4,
            swing_valid_seeds=len(swing["seeds"])))
    (OUT / "build-receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(receipt["checks"], ensure_ascii=False))


if __name__ == "__main__":
    main()
