"""Publishable snapshot builder. Never edits the scientific source tree."""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import tarfile
import time

CHUNK = 1024 * 1024
BINARY = {'.pt','.pth','.pkl','.joblib','.npy','.npz','.so','.dll','.gz','.zip','.xz','.tar'}
SECRETS = [
    ('private_key',re.compile(rb'-----BEGIN (?:OPENSSH |RSA |EC |DSA )?PRIVATE KEY-----')),
    ('github_token',re.compile(rb'(?<![A-Za-z0-9])(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})')),
    ('openai_key',re.compile(rb'(?<![A-Za-z0-9])sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}')),
    ('aws_access_key',re.compile(rb'(?<![A-Za-z0-9])(?:AKIA|ASIA)[A-Z0-9]{16}(?![A-Z0-9])')),
    ('slack_token',re.compile(rb'xox[baprs]-[A-Za-z0-9-]{20,}')),
]


def fs(q):
    q=Path(q).absolute()
    return Path('\\\\?\\'+str(q)) if os.name=='nt' and not str(q).startswith('\\\\?\\') else q


def dump(q, value):
    q=Path(q);q.parent.mkdir(parents=True,exist_ok=True)
    temp=q.with_suffix(q.suffix+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    os.replace(temp,q)


def sha(q):
    h=hashlib.sha256()
    with Path(q).open('rb') as f:
        for data in iter(lambda:f.read(CHUNK),b''):h.update(data)
    return h.hexdigest()


class SplitWriter:
    def __init__(self, root, progress, size=1000*1024**2):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=False)
        self.limit=size;self.progress=progress;self.file=None;self.assets=[];self.total=0

    def open_part(self):
        self.name='benchmark-artifacts.tar.gz.part%03d'%(len(self.assets)+1)
        self.file=(self.root/self.name).open('xb');self.n=0;self.h=hashlib.sha256()

    def finish_part(self):
        if self.file is None:return
        self.file.flush();self.file.close()
        self.assets.append(dict(name=self.name,bytes=self.n,sha256=self.h.hexdigest()))
        self.file=None
        dump(self.progress,dict(stage='packing',closed_assets=self.assets,total_compressed_bytes=self.total))

    def write(self, data):
        original=len(data);view=memoryview(data)
        while view:
            if self.file is None:self.open_part()
            amount=min(len(view),self.limit-self.n);part=view[:amount]
            self.file.write(part);self.h.update(part);self.n+=amount;self.total+=amount;view=view[amount:]
            if self.n==self.limit:self.finish_part()
        return original

    def flush(self):
        if self.file is not None:self.file.flush()

    def close(self):self.finish_part()


class HashReader:
    def __init__(self,file,path,scan):
        self.file=file;self.path=path;self.hash=hashlib.sha256();self.n=0;self.scan=scan;self.tail=b''

    def read(self,n=-1):
        data=self.file.read(n);self.hash.update(data);self.n+=len(data)
        if self.scan and data:
            joined=self.tail+data
            for kind,pattern in SECRETS:
                if pattern.search(joined):raise ValueError('Potential credential: '+kind+' in '+self.path+'; value withheld')
            self.tail=joined[-512:]
        return data


