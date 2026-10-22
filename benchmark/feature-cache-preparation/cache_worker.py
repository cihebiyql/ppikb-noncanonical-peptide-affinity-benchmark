"""One CPU-only native feature cache cell; never constructs a model."""
from pathlib import Path
import importlib.util
import json
import os
import sys
import time

HERE=Path(__file__).resolve().parent
def main():
    contract=json.loads(Path(sys.argv[1]).read_text())
    assert os.uname().nodename=='node23' and os.environ.get('CUDA_VISIBLE_DEVICES')==''
    spec=importlib.util.spec_from_file_location('cache_snapshot_runner',HERE/'stage/runner.py')
    runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
    import torch,torch_geometric,rdkit,numpy
    runner.require_hash(contract['spec_path'],contract['derived_spec_sha256'])
    # Explicit construction tripwire: this process must only invoke native encoders.
    construction_calls=0
    def forbidden(*args,**kwargs):
        nonlocal construction_calls
        construction_calls+=1
        raise AssertionError('Model construction forbidden in feature-preparation worker')
    runner.native_model=forbidden
    original_load=runner.load_adapter
    def guarded_load(*args,**kwargs):
        adapter=original_load(*args,**kwargs)
        assert runner.adapter_tree_hash(adapter)==contract['adapter_tree_sha256']
        adapter.build_model=forbidden
        return adapter
    runner.load_adapter=guarded_load
    started=time.time()
    receipt=runner.prepare_cache(contract['spec_path'])
    derived=runner.read_json(contract['spec_path'])
    key=derived['split_id']+'-'+derived['regime']+'-'+derived['method_id']
    cache=Path(derived['cache_root'])
    files=[]
    for name in (key+'-train.pkl',key+'-validation-'+derived['validation_scope']+'.pkl'):
        path=cache/name
        for output in (path,path.with_suffix('.input-audit.jsonl')):
            if not output.is_file():raise FileNotFoundError(output)
            files.append(dict(filename=output.name,path=str(output),bytes=output.stat().st_size,sha256=runner.sha_file(output)))
    receipt.update(cell_id=contract['cell_id'],pid=os.getpid(),pgid=os.getpgid(0),host=os.uname().nodename,
        stage='feature_preprocessing_only',model_construction_calls=construction_calls,optimizer_steps=0,
        test_label_reads=0,external_label_reads=0,input_sha256=contract['input_sha256'],
        derived_spec_sha256=contract['derived_spec_sha256'],original_gpu_spec_sha256=contract['original_gpu_spec_sha256'],
        producer_versions=dict(torch=torch.__version__,pyg=torch_geometric.__version__,rdkit=rdkit.__version__,numpy=numpy.__version__),
        python=sys.executable,outputs=files,elapsed_seconds=time.time()-started,
        runtime_boundary='Torch2.6 CPU pickle producer; GPU Torch2.12 compatibility requires consumer verification; not a fit or baseline metric')
    runner.write_json(HERE/'receipts'/(contract['cell_id']+'.json'),receipt)
    print(json.dumps(receipt))
if __name__=='__main__':main()
