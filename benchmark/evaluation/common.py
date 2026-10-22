"""Shared immutable-source loading and label-free cache identities."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

SCHEMA='label-free-fixed-author-X-v1'
METHODS=['GraphDTA-GIN','MGraphDTA','DGDTA-CL','DeepNC-GEN','GS-DTA']
FOLDERS={'GraphDTA-GIN':'graphdta-deepnc','DeepNC-GEN':'graphdta-deepnc','MGraphDTA':'mgraph-dgdta','DGDTA-CL':'mgraph-dgdta','GS-DTA':'gs-dta'}
GOLD_KEYS={'pKd','pKd_true','p_value','value','value_molar','affinity','gold','label','y'}

def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda:handle.read(1024**2),b''):digest.update(block)
    return digest.hexdigest()
def read_json(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def write_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    temporary.replace(path)
def read_inputs(path):
    rows=[];seen=set()
    with Path(path).open(encoding='utf-8-sig') as handle:
        for line in handle:
            if not line.strip():continue
            row=json.loads(line)
            forbidden=GOLD_KEYS & set(row)
            if forbidden:raise ValueError('Label-free input contains prohibited keys '+repr(sorted(forbidden)))
            if row['record_id'] in seen:raise ValueError('Duplicate input record ID')
            seen.add(row['record_id']);rows.append(row)
    return rows
def tree_hash(root):
    root=Path(root)
    entries=[(str(path.relative_to(root)).replace('\\','/'),sha(path)) for path in sorted(root.rglob('*.py')) if '__pycache__' not in path.parts]
    return hashlib.sha256(json.dumps(entries,separators=(',',':')).encode()).hexdigest()
def signature(method_id,input_sha256,adapter_tree_sha256):
    return hashlib.sha256(json.dumps(dict(schema=SCHEMA,method_id=method_id,input_sha256=input_sha256,
        adapter_tree_sha256=adapter_tree_sha256,placeholder_pKd=0.0),sort_keys=True,separators=(',',':')).encode()).hexdigest()
def load_runner(path,expected_sha256):
    if sha(path)!=expected_sha256:raise ValueError('Frozen runner SHA mismatch')
    spec=importlib.util.spec_from_file_location('frozen_evaluation_runner',path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module)
    return module
