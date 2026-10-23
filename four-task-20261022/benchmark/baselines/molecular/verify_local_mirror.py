"""Verify source archive and every mirrored file, preserving existing local artifacts."""
import hashlib
import json
import tarfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def sha(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""):
            value.update(block)
    return value.hexdigest()


def main():
    archive = HERE/"molecular-results-recovery-v1.tar.gz"
    receipt = json.loads((HERE/"molecular-archive-recovery-receipt.json").read_text(encoding="utf-8"))
    if archive.stat().st_size!=receipt["archive_bytes"] or sha(archive)!=receipt["archive_sha256"]:
        raise ValueError("downloaded molecular archive is incomplete or different")
    manifest_name = "baselines/molecular/molecular-result-files-recovery-v1.json"
    with tarfile.open(archive,"r:gz") as bundle:
        manifest = json.loads(bundle.extractfile(manifest_name).read().decode("utf-8"))
        expected = {item["path"]:item for item in manifest["files"]}
        for member in bundle.getmembers():
            path = PurePosixPath(member.name)
            target = (ROOT/Path(member.name)).resolve()
            if path.is_absolute() or ".." in path.parts or not target.is_relative_to(ROOT.resolve()):
                raise ValueError("archive member is outside intended new project")
            if not (member.name.startswith("runs/cpu-molecular-v1/") or member.name==manifest_name):
                raise ValueError("unexpected archive member")
            if not member.isfile():
                raise ValueError("only regular files expected in this source archive")
            item = expected.get(member.name)
            expected_sha = item["sha256"] if item else receipt["source_manifest_sha256"]
            if target.exists():
                if sha(target)!=expected_sha:
                    raise ValueError(f"existing local file differs, refusing overwrite: {target}")
                continue
            target.parent.mkdir(parents=True,exist_ok=True)
            stream = bundle.extractfile(member)
            with target.open("xb") as output:
                for block in iter(lambda:stream.read(1024*1024),b""):
                    output.write(block)
    failures = []
    for item in manifest["files"]:
        path = ROOT/Path(item["path"])
        if path.stat().st_size!=item["bytes"] or sha(path)!=item["sha256"]:
            failures.append(item["path"])
    result = {"completed_at":datetime.now(timezone.utc).isoformat(),"passed":not failures,"errors":failures,
              "source_host":"node23","files_verified":len(manifest["files"]),"bytes_verified":manifest["bytes"],
              "archive_sha256":receipt["archive_sha256"],"local_run_path":str(ROOT/"runs/cpu-molecular-v1"),
              "new_fits":0,"new_model_predictions":0,"old_failures_deleted":False,
              "remote_prefix":"/data/qlyu/projects/peptide-four-task-benchmark-20261022","local_prefix":str(ROOT)}
    (HERE/"local-mirror-receipt.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({key:result[key] for key in ("passed","errors","files_verified","bytes_verified","new_fits")},ensure_ascii=False))
    return 0 if not failures else 2


if __name__=="__main__":
    raise SystemExit(main())
