"""Label-free fixed-author X caches, independent of seeds, weights and gold."""
from pathlib import Path
import argparse
import ast
import json
import os
import pickle
import sys
import time
import common

MODEL_FILES={'GraphDTA-GIN':'graphdta-deepnc/vendor/graphdta_gin.py',
 'DeepNC-GEN':'graphdta-deepnc/vendor/deepnc_gen.py','MGraphDTA':'mgraph-dgdta/patched-author/mgraph_model.py',
 'DGDTA-CL':'mgraph-dgdta/patched-author/dgdta_model.py','GS-DTA':'gs-dta/author_model.py'}

def forward_y_audit(methods_root,method_id):
    path=Path(methods_root)/MODEL_FILES[method_id]
    tree=ast.parse(path.read_text(encoding='utf-8-sig'))
    reads=[]
    for forward in [node for node in ast.walk(tree) if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name=='forward']:
        for node in ast.walk(forward):
            if isinstance(node,ast.Attribute) and node.attr=='y':reads.append(node.lineno)
            if isinstance(node,ast.Subscript) and isinstance(node.slice,ast.Constant) and node.slice.value=='y':reads.append(node.lineno)
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='getattr' and len(node.args)>1 and isinstance(node.args[1],ast.Constant) and node.args[1].value=='y':reads.append(node.lineno)
    return dict(method_id=method_id,source_path=str(path),source_sha256=common.sha(path),
                forward_y_reads=sorted(set(reads)),passed=not reads,
                scope='Static author forward methods; paired dynamic random-model proof is separately required')

def assert_zero_targets(adapter,items):
    import torch
    for start in range(0,len(items),64):
        batch=adapter.collate(items[start:start+64])
        targets=adapter.batch_targets(batch).detach().cpu().reshape(-1)
        if len(targets)!=len(items[start:start+64]) or not torch.isfinite(targets).all() or torch.count_nonzero(targets):
            raise ValueError('Cache targets are not identically zero')

def encode_zero_items(runner,adapter,method_id,rows):
    # Callers must supply rows read through read_inputs; never strip actual gold silently.
    if any(common.GOLD_KEYS & set(row) for row in rows):raise ValueError('Gold-bearing row rejected')
    items=[runner.encode(adapter,method_id,dict(row,pKd=0.0)) for row in rows]
    assert_zero_targets(adapter,items)
    return items

