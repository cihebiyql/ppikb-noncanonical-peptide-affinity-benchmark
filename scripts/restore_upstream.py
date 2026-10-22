"""Fetch locked official code ZIPs only. Downloading grants no redistribution license."""
import argparse
import hashlib
import json
import re
import stat
import urllib.parse
import zipfile
from pathlib import Path
from restore_artifacts import checked_copy, digest, fetch, native, relative, safe_path

METHODS = {"GraphDTA-GIN", "MGraphDTA", "DGDTA-CL", "DeepNC-GEN", "GS-DTA"}
AUTHORS = {"GraphDTA-GIN": "https://github.com/thinng/GraphDTA", "MGraphDTA": "https://github.com/guaguabujianle/MGraphDTA", "DGDTA-CL": "https://github.com/luojunwei/DGDTA", "DeepNC-GEN": "https://github.com/thntran/DeepNC", "GS-DTA": "https://github.com/zhuziguang/GS-DTA"}


def restore(repo_root, verify_only=False):
    root = Path(repo_root).resolve()
    with open(native(root / "permissions/fetch-lock.json"), encoding="utf-8-sig") as stream: lock = json.load(stream)
    if lock.get("schema") != "upstream-fetch-lock.v1" or {row["method_id"] for row in lock["repositories"]} != METHODS or len(lock["repositories"]) != 5: raise ValueError("Only exact five formal author repositories allowed")
    records = []
    for row in lock["repositories"]:
        if row["repository_url"] != AUTHORS[row["method_id"]]: raise ValueError("Repository must be the formal method's original author source")
        repo = urllib.parse.urlparse(row["repository_url"])
        if repo.scheme != "https" or repo.netloc != "github.com" or not re.fullmatch(r"/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo.path) or not re.fullmatch("[0-9a-f]{40}", row["commit"]): raise ValueError("Expected official immutable GitHub repository/commit")
        owner, name = repo.path.strip("/").split("/")
        expected = "https://codeload.github.com/" + owner + "/" + name + "/zip/" + row["commit"]
        if row["official_archive_url"] != expected or not re.fullmatch("[0-9a-f]{64}", row["archive_sha256"]): raise ValueError("Only the exact officially locked ZIP URL/SHA is allowed")
        folder = safe_path(root / "benchmark/resources/upstream-full-v1", row["method_id"])
        archive = fetch(expected, folder / "archive.zip", row["archive_sha256"])
        if verify_only: records.append({"method_id": row["method_id"], "archive_verified": True, "extracted": False}); continue
        targets = [folder / "extracted", safe_path(root / "benchmark/model-audit/author-source", owner + "__" + name) / "source"]
        files = 0
        with zipfile.ZipFile(native(archive)) as source:
            members = source.infolist(); prefixes = {relative(item.filename).split("/")[0] for item in members}
            if len(prefixes) != 1: raise ValueError("Official ZIP must have one safe root directory")
            for item in members:
                name_in_zip = relative(item.filename); split = name_in_zip.split("/", 1)
                if len(split) == 1:
                    if not item.is_dir(): raise ValueError("Unexpected file at ZIP top root")
                    continue
                rel = split[1]; file_type = stat.S_IFMT(item.external_attr >> 16)
                if file_type not in (0, stat.S_IFREG, stat.S_IFDIR): raise ValueError("ZIP links/special members rejected")
                if item.is_dir():
                    for target in targets: safe_path(target, rel).mkdir(parents=True, exist_ok=True)
                    continue
                with source.open(item) as stream:
                    value = hashlib.sha256()
                    for block in iter(lambda: stream.read(1024 * 1024), b""): value.update(block)
                for target in targets:
                    with source.open(item) as stream: checked_copy(stream, safe_path(target, rel), value.hexdigest(), item.file_size)
                files += 1
        records.append({"method_id": row["method_id"], "archive_verified": True, "files_in_each_code_copy": files, "license_status_unchanged": row["license_status"], "scientific_commands_executed": 0})
    return {"repositories": records, "redistribution_permission_granted": False, "automatic_prepare_training_or_model_execution": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parent.parent)); parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(); print(json.dumps(restore(args.repo_root, args.verify_only), indent=2))
