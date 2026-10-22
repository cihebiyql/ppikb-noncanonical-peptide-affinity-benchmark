"""Synthetic split artifacts only; no real network/model/source downloads."""
import gzip
import hashlib
import io
import json
import tarfile
import time
import unittest
from unittest.mock import patch
from pathlib import Path
import restore_artifacts as r
import restore_upstream as u

HERE = Path(__file__).resolve().parent
H = lambda value: hashlib.sha256(value).hexdigest()


def fixture(extra=None, long=False):
    root = HERE / ("synthetic-" + str(time.time_ns())); root.mkdir()
    (root / "manifest").mkdir(); (root / "benchmark").mkdir(); cache = root / "cache"; cache.mkdir()
    (root / "benchmark/git.txt").write_bytes(b"git-file")
    name = "/".join(["longsegment" * 3] * 9) + "/a.txt" if long else "nested/a.txt"
    data = {name: b"alpha", "b.txt": b"beta"}; buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for key, value in data.items():
            member = tarfile.TarInfo(key); member.size = len(value); archive.addfile(member, io.BytesIO(value))
        if extra:
            member = tarfile.TarInfo(extra[0]); member.type = extra[1]
            if member.type in (tarfile.SYMTYPE, tarfile.LNKTYPE): member.linkname = "../outside"
            archive.addfile(member, io.BytesIO(b""))
    payload = gzip.compress(buffer.getvalue()); middle = len(payload) // 2
    parts = []
    for i, value in enumerate((payload[:middle], payload[middle:])):
        part = "artifact.part" + str(i); (cache / part).write_bytes(value); parts.append({"name": part, "bytes": len(value), "sha256": H(value)})
    (root / "manifest/artifact-assets.json").write_text(json.dumps({"schema": "split-gzip-tar-artifacts.v1", "repository": "synthetic/never-requested", "tag": "synthetic", "parts": parts}), encoding="utf-8")
    rows = [{"path": "git.txt", "bytes": 8, "sha256": H(b"git-file"), "storage": "git", "public_path": "benchmark/git.txt"}]
    rows += [{"path": key, "bytes": len(value), "sha256": H(value), "storage": "release", "public_path": "benchmark/" + key} for key, value in data.items()]
    (root / "manifest/source-files.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return root, cache, data


class RestoreTests(unittest.TestCase):
    def test_two_ordered_parts_restore_and_identical_resume(self):
        root, cache, data = fixture(); result = r.restore(root, cache)
        self.assertEqual(result["restored"], 2)
        for name, value in data.items():
            with open(r.native(root / "benchmark" / name), "rb") as stream: self.assertEqual(stream.read(), value)
        self.assertEqual(r.restore(root, cache)["identical_skipped"], 2)
    def test_verify_only_does_not_extract(self):
        root, cache, data = fixture(); result = r.restore(root, cache, True)
        self.assertFalse(result["extracted"]); self.assertEqual(result["release_files_not_yet_restored"], 2)
        self.assertFalse((root / "benchmark/b.txt").exists())
    def test_wrong_part_sha_rejected(self):
        root, cache, _ = fixture(); path = root / "manifest/artifact-assets.json"; body = json.loads(path.read_text()); body["parts"][0]["sha256"] = "0" * 64; path.write_text(json.dumps(body))
        with self.assertRaises(ValueError): r.restore(root, cache)
    def test_tar_traversal_rejected(self):
        root, cache, _ = fixture(("../escape.txt", tarfile.REGTYPE))
        with self.assertRaises(ValueError): r.restore(root, cache)
        self.assertFalse((root / "escape.txt").exists())
    def test_tar_symlink_rejected(self):
        root, cache, _ = fixture(("link", tarfile.SYMTYPE))
        with self.assertRaises(ValueError): r.restore(root, cache)
    def test_tar_hardlink_rejected(self):
        root, cache, _ = fixture(("link", tarfile.LNKTYPE))
        with self.assertRaises(ValueError): r.restore(root, cache)
    def test_existing_different_file_never_overwritten(self):
        root, cache, _ = fixture(); (root / "benchmark/b.txt").write_bytes(b"old-user-content")
        with self.assertRaises(FileExistsError): r.restore(root, cache)
        self.assertEqual((root / "benchmark/b.txt").read_bytes(), b"old-user-content")
    def test_long_relative_path(self):
        root, cache, _ = fixture(long=True); self.assertEqual(r.restore(root, cache)["restored"], 2)
    def test_windows_drive_ads_absolute_and_parent_rejected(self):
        for value in ("C:/outside", "../outside", "a/../../outside", "/outside", "a:stream", "\\\\server\\share\\a"):
            with self.subTest(path=value), self.assertRaises(ValueError): r.relative(value)
    def test_upstream_exact_five_schema_without_network(self):
        root, _, _ = fixture(); (root / "permissions").mkdir()
        entries = []
        for method, repository in u.AUTHORS.items():
            entries.append({"method_id": method, "repository_url": repository, "commit": "1" * 40, "official_archive_url": repository.replace("https://github.com/", "https://codeload.github.com/") + "/zip/" + "1" * 40, "archive_sha256": "0" * 64, "license_status": "synthetic_no_permission", "license_paths": []})
        (root / "permissions/fetch-lock.json").write_text(json.dumps({"schema": "upstream-fetch-lock.v1", "repositories": entries}), encoding="utf-8")
        with patch.object(u, "fetch", return_value=root / "not-opened.zip") as mocked:
            result = u.restore(root, True)
        self.assertEqual(mocked.call_count, 5); self.assertEqual(len(result["repositories"]), 5); self.assertFalse(result["redistribution_permission_granted"])
    def test_upstream_relabelled_nonformal_source_rejected(self):
        root, _, _ = fixture(); (root / "permissions").mkdir()
        entries = [{"method_id": method, "repository_url": repo, "commit": "1" * 40, "official_archive_url": repo.replace("https://github.com/", "https://codeload.github.com/") + "/zip/" + "1" * 40, "archive_sha256": "0" * 64, "license_status": "synthetic", "license_paths": []} for method, repo in u.AUTHORS.items()]
        entries[0]["repository_url"] = "https://github.com/unrelated/not-formal"
        (root / "permissions/fetch-lock.json").write_text(json.dumps({"schema": "upstream-fetch-lock.v1", "repositories": entries}), encoding="utf-8")
        with patch.object(u, "fetch", side_effect=AssertionError("Network must not be reached")):
            with self.assertRaises(ValueError): u.restore(root, True)


if __name__ == "__main__": unittest.main()
