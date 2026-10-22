"""Four optimizer steps on an explicitly frozen train-only sample; no holdouts."""
import argparse
import json
import os
from pathlib import Path
import resource
import time
import torch
import runner

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--contract',required=True)
    args=parser.parse_args()
    contract=runner.read_json(args.contract)
    if contract['stage']!='train-only-performance-canary':raise ValueError('Wrong contract')
    if os.environ.get('CUDA_VISIBLE_DEVICES'):raise ValueError('CPU only')
    resource.setrlimit(resource.RLIMIT_AS,(int(contract['memory_gib'])*1024**3,)*2)
    runner.require_hash(contract['train_sample'],contract['train_sample_sha256'])
    rows=runner.read_jsonl(contract['train_sample'])
    if len(rows)!=32 or len({row['record_id'] for row in rows})!=32:raise ValueError('Exactly 32 distinct frozen training rows')
    if len(set(contract['allowed_train_ids']) & {row['record_id'] for row in rows})!=32:
        raise ValueError('Sample row not in frozen training panel')
    runner.seed_everything(contract['seed'],contract['cpu_threads'])
    method=contract['method_id']
    adapter=runner.load_adapter(method,contract['methods_root'])
    started=time.time()
    items=[runner.encode(adapter,method,row) for row in rows]
    encoding_seconds=time.time()-started
    model=runner.native_model(adapter,method)
    optimizer=torch.optim.Adam(model.parameters(),lr=1e-3,weight_decay=0.)
    model.train()
    batch_size=1 if method=='MRBDTA' else int(contract['batch_size'])
    accumulation=8 if method=='MRBDTA' else 1
    timings=[]
    losses=[]
    training_started=time.time()
    for step in range(4):
        started=time.time()
        optimizer.zero_grad(set_to_none=True)
        total=0.
        for micro in range(accumulation):
            begin=((step*accumulation+micro)*batch_size)%len(items)
            group=[items[(begin+j)%len(items)] for j in range(batch_size)]
            batch=adapter.collate(group)
            pred=adapter.predict(model,batch,'cpu')
            loss=torch.nn.functional.mse_loss(pred,adapter.batch_targets(batch))/accumulation
            if not torch.isfinite(loss):raise FloatingPointError('Nonfinite loss')
            loss.backward()
            total+=float(loss.detach())
        if any(p.grad is not None and not torch.isfinite(p.grad).all() for p in model.parameters()):
            raise FloatingPointError('Nonfinite gradient')
        optimizer.step()
        timings.append(time.time()-started)
        losses.append(total)
    receipt=dict(status='passed',stage=contract['stage'],method_id=method,host=os.uname().nodename,pid=os.getpid(),
                 cpu_threads=contract['cpu_threads'],gpu_count=0,parameter_count=sum(p.numel() for p in model.parameters()),
                 train_sample_n=32,optimizer_steps=4,batch_size=batch_size,gradient_accumulation=accumulation,
                 encoding_seconds=encoding_seconds,step_seconds=timings,training_seconds=time.time()-training_started,
                 diagnostic_train_losses=losses,max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                 sample_sha256=contract['train_sample_sha256'],contract_sha256=runner.sha_file(args.contract),
                 adapter_tree_sha256=runner.adapter_tree_hash(adapter),test_label_reads=0,
                 claim='performance canary only; not a benchmark fit, no model checkpoint retained')
    runner.write_json(contract['receipt_path'],receipt)
    print(json.dumps(receipt))

if __name__=='__main__':main()
