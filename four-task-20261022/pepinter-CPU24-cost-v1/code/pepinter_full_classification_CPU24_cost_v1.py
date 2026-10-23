"""PREPARED CPU16/FP32 B24 TRAIN991 two-step cost gate; no formal fit."""
import argparse,contextlib,gc,json,math,os,random,sys,time,resource
from pathlib import Path
for key in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[key]='16'
os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['TOKENIZERS_PARALLELISM']='false'
sys.path.insert(0,str(Path(__file__).resolve().parent/'continuation-20261023/native-full-classification-CPU24-prepare-v1'))
import cpu24_observe as _observe
from cpu24_observe import phase as _phase
import numpy as np
import torch
from transformers import get_linear_schedule_with_warmup
from common import now,save,sha,sha_text,read_view
from pepinter_extract import audited_loader
PARAMETERS=576293761
def model_and_tokenizer(args):
    sys.path.insert(0, str(Path(args.source_dir) / 'src'))
    from pepinter.pepinter.configuration_pepinter import PepInterConfig
    from pepinter.pepinter.modeling_pepinter import PepInterModelForClassification
    from pepinter.pepinter.tokenization_pepinter import ESMSeqTokenizer
    with _phase('model_constructor'):
        model = PepInterModelForClassification(PepInterConfig(vocab_size=64, hidden_size=1152, num_attention_heads=18, num_hidden_layers=36, num_labels=1, problem_type='single_label_classification', dropout=0.1))
    with _phase('published_checkpoint_load'):
        state, loading = audited_loader(args.loader)(args.checkpoint)
    with _phase('initializer_tensor_copy'):
        result = model.load_state_dict({k: v for k, v in state.items() if not k.startswith('classifier.')}, strict=False)
    if set(result.missing_keys) != {k for k in model.state_dict() if k.startswith('classifier.')} or result.unexpected_keys:
        raise ValueError('Only new original classification head may be absent from public regression initializer')
    del state
    gc.collect()
    if sum((p.numel() for p in model.parameters())) != PARAMETERS or sum((p.numel() for p in model.parameters() if p.requires_grad)) != PARAMETERS:
        raise ValueError('All576293761native parameters must remain trainable')
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': False})
    if not model.transformer.gradient_checkpointing:
        raise ValueError('Native gradient checkpointing inactive')
    tokenizer = ESMSeqTokenizer()
    public = json.loads(tokenizer.backend_tokenizer.to_str())
    if {'vocab': public['model']['vocab'], 'pair_template': public['post_processor']['pair']} != loading['legacy_tokenizer_spec']:
        raise ValueError('Original paired tokenizer differs')
    return (model.to('cpu'), tokenizer, loading)

def encode(tokenizer, rows):
    value = tokenizer([r['target'] for r in rows], [r['peptide'] for r in rows], padding='longest', truncation=False, return_token_type_ids=True, return_tensors='pt')
    if value['input_ids'].shape[1] != max((len(r['target']) + len(r['peptide']) + 3 for r in rows)):
        raise ValueError('Actual paired tokenizer length mismatch or hidden truncation')
    return (value.to('cpu'), torch.tensor([r['label'] for r in rows], dtype=torch.float32, device='cpu'))

def train_step(model, tokenizer, optimizer, scheduler, rows):
    model.train()
    with _phase('tokenization'):
        tokens, labels = encode(tokenizer, rows)
    optimizer.zero_grad(set_to_none=True)
    lr = optimizer.param_groups[0]['lr']
    with _phase('forward'):
        with contextlib.nullcontext():
            out = model(**tokens, labels=labels)
    if not torch.isfinite(out.loss):
        raise ValueError('Nonfinite native Focal loss')
    with _phase('backward'):
        out.loss.backward()
    if any((p.grad is None for p in model.parameters())) or sum((p.numel() for p in model.parameters() if p.grad is not None)) != PARAMETERS:
        raise ValueError('All native parameter tensors must receive gradients')
    with _phase('gradient_clip'):
        norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0, error_if_nonfinite=True)
    with _phase('AdamW_update'):
        optimizer.step()
    with _phase('scheduler_update'):
        scheduler.step()
    record = {'native_batch_mean_Focal': float(out.loss.detach()), 'gradient_norm_before_clip': float(norm), 'learning_rate_used': lr, 'learning_rate_after_scheduler': optimizer.param_groups[0]['lr'], 'parameters_with_gradient': PARAMETERS, 'rows': len(rows), 'paired_token_length': int(tokens['input_ids'].shape[1])}
    del out, tokens, labels
    return record

def finite_model_and_adam(model, optimizer, expected_steps):
    count = 0
    moments = 0
    if len(optimizer.state) != len(list(model.parameters())):
        raise ValueError('Missing native Adam states')
    for p in model.parameters():
        if not torch.isfinite(p).all().item():
            raise ValueError('Nonfinite parameter after update')
        state = optimizer.state[p]
        if int(state['step'].item()) != expected_steps:
            raise ValueError('Adam step mismatch')
        for key, value in state.items():
            if isinstance(value, torch.Tensor):
                count += 1
                if not torch.isfinite(value).all().item():
                    raise ValueError('Nonfinite Adam state')
                if key in {'exp_avg', 'exp_avg_sq'}:
                    moments += value.numel()
                    if value.dtype != torch.float32 or value.shape != p.shape:
                        raise ValueError('All native FP32 moments must match parameter shape')
    if moments != 2 * PARAMETERS:
        raise ValueError('Full Adam moment element count differs')
    return {'all_model_and_optimizer_tensors_finite': True, 'Adam_state_tensor_count': count, 'Adam_moment_elements': moments, 'optimizer_steps': expected_steps}

