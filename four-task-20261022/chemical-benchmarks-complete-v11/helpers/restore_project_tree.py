"""Restore disclosed self-authored files without modifying existing different bytes.

Standard library only. Third-party libraries, original datasets and upstream
weights are obtained separately from their attributed official sources.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath


def digest(data):return hashlib.sha256(data).hexdigest()


def relative_ref(ref):
    prefix='record-ref:project/'
    if not isinstance(ref,str) or not ref.startswith(prefix):raise ValueError('Expected a project-relative source reference')
    raw=ref[len(prefix):];p=PurePosixPath(raw)
    if not raw or '\\' in raw or ':' in raw or p.is_absolute() or any(x in ('','.','..') for x in raw.split('/')):raise ValueError('Unsafe source reference')
    return p


def confined(base,relative):
    base=Path(base).resolve();relative=PurePosixPath(relative)
    if relative.is_absolute() or any(x in ('','..') for x in relative.parts):raise ValueError('Unsafe relative path')
    path=base.joinpath(*relative.parts);cursor=path
    while cursor!=base:
        if cursor.is_symlink():raise ValueError('Symlinks in a restore path are forbidden')
        cursor=cursor.parent
    if not path.resolve().is_relative_to(base):raise ValueError('Restore path escapes the target tree')
    return path


def restore(sources,destination):
    raw_destination=os.path.abspath(os.fspath(destination))
    if os.name=='nt' and not raw_destination.startswith('\\\\?\\'):raw_destination='\\\\?\\'+raw_destination
    destination=Path(raw_destination)
    if destination.is_symlink():raise ValueError('Destination symlink forbidden')
    pending={}
    for bundle in sources:
        bundle=Path(bundle).resolve()
        mapping=json.loads((bundle/'SOURCE-MAPPING.json').read_text(encoding='utf-8'))
        for entry in mapping['entries']:
            public=PurePosixPath(entry['public_path'])
            if not public.parts or public.parts[0]!='code' or public.suffix not in ('.py','.json'):continue
            relative=relative_ref(entry['source_ref']);source=confined(bundle,public);data=source.read_bytes()
            if digest(data)!=entry['public_sha256']:raise ValueError('Published source bytes fail their recorded SHA')
            transform='public bytes'
            if entry.get('restore_policy')=='public_portable_path_adapter':
                # Explicitly disclosed environment-only adapter: never report
                # these bytes as the original executed scientific source.
                transform='disclosed portable path adapter; original source SHA is provenance only'
            elif public.suffix=='.py':
                normalized=data.replace(b'\r\r\n',b'\n').replace(b'\r\n',b'\n').replace(b'\r',b'\n')
                candidates=[('public bytes',data),('LF recovery',normalized),('CRLF recovery',normalized.replace(b'\n',b'\r\n'))]
                match=next(((name,value) for name,value in candidates if digest(value)==entry['source_sha256']),None)
                if match is None:raise ValueError('Original scientific source SHA cannot be safely recovered')
                transform,data=match
            elif entry.get('pinned_original_bytes') or relative.name in ('ringfix-recipe.json','recipe.json','NN-SOURCE-MANIFEST.json'):
                if digest(data)!=entry['source_sha256']:raise ValueError('Pinned JSON original bytes changed')
            target=confined(destination,relative)
            if target in pending and pending[target][0]!=data:raise ValueError('Conflicting versions in supplied bundles')
            if target.exists() and (not target.is_file() or target.read_bytes()!=data):raise ValueError('Refuse to overwrite different existing bytes')
            pending[target]=(data,{'project_relative_path':relative.as_posix(),'source_sha256':entry['source_sha256'],'public_sha256':entry['public_sha256'],'restored_sha256':digest(data),'original_source_bytes_restored':digest(data)==entry['source_sha256'],'transform':transform})
    if not pending:raise ValueError('No eligible self-authored source files')
    result=[]
    for path,(data,entry) in sorted(pending.items(),key=lambda x:str(x[0])):
        path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():
            with path.open('xb') as stream:stream.write(data)
        elif path.read_bytes()!=data:raise ValueError('Concurrent target change')
        result.append(entry)
    return {'schema':'public-project-code-recovery.v2','restored_files':result,'models_loaded':0,'scientific_fits':0,'scientific_predictions':0}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,action='append',required=True);parser.add_argument('--destination',type=Path,required=True);parser.add_argument('--receipt',type=Path,required=True)
    args=parser.parse_args();result=restore(args.source,args.destination)
    with args.receipt.open('x',encoding='utf-8',newline='\n') as stream:json.dump(result,stream,indent=2);stream.write('\n')


if __name__=='__main__':main()
