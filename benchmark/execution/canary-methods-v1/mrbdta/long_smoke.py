"""One longest authentic molecular input, native model resource canary."""
import json
import os
import resource
import socket
import time
from pathlib import Path
import torch
import adapter

torch.set_num_threads(1);torch.manual_seed(0)
P=Path(__file__).resolve().parent
row=json.loads((P/'long-smoke-input.json').read_text())
start=time.perf_counter()
item=adapter.encode_record(row);batch=adapter.collate([item])
model=adapter.build_model('MRBDTA',{});model.train()
t0=time.perf_counter();pred=adapter.predict(model,batch,'cpu');forward=time.perf_counter()-t0
loss=(pred-adapter.batch_targets(batch)).square().mean()
t0=time.perf_counter();loss.backward();backward=time.perf_counter()-t0
assert pred.shape==(1,) and torch.isfinite(pred).all() and torch.isfinite(loss)
grads=[p.grad for p in model.parameters() if p.grad is not None]
assert grads and all(torch.isfinite(g).all() for g in grads)
assert all(torch.isfinite(p).all() for p in model.parameters())
receipt={'status':'passed','host':socket.gethostname(),'torch':torch.__version__,'CUDA_VISIBLE_DEVICES':os.environ.get('CUDA_VISIBLE_DEVICES'),
 'cpu_threads':torch.get_num_threads(),'cpu_affinity':sorted(os.sched_getaffinity(0)),
 'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'seconds':time.perf_counter()-start,
 'forward_seconds':forward,'backward_seconds':backward,'parameter_count':sum(p.numel() for p in model.parameters()),
 'gradient_tensor_count':len(grads),'parameters_finite':True,'gradients_finite':True,
 'input':item['metadata'],'loss_is_compatibility_only':loss.item(),'no_optimizer_steps':True,'gpu_used':False,'full_training':False}
(P/'long-smoke-receipt.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt,indent=2))
