"""Stage only this molecular lane's immutable code and frozen benign input views."""
import datetime as dt
import hashlib
import json
import shutil
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
REMOTE = Path("/data/qlyu/projects/peptide-four-task-benchmark-20261022")
IDS = ["ppikb_kd_source_cold_scope_v2","ppikb_kd_target_cold_scope_v2","ppikb_effect_metadata_silver_source_cold"]


def sha(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""):
            value.update(block)
    return value.hexdigest()


def main():
    inputs = HERE/"inputs"
    inputs.mkdir(exist_ok=True)
    original_manifest = ROOT/"data"/"view_manifest.json"
    source = json.loads(original_manifest.read_text(encoding="utf-8"))
    views = []
    staged = []
    for identifier in IDS:
        view = dict(next(value for value in source["views"] if value["id"]==identifier))
        original = Path(view["path"])
        if sha(original)!=view["sha256"]:
            raise ValueError("frozen source view changed before molecular staging")
        destination = inputs/original.name
        if destination.exists() and sha(destination)!=view["sha256"]:
            raise ValueError("different existing staged input would be overwritten")
        if not destination.exists():
            shutil.copyfile(original,destination)
        view["original_local_path"] = str(original)
        view["path"] = str(REMOTE/"baselines"/"molecular"/"inputs"/original.name).replace("\\","/")
        views.append(view)
        staged.append(destination)
    manifest = {"schema":"four-task.molecular-frozen-views.v1","views":views,
                "original_manifest_sha256":sha(original_manifest),"raw_input_bytes_identical_to_frozen_data_views":True,
                "new_scope_filtering":False,"labels_or_splits_changed":False}
    manifest_path = inputs/"manifest.json"
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
    files = staged+[manifest_path]+[HERE/name for name in ["molecular_features.py","run_molecular_baselines.py","supervise_molecular.py","test_molecular.py"]]
    checks = [{"path":str(REMOTE/path.relative_to(ROOT)).replace("\\","/"),"sha256":sha(path)} for path in files]
    python = "/data/qlyu/projects/peptide-binding-benchmark-20261020/common-prior-methods-20261021/swing/.venv/bin/python"
    command = [python,"-B",str(REMOTE/"baselines/molecular/run_molecular_baselines.py").replace("\\","/"),
               "--manifest",str(REMOTE/"baselines/molecular/inputs/manifest.json").replace("\\","/"),
               "--output",str(REMOTE/"runs/cpu-molecular-v1").replace("\\","/"),"--max-seconds","2700"]
    for identifier in IDS:
        command += ["--view",identifier]
    spec = {"schema":"four-task.molecular-owned-cpu-spec.v1","prepared_at":dt.datetime.now(dt.timezone.utc).isoformat(),
            "output":str(REMOTE/"runs/cpu-molecular-v1").replace("\\","/"),"cwd":str(REMOTE/"baselines/molecular").replace("\\","/"),
            "command":command,"cpu_affinity":[28,29],"cpu_threads":2,"memory_limit_bytes":6*1024**3,
            "timeout_seconds":2800,"deadline_at":(dt.datetime.now(dt.timezone.utc)+dt.timedelta(seconds=2800)).isoformat(),
            "input_hashes":checks,"gpu":None,"new_dependencies":False,
            "coordination":"interaction_build explicitly released cores28-29 after its temporary CPU1 external inference; SWING workers remain24-27"}
    spec_path = HERE/"node23-spec.json"
    spec_path.write_text(json.dumps(spec,ensure_ascii=False,indent=2),encoding="utf-8")
    files.append(spec_path)
    archive = HERE/"deployment-payload.tar.gz"
    with tarfile.open(archive,"w:gz") as bundle:
        for path in files:
            bundle.add(path,arcname=str(path.relative_to(ROOT)).replace("\\","/"))
    receipt = {"payload":str(archive),"payload_sha256":sha(archive),"bytes":archive.stat().st_size,"files":len(files),
               "source_views":IDS,"existing_runtime_python":python,"cpu_affinity":[28,29],"threads":2,"gpu":False}
    (HERE/"deployment-receipt.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(receipt,ensure_ascii=False))


if __name__=="__main__":
    main()
