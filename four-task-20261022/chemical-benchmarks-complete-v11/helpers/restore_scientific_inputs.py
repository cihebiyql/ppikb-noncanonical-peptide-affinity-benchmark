"""Restore and verify immutable target-runtime input closure. Standard library only.

NPZ files are generated frozen features, not upstream neural weights. This tool
does not import NumPy/Torch, unpickle objects, fit a model or generate predictions.
"""
import argparse
import ast
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import struct
import tarfile
import zipfile

from scientific_path_bridge import path_bridge


def sha(data):return hashlib.sha256(data).hexdigest()


def native_root(path):
    value=os.path.abspath(os.fspath(path))
    if os.name=='nt' and not value.startswith('\\\\?\\'):value='\\\\?\\'+value
    return Path(value)


def relative_path(raw):
    p=PurePosixPath(raw)
    if not raw or '\\' in raw or ':' in raw or p.is_absolute() or any(x in ('','.','..') for x in raw.split('/')):raise ValueError('Unsafe archive/scientific path')
    return p


def check_npz(path):
    result={};keys=None;dimensions=None
    with zipfile.ZipFile(path) as archive:
        entries=archive.infolist()
        names={x.filename for x in entries}
        if len(entries)!=2 or names not in ({'sequence_ids.npy','embeddings.npy'},{'smiles_sha256.npy','embeddings.npy'}):raise ValueError('Only declared generated-feature fields are accepted')
        for item in entries:
            if item.file_size>32*1024**2:raise ValueError('Oversized NPZ member')
            data=archive.read(item)
            if data[:6]!=b'\x93NUMPY':raise ValueError('Not an NPY array')
            major,minor=data[6:8]
            if major==1:length=struct.unpack('<H',data[8:10])[0];offset=10
            elif major in (2,3):length=struct.unpack('<I',data[8:12])[0];offset=12
            else:raise ValueError('Unsupported NPY version')
            if length>65536 or offset+length>len(data):raise ValueError('Invalid/oversized NPY header')
            header=ast.literal_eval(data[offset:offset+length].decode('utf-8' if major==3 else 'latin1'))
            payload=data[offset+length:]
            if set(header)!={'descr','fortran_order','shape'} or header['fortran_order'] is not False:raise ValueError('Unexpected feature layout')
            shape=tuple(header['shape']);dtype=header['descr']
            if item.filename=='embeddings.npy':
                if dtype!='<f4' or len(shape)!=2 or len(payload)!=math.prod(shape)*4:raise ValueError('Expected exact FP32 two-dimensional embeddings')
                if not all(math.isfinite(x[0]) for x in struct.iter_unpack('<f',payload)):raise ValueError('Nonfinite frozen features')
                dimensions=shape
            else:
                if dtype!='<U64' or len(shape)!=1 or len(payload)!=shape[0]*64*4:raise ValueError('Expected exact raw-input SHA Unicode64 keys, no pickle/object arrays')
                text=payload.decode('utf-32-le');keys=[text[i*64:(i+1)*64].rstrip('\0') for i in range(shape[0])]
                if len(set(keys))!=len(keys) or any(re.fullmatch('[0-9a-f]{64}',x) is None for x in keys):raise ValueError('Invalid or duplicate raw-input SHA keys')
            result[item.filename]={'dtype':dtype,'shape':list(shape)}
    if dimensions[0]!=len(keys):raise ValueError('Key/embedding row mismatch')
    return {'fields':result,'rows':dimensions[0],'dimensions':dimensions[1],'keys':set(keys)}


def restore(archive_path,destination,expected_sha=None):
    archive_path=Path(archive_path);destination=native_root(destination)
    if destination.is_symlink():raise ValueError('Destination symlink forbidden')
    if expected_sha and sha(archive_path.read_bytes())!=expected_sha:raise ValueError('Scientific asset SHA mismatch')
    with tarfile.open(archive_path,'r:gz') as archive:
        members=archive.getmembers()
        if len({x.name for x in members})!=len(members):raise ValueError('Duplicate asset members')
        if any(not x.isfile() or x.size>16*1024**2 for x in members) or sum(x.size for x in members)>128*1024**2:raise ValueError('Unsafe asset member type/size')
        manifest=json.loads(archive.extractfile('SCIENTIFIC-INPUT-CLOSURE.original.json').read())
        files=manifest['files']
        index={x['archive_path']:x for x in files}
        if {x.name for x in members}!={*index,'SCIENTIFIC-INPUT-CLOSURE.original.json'}:raise ValueError('Asset inventory differs')
        pending=[]
        for member in members:
            if member.name not in index:continue
            entry=index[member.name];relative=relative_path(entry['project_relative_path'])
            if member.name!='project/'+relative.as_posix():raise ValueError('Inventory/archive path mismatch')
            data=archive.extractfile(member).read()
            if sha(data)!=entry['sha256'] or len(data)!=entry['size_bytes']:raise ValueError('Original scientific file changed')
            target=destination.joinpath(*relative.parts);cursor=target
            while cursor!=destination:
                if cursor.is_symlink():raise ValueError('Symlink in scientific restore target')
                cursor=cursor.parent
            if target.exists() and (not target.is_file() or target.read_bytes()!=data):raise ValueError('Refuse different existing scientific input bytes')
            pending.append((target,data))
        for target,data in pending:
            target.parent.mkdir(parents=True,exist_ok=True)
            if not target.exists():
                with target.open('xb') as stream:stream.write(data)
    return manifest


