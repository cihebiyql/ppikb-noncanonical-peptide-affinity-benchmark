"""Execute only the root-authorized original administrative archive interfaces."""
import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent; PROJECT = HERE.parent.parent
sha = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
parser = argparse.ArgumentParser(); parser.add_argument("stage", choices=("archive", "attach", "validate")); args = parser.parse_args()
if datetime.now(timezone.utc) >= datetime.fromisoformat("2026-10-22T01:45:00+00:00"): raise TimeoutError("Original project cutoff reached")
proof = json.loads((HERE / "archive-inputs.actual-v2.json").read_text(encoding="utf-8"))
assert proof["root_result_archival_authorized"] is True and proof["root_accept_reviewed_records"] is True
assert sha(proof["CUDA_chain"]["path"]) == proof["CUDA_chain"]["sha256"] == "d2338c08ad35006eac485064767c56c95c0b818515a98e813273ac9b8f5b128f"
f1 = PROJECT / "administration/cuda-recovery02-hostexit-v2/f1"
commands = {
    "archive": [sys.executable, "-X", "utf8", str(PROJECT / "administration/assemble_postjoint_archive.py"), "--inputs", str(HERE / "archive-inputs.actual-v2.json"), "--out", str(PROJECT / "administration/a1")],
    "attach": [sys.executable, "-X", "utf8", str(PROJECT / "administration/cuda-recovery02-hostexit-v2/attach_archive_lineage.py"), "--root-attach-final-lineage-authorized", "--root-review-accept-lineage", "--index", str(PROJECT / "administration/a1/standard-result-index.json"), "--chain", proof["CUDA_chain"]["path"], "--out", str(f1)],
    "validate": [sys.executable, "-X", "utf8", str(PROJECT / "administration/validate_stage_result_index.py"), "--index", str(f1 / "standard-result-index.with-CUDA-lineage.json"), "--out", str(PROJECT / "administration/v1")]
}
stdout, stderr = HERE / (args.stage + ".actual.stdout.log"), HERE / (args.stage + ".actual.stderr.log")
started = datetime.now(timezone.utc).isoformat()
with stdout.open("xb") as out, stderr.open("xb") as err:
    child = subprocess.Popen(commands[args.stage], stdout=out, stderr=err)
    try: code = child.wait(timeout=600)
    except subprocess.TimeoutExpired:
        child.kill(); child.wait(); code = child.returncode
        raise
receipt = {"stage": args.stage, "argv": commands[args.stage], "pid": child.pid, "exit_code": code, "started_at": started, "ended_at": datetime.now(timezone.utc).isoformat(), "stdout": {"path": str(stdout), "sha256": sha(stdout)}, "stderr": {"path": str(stderr), "sha256": sha(stderr)}, "actual_metadata_only": True, "scientific_processes_started": 0, "raw_model_gold_prediction_bytes_read_by_controller": 0}
with (HERE / (args.stage + ".actual-exit.json")).open("x", encoding="utf-8") as stream: json.dump(receipt, stream, ensure_ascii=False, indent=2); stream.write("\n")
print(json.dumps({"stage": args.stage, "actual_child_exit_code": code, "receipt": str(HERE / (args.stage + ".actual-exit.json"))}, ensure_ascii=False))
raise SystemExit(code)
