import json,hashlib,tarfile,datetime as dt,os
from pathlib import Path
H=Path(r'D:\work\科研工作台\research-tasks\peptide-four-task-benchmark-20261022/methods/dta/administrative-preservation-v1');archive=H/'partial-and-failed-assets.tar.gz';receipt=json.loads((H/'source-receipt.json').read_text());manifest=json.loads((H/'source-manifest.json').read_text());expected={x['path']:x for x in manifest['files']}
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024**2),b''):h.update(b)
 return h.hexdigest()
assert archive.stat().st_size==receipt['archive_bytes'] and sha(archive)==receipt['archive_sha256'];dest=(H/'restored').resolve();dest.mkdir(exist_ok=True);dest=Path(chr(92)*2+'?'+chr(92)+str(dest)) if os.name=='nt' else dest;seen=set()
with tarfile.open(archive,'r:gz') as tar:
 for member in tar:
  if member.name=='ADMINISTRATIVE_MANIFEST.json':continue
  assert member.isfile() and member.name in expected;out=(dest/Path(member.name)).resolve();assert dest in out.parents;data=tar.extractfile(member).read();e=expected[member.name];assert len(data)==e['bytes'] and hashlib.sha256(data).hexdigest()==e['sha256'];out.parent.mkdir(parents=True,exist_ok=True)
  if out.exists():assert sha(out)==e['sha256']
  else:out.write_bytes(data)
  seen.add(member.name)
assert seen==set(expected)
record={'at':dt.datetime.now(dt.timezone.utc).isoformat(),'local_archive':str(archive),'local_restored_root':str(dest),'archive_bytes':archive.stat().st_size,'archive_sha256':receipt['archive_sha256'],'all_archive_and_file_hashes_match':True,'files_restored':len(seen),'restored_source_bytes':manifest['total_bytes'],'checkpoints':receipt['checkpoints'],'scientific_partial_attempt_directories':receipt['scientific_partial_units'],'original_remote_files_changed':False,'scientific_models_executed':False};(H/'local-preservation-receipt.json').write_text(json.dumps(record,indent=2));print(json.dumps(record))