def main():
    p=argparse.ArgumentParser()
    for key in ['data','source-dir','checkpoint','loader','output']:p.add_argument('--'+key,required=True)
    p.add_argument('--timeout',type=int,default=6900);a=p.parse_args()
    if os.environ.get('CUDA_VISIBLE_DEVICES')!='' or torch.cuda.is_initialized():raise RuntimeError('CPU only, CUDA hidden and uninitialized required')
    torch.set_num_threads(16);torch.set_num_interop_threads(1)
    if torch.get_num_threads()!=16 or len(os.sched_getaffinity(0))!=16 or set(os.sched_getaffinity(0))&set(range(14,30)):raise RuntimeError('Exactly16 centrally assigned CPUs excluding14..29 required')
    if torch.get_default_dtype()!=torch.float32:raise ValueError('NativeCPU FP32 explicit dtype required')
    random.seed(0);np.random.seed(0);torch.manual_seed(0);torch.set_float32_matmul_precision('highest')
    out=Path(a.output);out.mkdir(parents=True,exist_ok=False);_observe.PHASE_PATH=out/'phase-timings.jsonl';start=time.monotonic()
    def bounded():
        if time.monotonic()-start>a.timeout:raise TimeoutError('CPU24 cost gate timeout; no shortened fallback')
    rows,excluded=read_view(a.data)
    if excluded or len(rows)!=24 or any(r['split']!='train' for r in rows):raise ValueError('Exact frozen24 TRAIN rows required,0val/test')
    if sha(a.data)!='edc1b966d55b4c0f933198f354fe9f4cce1a4d24ff2f2cdc9662f25bb118ccfe':raise ValueError('Original longest24TRAIN bytes/order must remain unchanged')
    if max(len(r['target'])+len(r['peptide'])+3 for r in rows)!=991:raise ValueError('Original full padded991 shape required')
    save(out/'frozen-config.json',{'at':now(),'source_sha256':sha(__file__),'data_sha256':sha(a.data),'row_order_sha256':sha_text('\n'.join(r['row_id'] for r in rows)),'initializer_sha256':sha(a.checkpoint),'loader_sha256':sha(a.loader),'backend':'CPU FP32,noautocast; not CUDA BF16 bitwise equivalence','threads':16,'affinity':sorted(os.sched_getaffinity(0)),'torch':str(torch.__version__),'batch_size':24,'padded_tokens':991,'train_rows':24,'validation_test_rows':0,'parameters':PARAMETERS,'total_steps':2270,'warmup_steps':113,'optimizer':'stock CPU AdamW default foreach; backend may differ from CUDA','scope':'Two-step representative cost gate, not fiveepoch candidate or completed seed','checkpoint_write_cost_measured':False})
    try:
        with _phase('whole_model_and_tokenizer'):model,tokenizer,loading=model_and_tokenizer(a)
        model.train();bounded()
        optimizer=torch.optim.AdamW(model.parameters(),lr=1e-4,weight_decay=.01)
        if optimizer.defaults['foreach'] is not None:raise ValueError('Native defaultCPU AdamW policy must remain untouched')
        scheduler=get_linear_schedule_with_warmup(optimizer,num_warmup_steps=113,num_training_steps=2270)
        probe=next(p for name,p in model.named_parameters() if name.startswith('transformer.') and p.ndim>=2);before=probe.detach().reshape(-1)[:32].float().cpu().clone();records=[]
        for step in range(1,3):
            with _phase('whole_step_'+str(step)):
                record={'step':step,**train_step(model,tokenizer,optimizer,scheduler,rows)}
                with _phase('full_model_Adam_finite_audit'):record.update(finite_model_and_adam(model,optimizer,step))
            if record['paired_token_length']!=991 or record['rows']!=24:raise ValueError('No silent shorter shape/batch')
            if record['learning_rate_used']!=([0.,1e-4/113][step-1]):raise ValueError('Original warmupLR0 thenpositive required')
            records.append(record);save(out/'gate-progress.json',{'at':now(),'completed_optimizer_steps':step,'records':records,'completed_baseline_seeds':0,'validation_test_rows':0});bounded()
        delta=float((probe.detach().reshape(-1)[:32].float().cpu()-before).abs().max())
        if delta<=0:raise ValueError('Original encoder probe must change after secondwarmup step')
        if torch.cuda.is_initialized():raise RuntimeError('UnexpectedCUDA initialized in CPU gate')
        save(out/'summary.json',{'status':'succeeded','completed_at':now(),'scope':'CPU16FP32 native B24[24,991]twoAdam cost gate only','parameters':PARAMETERS,'trainable_parameters':PARAMETERS,'step_records':records,'encoder_update_probe':delta,'new_optimizer_steps':2,'completed_baseline_seeds':0,'validation_test_rows':0,'CPU_FP32_not_GPU_BF16_bitwise_equivalence':True,'cpu_default_foreach':optimizer.defaults['foreach'],'source_checkpoint_loading':loading,'elapsed_seconds':time.monotonic()-start,'process_peak_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,'full_checkpoint_write_not_measured':True,'GPU_initialized':False})
    except Exception as exc:
        save(out/'failure-diagnostic.json',{'at':now(),'type':type(exc).__name__,'error':str(exc),'scope':'CPU24cost gate only','no_reduced_batch_or_freeze_fallback':True,'completed_baseline_seeds':0,'validation_test_rows':0,'elapsed_seconds':time.monotonic()-start,'process_peak_RSS_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024});raise
if __name__=='__main__':main()
