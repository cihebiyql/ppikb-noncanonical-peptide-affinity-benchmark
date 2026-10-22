"""Standard-library verified GitHub Release artifact restore; executes no science."""
import argparse
import gzip
import hashlib
import io
import json
import os
import re
import shutil
import stat
import tarfile
import urllib.parse
import urllib.request
import uuid
from pathlib import Path, PurePosixPath


def native(path):
    path = os.path.abspath(os.fspath(path))
    if os.name == "nt" and not path.startswith("\\\\?\\"):
        return "\\\\?\\UNC\\" + path[2:] if path.startswith("\\\\") else "\\\\?\\" + path
    return path


def digest(path):
    value = hashlib.sha256()
    with open(native(path), "rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""): value.update(block)
    return value.hexdigest()


def relative(value):
    value = str(value).replace("\\", "/")
    if not value or value.startswith("/") or "\x00" in value or ":" in value:
        raise ValueError("Absolute, drive/ADS or empty archive path rejected")
    parts = PurePosixPath(value).parts
    if any(part in ("..", ".") or part.endswith((" ", ".")) for part in parts): raise ValueError("Unsafe archive path component")
    return "/".join(parts)


def is_link(path):
    try:
        value = os.lstat(native(path))
        return stat.S_ISLNK(value.st_mode) or bool(getattr(value, "st_file_attributes", 0) & 0x400)
    except FileNotFoundError: return False


def safe_path(root, rel):
    root = Path(root).absolute(); rel = relative(rel)
    if is_link(root): raise ValueError("Restore root cannot be a symlink/reparse point")
    current = root
    for part in rel.split("/"):
        current = current / part
        if is_link(current): raise ValueError("Existing symlink/reparse point rejected")
    if not current.resolve().is_relative_to(root.resolve()): raise ValueError("Path escapes restore root")
    return Path(native(current))


def checked_copy(stream, target, expected_sha, expected_size):
    """Verify incoming bytes first; no overwrite of any differing existing file."""
    target = Path(target); target.parent.mkdir(parents=True, exist_ok=True)
    if is_link(target): raise ValueError("Existing target link rejected")
    temporary = target.with_name(".__restore_" + uuid.uuid4().hex + ".tmp")
    value, size = hashlib.sha256(), 0
    try:
        with open(native(temporary), "xb") as output:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                size += len(chunk); value.update(chunk); output.write(chunk)
        if (expected_size is not None and size != expected_size) or value.hexdigest() != expected_sha: raise ValueError("Incoming file size/SHA mismatch")
        if target.exists():
            if not target.is_file() or target.stat().st_size != size or digest(target) != expected_sha: raise FileExistsError("Existing different content is never overwritten: " + str(target))
            return "identical_skipped"
        # Atomic no-clobber install on ordinary NTFS/POSIX filesystems. Temporary
        # hardlink is removed immediately; archives themselves never allow links.
        try: os.link(native(temporary), native(target))
        except FileExistsError:
            if target.is_file() and digest(target) == expected_sha: return "identical_skipped"
            raise
        except OSError:
            # Exclusive creation fallback still never overwrites existing bytes.
            with open(native(target), "xb") as output, open(native(temporary), "rb") as source: shutil.copyfileobj(source, output, 1024 * 1024)
        return "restored"
    finally:
        if temporary.exists(): os.unlink(native(temporary))


def fetch(url, target, expected_sha, expected_size=None):
    target = Path(target)
    if target.exists():
        if (expected_size is not None and target.stat().st_size != expected_size) or digest(target) != expected_sha: raise ValueError("Existing cache differs; retain it and choose a fresh cache directory")
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "verified-benchmark-restorer/1"})
    with urllib.request.urlopen(request, timeout=90) as response:
        checked_copy(response, target, expected_sha, expected_size)
    return target


class Concatenated(io.RawIOBase):
    def __init__(self, paths): self.paths, self.index, self.current = list(paths), 0, None
    def readable(self): return True
    def readinto(self, buffer):
        while True:
            if self.current is None:
                if self.index == len(self.paths): return 0
                self.current = open(native(self.paths[self.index]), "rb"); self.index += 1
            count = self.current.readinto(buffer)
            if count: return count
            self.current.close(); self.current = None
    def close(self):
        if self.current: self.current.close()
        super().close()


