"""Archive the completed owned branch and verify every delivered local byte; no fitting."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path, PurePosixPath
import socket
import tarfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
RUN=ROOT/'runs/plm-classification-contact-v1'

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024**2),b''):h.update(block)
    return h.hexdigest()

def write(path,obj):path.write_text(json.dumps(obj,indent=2,allow_nan=False),encoding='utf-8')

def archive():
    assert socket.gethostname()=='node23'
    pipeline=json.loads((HERE/'binary-pipeline-receipt.json').read_text())
    audit=json.loads((RUN/'heads/independent-recalculation.json').read_text())
    cache=json.loads((HERE/'independent-cache-audit.json').read_text())
    process=json.loads((RUN/'heads/process-receipt.json').read_text())
    assert pipeline['status']=='succeeded'
    assert audit['passed'] and audit['selected_runs']==100 and audit['candidate_fits']==200
    assert cache['passed']
    assert process['exit_code']==0 and process['worker_pid_absent'] and not process['surviving_group_pids']
    excluded={'binary-artifacts.tar.gz','source-artifact-manifest.json','archive-receipt.json','local-mirror-receipt.json'}
    files=sorted(p for p in RUN.rglob('*') if p.is_file())
    files+=sorted(p for p in HERE.rglob('*') if p.is_file() and p.name not in excluded and '__pycache__' not in p.parts and p.suffix!='.tar.gz')
    rows=[{'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in files]
    manifest=HERE/'source-artifact-manifest.json'
    write(manifest,{'source_host':'node23','recorded_at':dt.datetime.now(dt.timezone.utc).isoformat(),
        'files':rows,'file_count':len(rows),'bytes':sum(r['bytes'] for r in rows)})
    target=HERE/'binary-artifacts.tar.gz';assert not target.exists()
    with tarfile.open(target,'w:gz',compresslevel=1) as tar:
        for path in files+[manifest]:tar.add(path,arcname=path.relative_to(ROOT).as_posix())
    receipt={'archive_bytes':target.stat().st_size,'archive_sha256':sha(target),'manifest_sha256':sha(manifest),
        'source_file_count':len(rows),'source_bytes':sum(r['bytes'] for r in rows),'new_fit_count':0,'new_forward_count':0}
    write(HERE/'archive-receipt.json',receipt);print(json.dumps(receipt))

def receive():
    receipt=json.loads((HERE/'archive-receipt.json').read_text(encoding='utf-8'))
    path=HERE/'binary-artifacts.tar.gz'
    assert sha(path)==receipt['archive_sha256'] and path.stat().st_size==receipt['archive_bytes']
    manifest_name='baselines/plm-classification-contact-v1/source-artifact-manifest.json'
    with tarfile.open(path,'r:gz') as tar:
        manifest=json.loads(tar.extractfile(manifest_name).read())
        expected={r['path']:r for r in manifest['files']}
        for member in tar.getmembers():
            parts=PurePosixPath(member.name);target=(ROOT/Path(member.name)).resolve()
            assert not parts.is_absolute() and '..' not in parts.parts and member.isfile()
            assert target.is_relative_to(ROOT.resolve())
            assert member.name.startswith('runs/plm-classification-contact-v1/') or member.name.startswith('baselines/plm-classification-contact-v1/')
            digest=expected[member.name]['sha256'] if member.name in expected else receipt['manifest_sha256']
            if target.exists():assert sha(target)==digest,str(target);continue
            target.parent.mkdir(parents=True,exist_ok=True)
            with target.open('xb') as out:
                source=tar.extractfile(member)
                for block in iter(lambda:source.read(1024**2),b''):out.write(block)
    failures=[r['path'] for r in manifest['files'] if sha(ROOT/Path(r['path']))!=r['sha256'] or (ROOT/Path(r['path'])).stat().st_size!=r['bytes']]
    report={'passed':not failures,'errors':failures,'files_verified':manifest['file_count'],'bytes_verified':manifest['bytes'],
        'archive_sha256':receipt['archive_sha256'],'new_fit_count':0,'new_forward_count':0,'previous_results_changed':False}
    write(HERE/'local-mirror-receipt.json',report);print(json.dumps(report));assert not failures

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['archive','receive']);args=parser.parse_args()
    archive() if args.mode=='archive' else receive()
