"""Replace only the isolated recovery metadata coordinate;30spec bytes unchanged."""
import copy
import json
from pathlib import Path

import prepare_campaign as pc

BASE = Path(__file__).resolve().parent
PROJECT = BASE.parent
REC = BASE / "io-recovery01"
WSL = "/mnt/d/work/科研工作台/research-tasks/peptide-binding-nc-benchmark-20261021"
OLD = "MGraphDTA__target_reference_homology_cold__NC_only__seed08"
NEW = OLD + "__io_recovery01"


if __name__ == "__main__":
    source = BASE / "score-spec-assets-v2" / "evaluation-plan.prebarrier.json"
    plan = copy.deepcopy(pc.read(source))
    scientific = REC / "execution-index-v5-recovery.json"
    eligible = REC / "eligible-training-freeze-index-v5.json"
    row = next(row for row in pc.read(scientific)["units"] if row["unit_id"] == NEW)
    if NEW in plan["units"] or OLD not in plan["units"]:
        raise ValueError("Replace exactlyone old failed coordinate once")
    old_mapping = plan["units"].pop(OLD)
    replacement = copy.deepcopy(old_mapping)
    replacement["selection"] = {"path": row["selection_path"], "sha256": None}
    replacement["checkpoint_path"] = None
    replacement["checkpoint_sha256"] = None
    replacement["fit_spec"] = {"path": row["spec_wsl_path"], "sha256": row["spec_sha256"]}
    plan["units"][NEW] = replacement
    plan["training_index"] = {"path": str(eligible), "sha256": pc.sha(eligible)}
    plan["scientific_execution_index"] = {"path": str(scientific), "sha256": pc.sha(scientific)}
    plan["recovery_provenance"] = {"original_failed_unit": OLD, "active_training_unit": NEW, "root_frozen_recovery_index": {"path": str(REC / "issued-root-v2" / "freeze-index.json"), "sha256": pc.sha(REC / "issued-root-v2" / "freeze-index.json")}, "source_prebarrier_plan": {"path": str(source), "sha256": pc.sha(source)}, "shared_score_specs_changed": False, "original_failed_attempt_retained": True, "root_global_clock_unchanged": True}
    plan["predeclared_auxiliary_classic_RF"] = {"selection_cells": 40, "candidate_fits": 80, "paper_count_contribution": 0, "joint_high_level_root_authorization_required_before_any_holdout": True, "original_NN200_barrier_program_unchanged": True, "terminal_failure_policy": "Only preregistered bounded asset/resource failure may be acknowledged before any holdout score; root must preserve actual receipts, not choose by holdout performance"}
    if len(plan["units"]) != 200 or replacement["score_specs"] != old_mapping["score_specs"]:
        raise ValueError("Recovery metadata must not change the scientific score grid/specs")
    out = BASE / "evaluation-plan-eligible-v5.prebarrier.json"
    pc.write_new(out, plan)
    pc.write_new(BASE / "evaluation-plan-v5-recovery-adoption.json", {"created_at": pc.now(), "new_plan": {"path": str(out), "sha256": pc.sha(out)}, "eligible_training_index": plan["training_index"], "scientific_execution_index": plan["scientific_execution_index"], "unit_keys_replaced": 1, "old_unit": OLD, "new_unit": NEW, "unit_count": 200, "shared_score_spec_changes": 0, "actual_selection_checkpoint_gold_prediction_reads": 0, "scoring_authorized": False})
    print(json.dumps({"plan_path": str(out), "unit_count": 200, "unit_key_replacements": 1, "shared_specs_changed": 0, "scoring_authorized": False}, ensure_ascii=False))
