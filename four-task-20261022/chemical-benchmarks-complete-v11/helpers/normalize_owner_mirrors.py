"""Copy byte-verified small owner mirrors into an immutable preparation input.

This is a metadata/file copier, not a scientific process. Conflicting snapshots
of the same remote file must be kept in distinct components rather than merged.
"""
import argparse
import json
import os
from pathlib import Path
from public_artifacts import sha


def normalize(maps, output):
    output=Path(output)
    if output.exists():raise FileExistsError(output)
    records={};sources=[]
    for manifest in maps:
        manifest=Path(manifest);raw=manifest.read_bytes();parsed=json.loads(raw)
        sources.append({'map_sha256':sha(raw),'archive_sha256':parsed.get('archive_sha256'),'source_files':len(parsed['files'])})
        for record in parsed['files']:
            source=Path(record.get('local_mirror') or record.get('local') or manifest.parent/record.get('archive_member',record.get('member','')))
            full=os.path.abspath(source)
            if os.name=='nt' and not full.startswith('\\\\?\\'):source=Path('\\\\?\\'+full)
            data=source.read_bytes()
            if len(data)!=record['bytes'] or sha(data)!=record['sha256']:raise ValueError('Original mirror byte mismatch')
            remote=record['remote']
            if remote in records and records[remote][0]['sha256']!=record['sha256']:
                raise ValueError('Conflicting remote snapshots require separate history components')
            records[remote]=(record,data)
    output.mkdir(parents=True)
    entries=[]
    for number,(remote,(record,data)) in enumerate(sorted(records.items())):
        member=str(number).zfill(5)+'-'+Path(remote).name
        with (output/member).open('xb') as stream:stream.write(data)
        entries.append({'remote':remote,'archive_member':member,'bytes':len(data),'sha256':sha(data)})
    receipt={'schema':'publication.normalized-owner-mirror.v1','all_files_exact_verified':True,'archive_sha256':sources[0].get('archive_sha256') if len(sources)==1 else None,'source_manifest_set_sha256':sha(json.dumps(sources,sort_keys=True).encode()),'source_maps':sources,'files':entries,'new_fits':0,'new_predictions':0,'weights_loaded':0}
    with (output/'LOCAL-MIRROR-MAP.actual.json').open('x',encoding='utf-8',newline='\n') as stream:json.dump(receipt,stream,indent=2);stream.write('\n')
    return {'files':len(entries),'source_maps':sources,'map_sha256':sha((output/'LOCAL-MIRROR-MAP.actual.json').read_bytes())}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--map',type=Path,action='append',required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(normalize(args.map,args.output),indent=2))
