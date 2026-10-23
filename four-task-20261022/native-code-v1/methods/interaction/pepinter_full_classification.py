"""Prepared native full-parameter PepInter classification fit/gate/selected inference.

Not launched by this module; every real CUDA execution needs the central dispatcher.
Formal fit is one seed/LR candidate, five complete epochs, batch24, final-only validation.
"""
import argparse,gc,json,math,os,random,shutil,sys,time
from pathlib import Path
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:os.environ[key]='1'
os.environ['TOKENIZERS_PARALLELISM']='false'
import numpy as np
import torch
from transformers import get_linear_schedule_with_warmup
from common import now,save,sha,sha_text,read_view,prediction_rows,write_csv,score
from pepinter_extract import audited_loader
from pepinter_full_classification_utils import capture_rng,restore_rng,validate_sampler,atomic_checkpoint,safe_torch_load,validate_checkpoint_identity,append_event,retire_nonfinal_recovery
PARAMETERS=576293761

def model_and_tokenizer(args):
    sys.path.insert(0,str(Path(args.source_dir)/'src'))
    from pepinter.pepinter.configuration_pepinter import PepInterConfig
    from pepinter.pepinter.modeling_pepinter import PepInterModelForClassification
    from pepinter.pepinter.tokenization_pepinter import ESMSeqTokenizer
    model=PepInterModelForClassification(PepInterConfig(vocab_size=64,hidden_size=1152,num_attention_heads=18,num_hidden_layers=36,num_labels=1,problem_type='single_label_classification',dropout=.1))
    state,loading=audited_loader(args.loader)(args.checkpoint)
    result=model.load_state_dict({k:v for k,v in state.items() if not k.startswith('classifier.')},strict=False)
    if set(result.missing_keys)!={k for k in model.state_dict() if k.startswith('classifier.')} or result.unexpected_keys:raise ValueError('Only new original classification head may be absent from public regression initializer')
    del state;gc.collect()
    if sum(p.numel() for p in model.parameters())!=PARAMETERS or sum(p.numel() for p in model.parameters() if p.requires_grad)!=PARAMETERS:raise ValueError('All576293761native parameters must remain trainable')
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False})
    if not model.transformer.gradient_checkpointing:raise ValueError('Native gradient checkpointing inactive')
    tokenizer=ESMSeqTokenizer();public=json.loads(tokenizer.backend_tokenizer.to_str())
    if {'vocab':public['model']['vocab'],'pair_template':public['post_processor']['pair']}!=loading['legacy_tokenizer_spec']:raise ValueError('Original paired tokenizer differs')
    return model.to('cuda:0'),tokenizer,loading

def encode(tokenizer,rows):
    value=tokenizer([r['target'] for r in rows],[r['peptide'] for r in rows],padding='longest',truncation=False,return_token_type_ids=True,return_tensors='pt')
    if value['input_ids'].shape[1]!=max(len(r['target'])+len(r['peptide'])+3 for r in rows):raise ValueError('Actual paired tokenizer length mismatch or hidden truncation')
    return value.to('cuda:0'),torch.tensor([r['label'] for r in rows],dtype=torch.float32,device='cuda:0')

def train_step(model,tokenizer,optimizer,scheduler,rows):
    model.train();tokens,labels=encode(tokenizer,rows);optimizer.zero_grad(set_to_none=True);lr=optimizer.param_groups[0]['lr']
    with torch.autocast('cuda',dtype=torch.bfloat16):out=model(**tokens,labels=labels)
    if not torch.isfinite(out.loss):raise ValueError('Nonfinite native Focal loss')
    out.loss.backward()
    if any(p.grad is None for p in model.parameters()) or sum(p.numel() for p in model.parameters() if p.grad is not None)!=PARAMETERS:raise ValueError('All native parameter tensors must receive gradients')
    norm=torch.nn.utils.clip_grad_norm_(model.parameters(),1.,error_if_nonfinite=True)
    optimizer.step();scheduler.step();torch.cuda.synchronize()
    record={'native_batch_mean_Focal':float(out.loss.detach()),'gradient_norm_before_clip':float(norm),'learning_rate_used':lr,'learning_rate_after_scheduler':optimizer.param_groups[0]['lr'],'parameters_with_gradient':PARAMETERS,'rows':len(rows),'paired_token_length':int(tokens['input_ids'].shape[1])}
    del out,tokens,labels
    return record