def build_cache(manifest_path,authorization_path,job_index,input_path,methods_root,runner_path,output_root):
    manifest=common.read_json(manifest_path)
    authorization=common.read_json(authorization_path)
    if authorization.get('root_cache_generation_authorized') is not True or authorization.get('manifest_sha256')!=common.sha(manifest_path):
        raise PermissionError('Root authorization for this exact cache manifest is required')
    if manifest['schema']!=common.SCHEMA or manifest['job_count'] not in (15,20):raise ValueError('Unexpected manifest scope')
    if not 0<=job_index<manifest['job_count']:raise ValueError('Invalid job index')
    if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise ValueError('CPU X preparation requires CUDA_VISIBLE_DEVICES empty')
    job=manifest['jobs'][job_index]
    if common.sha(input_path)!=job['input_sha256']:raise ValueError('Input raw bytes changed')
    rows=common.read_inputs(input_path)
    if len(rows)!=job['n']:raise ValueError('Input row count changed')
    runner=common.load_runner(runner_path,manifest['runner_sha256'])
    runner.seed_everything(0,1)
    adapter=runner.load_adapter(job['method_id'],methods_root)
    if runner.adapter_tree_hash(adapter)!=job['adapter_tree_sha256']:raise ValueError('Author Python tree changed')
    static=forward_y_audit(methods_root,job['method_id'])
    if not static['passed']:raise RuntimeError('Author forward reads y; zero-placeholder cache forbidden')
    signature=common.signature(job['method_id'],job['input_sha256'],job['adapter_tree_sha256'])
    if signature!=job['signature']:raise ValueError('Cache identity mismatch')
    root=Path(output_root);root.mkdir(parents=True,exist_ok=True)
    cache=root/job['cache_filename']
    receipt=cache.with_suffix('.manifest.json')
    if cache.exists() or receipt.exists():raise FileExistsError('Preserve existing cache or manifest')
    def no_model(*args,**kwargs):raise AssertionError('Model construction forbidden during X preprocessing')
    adapter.build_model=no_model
    started=time.time()
    items=encode_zero_items(runner,adapter,job['method_id'],rows)
    import torch,torch_geometric,rdkit,numpy,platform
    versions=dict(python=sys.version,torch=torch.__version__,pyg=torch_geometric.__version__,rdkit=rdkit.__version__,numpy=numpy.__version__)
    payload=dict(schema=common.SCHEMA,signature=signature,method_id=job['method_id'],
        input_sha256=job['input_sha256'],adapter_tree_sha256=job['adapter_tree_sha256'],
        placeholder_pKd=0.0,record_ids=[row['record_id'] for row in rows],items=items,producer_versions=versions)
    temporary=cache.with_name(cache.name+'.'+str(os.getpid())+'.tmp')
    with temporary.open('xb') as handle:pickle.dump(payload,handle,protocol=pickle.HIGHEST_PROTOCOL)
    # Same-filesystem hard link commits without overwriting an existing path.
    os.link(temporary,cache);temporary.unlink()
    metadata=dict(schema=common.SCHEMA,status='producer_complete',dataset_id=job['dataset_id'],
        method_id=job['method_id'],signature=signature,input_sha256=job['input_sha256'],n=len(rows),
        adapter_tree_sha256=job['adapter_tree_sha256'],runner_sha256=manifest['runner_sha256'],
        cache_filename=cache.name,cache_sha256=common.sha(cache),cache_bytes=cache.stat().st_size,
        placeholder_pKd=0.0,all_cached_targets_zero=True,record_id_order_sha256=__import__('hashlib').sha256(json.dumps(payload['record_ids']).encode()).hexdigest(),
        producer_versions=versions,host=platform.node(),pid=os.getpid(),elapsed_seconds=time.time()-started,
        forward_y_static_audit=static,model_constructions=0,optimizer_steps=0,
        gold_reads=0,selection_reads=0,trained_checkpoint_reads=0,actual_holdout_predictions=0,
        source_manifest_sha256=common.sha(manifest_path),authorization_sha256=common.sha(authorization_path),
        producer_code_sha256=common.sha(__file__),consumer_compatibility='Must verify actual pickle and source signatures in consumer runtime')
    common.write_json(receipt,metadata)
    return metadata

def load_cache(runner,adapter,cache_manifest_path,cache_path,input_path,method_id):
    metadata=common.read_json(cache_manifest_path)
    rows=common.read_inputs(input_path)
    input_hash=common.sha(input_path)
    adapter_hash=runner.adapter_tree_hash(adapter)
    expected=common.signature(method_id,input_hash,adapter_hash)
    if metadata['schema']!=common.SCHEMA or metadata['method_id']!=method_id or metadata['signature']!=expected:
        raise ValueError('X cache manifest identity mismatch')
    if metadata['input_sha256']!=input_hash or metadata['adapter_tree_sha256']!=adapter_hash:
        raise ValueError('X source changed')
    if common.sha(cache_path)!=metadata['cache_sha256']:raise ValueError('X pickle SHA mismatch')
    with Path(cache_path).open('rb') as handle:payload=pickle.load(handle)
    if payload['schema']!=common.SCHEMA or payload['signature']!=expected or payload['placeholder_pKd']!=0.0:
        raise ValueError('X pickle identity or placeholder mismatch')
    if payload['method_id']!=method_id or payload['input_sha256']!=input_hash or payload['adapter_tree_sha256']!=adapter_hash:
        raise ValueError('X pickle source mismatch')
    if payload['record_ids']!=[row['record_id'] for row in rows] or len(payload['items'])!=len(rows):
        raise ValueError('X row ordering mismatch')
    assert_zero_targets(adapter,payload['items'])
    return rows,payload['items'],metadata

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',required=True);parser.add_argument('--authorization',required=True)
    parser.add_argument('--job-index',type=int,required=True);parser.add_argument('--input',required=True)
    parser.add_argument('--methods-root',required=True);parser.add_argument('--runner',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    print(json.dumps(build_cache(args.manifest,args.authorization,args.job_index,args.input,args.methods_root,args.runner,args.output)))
if __name__=='__main__':main()
