"""Independent random-model checks on 32 approved TRAIN rows; no holdout scoring."""
from pathlib import Path
import copy
import hashlib
import json
import os
import sys
import time
import common
import feature_cache

HERE=Path(__file__).resolve().parent
NODE='/data/qlyu/projects/peptide-binding-nc-benchmark-20261021'
def tensor_bytes(value):
    import torch,numpy as np
    if isinstance(value,torch.Tensor):return value.detach().cpu().contiguous().numpy().tobytes()
    return np.asarray(value).tobytes()
def feature_fingerprint(item):
    digest=hashlib.sha256()
    graph=item.get('graph')
    if graph is not None:
        for key in ('x','edge_index','edge_attr','target'):
            value=getattr(graph,key,None)
            if value is not None:digest.update(key.encode()+tensor_bytes(value))
    else:
        for key in ('x','edge_index','target'):
            digest.update(key.encode()+tensor_bytes(item[key]))
    return digest.hexdigest()
def main():
    assert os.uname().nodename=='node23' and os.environ.get('CUDA_VISIBLE_DEVICES')==''
    manifest=common.read_json(HERE/'authorized-manifest-v2.json')
    runner=common.load_runner(manifest['node_runner'],manifest['runner_sha256'])
    rows=runner.read_jsonl(NODE+'/execution/canary-staging-v1/train-only-32.jsonl')
    assert len(rows)==32
    import torch
    methods=[];started=time.time()
    for method in common.METHODS:
        runner.seed_everything(314159,1)
        adapter=runner.load_adapter(method,manifest['node_methods_root'])
        static=feature_cache.forward_y_audit(manifest['node_methods_root'],method)
        assert static['passed'],static
        # The nonzero values below are pre-existing TRAIN measurements, never holdout gold.
        direct=[runner.encode(adapter,method,row) for row in rows]
        inputs=[{key:value for key,value in row.items() if key!='pKd'} for row in rows]
        zero=feature_cache.encode_zero_items(runner,adapter,method,inputs)
        assert [feature_fingerprint(item) for item in direct]==[feature_fingerprint(item) for item in zero]
        before=[feature_fingerprint(item) for item in zero]
        model=runner.native_model(adapter,method);model.eval()
        with torch.no_grad():
            direct_pred=runner.predict_rows(adapter,model,direct,'cpu',32)
            cached_pred=runner.predict_rows(adapter,model,zero,'cpu',32)
            batch=adapter.collate(zero)
            adapter.batch_targets(batch).fill_(123.456)
            assert torch.all(adapter.batch_targets(batch)==torch.tensor(123.456,dtype=torch.float32))
            arbitrary=adapter.predict(model,batch,'cpu').detach().cpu()
            single=runner.predict_rows(adapter,model,zero,'cpu',1)
            reversed_pred=runner.predict_rows(adapter,model,zero[::-1],'cpu',32)[::-1]
        expected=torch.tensor(cached_pred)
        torch.testing.assert_close(torch.tensor(direct_pred),expected,rtol=0,atol=0)
        torch.testing.assert_close(arbitrary,expected,rtol=0,atol=0)
        torch.testing.assert_close(torch.tensor(single),expected,rtol=1e-4,atol=1e-5)
        torch.testing.assert_close(torch.tensor(reversed_pred),expected,rtol=1e-4,atol=1e-5)
        assert before==[feature_fingerprint(item) for item in zero]
        methods.append(dict(method_id=method,adapter_tree_sha256=runner.adapter_tree_hash(adapter),
            forward_y_independent=True,zero_vs_real_TRAIN_y_prediction_max_abs_difference=0.,
            zero_vs_arbitrary_y_prediction_max_abs_difference=0.,feature_bytes_equal=True,
            single_batch_max_difference=float((torch.tensor(single)-expected).abs().max()),
            batch_permutation_passed=True,cache_inputs_unchanged=True,static_forward_y_audit=static,
            model_source='random initialization seed314159; no trained checkpoint loaded',n_train_fixture_rows=32))
    receipt=dict(status='passed',stage='random_model_training_fixture_X_cache_parity_only',methods=methods,
        training_fixture_sha256=common.sha(NODE+'/execution/canary-staging-v1/train-only-32.jsonl'),
        actual_holdout_predictions=0,holdout_gold_reads=0,selection_reads=0,trained_checkpoint_reads=0,
        parameter_updates=0,CPU_threads=1,CUDA_VISIBLE_DEVICES='',elapsed_seconds=time.time()-started)
    common.write_json(HERE/'forward-y-parity-receipt.json',receipt)
    print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
