"""Conditionally finish only validation after a preserved original timeout."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import pickle
import sys
import time

HERE=Path(__file__).resolve().parent
def main():
    contract=json.loads(Path(sys.argv[1]).read_text())
    assert contract['stage']=='validation-cache-completion-v2'
    assert os.uname().nodename=='node23' and os.environ.get('CUDA_VISIBLE_DEVICES')==''
    spec=importlib.util.spec_from_file_location('completion_snapshot_runner',HERE/'stage/runner.py')
    runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
    import torch,torch_geometric,rdkit,numpy
    runner.require_hash(contract['spec_path'],contract['derived_spec_sha256'])
    original=runner.read_json(contract['original_process_receipt'])
    assert original['status']=='failed' and original['stop_reason']=='timeout'
    assert not Path('/proc/'+str(original['pid'])).exists(),'Original PID has not reached absent terminal state'
    derived=runner.read_json(contract['spec_path'])
    runner.seed_everything(0,1)
    runner.require_hash(derived['train_rows'],derived['train_rows_sha256'])
    rows=runner.filter_scope(runner.read_jsonl(derived['train_rows']),derived['regime'])
    adapter=runner.load_adapter(derived['method_id'],derived['methods_root'])
    assert runner.adapter_tree_hash(adapter)==contract['adapter_tree_sha256']
    key=derived['split_id']+'-'+derived['regime']+'-'+derived['method_id']
    train=Path(derived['cache_root'])/(key+'-train.pkl')
    val=Path(derived['cache_root'])/(key+'-validation-'+derived['validation_scope']+'.pkl')
    assert train.is_file() and not val.exists(),'Only a complete train plus missing validation qualifies'
    train_hash=runner.sha_file(train)
    audits=runner.read_jsonl(train.with_suffix('.input-audit.jsonl'))
    assert [row['record_id'] for row in audits]==[row['record_id'] for row in rows]
    # A cache-hit call with encoding forbidden proves signature/source validity and
    # prevents this recovery path from silently rebuilding the whole training set.
    encode_original=adapter.encode_record
    def forbidden_encode(*args,**kwargs):raise AssertionError('Training-cache re-encoding forbidden')
    adapter.encode_record=forbidden_encode
    runner.cache_items(adapter,derived['method_id'],rows,train)
    adapter.encode_record=encode_original
    def forbidden_model(*args,**kwargs):raise AssertionError('Model construction forbidden')
    runner.native_model=forbidden_model
    actual_loader=runner.load_adapter
    def guarded_loader(*args,**kwargs):
        loaded=actual_loader(*args,**kwargs);loaded.build_model=forbidden_model;return loaded
    runner.load_adapter=guarded_loader
    started=time.time()
    receipt=runner.prepare_cache(contract['spec_path'])
    assert runner.sha_file(train)==train_hash,'Existing train bytes changed'
    outputs=[]
    for path in (train,train.with_suffix('.input-audit.jsonl'),val,val.with_suffix('.input-audit.jsonl')):
        outputs.append(dict(filename=path.name,path=str(path),bytes=path.stat().st_size,sha256=runner.sha_file(path)))
    receipt.update(cell_id=contract['cell_id'],stage='feature_preprocessing_only',completion_type=contract['stage'],
        pid=os.getpid(),pgid=os.getpgid(0),host=os.uname().nodename,model_construction_calls=0,optimizer_steps=0,
        test_label_reads=0,external_label_reads=0,train_cache_sha256_unchanged=train_hash,
        original_failure=original,original_process_receipt_sha256=runner.sha_file(contract['original_process_receipt']),
        original_gpu_spec_sha256=contract['original_gpu_spec_sha256'],derived_spec_sha256=contract['derived_spec_sha256'],
        input_sha256=contract['input_sha256'],producer_versions=dict(torch=torch.__version__,pyg=torch_geometric.__version__,
        rdkit=rdkit.__version__,numpy=numpy.__version__),outputs=outputs,elapsed_seconds=time.time()-started,
        global_deadline_preserved=True,no_paperclock_reset=True)
    main_receipt=HERE/'receipts'/(contract['cell_id']+'.json')
    assert not main_receipt.exists(),'Preserve any existing producer receipt'
    runner.write_json(HERE/'validation-cache-completion-v2'/(contract['cell_id']+'.receipt.json'),receipt)
    runner.write_json(main_receipt,receipt)
    print(json.dumps(receipt))
if __name__=='__main__':main()
