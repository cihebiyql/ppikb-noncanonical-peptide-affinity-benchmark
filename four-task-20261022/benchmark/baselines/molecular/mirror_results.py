"""Administrative full-file mirror archive; never fit or execute stored models."""
import hashlib
import json
import socket
import tarfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/data/qlyu/projects/peptide-four-task-benchmark-20261022")
RUN = ROOT/"runs"/"cpu-molecular-v1"
OUT = ROOT/"baselines"/"molecular"


def sha(path):
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""):
            result.update(block)
    return result.hexdigest()


def main():
    if socket.gethostname()!="node23":
        raise RuntimeError("only the verified node23 source can produce this archive")
    process = json.loads((RUN/"process-receipt.json").read_text())
    if process["exit_code"] or process["termination_reason"] or not process["worker_pid_absent"]:
        raise RuntimeError("run was not a clean completed process")
    files = sorted(path for path in RUN.rglob("*") if path.is_file())
    items = [{"path":str(path.relative_to(ROOT)),"bytes":path.stat().st_size,"sha256":sha(path)} for path in files]
    manifest_path = OUT/"molecular-result-files-recovery-v1.json"
    manifest = {"created_at":datetime.now(timezone.utc).isoformat(),"source_host":"node23","source_root":str(ROOT),
                "files":items,"file_count":len(items),"bytes":sum(item["bytes"] for item in items),
                "new_fits":0,"new_predictions":0,"old_failures_preserved":True}
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    archive = OUT/"molecular-results-recovery-v1.tar.gz"
    with tarfile.open(archive,"w:gz",compresslevel=1) as bundle:
        for path in files+[manifest_path]:
            bundle.add(path,arcname=str(path.relative_to(ROOT)))
    receipt = {"archive":str(archive),"archive_bytes":archive.stat().st_size,"archive_sha256":sha(archive),
               "source_manifest_path":str(manifest_path),"source_manifest_sha256":sha(manifest_path),
               "source_files":len(items),"source_bytes":manifest["bytes"],"new_fits":0,"new_predictions":0}
    (OUT/"molecular-archive-recovery-receipt.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
    print(json.dumps(receipt))


if __name__=="__main__":
    main()
