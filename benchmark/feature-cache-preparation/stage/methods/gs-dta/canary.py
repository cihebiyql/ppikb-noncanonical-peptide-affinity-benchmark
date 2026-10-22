"""Frozen train-only compatibility/resource canary; never model selection."""
import argparse,hashlib,json,os,platform,resource,time
from pathlib import Path
import torch
import torch_geometric
import rdkit
import adapter
P=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 a=argparse.ArgumentParser();a.add_argument('--contract',required=True);args=a.parse_args();c=json.loads(Path(args.contract).read_text())
 assert platform.node()=='cihebi'
 torch.set_num_threads(2);torch.manual_seed(0)
 torch.use_deterministic_algorithms(True,warn_only=True)
 assert sha(P/'train-only-32.jsonl')==c['train_sample_sha256']
 for name,value in c['source_files_sha256'].items():assert sha(P/name)==value
 rows=[json.loads(l) for l in (P/'train-only-32.jsonl').read_text().splitlines()]
 assert len(rows)==len({r['record_id'] for r in rows})==32
 assert {r['record_id'] for r in rows}==set(c['allowed_train_ids'])
 started=time.perf_counter();items=[adapter.encode_record(r,'GS-DTA') for r in rows]
 encoding=time.perf_counter()-started
 model=adapter.build_model('GS-DTA',{});paramcount=sum(p.numel() for p in model.parameters())
 receipt={'mode':c['mode'],'host':platform.node(),'torch':torch.__version__,'torch_geometric':torch_geometric.__version__,'rdkit':rdkit.__version__,
  'parameter_count':paramcount,'cpu_threads':torch.get_num_threads(),'cpu_affinity':sorted(os.sched_getaffinity(0)),'encoding_seconds':encoding,
  'contract_sha256':sha(args.contract),'sample_sha256':sha(P/'train-only-32.jsonl'),'source_files_sha256':c['source_files_sha256'],
  'train_only':True,'test_label_reads':0,'external_label_reads':0,'no_checkpoint_retained':True}
 if c['mode']=='cpu':
  shape={};hooks=[]
  for name in ['gatv2_conv1','gcn_conv1','fc_g1','embedding_xt','conv_xt1','lstm_xt','transformer_encoder','fc1','out']:
   def hook(m,args,out,name=name):
    val=out[0] if isinstance(out,tuple) else out;shape[name]=list(val.shape)
   hooks.append(getattr(model,name).register_forward_hook(hook))
  tests=[]
  for n in [1,2]:
   model.train();model.zero_grad(set_to_none=True);batch=adapter.collate(items[:n]);pred=adapter.predict(model,batch,'cpu');loss=(pred-adapter.batch_targets(batch)).square().mean();loss.backward()
   assert pred.shape==(n,) and torch.isfinite(pred).all()
   grads=[p.grad for p in model.parameters() if p.grad is not None];assert all(torch.isfinite(g).all() for g in grads)
   tests.append({'B':n,'pred_shape':list(pred.shape),'diagnostic_loss':loss.item(),'gradient_tensors':len(grads),'module_output_shapes':dict(shape)})
  model.eval()
  with torch.no_grad():
   pred=adapter.predict(model,adapter.collate(items[:2]),'cpu');rev=adapter.predict(model,adapter.collate(items[:2][::-1]),'cpu').flip(0)
   single=torch.cat([adapter.predict(model,adapter.collate([i]),'cpu') for i in items[:2]])
   ordererr=(pred-rev).abs().max().item();singleerr=(pred-single).abs().max().item()
   assert torch.allclose(pred,rev,atol=1e-5,rtol=1e-5) and torch.allclose(pred,single,atol=1e-5,rtol=1e-5)
  for h in hooks:h.remove()
  receipt.update(tests=tests,evaluation_order_max_abs_error=ordererr,singleton_vs_batch_max_abs_error=singleerr,optimizer_steps=0,gpu_used=False)
 else:
  assert os.environ.get('CUDA_VISIBLE_DEVICES')==c['GPU_UUID'] and torch.cuda.is_available()
  torch.cuda.set_per_process_memory_fraction(3*1024**3/torch.cuda.get_device_properties(0).total_memory,0)
  model=model.to('cuda:0');optimizer=torch.optim.Adam(model.parameters(),lr=.001,weight_decay=0);model.train();torch.cuda.reset_peak_memory_stats()
  times=[];losses=[];visits=[]
  for step in range(2):
   batch=adapter.collate(items);torch.cuda.synchronize();t=time.perf_counter();optimizer.zero_grad(set_to_none=True)
   pred=adapter.predict(model,batch,'cuda:0');loss=(pred-adapter.batch_targets(batch).to('cuda:0')).square().mean()
   assert torch.isfinite(loss);loss.backward();assert all(torch.isfinite(p.grad).all() for p in model.parameters() if p.grad is not None)
   optimizer.step();torch.cuda.synchronize();times.append(time.perf_counter()-t);losses.append(loss.item());visits.extend(r['record_id'] for r in rows)
  receipt.update(gpu_used=True,GPU_UUID=c['GPU_UUID'],gpu_name=torch.cuda.get_device_name(),optimizer_steps=2,batch_size=32,
   step_seconds=times,diagnostic_train_losses=losses,sample_visits=len(visits),unique_training_ids_visited=len(set(visits)),
   peak_gpu_allocated_bytes=torch.cuda.max_memory_allocated(),peak_gpu_reserved_bytes=torch.cuda.max_memory_reserved(),
   compiled_scatter_available=torch_geometric.typing.WITH_TORCH_SCATTER,compiled_sparse_available=torch_geometric.typing.WITH_TORCH_SPARSE)
 receipt.update(status='passed',seconds=time.perf_counter()-started,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
  claim='Compatibility/resource canary only, no full fit or evaluation metric')
 (P/(c['mode']+'-input-audit.jsonl')).write_text(''.join(json.dumps(i['audit'])+'\n' for i in items))
 Path(c['receipt_path']).write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
if __name__=='__main__':main()
