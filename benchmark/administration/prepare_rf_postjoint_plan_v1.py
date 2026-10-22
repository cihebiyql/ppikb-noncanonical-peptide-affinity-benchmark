"""Join frozen RF scoring code/spec metadata; no actual selections or scores read."""
from pathlib import Path
import json

import prepare_campaign as pc

BASE = Path(__file__).resolve().parent
PROJECT = BASE.parent
RF = PROJECT / "auxiliary-rf-baseline"
CONTROL = PROJECT / "control"
WSL = "/mnt/d/work/科研工作台/research-tasks/peptide-binding-nc-benchmark-20261021"


def wsl(path):
    return WSL + "/" + str(Path(path).relative_to(PROJECT)).replace("\\", "/")


if __name__ == "__main__":
    source = pc.read(RF / "SOURCE-FREEZE-v1.json")
    launch_root = CONTROL / "rf-score-launch-v1"
    frozen_path = launch_root / "FROZEN-RF-SCORE-LAUNCHER-v1.json"
    frozen = pc.read(frozen_path)
    for name, expected in frozen["source_sha256"].items():
        if pc.sha(launch_root / name) != expected:
            raise ValueError("Final RF postjoint launcher changed after mechanical freeze")
    code_paths = [launch_root / name for name in ("rfs_common.py", "rf_score_pool.py", "rf_score_unit.py")] + [CONTROL / "rf-launch-v1" / "rf_common.py", PROJECT / "launch" / "common.py", PROJECT / "evaluation" / "metrics_stable.py"] + [RF / name for name in source["source_sha256"]]
    code_files = [{"path": wsl(file), "sha256": pc.sha(file)} for file in code_paths]
    for name, expected in source["source_sha256"].items():
        if pc.sha(RF / name) != expected:
            raise ValueError("Frozen RF worker source changed")
    specs_path = RF / "score-specs-v1" / "score-spec-index.json"
    if pc.sha(specs_path) != source["artifact_sha256"]["score-specs-v1/score-spec-index.json"]:
        raise ValueError("Frozen six scoring specs index changed")
    units = pc.read(RF / "specs-v1" / "task-spec-index.json")["units"]
    plan = {"schema": "auxiliary-RF-postjoint-stage-plan.v1", "root_postjoint_RF_scoring_authorized": False, "authorization": None, "joint_barrier": None, "NN_barrier": None, "RF_barrier": None, "live_cpu_proof": {"path": wsl(CONTROL / "rf-live-resource-v1.json"), "sha256": pc.sha(CONTROL / "rf-live-resource-v1.json")}, "code_files": code_files, "source_freeze": {"path": wsl(RF / "SOURCE-FREEZE-v1.json"), "sha256": pc.sha(RF / "SOURCE-FREEZE-v1.json")}, "launcher_freeze": {"path": wsl(frozen_path), "sha256": pc.sha(frozen_path)}, "score_spec_index": {"path": wsl(specs_path), "sha256": pc.sha(specs_path)}, "score_root": WSL + "/auxiliary-rf-baseline/rf-scores-v1", "pool_output_root": WSL + "/control/rf-score-launch-v1/pool-runs", "units": {unit["unit_id"]: {"selection": {"path": unit["selection_path"], "sha256": None}, "model_path": None, "model_sha256": None} for unit in units}, "fixed_unit_count": 40, "fixed_score_count": 120, "fixed_prediction_rows": 53160, "fixed_timeout_seconds": 1800, "original_global_deadline": "2026-10-22T01:45:00+00:00", "paper_count_contribution": 0, "source_payloads_read": 0, "gold_predictions_selections_models_arrays_opened": 0, "actual_score_processes_launched": 0}
    output = BASE / "rf-postjoint-plan.prebarrier-v1.json"
    pc.write_new(output, plan)
    print(json.dumps({"plan_path": str(output), "code_proofs": len(code_files), "units": len(units), "actual_score_calls": 0}, ensure_ascii=False))
