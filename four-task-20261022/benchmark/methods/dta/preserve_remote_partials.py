"""Read-only snapshot of all remotely retained DTA partial/failed scientific assets and dispatch evidence."""
import json,tarfile,hashlib,io,datetime as dt,os
from pathlib import Path
R=Path('/data/qlyu/projects/peptide-four-task-benchmark-20261022');H=R/'methods/dta';O=H/'administrative-preservation-v1';O.mkdir(exist_ok=True);archive=O/'partial-and-failed-assets.tar.gz';assert not archive.exists();roots=[];files=set();units=[]
for top in (R/'runs').iterdir():
 if not top.is_dir():continue
 if top.name.startswith('dta'):
  for started in top.rglob('started.json'):
   unit=started.parent
   if (unit/'complete.json').exists():continue
   units.append({'path':str(unit.relative_to(R)),'reason':'scientific_started_without_full_complete','checkpoint_count':len(list(unit.rglob('*.pt')))});roots.append(unit)
 elif top.name.startswith('resource-') and any(m in top.name for m in ['GraphDTA-GIN','MGraphDTA','DGDTA-CL','DeepNC-GEN','GS-DTA']):roots.append(top)
for name in ['node23-cpu-v1','node23-cpu-recovery-v2','node23-cpu-recovery-v3','node23-cached-v4','node23-cached-v5']:
 p=H/name
 if p.exists():roots.append(p)
for name in ['mgraph-backend-v4','mgraph-effect-backend-v4']:
 p=R/'resources'/name
 if p.exists():roots.append(p)
for root in roots:
 for p in root.rglob('*'):
  if p.is_symlink():raise RuntimeError('No symlink snapshots')
  if p.is_file():assert R in p.resolve().parents;files.add(p)
entries=[]
with tarfile.open(archive,'w:gz',compresslevel=1) as t:
 for p in sorted(files):
  data=p.read_bytes();rel=p.relative_to(R).as_posix();info=tarfile.TarInfo(rel);info.size=len(data);info.mtime=int(p.stat().st_mtime);info.mode=0o644;t.addfile(info,io.BytesIO(data));entries.append({'path':rel,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
 manifest={'at':dt.datetime.now(dt.timezone.utc).isoformat(),'scope':'Administrative read-only preservation after scientific deadline; original partial and failed scientific folders plus their dispatch/contracts; no model execution','source_root':str(R),'scientific_partial_units':units,'files':entries,'file_count':len(entries),'total_bytes':sum(e['bytes'] for e in entries),'checkpoints':sum(e['path'].endswith('.pt') for e in entries),'original_files_changed':False}
 payload=json.dumps(manifest,indent=2).encode();info=tarfile.TarInfo('ADMINISTRATIVE_MANIFEST.json');info.size=len(payload);info.mode=0o644;t.addfile(info,io.BytesIO(payload))
(O/'source-manifest.json').write_text(json.dumps(manifest,indent=2));receipt={'at':dt.datetime.now(dt.timezone.utc).isoformat(),'archive_path':str(archive),'archive_bytes':archive.stat().st_size,'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'files':len(entries),'source_bytes':manifest['total_bytes'],'checkpoints':manifest['checkpoints'],'scientific_partial_units':len(units)};(O/'source-receipt.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
