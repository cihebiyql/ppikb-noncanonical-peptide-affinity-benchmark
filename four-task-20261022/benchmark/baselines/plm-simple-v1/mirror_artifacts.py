"""Archive and verify every owned scientific artifact; do not execute stored weights."""
import argparse
import datetime as dt
import hashlib
import json
import socket
import tarfile
from pathlib import Path, PurePosixPath

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024**2),b''):digest.update(block)
    return digest.hexdigest()

def archive():
    assert socket.gethostname()=='node23'
    run=ROOT/'runs/plm-simple-v1'
    process=json.loads((run/'heads/process-receipt.json').read_text())
    assert process['exit_code']==0 and process['worker_pid_absent'] and not process['termination_reason']
    independent=json.loads((run/'heads/independent-recalculation.json').read_text())
    assert independent['passed'] and independent['selected_runs']==150
    files=[p for p in run.rglob('*') if p.is_file()]
    files += [p for p in (HERE/'feature-cache-cpu-v3').rglob('*') if p.is_file()]
    files += [p for p in (HERE/'actual-runtime-source').rglob('*') if p.is_file()]
    for name in ['feature-cache-binding.json','head-run-spec.json','head-runtime-canary.json',
                 'cpu-extraction-spec-canary.json','cpu-extraction-spec-formal.json',
                 'generic-contract-validation.cpu-revision3.json','generic-contract-validation.revision2.json',
                 'cpu-canary-supervisor.log','cpu-formal-supervisor.log','cpu-formal-supervisor.revision2.log',
                 'cpu-head-supervisor.log','continuation-chain.log','continuation-chain-receipt.json']:
        path=HERE/name
        if path.exists():files.append(path)
    files=sorted(set(files))
    items=[{'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in files]
    manifest=HERE/'full-artifact-source-manifest.json'
    manifest.write_text(json.dumps({'source_host':'node23','recorded_at':dt.datetime.now(dt.timezone.utc).isoformat(),
        'file_count':len(items),'bytes':sum(r['bytes'] for r in items),'files':items,
        'new_fit_count':0,'new_forward_count':0,'scientific_selected_runs':150},indent=2),encoding='utf-8')
    path=HERE/'full-artifacts.tar.gz';assert not path.exists()
    with tarfile.open(path,'w:gz',compresslevel=1) as tar:
        for p in files+[manifest]:tar.add(p,arcname=p.relative_to(ROOT).as_posix())
    receipt={'archive_bytes':path.stat().st_size,'archive_sha256':sha(path),
             'manifest_sha256':sha(manifest),'files':len(items),'source_bytes':sum(r['bytes'] for r in items),
             'new_fit_count':0,'new_forward_count':0}
    (HERE/'archive-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8');print(json.dumps(receipt))

def receive():
    receipt=json.loads((HERE/'archive-receipt.json').read_text());path=HERE/'full-artifacts.tar.gz'
    assert path.stat().st_size==receipt['archive_bytes'] and sha(path)==receipt['archive_sha256']
    manifest_name='baselines/plm-simple-v1/full-artifact-source-manifest.json'
    with tarfile.open(path,'r:gz') as tar:
        manifest=json.loads(tar.extractfile(manifest_name).read())
        items={r['path']:r for r in manifest['files']}
        for member in tar.getmembers():
            relative=PurePosixPath(member.name);target=(ROOT/Path(member.name)).resolve()
            assert not relative.is_absolute() and '..' not in relative.parts and member.isfile()
            assert target.is_relative_to(ROOT.resolve())
            assert member.name.startswith('runs/plm-simple-v1/') or member.name.startswith('baselines/plm-simple-v1/')
            expected=items[member.name]['sha256'] if member.name in items else receipt['manifest_sha256']
            if target.exists():assert sha(target)==expected;continue
            target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as out:
                stream=tar.extractfile(member)
                for block in iter(lambda:stream.read(1024**2),b''):out.write(block)
        failures=[]
        for item in manifest['files']:
            target=ROOT/Path(item['path'])
            if target.stat().st_size!=item['bytes'] or sha(target)!=item['sha256']:failures.append(item['path'])
    result={'passed':not failures,'errors':failures,'files_verified':manifest['file_count'],
            'bytes_verified':manifest['bytes'],'source_host':'node23','new_fit_count':0,'new_forward_count':0,
            'archive_sha256':receipt['archive_sha256'],'old_failures_preserved':True,
            'remote_to_local_prefix_mapping':{'remote':'/data/qlyu/projects/peptide-four-task-benchmark-20261022','local':str(ROOT)}}
    (HERE/'local-mirror-receipt.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result));assert not failures

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['archive','receive']);args=p.parse_args()
    archive() if args.mode=='archive' else receive()