def exclusion(rel, policy):
    if '__pycache__' in Path(rel).parts or Path(rel).suffix.lower()=='.pyc':return 'Regenerable Python bytecode'
    if '.git' in Path(rel).parts:return 'Unreviewed nested Git history'
    for item in policy.get('excluded_prefixes',[]):
        if rel.startswith(item['prefix']):return item['reason']
    for item in policy.get('excluded_paths',[]):
        if rel==item['path']:return item['reason']
    return None


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',required=True);parser.add_argument('--inventory',required=True)
    parser.add_argument('--policy',required=True);parser.add_argument('--repo',required=True);parser.add_argument('--assets',required=True)
    parser.add_argument('--audit',required=True);args=parser.parse_args()
    source=Path(args.source).resolve();repo=Path(args.repo).resolve();audit=Path(args.audit).resolve()
    assert not repo.is_relative_to(source) and not source.is_relative_to(repo)
    assert not repo.exists(),'New publication directory required'
    policy=json.loads(Path(args.policy).read_text(encoding='utf-8-sig'))
    assert policy['root_publication_preflight_accepted'] is True
    inventory=json.loads(Path(args.inventory).read_text(encoding='utf-8-sig'));assert not inventory['symlinks']
    repo.mkdir(parents=True);(repo/'manifest').mkdir()
    shutil.copyfile(args.policy,repo/'manifest/PUBLICATION-POLICY.json')
    writer=SplitWriter(args.assets,audit/'packaging-progress.json')
    manifests=[];excluded=[];start=time.time();done=0;total=0
    with gzip.GzipFile(fileobj=writer,mode='wb',filename='',mtime=0,compresslevel=1) as zipped:
        with tarfile.open(fileobj=zipped,mode='w|',format=tarfile.PAX_FORMAT) as tar:
            for entry in inventory['files']:
                rel=entry['path'];q=source/rel;assert q.is_relative_to(source) and not q.is_symlink()
                reason=exclusion(rel,policy)
                if reason:
                    excluded.append(dict(entry,reason=reason));continue
                assert fs(q).stat().st_size==entry['bytes'],rel+' changed since inventory'
                binary=Path(rel).suffix.lower() in BINARY
                storage='release' if binary or entry['bytes']>16*1024**2 else 'git'
                with fs(q).open('rb') as original:
                    reader=HashReader(original,rel,scan=not binary)
                    if storage=='release':
                        info=tarfile.TarInfo('benchmark/'+rel);info.size=entry['bytes'];info.mode=0o644;info.mtime=0
                        tar.addfile(info,reader)
                    else:
                        dest=repo/'benchmark'/rel;fs(dest.parent).mkdir(parents=True,exist_ok=True)
                        with fs(dest).open('xb') as output:
                            for data in iter(lambda:reader.read(CHUNK),b''):output.write(data)
                    assert reader.n==entry['bytes'],rel+' read length mismatch'
                    manifests.append(dict(entry,sha256=reader.hash.hexdigest(),storage=storage,public_path='benchmark/'+rel,modified=False))
                done+=1;total+=entry['bytes']
                if done%250==0:
                    dump(audit/'file-progress.json',dict(stage='packing',files=done,uncompressed_bytes=total,seconds=time.time()-start,current=rel,closed_assets=len(writer.assets)))
    writer.close()
    with (repo/'manifest/source-files.jsonl').open('x',encoding='utf-8') as h:
        for row in manifests:h.write(json.dumps(row,ensure_ascii=False)+'\n')
    with (repo/'manifest/excluded-files.jsonl').open('x',encoding='utf-8') as h:
        for row in excluded:h.write(json.dumps(row,ensure_ascii=False)+'\n')
    assets=dict(schema='split-gzip-tar-artifacts.v1',repository=policy['repository'],tag=policy['release_tag'],archive='benchmark-artifacts.tar.gz',parts=writer.assets,
                compressed_bytes=writer.total,files=sum(r['storage']=='release' for r in manifests),format='Concatenate parts in listed order to recover a gzip-compressed tar archive; member paths start with benchmark/.')
    dump(repo/'manifest/artifact-assets.json',assets)
    result=dict(status='packaged_not_uploaded',included_files=len(manifests),excluded_files=len(excluded),original_files=len(inventory['files']),git_files=sum(r['storage']=='git' for r in manifests),release_files=assets['files'],included_bytes=total,release_compressed_bytes=writer.total,release_parts=len(writer.assets),seconds=time.time()-start,original_scientific_files_modified=False,streaming_credential_scan_all_included_text_passed=True)
    assert len(manifests)+len(excluded)==len(inventory['files'])
    dump(repo/'manifest/packaging-summary.json',result);dump(audit/'PACKAGING-READY.json',dict(result,repository_root=str(repo),assets_root=args.assets,source_manifest_sha256=sha(repo/'manifest/source-files.jsonl'),asset_manifest_sha256=sha(repo/'manifest/artifact-assets.json')))
    print(json.dumps(result))


if __name__=='__main__':main()
