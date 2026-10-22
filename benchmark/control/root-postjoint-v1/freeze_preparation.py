"""Freeze source/metadata and synthetic evidence; never execute actual workflow."""
import hashlib
import json
import os
import py_compile
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent.parent
WSL = "/mnt/d/work/科研工作台/research-tasks/peptide-binding-nc-benchmark-20261021"
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
read = lambda path: json.loads(Path(path).read_text(encoding="utf-8"))


def local(path):
    return Path("D:/" + path[len("/mnt/d/"):]) if str(path).startswith("/mnt/d/") else Path(path)


def main():
    if (HERE / "SOURCE-FREEZE-v1.json").exists():
        raise FileExistsError("Preserve existing source freeze")
    for name in ("root_postjoint.py", "wsl_prepare.py", "test_root_postjoint.py"):
        py_compile.compile(str(HERE / name), doraise=True)
    command = [sys.executable, "-X", "utf8", "-m", "unittest", "-v", "test_root_postjoint.py"]
    completed = subprocess.run(command, cwd=HERE, capture_output=True, encoding="utf-8", timeout=60, check=False)
    for name, content in (("synthetic.stdout.log", completed.stdout), ("synthetic.stderr.log", completed.stderr)):
        with (HERE / name).open("x", encoding="utf-8") as stream:
            stream.write(content)
    if completed.returncode:
        raise RuntimeError("Synthetic tests failed; source not frozen")
    paths = {HERE / name for name in ("root_postjoint.py", "wsl_prepare.py", "test_root_postjoint.py", "freeze_preparation.py", "README.md", "pool-exit-proof.example.json")}
    for relative in ("execution/runner.py", "evaluation/FROZEN-SCORER-v1.json", "auxiliary-rf-baseline/SOURCE-FREEZE-v1.json", "auxiliary-rf-baseline/score-specs-v1/score-spec-index.json", "control/unit-index-v5-all-recovery.json", "administration/io-recovery01/execution-index-v5-recovery.json", "administration/io-recovery01/eligible-training-freeze-index-v5.json", "administration/postjoint_issue_all.py", "administration/prepare_evaluation_contracts.py", "administration/prepare_rf_score_contracts.py", "administration/prepare_campaign.py", "administration/evaluation-plan-eligible-v5.prebarrier.json", "administration/rf-postjoint-plan.prebarrier-v1.json"):
        paths.add(PROJECT / relative)
    for relative in ("administration/evaluation-plan-eligible-v5.prebarrier.json", "administration/rf-postjoint-plan.prebarrier-v1.json"):
        plan = read(PROJECT / relative)
        for row in plan["code_files"]:
            path = local(row["path"])
            if sha(path) != row["sha256"]:
                raise ValueError("Actual frozen code digest differs")
            paths.add(path)
        if relative.endswith("evaluation-plan-eligible-v5.prebarrier.json"):
            for unit in plan["units"].values():
                for row in unit["score_specs"]:
                    path = local(row["path"])
                    if sha(path) != row["sha256"]:
                        raise ValueError("Frozen NN score spec mutated")
                    paths.add(path)
    for row in read(PROJECT / "auxiliary-rf-baseline/score-specs-v1/score-spec-index.json")["entries"]:
        path = local(row["score_spec_path"])
        if sha(path) != row["score_spec_sha256"]:
            raise ValueError("Frozen RF score spec mutated")
        paths.add(path)
    for relative in ("evaluation/FROZEN-SCORER-v1.json", "auxiliary-rf-baseline/SOURCE-FREEZE-v1.json"):
        source = read(PROJECT / relative)
        mapping = source.get("evaluation_code_sha256", source.get("source_sha256"))
        folder = (PROJECT / relative).parent
        for name, expected in mapping.items():
            path = folder / name
            if sha(path) != expected:
                raise ValueError("Frozen scientific source changed")
            paths.add(path)
    paths.add(PROJECT.parent.parent / "复现/规范/validate_reproduction.py")
    files = []
    for path in sorted(paths, key=str):
        if path.suffix not in (".py", ".json", ".md") or any(word in path.name.lower() for word in ("gold", "predictions")):
            raise PermissionError("Freeze only code/spec metadata")
        files.append({"relative_path": os.path.relpath(path, PROJECT).replace("\\", "/"), "sha256": sha(path)})
    receipt = {"schema": "root-postjoint-explicit-execution-source-freeze.v1", "created_at": datetime.now(timezone.utc).isoformat(), "files": files, "synthetic_tests": {"command": command, "exit_code": completed.returncode, "tests": 10, "stdout_sha256": sha(HERE / "synthetic.stdout.log"), "stderr_sha256": sha(HERE / "synthetic.stderr.log")}, "actual_selection_weight_gold_prediction_reads": 0, "actual_authorizations_issued": 0, "actual_model_or_score_processes_started": 0, "NN_scientific_index_sha256": "c7b3bde68c9a741c0ac3f255a825e4a55dd7234e2b4e6d48f212fee8d5609ab1", "NN_pool_index_sha256": "fe51a0d03f4f9c08e710e9d8b582d56c497d8c59dc5d14e8cbc6e6d8b41e51d2", "deadline": "2026-10-22T01:45:00+00:00", "current_runtime_permission": False}
    with (HERE / "SOURCE-FREEZE-v1.json").open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"files": len(files), "tests": 10, "actual_workflow_executions": 0, "source_freeze_sha256": sha(HERE / "SOURCE-FREEZE-v1.json")}))


if __name__ == "__main__":
    main()
