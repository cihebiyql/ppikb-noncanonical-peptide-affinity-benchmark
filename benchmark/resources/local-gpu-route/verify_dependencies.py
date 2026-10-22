import hashlib
import importlib
import importlib.metadata as md
import json
from pathlib import Path
import sys
import sysconfig
import tarfile

HERE = Path(__file__).resolve().parent
manifest = json.loads((HERE / 'dependency-export-manifest.json').read_text())
archive = HERE / 'vendor-dependencies-v1.tar.gz'
assert hashlib.sha256(archive.read_bytes()).hexdigest() == manifest['archive_sha256']
assert sys.version_info[:2] == (3, 11)
assert sysconfig.get_config_var('SOABI') == manifest['source_SOABI']
dest = HERE / 'vendor-dependencies'
dest.mkdir(exist_ok=False)
with tarfile.open(archive) as bundle:
    for member in bundle.getmembers():
        if member.issym() or member.islnk() or not (dest / member.name).resolve().is_relative_to(dest.resolve()):
            raise RuntimeError('Unsafe member')
    bundle.extractall(dest)
for row in manifest['files']:
    path = dest / row['relative_path']
    assert path.stat().st_size == row['bytes']
    assert hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256']
sys.path.insert(0, str(dest))
names = {'torch-geometric':'torch_geometric', 'aiohttp':'aiohttp', 'psutil':'psutil', 'pyparsing':'pyparsing', 'xxhash':'xxhash', 'frozenlist':'frozenlist', 'multidict':'multidict', 'propcache':'propcache', 'yarl':'yarl', 'aiohappyeyeballs':'aiohappyeyeballs', 'aiosignal':'aiosignal'}
imports = {}
for name, module in names.items():
    loaded = importlib.import_module(module)
    imports[name] = {'version': md.version(name), 'file': str(Path(loaded.__file__).resolve())}
result = {'all_846_copied_file_hashes_match': True, 'source_target_ABI_match': True, 'SOABI': sysconfig.get_config_var('SOABI'), 'imports': imports, 'installation_performed': False, 'shared_runtime_modified': False}
(HERE / 'dependency-import-verification.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result))
