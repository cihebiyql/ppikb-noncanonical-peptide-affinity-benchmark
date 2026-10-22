"""Authorized CPU-only consumer ABI check: sequential X-only unpickle, no models."""
from pathlib import Path
from collections import Counter
import gc
import json
import os
import resource
import sys
import time
import warnings
import common
import feature_cache

HERE=Path(__file__).resolve().parent
PROJECT=HERE.parent
def main():
    assert os.environ.get('CUDA_VISIBLE_DEVICES')==''
    manifest=common.read_json(HERE/'authorized-manifest-v2.json')
    runner=common.load_runner(PROJECT/'execution/runner.py',manifest['runner_sha256'])
    import torch,torch_geometric,rdkit,numpy
    torch.set_num_threads(2)
    def forbidden(*args,**kwargs):raise AssertionError('No model construction/forward allowed in consumer X check')
    runner.native_model=forbidden
    results=[];seen_warnings=Counter();started=time.time()
    for job in manifest['jobs']:
        adapter=runner.load_adapter(job['method_id'],PROJECT/'methods')
        adapter.build_model=forbidden;adapter.predict=forbidden
        path=HERE/'feature-caches-v2'/job['cache_filename']
        dataset=manifest['datasets'][job['dataset_id']]
        input_path=PROJECT/dataset['input_relative']
        with warnings.catch_warnings(record=True) as observed:
            warnings.simplefilter('always')
            rows,items,metadata=feature_cache.load_cache(runner,adapter,path.with_suffix('.manifest.json'),path,input_path,job['method_id'])
        for warning in observed:
            seen_warnings[(warning.category.__name__,str(warning.message),str(warning.filename),warning.lineno)]+=1
        results.append(dict(dataset_id=job['dataset_id'],method_id=job['method_id'],n=len(rows),
            cache_sha256=metadata['cache_sha256'],signature=metadata['signature'],
            adapter_tree_sha256=metadata['adapter_tree_sha256'],all_y_zero=True,
            input_id_order_matches=True,producer_versions=metadata['producer_versions']))
        del rows,items,metadata,adapter,observed
        gc.collect()
        if resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024>4*1024**3:raise MemoryError('Consumer RSS budget exceeded')
    receipt=dict(status='passed',checks=len(results),results=results,
        consumer_versions=dict(python=sys.version,executable=sys.executable,torch=torch.__version__,pyg=torch_geometric.__version__,
                               rdkit=rdkit.__version__,numpy=numpy.__version__),
        cpu_threads=torch.get_num_threads(),CUDA_VISIBLE_DEVICES='',model_constructions=0,model_forwards=0,
        gold_reads=0,selection_reads=0,trained_weights_reads=0,each_cache_loaded_once=True,sequential_release_gc=True,
        elapsed_seconds=time.time()-started,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        warnings=[dict(category=k[0],message=k[1],filename=k[2],line=k[3],count=v) for k,v in seen_warnings.items()],
        authorized_scope='Direct root approval: actual Torch2.12 consumer unpickle/signature/zero-y only, not holdout scoring')
    common.write_json(HERE/'consumer-compatibility-receipt.json',receipt)
    print(json.dumps({key:value for key,value in receipt.items() if key!='results'},indent=2))
if __name__=='__main__':main()