def source_manifest(path):
    rows = {}
    with open(native(path), encoding="utf-8-sig") as stream:
        for line in stream:
            if not line.strip(): continue
            row = json.loads(line); rel = relative(row["path"])
            if rel in rows: raise ValueError("Duplicate source-manifest path")
            if row.get("public_path", "benchmark/" + rel) != "benchmark/" + rel: raise ValueError("Unexpected public_path")
            if row["storage"] not in ("git", "release") or not re.fullmatch("[0-9a-fA-F]{64}", row["sha256"]): raise ValueError("Invalid source-file lock")
            row["bytes"] = int(row.get("bytes", row.get("size", -1)))
            if row["bytes"] < 0: raise ValueError("Explicit source byte size required")
            rows[rel] = row
    return rows


def restore(repo_root, cache_dir=None, verify_only=False):
    repo = Path(repo_root).resolve(); cache = Path(cache_dir) if cache_dir else repo / ".artifact-cache"
    with open(native(repo / "manifest/artifact-assets.json"), encoding="utf-8-sig") as stream: assets = json.load(stream)
    if assets.get("schema") != "split-gzip-tar-artifacts.v1" or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", assets["repository"]): raise ValueError("Unsupported artifact asset lock")
    parts, names = [], set()
    for row in assets["parts"]:
        name = relative(row["name"])
        if "/" in name or name in names or not re.fullmatch("[0-9a-fA-F]{64}", row["sha256"]): raise ValueError("Invalid/duplicate release asset name or digest")
        names.add(name)
        url = "https://github.com/" + assets["repository"] + "/releases/download/" + urllib.parse.quote(str(assets["tag"]), safe="") + "/" + urllib.parse.quote(name, safe="")
        parts.append(fetch(url, safe_path(cache, name), row["sha256"], int(row["bytes"])))
    if not parts: raise ValueError("No ordered artifact parts")
    files = source_manifest(repo / "manifest/source-files.jsonl"); root = repo / "benchmark"
    for rel, row in files.items():
        if row["storage"] == "git":
            path = safe_path(root, rel)
            if not path.is_file() or path.stat().st_size != row["bytes"] or digest(path) != row["sha256"]: raise ValueError("Git-stored source file missing or changed: " + rel)
    release = {key: row for key, row in files.items() if row["storage"] == "release"}
    if verify_only:
        present = 0
        for rel, row in release.items():
            path = safe_path(root, rel)
            if path.exists():
                if not path.is_file() or path.stat().st_size != row["bytes"] or digest(path) != row["sha256"]: raise ValueError("Existing restored artifact changed")
                present += 1
        return {"verified_parts": len(parts), "git_files_verified": len(files) - len(release), "release_files_present_verified": present, "release_files_not_yet_restored": len(release) - present, "extracted": False}
    seen, counts = set(), {"restored": 0, "identical_skipped": 0}
    with io.BufferedReader(Concatenated(parts)) as joined, gzip.GzipFile(fileobj=joined, mode="rb") as compressed, tarfile.open(fileobj=compressed, mode="r|") as archive:
        for member in archive:
            name = relative(member.name)
            if name == "benchmark":
                if not member.isdir(): raise ValueError("benchmark root must be a directory")
                continue
            if name.startswith("benchmark/"): name = name[len("benchmark/"):]
            destination = safe_path(root, name)
            if member.isdir(): destination.mkdir(parents=True, exist_ok=True); continue
            if not member.isreg(): raise ValueError("Only regular files/directories allowed; links/devices rejected")
            if name not in release or name in seen: raise ValueError("Unlisted or duplicate release archive member")
            row = release[name]
            if member.size != row["bytes"]: raise ValueError("Tar member byte count differs from source manifest")
            with archive.extractfile(member) as stream: counts[checked_copy(stream, destination, row["sha256"], row["bytes"])] += 1
            seen.add(name)
        # Reach gzip EOF so its trailer/CRC is checked even after tar end blocks.
        for _ in iter(lambda: compressed.read(1024 * 1024), b""): pass
    if seen != set(release): raise ValueError("Missing release files; incomplete restore is retained for verified resume")
    return {"verified_parts": len(parts), "git_files_verified": len(files) - len(release), "release_files_verified": len(seen), **counts, "scientific_commands_executed": 0}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parent.parent)); parser.add_argument("--cache-dir"); parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(); print(json.dumps(restore(args.repo_root, args.cache_dir, args.verify_only), indent=2))
