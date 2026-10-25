"""Acquire pinned official assets without regenerating frozen receipts.

Default is a plan only. --fetch explicitly downloads missing upstream files and
restores only the22 hash-locked wheel members. No package installation, model
loading, training or remote-code execution occurs in this helper.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import urllib.parse
import urllib.request
import zipfile

from restore_scientific_inputs import native_root


def file_sha(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda:stream.read(1024*1024),b''):value.update(data)
    return value.hexdigest()


def target_path(root,raw):
    relative=PurePosixPath(raw)
    if not raw or '\\' in raw or ':' in raw or relative.is_absolute() or any(x in ('','.','..') for x in raw.split('/')):raise ValueError('Unsafe locked asset destination')
    target=root.joinpath(*relative.parts)
    if not target.resolve().is_relative_to(root.resolve()):raise ValueError('Asset path escapes project')
    cursor=target
    while cursor!=root:
        if cursor.is_symlink():raise ValueError('Asset symlink forbidden')
        cursor=cursor.parent
    return target


def official_url(url):
    parsed=urllib.parse.urlsplit(url)
    allowed={'huggingface.co','raw.githubusercontent.com','files.pythonhosted.org'}
    if parsed.scheme!='https' or parsed.hostname not in allowed or parsed.username or parsed.password:raise ValueError('Only declared official HTTPS asset URLs are accepted')


def acquire(lock,project,fetch=False):
    project=native_root(project);downloaded=0;already=0;missing=[]
    if project.is_symlink():raise ValueError('Project symlink forbidden')
    for item in lock['files']:
        official_url(item['url']);target=target_path(project,item['project_relative_path'])
        if target.exists():
            if target.stat().st_size!=item['size_bytes'] or file_sha(target)!=item['sha256']:raise ValueError('Refuse changed existing upstream asset')
            already+=1;continue
        missing.append({'project_relative_path':item['project_relative_path'],'size_bytes':item['size_bytes'],'sha256':item['sha256']})
        if not fetch:continue
        target.parent.mkdir(parents=True,exist_ok=True)
        partial=target.with_name(target.name+'.download-partial')
        if partial.exists():raise ValueError('Preserve existing partial download; choose an explicit recovery action')
        value=hashlib.sha256();size=0
        request=urllib.request.Request(item['url'],headers={'User-Agent':'PPIKB-public-pinned-input-recovery/1'})
        with urllib.request.urlopen(request,timeout=120) as response,partial.open('xb') as stream:
            if urllib.parse.urlsplit(response.url).scheme!='https':raise ValueError('Reject non-HTTPS redirect')
            for data in iter(lambda:response.read(1024*1024),b''):
                stream.write(data);value.update(data);size+=len(data)
                if size>item['size_bytes']:raise ValueError('Download exceeds frozen size; partial retained')
        if size!=item['size_bytes'] or value.hexdigest()!=item['sha256']:raise ValueError('Official file hash mismatch; partial retained')
        if target.exists():raise ValueError('Concurrent asset appeared; partial retained')
        # Publish the validated bytes without replacing any pre-existing file.
        with partial.open('rb') as source,target.open('xb') as output:
            for data in iter(lambda:source.read(1024*1024),b''):output.write(data)
        partial.unlink();downloaded+=1
    vendor_count=0
    if fetch:
        for item in lock['vendor_members']:
            target=target_path(project,item['project_relative_path']);wheel=target_path(project,item['wheel_project_relative_path'])
            member=item['zip_member'];relative=PurePosixPath(member)
            if relative.is_absolute() or '\\' in member or any(x in ('','.','..') for x in member.split('/')):raise ValueError('Unsafe wheel member')
            with zipfile.ZipFile(wheel) as archive:
                info=archive.getinfo(member)
                if info.file_size!=item['size_bytes'] or info.file_size>4*1024**2:raise ValueError('Wheel member exceeds original bounds')
                data=archive.read(info)
            if hashlib.sha256(data).hexdigest()!=item['sha256']:raise ValueError('Original vendor member hash differs')
            if target.exists():
                if target.read_bytes()!=data:raise ValueError('Refuse different existing vendor bytes')
            else:
                target.parent.mkdir(parents=True,exist_ok=True)
                with target.open('xb') as stream:stream.write(data)
            vendor_count+=1
    return {'schema':'public-official-input-recovery-execution.v1','mode':'fetch' if fetch else 'plan_only','locked_files':len(lock['files']),'already_present_verified':already,'missing_or_downloaded_files':missing,'new_downloads':downloaded,'original_vendor_members_verified':vendor_count,'frozen_receipts_rewritten':False,'packages_installed':0,'models_loaded':0,'new_fits':0,'new_predictions':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--lock',type=Path,required=True);parser.add_argument('--project',type=Path,required=True);parser.add_argument('--fetch',action='store_true');parser.add_argument('--receipt',type=Path,required=True)
    args=parser.parse_args();lock=json.loads(args.lock.read_text(encoding='utf-8'))
    result=acquire(lock,args.project,args.fetch)
    with args.receipt.open('x',encoding='utf-8',newline='\n') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='missing_or_downloaded_files'},indent=2))
