"""State, sampler and checkpoint utilities for native PepInter full-parameter training.

No model construction, CUDA access or scientific execution occurs on import.
"""
import hashlib,json,os,random
from pathlib import Path
import numpy as np
import torch
from common import now,save,sha,sha_text

def capture_rng():
    n=np.random.get_state()
    return {'python':random.getstate(),'numpy':{'name':n[0],'keys':n[1].tolist(),'position':int(n[2]),'has_gauss':int(n[3]),'cached_gaussian':float(n[4])},
        'torch_cpu':torch.get_rng_state(),'torch_cuda':torch.cuda.get_rng_state_all() if torch.cuda.is_initialized() else []}

def restore_rng(value):
    random.setstate(value['python']);n=value['numpy'];np.random.set_state((n['name'],np.asarray(n['keys'],dtype=np.uint32),n['position'],n['has_gauss'],n['cached_gaussian']))
    torch.set_rng_state(value['torch_cpu'])
    if value['torch_cuda']:
        if not torch.cuda.is_initialized():raise ValueError('Checkpoint CUDA RNG requires initialized assigned device')
        torch.cuda.set_rng_state_all(value['torch_cuda'])

def sampler_plan(row_ids,seed,epochs=5):
    if len(row_ids)!=len(set(row_ids)) or not row_ids:raise ValueError('Unique nonempty canonical TRAIN identifiers required')
    generator=torch.Generator(device='cpu').manual_seed(seed);records=[]
    for epoch in range(epochs):
        before=generator.get_state().tolist();order=torch.randperm(len(row_ids),generator=generator).tolist();after=generator.get_state().tolist()
        ids=[row_ids[i] for i in order]
        records.append({'epoch':epoch+1,'ordered_row_ids':ids,'ordered_row_ids_sha256':sha_text('\n'.join(ids)),'generator_state_before_uint8':before,'generator_state_after_uint8':after})
    return {'schema':'fourtask.native-full-training-sampler.v1','seed':seed,'epochs':epochs,'shuffle':'One Torch RandomSampler-style randperm per epoch, dedicated seededCPU generator; explicit common-data sampler adaptation','row_count':len(row_ids),'canonical_train_row_ids_sha256':sha_text('\n'.join(row_ids)),'epoch_records':records}

def validate_sampler(value,row_ids,seed):
    if value['seed']!=seed or value['epochs']!=5 or value['canonical_train_row_ids_sha256']!=sha_text('\n'.join(row_ids)):raise ValueError('Sampler identity does not match exact canonical TRAIN input')
    if len(value['epoch_records'])!=5:raise ValueError('All5epochs must be frozen')
    expected_state=torch.Generator(device='cpu').manual_seed(seed).get_state().tolist()
    for i,r in enumerate(value['epoch_records'],1):
        if r['generator_state_before_uint8']!=expected_state:raise ValueError('Epoch sampler state chain differs from declared seed')
        ids=r['ordered_row_ids']
        if r['epoch']!=i or len(ids)!=len(row_ids) or set(ids)!=set(row_ids) or r['ordered_row_ids_sha256']!=sha_text('\n'.join(ids)):raise ValueError('Epoch permutation omits/repeats/changes a TRAIN row')
        g=torch.Generator(device='cpu');g.set_state(torch.tensor(r['generator_state_before_uint8'],dtype=torch.uint8));order=torch.randperm(len(row_ids),generator=g).tolist()
        if [row_ids[k] for k in order]!=ids or g.get_state().tolist()!=r['generator_state_after_uint8']:raise ValueError('Frozen actual Torch permutation RNG replay differs')
        expected_state=r['generator_state_after_uint8']
    return True

def batch_equal_mean_fp32(values):
    accumulator=np.float32(0)
    for value in values:accumulator=np.float32(accumulator+np.float32(value))
    return float(np.float32(accumulator/np.float32(len(values)))) if values else None

def safe_torch_load(path):
    return torch.load(path,map_location='cpu',weights_only=True,mmap=True)

def atomic_checkpoint(directory,payload,slot):
    """Write one exact owned rolling slot; prior complete slot remains until atomic replace."""
    directory=Path(directory).resolve();directory.mkdir(parents=True,exist_ok=True)
    if slot not in [0,1]:raise ValueError('Exactly two bounded recovery slots')
    path=directory/f'recovery-slot{slot}.pt';temp=directory/(path.name+'.partial')
    if temp.exists():raise FileExistsError('Preserve existing incomplete checkpoint; use a new attempt directory')
    with temp.open('xb') as f:
        torch.save(payload,f);f.flush();os.fsync(f.fileno())
    temp.replace(path)
    return {'path':str(path),'bytes':path.stat().st_size,'sha256':sha(path),'written_at':now(),'slot':slot,'optimizer_steps':payload['cursor']['completed_optimizer_steps'],'epoch':payload['cursor']['epoch'],'next_batch':payload['cursor']['next_batch']}

def validate_checkpoint_identity(checkpoint,identity):
    if checkpoint['schema']!='fourtask.pepinter-full-native-checkpoint.v1' or checkpoint['identity']!=identity:raise ValueError('Resume requires identical source/data/sampler/seed/candidate/numerical settings')
    if not {'model','optimizer','scheduler','rng','cursor'}<=set(checkpoint):raise ValueError('Incomplete fullparameter checkpoint state')
    return True

def append_event(path,row):
    path=Path(path)
    with path.open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())

def retire_nonfinal_recovery(directory,final_entry):
    """Keep terminal fullcheckpoint; retire only the other transient owned rolling slot."""
    directory=Path(directory).resolve();keep=Path(final_entry['path']).resolve()
    if keep.parent!=directory or not keep.is_file() or sha(keep)!=final_entry['sha256']:raise ValueError('Current final fullcheckpoint must be physically verified before retiring a transient slot')
    retired=[]
    for slot in [0,1]:
        path=directory/f'recovery-slot{slot}.pt'
        if path==keep or not path.exists():continue
        resolved=path.resolve()
        if resolved.parent!=directory or path.is_symlink():raise ValueError('Only exact task-owned regular transient recovery slot may be retired')
        retired.append({'path':str(path),'bytes':path.stat().st_size,'sha256':sha(path),'reason':'Other transient recovery slot after complete terminal finalcheckpoint verified; not a candidate/failed terminal artifact'})
        path.unlink()
    return retired