def finite_model_and_adam(model,optimizer,expected_steps):
    count=0;moments=0
    if len(optimizer.state)!=len(list(model.parameters())):raise ValueError('Missing native Adam states')
    for p in model.parameters():
        if not torch.isfinite(p).all().item():raise ValueError('Nonfinite parameter after update')
        state=optimizer.state[p]
        if int(state['step'].item())!=expected_steps:raise ValueError('Adam step mismatch')
        for key,value in state.items():
            if isinstance(value,torch.Tensor):
                count+=1
                if not torch.isfinite(value).all().item():raise ValueError('Nonfinite Adam state')
                if key in {'exp_avg','exp_avg_sq'}:
                    moments+=value.numel()
                    if value.dtype!=torch.float32 or value.shape!=p.shape:raise ValueError('All native FP32 moments must match parameter shape')
    if moments!=2*PARAMETERS:raise ValueError('Full Adam moment element count differs')
    return {'all_model_and_optimizer_tensors_finite':True,'Adam_state_tensor_count':count,'Adam_moment_elements':moments,'optimizer_steps':expected_steps}

def evaluate(model,tokenizer,rows,batch_size,outdir,seed,name):
    model.eval();pred=[];logits=[];batch_records=[];acc=torch.zeros((),device='cuda:0',dtype=torch.float32);weighted=0.
    with torch.inference_mode():
        for number,start in enumerate(range(0,len(rows),batch_size)):
            batch=rows[start:start+batch_size];tokens,labels=encode(tokenizer,batch)
            with torch.autocast('cuda',dtype=torch.bfloat16):output=model(**tokens,labels=labels)
            if not torch.isfinite(output.loss) or not torch.isfinite(output.logits).all():raise ValueError('Nonfinite evaluation output')
            # Original predict_step applies sigmoid to its native logits dtype, then transfers.
            probability=torch.sigmoid(output.logits.detach()).reshape(-1).float().cpu().tolist();raw=output.logits.detach().reshape(-1).float().cpu().tolist()
            pred.extend(probability);logits.extend(raw);loss=output.loss.detach().float();acc.add_(loss);weighted+=float(loss)*len(batch)
            batch_records.append({'batch':number,'rows':len(batch),'native_batch_mean_Focal':float(loss),'row_ids_sha256':sha_text('\n'.join(r['row_id'] for r in batch))})
    native_equal_batch=float(acc/len(batch_records));metrics=score([r['label'] for r in rows],pred,'classification')
    records=prediction_rows(rows,pred,seed,'PepInter_fullparameter_native_classification_conditional_init')
    for record,logit in zip(records,logits):
        record['native_logit_float32_view']=logit;record['native_strict_gt_half_class']=int(record['prediction']>.5);record['common_ge_half_class']=int(record['prediction']>=.5)
    write_csv(outdir/(name+'-predictions.csv'),records);write_csv(outdir/(name+'-batch-Focal.csv'),batch_records)
    save(outdir/(name+'-metrics.json'),metrics)
    return {'rows':len(rows),'native_equal_batch_Focal_MeanMetric_FP32':native_equal_batch,'sample_weighted_Focal':weighted/len(rows),'standard_probability_metrics':metrics,'native_hard_threshold':'>0.5; common benchmark metrics retain>=0.5', 'native_sigmoid_input_dtype':'Native BF16logits under authorBF16mixed policy; convert toFP32 only after sigmoid forCSV','prediction_sha256':sha(outdir/(name+'-predictions.csv'))}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--mode',choices=['fit','gate','evaluate-selected'],required=True)
    for k in ['data','source-dir','checkpoint','loader','output']:p.add_argument('--'+k,required=True)
    p.add_argument('--sampler-plan');p.add_argument('--seed',type=int,required=True);p.add_argument('--candidate',type=int,choices=[0,1],default=0)
    p.add_argument('--learning-rate',type=float,choices=[1e-4,1e-5],default=1e-4);p.add_argument('--memory-gib',type=float,required=True)
    p.add_argument('--batch-size',type=int,default=24);p.add_argument('--epochs',type=int,default=5);p.add_argument('--timeout',type=int,required=True)
    p.add_argument('--foreach',choices=['default','false'],default='default');p.add_argument('--resume');p.add_argument('--resume-sha256');p.add_argument('--selection');p.add_argument('--selection-sha256');p.add_argument('--gate-steps',type=int,choices=[2],default=2)
    a=p.parse_args()
    if a.batch_size!=24 or a.epochs!=5:raise ValueError('Formal native protocol fixes batch24 and5epochs; no silent microbatch/shortened training')
    if not 0<=a.seed<=9:raise ValueError('Exactly registered seeds0through9')
    if a.candidate!=[1e-4,1e-5].index(a.learning_rate):raise ValueError('Predeclared twoLR candidate identity differs')
    if not os.environ.get('CUDA_VISIBLE_DEVICES') or torch.cuda.device_count()!=1:raise RuntimeError('Only one centrally assigned visible GPU may execute this worker')
    torch.set_num_threads(1);torch.set_num_interop_threads(1);random.seed(a.seed);np.random.seed(a.seed);torch.manual_seed(a.seed);torch.cuda.manual_seed_all(a.seed)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False;torch.set_float32_matmul_precision('highest')
    torch.cuda.set_device(0);torch.cuda.set_per_process_memory_fraction(a.memory_gib*1024**3/torch.cuda.get_device_properties(0).total_memory);torch.cuda.reset_peak_memory_stats()
    out=Path(a.output);out.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    def bounded():
        if time.monotonic()-start>a.timeout:raise TimeoutError('Native fullparameter per-job timeout; last complete rolling state retained')
    rows,excluded=read_view(a.data)
    if excluded or any(r['label'] not in [0.,1.] or len(r['target'])>960 or len(r['peptide'])>64 for r in rows):raise ValueError('Only frozen literal20AA/nativebounds binary rows, no truncation')
    if a.mode=='fit' and set(r['split'] for r in rows)!={'train','validation'}:raise ValueError('Fit input must contain TRAIN+VALIDATION only, no TEST rows')
    if a.mode=='gate' and any(r['split']!='train' for r in rows):raise ValueError('Capacity gate is TRAIN only')
    if a.mode=='evaluate-selected' and any(r['split']!='test' for r in rows):raise ValueError('Postselection evaluation is TEST only')
    if a.mode=='evaluate-selected':
        if not a.selection or not a.selection_sha256 or sha(a.selection)!=a.selection_sha256:raise ValueError('Frozen completed validation-only selection required before TEST forward')
        selected=json.loads(Path(a.selection).read_text());assert selected['selected_before_test'] and selected['seed']==a.seed and selected['candidate']==a.candidate and selected['learning_rate']==a.learning_rate
        if sha(selected['checkpoint_path'])!=selected['checkpoint_sha256']:raise ValueError('Selected fullparameter checkpoint SHA differs')
        if selected['test_view_sha256']!=sha(a.data):raise ValueError('Selected protocol binds a different heldout TEST view')
    identity={'source_sha256':sha(__file__),'utils_sha256':sha(Path(__file__).with_name('pepinter_full_classification_utils.py')),'data_sha256':sha(a.data),'seed':a.seed,'candidate':a.candidate,'learning_rate':a.learning_rate,'epochs':5,'batch_size':24,'optimizer':'AdamW','foreach':a.foreach,'warmup_ratio':.05,'clip_norm':1.,'parameter_dtype':'FP32','autocast':'BF16','gradient_checkpointing':True,'initializer_sha256':sha(a.checkpoint),'native_source_reference':str(Path(a.source_dir).resolve()),'sampler_sha256':sha(a.sampler_plan) if a.sampler_plan else None}
    save(out/'frozen-configuration.json',{'created_at':now(),'mode':a.mode,'identity':identity,'standard_initializer_scope':'Released regression-supervised backbone conditional exposure; original energy checkpoint unavailable','completed_baseline_seeds':0,'test_forward_before_validation_selection':False,'checkpoint_policy':'Two atomic rolling slots, epochboundary only; preserve failedattempt complete state, retire redundant transient slot onlyafter successful final fullcheckpoint verified'})
    try:
        model,tokenizer,loading=model_and_tokenizer(a);bounded()
        if a.mode=='evaluate-selected':
            saved=safe_torch_load(selected['checkpoint_path']);validate_checkpoint_identity(saved,selected['fit_identity'])
            if saved['cursor']['epoch']!=6 or saved['cursor']['completed_optimizer_steps']!=2270:raise ValueError('Five complete native epochs required before TEST forward')
            model.load_state_dict(saved['model'],strict=True);del saved;gc.collect();result=evaluate(model,tokenizer,rows,24,out,a.seed,'test');bounded()
            save(out/'summary.json',{'status':'succeeded','completed_at':now(),'scope':'Selected fullnative candidate TEST evaluation only,0newfit','seed':a.seed,'selection_sha256':sha(a.selection),'selected_checkpoint_sha256':selected['checkpoint_sha256'],'test_result':result,'new_optimizer_steps':0,'peak_cuda_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_cuda_reserved_bytes':torch.cuda.max_memory_reserved()});return
        train=[r for r in rows if r['split']=='train'];valid=[r for r in rows if r['split']=='validation'];lookup={r['row_id']:r for r in train}
        if len(lookup)!=len(train):raise ValueError('Unique TRAIN observation IDs required')
        optimizer=torch.optim.AdamW(model.parameters(),lr=a.learning_rate,weight_decay=.01,**({'foreach':False} if a.foreach=='false' else {}))
        total_steps=math.ceil(10882/24)*5 if a.mode=='gate' else math.ceil(len(train)/24)*5;warmup_steps=int(total_steps*.05)
        scheduler=get_linear_schedule_with_warmup(optimizer,num_warmup_steps=warmup_steps,num_training_steps=total_steps)
        if a.mode=='gate':
            if len(train)!=24:raise ValueError('Worst-case gate requires exact frozen24TRAINrows')
            records=[];probe=next(p for name,p in model.named_parameters() if name.startswith('transformer.') and p.ndim>=2);before=probe.detach().reshape(-1)[:32].float().cpu().clone()
            for step in range(1,3):records.append({'step':step,**train_step(model,tokenizer,optimizer,scheduler,train),**finite_model_and_adam(model,optimizer,step)});save(out/'gate-progress.json',{'step_records':records,'completed_baseline_seeds':0,'validation_test_rows':0});bounded()
            delta=float((probe.detach().reshape(-1)[:32].float().cpu()-before).abs().max())
            if delta<=0:raise ValueError('Native encoder update after second warmup step required')
            save(out/'summary.json',{'status':'succeeded','completed_at':now(),'scope':'Fullnative worst24TRAINbatch2step capability only','seed':a.seed,'new_optimizer_steps':2,'completed_baseline_seeds':0,'validation_test_rows':0,'step_records':records,'encoder_update_probe':delta,'parameters':PARAMETERS,'total_schedule_steps':total_steps,'warmup_steps':warmup_steps,'peak_cuda_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_cuda_reserved_bytes':torch.cuda.max_memory_reserved(),'source_checkpoint_loading':loading});return
        if len(train)!=10882 or len(valid)!=2158 or not a.sampler_plan:raise ValueError('Exact previously frozen native classification TRAIN10882/VALID2158 input required')
        sampler=json.loads(Path(a.sampler_plan).read_text());validate_sampler(sampler,[r['row_id'] for r in train],a.seed)
        cursor={'epoch':1,'next_batch':0,'completed_optimizer_steps':0,'completed_epoch_summaries':[],'epoch_loss_weighted_sum':0.,'epoch_rows':0,'epoch_batch_loss_fp32_sum':0.,'epoch_batches':0}
        if a.resume:
            if not a.resume_sha256 or sha(a.resume)!=a.resume_sha256:raise ValueError('Exact last complete resume state SHA required')
            previous=safe_torch_load(a.resume);validate_checkpoint_identity(previous,identity)
            runtime={'torch':str(torch.__version__),'cuda':torch.version.cuda,'device_name':torch.cuda.get_device_name(),'compute_capability':list(torch.cuda.get_device_capability())}
            if previous['runtime']!=runtime:raise ValueError('Resume requires the same frozen Torch/CUDA/device architecture; other backend needs an explicit new numerical protocol')
            model.load_state_dict(previous['model'],strict=True);optimizer.load_state_dict(previous['optimizer']);scheduler.load_state_dict(previous['scheduler']);cursor=previous['cursor'];restore_rng(previous['rng']);del previous;gc.collect();save(out/'resume-origin.json',{'at':now(),'source_path':a.resume,'sha256':a.resume_sha256,'cursor':cursor,'new_independent_seed':False})
        if not 1<=cursor['epoch']<=6 or not 0<=cursor['completed_optimizer_steps']<=total_steps:raise ValueError('Invalid resume cursor')
        for epoch in range(cursor['epoch'],6):
            ids=sampler['epoch_records'][epoch-1]['ordered_row_ids'];batch_ids=[ids[k:k+24] for k in range(0,len(ids),24)]
            for number in range(cursor['next_batch'],len(batch_ids)):
                chosen=[lookup[rid] for rid in batch_ids[number]];record=train_step(model,tokenizer,optimizer,scheduler,chosen);cursor['completed_optimizer_steps']+=1;cursor['next_batch']=number+1
                cursor['epoch_loss_weighted_sum']+=record['native_batch_mean_Focal']*len(chosen);cursor['epoch_rows']+=len(chosen);cursor['epoch_batch_loss_fp32_sum']=float(np.float32(np.float32(cursor['epoch_batch_loss_fp32_sum'])+np.float32(record['native_batch_mean_Focal'])));cursor['epoch_batches']+=1
                append_event(out/'training-step-log.jsonl',{'at':now(),'epoch':epoch,'batch':number,'optimizer_step':cursor['completed_optimizer_steps'],'row_ids_sha256':sha_text('\n'.join(batch_ids[number])),**record});bounded()
            if cursor['epoch_rows']!=10882:raise ValueError('Every TRAIN observation exactlyonce per completed epoch')
            epoch_record={'epoch':epoch,'train_rows':cursor['epoch_rows'],'batch_count':cursor['epoch_batches'],'optimizer_steps_through_epoch':cursor['completed_optimizer_steps'],'native_equal_batch_train_Focal_FP32':float(np.float32(np.float32(cursor['epoch_batch_loss_fp32_sum'])/np.float32(cursor['epoch_batches']))),'sample_weighted_train_Focal':cursor['epoch_loss_weighted_sum']/cursor['epoch_rows'],'ordered_row_ids_sha256':sampler['epoch_records'][epoch-1]['ordered_row_ids_sha256'],'learning_rate_after_epoch':scheduler.get_last_lr()[0],'validation_performed':False}
            append_event(out/'epoch-log.jsonl',epoch_record);cursor['completed_epoch_summaries'].append(epoch_record);cursor.update(epoch=epoch+1,next_batch=0,epoch_loss_weighted_sum=0.,epoch_rows=0,epoch_batch_loss_fp32_sum=0.,epoch_batches=0)
            finite=finite_model_and_adam(model,optimizer,cursor['completed_optimizer_steps'])
            if shutil.disk_usage(out).free<3*7*1024**3+16*1024**3:raise RuntimeError('Remote fullcheckpoint atomic-write free-space reserve insufficient')
            torch.cuda.synchronize();payload={'schema':'fourtask.pepinter-full-native-checkpoint.v1','identity':identity,'model':model.state_dict(),'optimizer':optimizer.state_dict(),'scheduler':scheduler.state_dict(),'rng':capture_rng(),'cursor':json.loads(json.dumps(cursor)),'finite_state_audit':finite,'source_checkpoint_loading':loading,'runtime':{'torch':str(torch.__version__),'cuda':torch.version.cuda,'device_name':torch.cuda.get_device_name(),'compute_capability':list(torch.cuda.get_device_capability())}}
            checkpoint=atomic_checkpoint(out,payload,epoch%2);del payload;save(out/'last-complete-recovery-index.json',checkpoint);bounded()
        if cursor['completed_optimizer_steps']!=total_steps or len(cursor['completed_epoch_summaries'])!=5:raise ValueError('All5complete epochs and scheduled optimizersteps required before validation')
        if a.resume and cursor['epoch']==6 and 'checkpoint' not in locals():checkpoint={'path':a.resume,'bytes':Path(a.resume).stat().st_size,'sha256':sha(a.resume),'read_only_previous_attempt_final_state':True}
        validation=evaluate(model,tokenizer,valid,24,out,a.seed,'validation');bounded()
        retired=retire_nonfinal_recovery(out,checkpoint) if Path(checkpoint['path']).resolve().parent==out.resolve() else []
        save(out/'final-checkpoint.manifest.json',{'checkpoint':checkpoint,'retired_transient_recovery_slots':retired,'all_trainable_parameters_and_Adam_scheduler_RNG_retained':True,'terminal_candidate':True,'actual_epoch5_validation':validation,'candidate':a.candidate,'seed':a.seed})
        save(out/'summary.json',{'status':'succeeded','completed_at':now(),'mode':'fit_candidate','seed':a.seed,'candidate':a.candidate,'learning_rate':a.learning_rate,'epochs_completed':5,'optimizer_steps':total_steps,'training_rows_each_epoch':10882,'validation_rows':2158,'test_rows_processed':0,'native_validation_equal_batch_Focal':validation['native_equal_batch_Focal_MeanMetric_FP32'],'validation':validation,'full_checkpoint':checkpoint,'epoch_records':cursor['completed_epoch_summaries'],'parameters':PARAMETERS,'trainable_parameters':PARAMETERS,'gradient_checkpointing':True,'source_checkpoint_loading':loading,'supervised_initialization_scope':'Conditional regression-supervised transfer, not originalunreleasedenergyinitializer','scope':'One complete5epoch fullparameter candidate; completed benchmarkseed requires bothLR selection and heldoutTEST evaluation','completed_baseline_seeds':0,'peak_cuda_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_cuda_reserved_bytes':torch.cuda.max_memory_reserved(),'elapsed_seconds':time.monotonic()-start})
    except Exception as exc:
        save(out/'failure-diagnostic.json',{'at':now(),'error_type':type(exc).__name__,'error':str(exc),'mode':a.mode,'seed':a.seed,'candidate':a.candidate,'baseline_seeds_completed':0,'preserve_all_complete_failed_attempt_recovery_slots':True,'no_LoRA_or_freeze_or_epoch_shortening_fallback':True,'peak_cuda_allocated_bytes':torch.cuda.max_memory_allocated(),'peak_cuda_reserved_bytes':torch.cuda.max_memory_reserved()});raise
if __name__=='__main__':main()
