"""Upload only locked artifact files to an already-created draft release."""
import argparse
from concurrent.futures import ThreadPoolExecutor,as_completed
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
from datetime import datetime,timezone


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def validated(asset, expected):
    return asset.get('name')==expected['name'] and asset.get('size')==expected['bytes'] and asset.get('state')=='uploaded' and asset.get('digest')=='sha256:'+expected['sha256']


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--manifest',required=True);parser.add_argument('--assets',required=True)
    parser.add_argument('--audit',required=True);args=parser.parse_args()
    manifest=json.loads(Path(args.manifest).read_text());repo=manifest['repository'];tag=manifest['tag']
    assert repo=='cihebiyql/ppikb-noncanonical-peptide-affinity-benchmark' and tag=='v1.0.0'
    audit=Path(args.audit);audit.mkdir(parents=True,exist_ok=False);root=Path(args.assets)
    environment=dict(os.environ)
    for name in ['GH_DEBUG','GIT_TRACE','GIT_CURL_VERBOSE']:environment.pop(name,None)
    def gh(argv,timeout=120):
        return subprocess.run(['gh',*argv],capture_output=True,text=True,encoding='utf-8',env=environment,timeout=timeout,
                              creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    def release():
        r=gh(['api',f'repos/{repo}/releases/tags/{tag}']);assert r.returncode==0,r.stderr
        return json.loads(r.stdout)
    first=release();assert first['draft'] is True and first['tag_name']==tag
    release_id=first['id'];jobs=[];lock=threading.Lock()
    files=manifest['parts']+[dict(name='SHA256SUMS',bytes=(root/'SHA256SUMS').stat().st_size,sha256=digest(root/'SHA256SUMS'))]
    def save():
        temp=audit/'progress.tmp';temp.write_text(json.dumps(dict(release_id=release_id,tag=tag,jobs=jobs),indent=2)+'\n');os.replace(temp,audit/'progress.json')
    def upload(entry):
        path=root/entry['name'];assert path.stat().st_size==entry['bytes'] and digest(path)==entry['sha256']
        with lock:
            item=dict(name=entry['name'],status='uploading',expected=entry,started_at=datetime.now(timezone.utc).isoformat());jobs.append(item);save()
        current=release();assert current['id']==release_id and current['draft'] is True
        same=[a for a in current['assets'] if a['name']==entry['name']]
        if same:
            assert len(same)==1 and validated(same[0],entry),'Existing remote asset differs: '+entry['name']
            result_code=0;remote=same[0]
        else:
            result=gh(['release','upload',tag,str(path),'--repo',repo],timeout=3600)
            (audit/(entry['name']+'.stdout.log')).write_text(result.stdout,encoding='utf-8')
            (audit/(entry['name']+'.stderr.log')).write_text(result.stderr,encoding='utf-8')
            result_code=result.returncode
            remote=next((a for a in release()['assets'] if a['name']==entry['name']),{})
            assert validated(remote,entry),'Remote size/state/digest check failed: '+entry['name']+'; native exit='+str(result_code)
        with lock:
            item.update(status='uploaded_and_server_digest_verified',native_exit_code=result_code,remote_id=remote['id'],remote_digest=remote['digest'],remote_bytes=remote['size'],url=remote['browser_download_url'],finished_at=datetime.now(timezone.utc).isoformat());save()
        print(json.dumps(dict(asset=entry['name'],status=item['status'])),flush=True)
        return item
    failures=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        pending={pool.submit(upload,e):e for e in files}
        for future in as_completed(pending):
            try:future.result()
            except Exception as error:
                failures.append(dict(name=pending[future]['name'],error=str(error)))
                print(json.dumps(failures[-1]),flush=True)
    final=release();expected={e['name']:e for e in files}
    checks=[validated(a,expected[a['name']]) for a in final['assets'] if a['name'] in expected]
    success=not failures and len(checks)==len(expected) and all(checks)
    receipt=dict(status='all_assets_server_digest_verified' if success else 'failed_preserved',repository=repo,tag=tag,release_id=release_id,release_still_draft=final['draft'],expected_assets=len(expected),actual_verified_assets=sum(checks),jobs=jobs,failures=failures)
    (audit/'UPLOAD-RESULT.json').write_text(json.dumps(receipt,indent=2)+'\n')
    if not success:raise SystemExit(1)


if __name__=='__main__':main()
