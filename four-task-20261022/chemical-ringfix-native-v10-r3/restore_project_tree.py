"""Restore disclosed self-authored code into a fresh project layout. Standard library only."""
from pathlib import Path, PurePosixPath
import argparse, hashlib, json

def digest(data): return hashlib.sha256(data).hexdigest()

def relative_ref(ref):
    prefix='record-ref:project/'
    if not isinstance(ref,str) or not ref.startswith(prefix):raise ValueError('Expected project-relative source reference')
    raw=ref[len(prefix):]
    p=PurePosixPath(raw)
    if not raw or '\\' in raw or ':' in raw or p.is_absolute() or any(x in ('..','.') for x in raw.split('/')):
        raise ValueError('Unsafe source reference')
    return p

def confined(base,relative):
    if relative.is_absolute() or any(x=='..' for x in relative.parts):raise ValueError('Unsafe relative path')
    base=Path(base).resolve();p=base.joinpath(*relative.parts)
    cursor=p
    while cursor!=base:
        if cursor.is_symlink():raise ValueError('Symlink in restore path')
        cursor=cursor.parent
    if not p.resolve().is_relative_to(base):raise ValueError('Path escapes root')
    return p

def restore(sources,destination):
    destination=Path(destination)
    if destination.is_symlink():raise ValueError('Destination symlink forbidden')
    pending={}
    for bundle in sources:
        bundle=Path(bundle).resolve()
        mapping=json.loads((bundle/'SOURCE-MAPPING.json').read_text(encoding='utf-8'))
        for entry in mapping['entries']:
            rel=relative_ref(entry['source_ref'])
            public=PurePosixPath(entry['public_path'])
            if not public.parts or public.parts[0]!='code' or public.suffix not in ('.py','.json'):continue
            source=confined(bundle,public);data=source.read_bytes()
            if digest(data)!=entry['public_sha256']:raise ValueError('Disclosed bytes fail public SHA')
            transform='public JSON bytes'
            if public.suffix=='.py':
                normalized=data.replace(b'\r\r\n',b'\n').replace(b'\r\n',b'\n').replace(b'\r',b'\n')
                options=[('public bytes',data),('LF recovery',normalized),('CRLF recovery',normalized.replace(b'\n',b'\r\n'))]
                match=next(((name,b) for name,b in options if digest(b)==entry['source_sha256']),None)
                if match is None:raise ValueError('Original code SHA cannot be recovered safely')
                transform,data=match
            elif rel.name=='ringfix-recipe.json' and digest(data)!=entry['source_sha256']:
                raise ValueError('Pinned recipe must preserve original SHA')
            target=confined(destination,rel)
            if target in pending and pending[target][0]!=data:raise ValueError('Conflicting disclosed code sources')
            if target.exists() and (not target.is_file() or target.read_bytes()!=data):raise ValueError('Refuse different existing destination bytes')
            pending[target]=(data,{'project_relative_path':rel.as_posix(),'public_sha256':entry['public_sha256'],'source_sha256':entry['source_sha256'],'restored_sha256':digest(data),'transform':transform})
    if not pending:raise ValueError('No eligible self-authored code entries')
    receipt=[]
    for target,(data,record) in sorted(pending.items(),key=lambda kv:str(kv[0])):
        target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():
            with target.open('xb') as f:f.write(data)
        elif target.read_bytes()!=data:raise ValueError('Concurrent destination change')
        receipt.append(record)
    return {'schema':'public-project-code-recovery.v1','restored_files':receipt,'models_loaded':0,'scientific_fits':0,'scientific_predictions':0}

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,action='append',required=True);p.add_argument('--destination',type=Path,required=True);p.add_argument('--receipt',type=Path)
    a=p.parse_args();receipt=restore(a.source,a.destination)
    text=json.dumps(receipt,indent=2)+'\n'
    if a.receipt:
        with a.receipt.open('x',encoding='utf-8') as f:f.write(text)
    print(text,end='')
if __name__=='__main__':main()
