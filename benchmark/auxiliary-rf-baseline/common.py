from pathlib import Path
import hashlib
import json
import os
import threading
import time
import uuid
HERE=Path(__file__).resolve().parent
PROJECT=HERE.parent
PANELS=['source_peptide_dependency_cold','target_reference_homology_cold']
REGIMES=['NC_only','standard_only']
METHOD='RF-Morgan2-chiral-AAC-DP'

def path(value):
    value=str(value)
    if os.name=='nt' and value.startswith('/mnt/') and len(value)>7 and value[6]=='/':value=value[5].upper()+':'+value[6:]
    return Path(value)
def sha(value):
    digest=hashlib.sha256()
    with path(value).open('rb') as handle:
        for block in iter(lambda:handle.read(1048576),b''):digest.update(block)
    return digest.hexdigest()
def read(value):return json.loads(path(value).read_text(encoding='utf-8-sig'))
def write(value,obj):
    target=path(value);target.parent.mkdir(parents=True,exist_ok=True)
    temp=target.with_name(target.name+'.'+str(os.getpid())+'.'+str(threading.get_ident())+'.'+uuid.uuid4().hex+'.tmp')
    with temp.open('x',encoding='utf-8') as handle:handle.write(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False))
    # This runs in the worker/artifact writer, never in the resource-supervision
    # loop. Root's independent watchdog must keep its original deadline/RSS ticks.
    delays=(.05,.1,.2,.4,.8,1.)
    for attempt in range(len(delays)+1):
        try:temp.replace(target);return
        except PermissionError:
            if attempt==len(delays):raise
            time.sleep(delays[attempt])
def jsonl(value):
    with path(value).open(encoding='utf-8-sig') as handle:return [json.loads(line) for line in handle if line.strip()]
def write_jsonl(value,rows):
    target=path(value);target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('w',encoding='utf-8') as handle:
        for row in rows:handle.write(json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n')
def require(value,digest):
    if sha(value)!=digest:raise ValueError('Frozen file mismatch '+str(value))
def load_feature_dataset(manifest,dataset_id):
    import numpy as np
    matches=[entry for entry in manifest['entries'] if entry['dataset_id']==dataset_id]
    if len(matches)!=1:raise ValueError('Wrong X dataset')
    entry=matches[0]
    require(entry['matrix_path'],entry['matrix_sha256']);require(entry['record_ids_path'],entry['record_ids_sha256'])
    require(entry['audit_path'],entry['audit_sha256'])
    ids=read(entry['record_ids_path']);matrix=np.load(path(entry['matrix_path']),mmap_mode='r',allow_pickle=False)
    if matrix.shape!=(len(ids),2469) or str(matrix.dtype)!='float32' or len(ids)!=len(set(ids)):raise ValueError('Invalid X matrix')
    return matrix,{rid:index for index,rid in enumerate(ids)},entry
