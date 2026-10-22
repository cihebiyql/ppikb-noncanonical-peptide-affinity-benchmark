"""Reuse installed site-packages distributions only; never installs packages."""
import hashlib
import importlib.metadata as md
import json
from pathlib import Path
import platform
import sys
import sysconfig
import tarfile
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

HERE = Path(__file__).resolve().parent
probe = json.loads((HERE / 'wsl-live-probe.json').read_text())
installed = {canonicalize_name(k): v for k, v in probe['installed_distribution_versions'].items()}
requested = ['torch-geometric', 'aiohttp', 'psutil', 'pyparsing', 'xxhash']
selected = {}
requirements_audit = []
pending = list(requested)
while pending:
    name = canonicalize_name(pending.pop())
    if name in selected:
        continue
    dist = md.distribution(name)
    base = Path(dist.locate_file('')).resolve()
    if base.name != 'site-packages':
        raise RuntimeError(f'Not site-packages: {base}')
    selected[name] = dist
    for raw in dist.requires or []:
        req = Requirement(raw)
        if req.marker and not req.marker.evaluate({'extra': ''}):
            continue
        key = canonicalize_name(req.name)
        existing = installed.get(key)
        audit = {'parent': name, 'requirement': raw, 'WSL_existing_version': existing}
        if existing is not None:
            if req.specifier and existing not in req.specifier:
                raise RuntimeError(f'Existing WSL dependency incompatible: {req} {existing}')
            audit['action'] = 'reuse_existing_WSL_runtime'
        else:
            audit['action'] = 'copy_already_installed_Node23_distribution'
            pending.append(key)
        requirements_audit.append(audit)
entries = []
packages = []
with tarfile.open(HERE / 'vendor-dependencies-v1.tar.gz', 'w:gz') as archive:
    seen = set()
    for name, dist in sorted(selected.items()):
        base = Path(dist.locate_file('')).resolve()
        count = total = 0
        skipped = []
        for item in dist.files or []:
            relative = Path(str(item))
            if '..' in relative.parts or '__pycache__' in relative.parts or relative.suffix == '.pyc' or relative.name == 'direct_url.json':
                skipped.append(str(relative))
                continue
            source = (base / relative).resolve()
            if not source.is_relative_to(base):
                raise RuntimeError(f'Path outside site-packages: {item}')
            if not source.is_file():
                continue
            dest = str(relative)
            if dest in seen:
                continue
            seen.add(dest)
            data = source.read_bytes()
            entries.append({'distribution': name, 'relative_path': dest, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'source': str(source)})
            archive.add(source, arcname=dest, recursive=False)
            count += 1
            total += len(data)
        packages.append({'name': name, 'version': dist.version, 'source_site_packages': str(base), 'copied_file_count': count, 'copied_bytes': total, 'skipped': skipped})
result = {'source_host': platform.node(), 'source_python': sys.version, 'source_machine': platform.machine(), 'source_SOABI': sysconfig.get_config_var('SOABI'), 'target_python': probe['python'], 'target_machine': probe['machine'], 'target_SOABI': probe['SOABI'], 'packages': packages, 'requirements_resolution': requirements_audit, 'files': entries, 'archive_sha256': hashlib.sha256((HERE / 'vendor-dependencies-v1.tar.gz').read_bytes()).hexdigest(), 'no_package_install': True, 'shared_environments_changed': False}
(HERE / 'dependency-export-manifest.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'packages': [{k:v for k,v in p.items() if k != 'skipped'} for p in packages], 'files': len(entries), 'bytes': sum(p['copied_bytes'] for p in packages), 'archive_sha256': result['archive_sha256']}))
