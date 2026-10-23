"""PREPARED ONLY: strict CUDA reference/replay/save_on_cpu TRAIN48 gate.

No launcher is included. Central reviewed JIT contract is mandatory before execution.
This one-step engineering check never constitutes a trained baseline or a B24 gate.
"""
import argparse,contextlib,gc,hashlib,json,os,random,time
from pathlib import Path
for key in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[key]='1'
os.environ['TOKENIZERS_PARALLELISM']='false'
import numpy as np
import torch
from common import now,save,sha,sha_text,read_view
from pepinter_full_classification import model_and_tokenizer,encode,finite_model_and_adam,PARAMETERS
from pepinter_full_classification_utils import capture_rng,restore_rng

def tensor_record(t):
    v=t.detach().cpu().contiguous().reshape(-1).view(torch.uint8).numpy()
    return {'shape':list(t.shape),'stride':list(t.stride()),'dtype':str(t.dtype),'sha256':hashlib.sha256(memoryview(v)).hexdigest(),'finite':bool(torch.isfinite(t).all().item())}

def table(model,kind,optimizer=None):
    if kind=='parameters':return {k:tensor_record(p) for k,p in model.named_parameters()}
    if kind=='gradients':
        if any(p.grad is None for p in model.parameters()):raise ValueError('Every native parameter needs a gradient')
        return {k:tensor_record(p.grad) for k,p in model.named_parameters()}
    if kind=='buffers':return {k:tensor_record(t) for k,t in model.named_buffers()}
    if kind=='optimizer':
        result={}
        for k,p in model.named_parameters():
            if p not in optimizer.state:raise ValueError('Missing native Adam state')
            for key,t in optimizer.state[p].items():
                if not isinstance(t,torch.Tensor):raise ValueError('Unexpected native Adam state type')
                result[k+'.'+key]=tensor_record(t)
        if len(result)!=1107:raise ValueError('Expected369native tensors with3Adam state tensors each')
        return result
    raise ValueError(kind)

def rng_record():
    r=capture_rng()
    return {'python':sha_text(repr(r['python'])),'numpy':sha_text(json.dumps(r['numpy'],sort_keys=True)),'torch_cpu':tensor_record(r['torch_cpu']),'torch_cuda':[tensor_record(t) for t in r['torch_cuda']]}

def strict_equal(reference,other):
    keys=['initial_parameters','initial_buffers','initial_rng','initial_flags','loss','logits','gradients_preclip','gradient_norm','gradients_postclip','updated_parameters','updated_buffers','optimizer','post_rng','post_flags']
    errors=[k for k in keys if reference[k]!=other[k]]
    if errors:raise ValueError('Strict exact comparison failed: '+','.join(errors))
    return {'exact_fields_compared':keys,'differences':[],'tolerance':0,'status':'passed'}

# TRACE-V2-BEGIN
import sys as _trace_v2_sys
_trace_v2_sys.path.insert(0,str(Path(__file__).resolve().parent/'continuation-20261023/activation-offload-runtime-closure-v1'))
from trace_logging import TraceJournal as _TraceJournal,finish_without_masking_original as _trace_v2_finish
_trace_v2_journal=None
_trace_v2_original_tensor_record=tensor_record
def tensor_record(t):
    value=_trace_v2_original_tensor_record(t)
    if _trace_v2_journal is not None:_trace_v2_journal.emit('tensor_digest',value)
    return value
_trace_v2_original_table=table
def table(model,kind,optimizer=None):
    if _trace_v2_journal is not None:
        names=[k+'.'+key for k,p in model.named_parameters() for key in optimizer.state.get(p,{})] if kind=='optimizer' else [k for k,_ in (model.named_buffers() if kind=='buffers' else model.named_parameters())]
        _trace_v2_journal.begin_table(kind,names)
    try:return _trace_v2_original_table(model,kind,optimizer)
    finally:
        if _trace_v2_journal is not None:_trace_v2_journal.end_table()
# TRACE-V2-END

