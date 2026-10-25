"""Download pinned public encoder assets only. No model imports or execution."""
from __future__ import annotations
import concurrent.futures
import hashlib
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
METHOD = Path(__file__).resolve().parent
RESOURCE = ROOT / 'resources/chemical-encoders-20261024-v1'
MODELS = {
    'peptideclm-2-hybrid-small': '62d5db6922a5a5ece56f9cd5adc48ab2b19d2e57',
    'peptideclm-2-mlm-small': '7fe899df4d9753224aefa955ed0cf859d181e693',
}
REPOS = {
    'PeptideCLM-2': '6b9708d4cb05717307d310daaf1c0f88c71ff084',
    'PeptideCLM': '91f82e9715eabd185e59d80cabb47e2fb650d90f',
}
START = time.monotonic()
DEADLINE_SECONDS = 600


def jwrite(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def get_json(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'peptide-benchmark-audit/1'}), timeout=30) as response:
        return json.load(response)


def sha_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def download(item):
    if time.monotonic() - START > DEADLINE_SECONDS:
        raise TimeoutError('Download campaign time budget exhausted')
    destination = Path(item['path'])
    destination.parent.mkdir(parents=True, exist_ok=True)
    expected_sha = item.get('expected_sha256')
    expected_size = item['bytes']
    if destination.exists():
        actual_sha = sha_file(destination)
        if destination.stat().st_size == expected_size and (not expected_sha or expected_sha == actual_sha):
            return {**item, 'status': 'existing_verified', 'sha256': actual_sha}
        raise RuntimeError('Existing final asset differs; refusing overwrite: ' + str(destination))
    partial = destination.with_name(destination.name + '.partial')
    digest = hashlib.sha256()
    request = urllib.request.Request(item['url'], headers={'User-Agent': 'peptide-benchmark-audit/1'})
    with urllib.request.urlopen(request, timeout=40) as response, partial.open('wb') as handle:
        while True:
            if time.monotonic() - START > DEADLINE_SECONDS:
                raise TimeoutError('Download campaign time budget exhausted')
            block = response.read(1024 * 1024)
            if not block:
                break
            handle.write(block)
            digest.update(block)
    actual_sha = digest.hexdigest()
    assert partial.stat().st_size == expected_size, 'Size mismatch: ' + str(destination)
    assert not expected_sha or expected_sha == actual_sha, 'SHA mismatch: ' + str(destination)
    partial.replace(destination)
    return {**item, 'status': 'downloaded_verified', 'sha256': actual_sha}


def main():
    RESOURCE.mkdir(parents=True, exist_ok=True)
    queue, source_manifests = [], []
    for repo, commit in REPOS.items():
        url = f'https://api.github.com/repos/AaronFeller/{repo}/git/trees/{commit}?recursive=1'
        tree = get_json(url)
        assert not tree.get('truncated'), 'Truncated GitHub tree'
        jwrite(RESOURCE / 'metadata' / (repo + '.tree.json'), tree)
        selected, excluded = [], []
        for item in tree['tree']:
            if item['type'] != 'blob':
                continue
            relative = item['path']
            # Preserve source, tokenizer and license; do not download unrelated benchmark data/results.
            include = (relative in ('LICENSE', 'README.md', 'pyproject.toml', 'requirements.txt')
                       or relative.endswith('.py') or relative.startswith('tokenizer/') and relative.endswith(('.txt', '.json', '.vocab')))
            if include:
                selected.append(relative)
                queue.append({'kind': 'source_snapshot', 'repository': repo, 'revision': commit,
                              'relative_path': relative, 'bytes': item['size'],
                              'path': (METHOD / 'sources' / repo / relative).as_posix(),
                              'url': f'https://raw.githubusercontent.com/AaronFeller/{repo}/{commit}/{relative}'})
            else:
                excluded.append(relative)
        source_manifests.append({'repository': repo, 'commit': commit, 'source_url': url,
                                 'snapshot_scope': 'Source/tokenizer/license snapshot, not a full repository checkout or dataset download',
                                 'included_paths': selected, 'excluded_paths': excluded})
    for name, revision in MODELS.items():
        metadata = get_json(f'https://huggingface.co/api/models/aaronfeller/{name}?blobs=true')
        assert metadata['sha'] == revision, 'Pinned model revision changed'
        assert metadata.get('cardData', {}).get('license') == 'mit', 'Unexpected model license'
        jwrite(RESOURCE / 'metadata' / (name + '.model-info.json'), metadata)
        for item in metadata['siblings']:
            relative = item['rfilename']
            if relative == '.gitattributes':
                continue
            queue.append({'kind': 'model_asset', 'repository': 'aaronfeller/' + name, 'revision': revision,
                          'relative_path': relative, 'bytes': item['size'],
                          'expected_sha256': (item.get('lfs') or {}).get('sha256'),
                          'path': (RESOURCE / 'models' / name / relative).as_posix(),
                          'url': f'https://huggingface.co/aaronfeller/{name}/resolve/{revision}/{relative}'})
    jwrite(RESOURCE / 'DOWNLOAD-PLAN.json', {'created_at_utc': datetime.now(timezone.utc).isoformat(),
                                           'deadline_seconds': DEADLINE_SECONDS, 'items': queue,
                                           'source_snapshots': source_manifests})
    outcomes, errors = [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(download, item): item for item in queue}
        for future in concurrent.futures.as_completed(futures):
            try:
                outcomes.append(future.result())
            except Exception as exc:
                errors.append({'item': futures[future], 'error': type(exc).__name__ + ': ' + str(exc)})
    receipt = {'schema': 'chemical-encoder.assets.v1', 'finished_at_utc': datetime.now(timezone.utc).isoformat(),
               'status': 'succeeded' if not errors else 'partial', 'elapsed_seconds': time.monotonic() - START,
               'source_snapshots': source_manifests, 'files': sorted(outcomes, key=lambda x: x['path']), 'errors': errors,
               'model_loaded': False, 'gpu_used': False, 'chemical_canary_passed': False,
               'verified_files': len(outcomes), 'verified_bytes': sum(x['bytes'] for x in outcomes)}
    jwrite(RESOURCE / 'ASSET-RECEIPT.actual.json', receipt)
    print(json.dumps({k: receipt[k] for k in ('status', 'verified_files', 'verified_bytes', 'elapsed_seconds', 'errors')}, ensure_ascii=False))
    return 0 if not errors else 1


if __name__ == '__main__':
    raise SystemExit(main())
