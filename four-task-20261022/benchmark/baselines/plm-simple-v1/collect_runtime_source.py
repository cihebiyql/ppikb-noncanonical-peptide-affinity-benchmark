"""Read-only source provenance for the actual installed fair-esm2.0 package, no model import."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
receipt=json.loads((ROOT/'runs/plm-simple-v1/feature-canary-cpu-v3/receipt.json').read_text())
entry=next(Path(path) for path in receipt['esm_source_hashes'] if path.endswith('/esm/__init__.py'))
source=entry.parent
assert source==Path('/data/qlyu/anaconda3/envs/cuda12.1/lib/python3.11/site-packages/esm')
destination=HERE/'actual-runtime-source/esm'
destination.mkdir(parents=True,exist_ok=False)
files=[]
for path in sorted(source.rglob('*.py')):
    data=path.read_bytes();digest=hashlib.sha256(data).hexdigest()
    if str(path) in receipt['esm_source_hashes']:
        assert digest==receipt['esm_source_hashes'][str(path)]
    target=destination/path.relative_to(source);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    files.append({'source':str(path),'archived_path':target.relative_to(HERE).as_posix(),'bytes':len(data),'sha256':digest})
manifest={'installed_distribution':'fair-esm2.0.0','source_files':files,'file_count':len(files),
          'upstream_main_reference_commit':'2b369911bb5b4b0dda914521b9475cad1656b2ac',
          'installed_distribution_commit_is_not_inferred_from_main_reference':True,
          'new_imports_or_forward_count':0,'shared_environment_modified':False}
(HERE/'actual-runtime-source/source-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps({'files':len(files),'bytes':sum(row['bytes'] for row in files)}))
