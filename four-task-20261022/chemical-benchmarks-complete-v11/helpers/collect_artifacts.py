"""Read-only, standard-library scientific-log collection. Never deserialize models.

The original runtime remains authoritative. Large/binary files are indexed by size
and pre-existing producer hashes where available, not downloaded or freshly hashed.
"""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
from datetime import datetime, timezone

TEXT_SUFFIXES = {'.json', '.jsonl', '.csv', '.tsv', '.log', '.txt', '.md'}
BINARY_SUFFIXES = {'.joblib', '.pt', '.pth', '.bin', '.safetensors', '.npz', '.npy', '.pkl', '.pickle'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def add_bytes(archive, name, data):
    entry = tarfile.TarInfo(name)
    entry.size = len(data)
    entry.mode = 0o644
    entry.mtime = 0
    archive.addfile(entry, io.BytesIO(data))


def collect(inputs, output, max_file_bytes=32 * 1024 * 1024):
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    roots = {}
    for item in inputs:
        alias, raw = item.split('=', 1)
        if not alias or alias in roots or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for c in alias):
            raise ValueError('Unsafe or duplicate input alias')
        root = Path(raw).resolve(strict=True)
        if not root.is_dir():
            raise ValueError('Input must be an existing artifact directory')
        if output.resolve().is_relative_to(root):
            raise ValueError('Output may not lie inside a collected input')
        roots[alias] = root
    inventory = []
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open('xb') as raw_output, gzip.GzipFile(filename='', fileobj=raw_output, mode='wb', mtime=0) as compressed, tarfile.open(fileobj=compressed, mode='w|') as archive:
            for alias, root in sorted(roots.items()):
                for path in sorted(root.rglob('*')):
                    if path.is_dir() and not path.is_symlink():
                        continue
                    rel = path.relative_to(root).as_posix()
                    record = {'input': alias, 'relative_path': rel, 'source_path': str(path), 'size_bytes': path.lstat().st_size}
                    if path.is_symlink():
                        record.update(disposition='not_collected_symlink', reason='Do not dereference paths outside the supplied artifact root')
                    elif not path.is_file():
                        record.update(disposition='not_collected_special_file', reason='Only ordinary files are eligible')
                    elif path.suffix.lower() in BINARY_SUFFIXES:
                        record.update(disposition='not_collected_binary', reason='Model/checkpoint/cache retained in original runtime; producer hash may be joined from its original receipt, no model loading or fresh binary hash')
                    elif path.suffix.lower() not in TEXT_SUFFIXES:
                        record.update(disposition='not_collected_unclassified', reason='Explicit text suffix allowlist; requires separate review')
                    elif path.stat().st_size > max_file_bytes:
                        record.update(disposition='not_collected_size_limit', reason='Bounded metadata collection; requires a separately authorized transfer')
                    else:
                        data = path.read_bytes()
                        data.decode('utf-8-sig')
                        if len(data) != record['size_bytes']:
                            raise RuntimeError('File changed during collection: ' + str(path))
                        record.update(disposition='collected_original_bytes', sha256=sha(data), archive_path=alias + '/' + rel)
                        add_bytes(archive, record['archive_path'], data)
                    inventory.append(record)
            receipt = {'schema': 'public-log-source-collection.v1', 'created_utc': datetime.now(timezone.utc).isoformat(), 'inputs': {key: str(value) for key, value in roots.items()}, 'files': inventory, 'collected_files': sum(x['disposition'] == 'collected_original_bytes' for x in inventory), 'new_scientific_fits': 0, 'new_scientific_predictions': 0, 'models_deserialized': 0, 'large_binary_bytes_read': 0}
            add_bytes(archive, 'COLLECTION.original.json', (json.dumps(receipt, ensure_ascii=False, indent=2) + '\n').encode())
    except BaseException:
        # Preserve a partial archive as evidence; callers must not mistake it for a
        # terminal collection because it lacks the final inventory member.
        raise
    result = {'output': str(output), 'archive_sha256': sha(output.read_bytes()), 'archive_size_bytes': output.stat().st_size, 'collected_files': receipt['collected_files'], 'indexed_files': len(inventory), 'new_scientific_fits': 0, 'new_scientific_predictions': 0}
    receipt_path = output.with_suffix(output.suffix + '.receipt.json')
    with receipt_path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', action='append', required=True, help='safe-alias=existing-artifact-directory')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-file-bytes', type=int, default=32 * 1024 * 1024)
    args = parser.parse_args()
    print(json.dumps(collect(args.input, args.output, args.max_file_bytes), indent=2))


if __name__ == '__main__':
    main()
