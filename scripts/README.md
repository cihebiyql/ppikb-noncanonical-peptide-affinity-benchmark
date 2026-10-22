# Verified public restoration scripts

Copy `restore_artifacts.py` and `restore_upstream.py` into the repository's `scripts/` directory together. Both require only Python's standard library. No script imports scientific frameworks, executes author code, trains models or runs predictions. Preparation/tests used only small local synthetic data and performed no real downloads.

## Release artifacts

```text
python scripts/restore_artifacts.py --verify-only
python scripts/restore_artifacts.py
python scripts/restore_artifacts.py --cache-dir D:/artifact-cache
```

Default repository root is the script's parent directory; `--repo-root` can override it. `manifest/artifact-assets.json` must use schema `split-gzip-tar-artifacts.v1`, with `repository` as `owner/repository`, `tag`, and ordered `parts` each containing `name`, `bytes`, `sha256`. URLs are constructed only as GitHub Releases download URLs for that repository/tag/name. Parts are streamed to cache and individually size/SHA verified. A differing existing cache asset is retained and rejected; select a new cache rather than overwrite it.

`manifest/source-files.jsonl` contains each original relative `path`, `bytes`, `sha256`, `storage` (`git` or `release`), and optional exact `public_path=benchmark/<path>`. Git-stored files must already be present at the locked SHA. Only release-stored files may be extracted from the tar stream. Ordered parts are concatenated without creating a second joined archive, then streamed through gzip/tar into `benchmark/`; both original-relative and `benchmark/`-prefixed tar names are supported. Every extracted file is checked against source SHA/bytes and all expected release files must be present.

`--verify-only` downloads/verifies parts and checks Git-stored files plus any already-restored release files; it reports how many release files are still absent and does not extract them. Default restore retains exact file bytes and directory layout. Existing identical content is skipped after verification; different content is never overwritten. Paths support Windows extended-length file access. Only regular files/directories are accepted; symlinks, hardlinks, devices, path traversal, drive/ADS paths and existing reparse-point targets are rejected. Never use `tar.extractall`. Partial verified restore can be resumed with the same command; source scientific values are unchanged.

## Official author sources

```text
python scripts/restore_upstream.py --verify-only
python scripts/restore_upstream.py
```

Reads `permissions/fetch-lock.json` schema `upstream-fetch-lock.v1` and only the five formal methods. Actual fields are `method_id`, `repository_url`, `commit`, `official_archive_url`, `archive_sha256`, `license_status`, `license_paths`. Each method is bound to its original official GitHub repository, exact immutable codeload ZIP URL and archive SHA. No other candidate or previously blocked workflow is fetched.

For each method, saves `benchmark/resources/upstream-full-v1/<method>/archive.zip`, extracts locked code to that method's `extracted/`, and restores an identical source tree at `benchmark/model-audit/author-source/<owner>__<repository>/source/`. ZIP paths/links are checked and existing different files are never overwritten. Missing unlicensed upstream source files are deliberately not in the public source-file manifest; this separate fetch restores them directly from the author.

**Fetching does not grant permission to redistribute unlicensed code.** License status is retained from the lock and is not interpreted as permission. Existing own preparation adapters (for example `benchmark/methods/*/prepare_vendor.py`, `prepare_sources.py` or `prepare.py`) may then be inspected and invoked manually as documented by the benchmark; these scripts never execute them automatically.

`test_restore.py` verifies two synthetic split parts, checksum failures, traversal/link rejection, no overwrite, identical resume, verify-only and long paths. Synthetic test fixture directories are not publication artifacts; root should copy only the intended scripts/tests/docs, not helper fixture folders.
