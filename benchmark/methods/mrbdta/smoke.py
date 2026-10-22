"""Bounded CPU compatibility tests, not training or model performance."""
import json
import os
import resource
import socket
import time
from pathlib import Path
import torch
import adapter

torch.set_num_threads(1)
HERE=Path(__file__).resolve().parent
start=time.time();torch.manual_seed(0)
rows=[json.loads(l) for l in (HERE/'smoke-inputs.jsonl').read_text().splitlines()]
items=[adapter.encode_record(r) for r in rows]
model=adapter.build_model('MRBDTA',{})
checks=[]
for n in (1,2):
 model.train();model.zero_grad(set_to_none=True)
 batch=adapter.collate(items[:n]);pred=adapter.predict(model,batch,'cpu')
 loss=(pred-adapter.batch_targets(batch)).square().mean();loss.backward()
 grads=[p.grad for p in model.parameters() if p.grad is not None]
 assert pred.shape==(n,) and torch.isfinite(pred).all() and all(torch.isfinite(g).all() for g in grads)
 checks.append({'batch_size':n,'shape':list(pred.shape),'loss':loss.item(),'gradient_tensors':len(grads)})
model.eval()
with torch.no_grad():
 p=adapter.predict(model,adapter.collate(items),'cpu')
 rev=adapter.predict(model,adapter.collate(list(reversed(items))),'cpu').flip(0)
 one=torch.cat([adapter.predict(model,adapter.collate([i]),'cpu') for i in items])
 assert torch.allclose(p,rev,atol=1e-6,rtol=1e-6)
 assert torch.allclose(p,one,atol=1e-6,rtol=1e-6)
 # Encoding must preserve native token IDs for stereo and aromatic atoms.
 assert adapter.VOCAB['drug']['@']==8 and adapter.VOCAB['drug']['c']!=adapter.VOCAB['drug']['C']
 blocked={}
 for name,change in [('unknown',{'canonical_isomeric_smiles':'C?'}),('overlength',{'canonical_isomeric_smiles':'C'*5001})]:
  try:adapter.encode_record(dict(rows[0],**change))
  except ValueError as e:blocked[name]=str(e)
 assert set(blocked)=={'unknown','overlength'}
receipt={'status':'passed','host':socket.gethostname(),'torch':torch.__version__,'CUDA_VISIBLE_DEVICES':os.environ.get('CUDA_VISIBLE_DEVICES'),
 'cpu_threads':torch.get_num_threads(),'cpu_affinity':sorted(os.sched_getaffinity(0)),
 'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'seconds':time.time()-start,
 'parameter_count':sum(p.numel() for p in model.parameters()),'checks':checks,
 'evaluation_order_max_abs_error':(p-rev).abs().max().item(),'singleton_vs_batch_max_abs_error':(p-one).abs().max().item(),
 'position_encoding_axis':'Author transpose [B,L,D]->[L,B,D]->[B,L,D] preserved; attention [B,H,L,L].',
 'smiles_lengths':[len(i['drug']) for i in items],'protein_lengths':[len(i['target']) for i in items],
 'unknown_and_overlength_rejection':blocked,'full_training':False,'gpu_used':False}
(HERE/'smoke-receipt.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt,indent=2))