def verify(destination,manifest):
    destination=native_root(destination).resolve();tables={};checks=0;covered=[]
    with path_bridge(destination):
        for entry in manifest['files']:
            physical=destination/entry['project_relative_path']
            if sha(physical.read_bytes())!=entry['sha256']:raise ValueError('Restored source SHA drift')
            checks+=1
            if physical.suffix=='.npz':tables[entry['project_relative_path']]=check_npz(physical)
        for edge in manifest['runtime_dependency_edges']:
            physical=destination/edge['to']
            if sha(physical.read_bytes())!=edge['actual_sha256'] or (edge['expected_sha256'] and edge['actual_sha256']!=edge['expected_sha256']):raise ValueError('Runtime dependency SHA edge fails')
            checks+=1
        for start in manifest['starts']:
            path=destination/start['project_relative_path'];cohort=json.loads(path.read_text(encoding='utf-8'))
            if sha(path.read_bytes())!=start['sha256']:raise ValueError('Original cohort pin fails')
            view=next(x for x in cohort['views'] if '_target_' in x['id'])
            csv_path=Path(view['path'])
            if not csv_path.is_absolute():csv_path=path.parent/csv_path
            if sha(csv_path.read_bytes())!=view['sha256']:raise ValueError('Original cohort CSV pin fails')
            with csv_path.open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream))
            for item in cohort['model_cohort']['feature_specifications']:
                spec_path=Path(item['path'])
                if sha(spec_path.read_bytes())!=item['sha256']:raise ValueError('Original feature-spec pin fails')
                spec=json.loads(spec_path.read_text(encoding='utf-8'))
                def resolve(raw,parent):
                    value=Path(raw);return value if value.is_absolute() else parent/value
                binding_path=resolve(spec['protein_cache_binding'],spec_path.parent)
                if sha(binding_path.read_bytes())!=spec['protein_cache_binding_sha256']:raise ValueError('Protein binding pin fails')
                binding=json.loads(binding_path.read_text(encoding='utf-8'));directory=resolve(binding['directory'],binding_path.parent)
                protein=tables[(directory/'embeddings.npz').relative_to(destination).as_posix()]
                if protein['dimensions']!=320:raise ValueError('Wrong ESM dimension')
                if any(sha(row['target_sequence'].encode()) not in protein['keys'] for row in rows):raise ValueError('Protein cache does not cover exact original cohort')
                if spec['chemistry_mode']=='cached_encoder':
                    cache_path=resolve(spec['chemical_cache_manifest'],spec_path.parent)
                    if sha(cache_path.read_bytes())!=spec['chemical_cache_manifest_sha256']:raise ValueError('Chemical manifest pin fails')
                    cache=json.loads(cache_path.read_text(encoding='utf-8'));embedding=resolve(cache['embedding_file'],cache_path.parent)
                    chemistry=tables[embedding.relative_to(destination).as_posix()]
                    declared_dimension=spec.get('chemical_embedding_dimension',item.get('feature_audit',{}).get('chemical_dimension',cache['dimensions']))
                    if chemistry['dimensions']!=declared_dimension or chemistry['dimensions']!=cache['dimensions']:raise ValueError('Wrong chemistry dimension')
                    if any(sha(row['peptide_smiles'].encode()) not in chemistry['keys'] for row in rows):raise ValueError('Chemical cache does not cover exact original cohort')
                    canary_path=resolve(cache.get('chemical_canary_receipt','canary.json'),cache_path.parent)
                    if sha(canary_path.read_bytes())!=cache.get('chemical_canary_receipt_sha256',cache.get('canary_sha256')):raise ValueError('Canary source pin fails')
                    canary=json.loads(canary_path.read_text(encoding='utf-8'))
                    if canary['model_identity']!=cache['model_identity'] or canary.get('status')!='succeeded':raise ValueError('Canary/cache identity mismatch')
                covered.append({'cohort':start['scope'],'rows':len(rows),'feature_spec_sha256':item['sha256'],'protein_cache_rows':protein['rows'],'chemistry_mode':spec['chemistry_mode']})
    return {'schema':'public-scientific-runtime-input-restoration-check.v1','status':'passed','original_files_SHA_verified':len(manifest['files']),'runtime_dependency_SHA_edges_verified':len(manifest['runtime_dependency_edges']),'NPZ_tables':[{key:value for key,value in table.items() if key!='keys'} for table in tables.values()],'cohort_spec_coverage':covered,'standard_library_only':True,'models_loaded':0,'upstream_weights_read':0,'new_fits':0,'new_predictions':0,'scope':'Exact target runtime input closure; blocked-source/external/history-output references explicitly are not execution dependencies; no global closure graph rebuild or full neural training claim'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--archive',type=Path,required=True);parser.add_argument('--project',type=Path,required=True);parser.add_argument('--expected-sha256');parser.add_argument('--receipt',type=Path,required=True)
    args=parser.parse_args();manifest=restore(args.archive,args.project,args.expected_sha256);result=verify(args.project,manifest)
    with args.receipt.open('x',encoding='utf-8',newline='\n') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result,indent=2))