def main():
    p=argparse.ArgumentParser()
    for k in ['data','source-dir','checkpoint','loader','output']:p.add_argument('--'+k,required=True)
    p.add_argument('--seed',type=int,default=0);p.add_argument('--memory-gib',type=float,default=12.);p.add_argument('--timeout',type=int,default=1500)
    a=p.parse_args()
    if a.seed!=0 or a.memory_gib!=12.:raise ValueError('Frozen gate uses seed0 and12GiB allocator; no silent resource changes')
    if not os.environ.get('CUDA_VISIBLE_DEVICES') or torch.cuda.device_count()!=1:raise RuntimeError('One centrally leased visibleGPU required')
    torch.set_num_threads(1);torch.set_num_interop_threads(1)
    random.seed(0);np.random.seed(0);torch.manual_seed(0);torch.cuda.manual_seed_all(0)
    torch.set_float32_matmul_precision('highest');torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    torch.cuda.set_device(0);torch.cuda.set_per_process_memory_fraction(12*1024**3/torch.cuda.get_device_properties(0).total_memory)
    out=Path(a.output);out.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    def bounded():
        if time.monotonic()-start>a.timeout:raise TimeoutError('Strict offload gate internal timeout')
    rows,excluded=read_view(a.data)
    if excluded or not rows or any(r['split']!='train' for r in rows):raise ValueError('Literal-vocabulary TRAIN-only input required')
    row=sorted(rows,key=lambda r:(len(r['target'])+len(r['peptide']),r['row_id']))[0]
    if len(row['target'])+len(row['peptide'])+3!=48:raise ValueError('Exact frozen shortest TRAIN48 required')
    config={'at':now(),'source_sha256':sha(__file__),'full_native_source_sha256':sha(Path(__file__).with_name('pepinter_full_classification.py')),'full_native_utils_sha256':sha(Path(__file__).with_name('pepinter_full_classification_utils.py')),'input_sha256':sha(a.data),'initializer_sha256':sha(a.checkpoint),'loader_sha256':sha(a.loader),'row_id':row['row_id'],'batch_size':1,'tokens':48,'seed':0,'branches':['reference','reference-replay','save-on-cpu'],'optimizer':'stock CUDA AdamW default foreach/defaultbetas/eps,lr1e-4,weight_decay.01','clip_norm':1.,'step_count_per_branch':1,'parameter_dtype':'FP32','autocast':'BF16','save_on_cpu_pin_memory':False,'parameters_expected':PARAMETERS,'baseline_seeds':0,'validation_test_rows':0,'scope':'Strict engineering equivalence only; not B24/full training or clean pretrained initialization','numeric_comparison':'Every named full gradient before/after clip, parameter, buffer, Adam tensor and RNG SHA exact, zero tolerance; reference replay must pass before offload runs','allocator_environment':{k:os.environ.get(k) for k in ['PYTORCH_CUDA_ALLOC_CONF','PYTORCH_ALLOC_CONF']}}
    save(out/'frozen-configuration.json',config)
    # TRACE-V2-BEGIN
    global _trace_v2_journal
    _trace_v2_journal=_TraceJournal(out)
    # TRACE-V2-END
    try:
        model,tokenizer,loading=model_and_tokenizer(a);model.train();bounded()
        batchnorm=[k for k,m in model.named_modules() if isinstance(m,torch.nn.modules.batchnorm._BatchNorm)]
        if batchnorm:raise ValueError('Unexpected BatchNorm requires additional running-state protocol')
        initial_parameters={k:v.detach().cpu().clone() for k,v in model.named_parameters()}
        initial_buffers={k:v.detach().cpu().clone() for k,v in model.named_buffers()}
        rotary=[]
        for name,m in model.named_modules():
            if m.__class__.__name__=='RotaryEmbedding':
                keys=['_cos_cached','_sin_cached','_cos_k_cached','_sin_k_cached']
                if any(getattr(m,k) is not None for k in keys) or m._seq_len_cached!=0:raise ValueError('Initial Rotary cache is not pristine')
                rotary.append((name,m))
        if len(rotary)!=36:raise ValueError('Expected36native Rotary caches')
        initial_rng=capture_rng();branches=[]
        for name in config['branches']:
            # TRACE-V2-BEGIN
            if _trace_v2_journal is not None:_trace_v2_journal.start_branch(name)
            # TRACE-V2-END
            bounded()
            with torch.no_grad():
                for k,v in model.named_parameters():v.copy_(initial_parameters[k]);v.grad=None
                for k,v in model.named_buffers():v.copy_(initial_buffers[k])
            for _,m in rotary:
                for key in ['_cos_cached','_sin_cached','_cos_k_cached','_sin_k_cached']:setattr(m,key,None)
                m._seq_len_cached=0
            model.train();restore_rng(initial_rng);gc.collect();torch.cuda.empty_cache();torch.cuda.reset_peak_memory_stats()
            flags=lambda:{'training':{k:m.training for k,m in model.named_modules()},'requires_grad':{k:v.requires_grad for k,v in model.named_parameters()},'gradient_checkpointing':model.transformer.gradient_checkpointing,'BN_modules':batchnorm,'TF32_matmul':torch.backends.cuda.matmul.allow_tf32,'TF32_cudnn':torch.backends.cudnn.allow_tf32,'cudnn_benchmark':torch.backends.cudnn.benchmark,'cudnn_deterministic':torch.backends.cudnn.deterministic,'deterministic_algorithms':torch.are_deterministic_algorithms_enabled()}
            record={'branch':name,'started_at':now(),'initial_parameters':table(model,'parameters'),'initial_buffers':table(model,'buffers'),'initial_rng':rng_record(),'initial_flags':flags()}
            tokens,labels=encode(tokenizer,[row]);optimizer=torch.optim.AdamW(model.parameters(),lr=1e-4,weight_decay=.01)
            if optimizer.defaults['foreach'] is not None:raise ValueError('DefaultAdamW execution engine must remain untouched')
            optimizer.zero_grad(set_to_none=True);events=[];offload=torch.autograd.graph.save_on_cpu(pin_memory=False)
            # TRACE-V2-BEGIN
            if _trace_v2_journal is not None:_trace_v2_journal.events=events
            # TRACE-V2-END
            def pack(t):
                # TRACE-V2-BEGIN
                if _trace_v2_journal is not None:_trace_v2_journal.emit('pack_attempt',{'shape':list(t.shape),'stride':list(t.stride()),'dtype':str(t.dtype),'device':str(t.device),'bytes':t.numel()*t.element_size()})
                # TRACE-V2-END
                packed=offload.pack_hook(t);cpu=packed[1]
                if cpu.device.type!='cpu' or cpu.dtype!=t.dtype or cpu.shape!=t.shape or cpu.stride()!=t.stride():raise ValueError('Offloaded tensor dtype/shape/stride changed')
                original=tensor_record(t);stored=tensor_record(cpu)
                if original!=stored:raise ValueError('CPU-packed tensor values differ')
                events.append({'op':'pack','source_device':str(t.device),'saved_device':str(cpu.device),'bytes':t.numel()*t.element_size(),'tensor':original})
                return packed
            def unpack(packed):
                # TRACE-V2-BEGIN
                if _trace_v2_journal is not None:_trace_v2_journal.emit('unpack_attempt',{'saved_shape':list(packed[1].shape),'saved_stride':list(packed[1].stride()),'saved_dtype':str(packed[1].dtype),'restore_device':str(packed[0])})
                # TRACE-V2-END
                result=offload.unpack_hook(packed)
                if result.device!=packed[0] or tensor_record(result)!=tensor_record(packed[1]):raise ValueError('Restored tensor dtype/value/device/stride differs')
                events.append({'op':'unpack','restored_device':str(result.device),'bytes':result.numel()*result.element_size()})
                return result
            ctx=torch.autograd.graph.saved_tensors_hooks(pack,unpack) if name=='save-on-cpu' else contextlib.nullcontext()
            with ctx:
                with torch.autocast('cuda',dtype=torch.bfloat16):output=model(**tokens,labels=labels)
                record['loss']=tensor_record(output.loss);record['logits']=tensor_record(output.logits)
                if not record['loss']['finite'] or not record['logits']['finite']:raise ValueError('Nonfinite native forward')
                output.loss.backward()
            if sum(v.numel() for v in model.parameters() if v.grad is not None)!=PARAMETERS:raise ValueError('All576M parameters require native gradients')
            record['gradients_preclip']=table(model,'gradients')
            norm=torch.nn.utils.clip_grad_norm_(model.parameters(),1.,error_if_nonfinite=True)
            record['gradient_norm']=tensor_record(norm);record['gradients_postclip']=table(model,'gradients')
            optimizer.step();torch.cuda.synchronize()
            record.update({'updated_parameters':table(model,'parameters'),'updated_buffers':table(model,'buffers'),'optimizer':table(model,'optimizer',optimizer),'post_rng':rng_record(),'post_flags':flags(),'finite_native_state':finite_model_and_adam(model,optimizer,1),'hook_events':events,'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_reserved_bytes':torch.cuda.max_memory_reserved(),'completed_at':now()})
            for field in ['gradients_preclip','gradients_postclip','updated_parameters','updated_buffers','optimizer']:
                if not all(v['finite'] for v in record[field].values()):raise ValueError('Nonfinite full tensor audit: '+field)
            if name=='save-on-cpu' and not any(e['op']=='pack' and e['source_device'].startswith('cuda') and e['bytes']>0 for e in events):raise ValueError('No real CUDA tensor offload hook observed')
            save(out/(name+'.json'),record);branches.append(record)
            if len(branches)==2:save(out/'reference-replay-comparison.json',strict_equal(branches[0],record))
            if len(branches)==3:save(out/'offload-comparison.json',strict_equal(branches[0],record))
            del optimizer,output,tokens,labels,norm;model.zero_grad(set_to_none=True);gc.collect();torch.cuda.empty_cache();bounded()
        save(out/'summary.json',{'status':'succeeded','completed_at':now(),'scope':config['scope'],'native_parameters':PARAMETERS,'actual_optimizer_steps':3,'reference_replay_exact':True,'offload_exact':True,'branches':[{k:r[k] for k in ['branch','peak_allocated_bytes','peak_reserved_bytes','completed_at']} for r in branches],'source_checkpoint_loading':loading,'all_branch_files_sha256':{r['branch']:sha(out/(r['branch']+'.json')) for r in branches},'baseline_seeds_completed':0,'validation_test_rows':0,'B24_feasibility_demonstrated':False,'elapsed_seconds':time.monotonic()-start})
    except Exception as exc:
        save(out/'failure-diagnostic.json',{'at':now(),'type':type(exc).__name__,'error':str(exc),'stop_branch_on_reference_replay_or_offload_mismatch':True,'no_tolerance_relaxation_or_second_optimization_fallback':True,'baseline_seeds_completed':0,'validation_test_rows':0,'peak_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_reserved_bytes':torch.cuda.max_memory_reserved()});raise
    # TRACE-V2-BEGIN
    finally:
        _trace_v2_finish(_trace_v2_journal,locals().get('record'))
    # TRACE-V2-END
if __name__=='__main__':main()
