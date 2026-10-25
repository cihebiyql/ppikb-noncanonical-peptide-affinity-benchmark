"""CPU-only explicit PeptideCLM2025 SPEfix adaptation, canary and features.

Resource owner launches this file. No unsafe pickle fallback or shared install.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

LOADER_SHA256 = '900827f3778996544572360606c7303deaedcce4964faeba01b57b97cf109807'
CANARIES = {
    'alanine_L':'N[C@@H](C)C(=O)O', 'alanine_D':'N[C@H](C)C(=O)O',
    'serine':'N[C@@H](CO)C(=O)O', 'phosphoserine':'N[C@@H](COP(=O)(O)O)C(=O)O',
    'aminobutyrate':'N[C@@H](CC)C(=O)O', 'alaninamide':'N[C@@H](C)C(=O)N',
    'tryptophan_fused12_L':'N[C@@H](Cc1c[nH]c2ccccc12)C(=O)O',
    'tryptophan_fused12_D':'N[C@H](Cc1c[nH]c2ccccc12)C(=O)O',
}
PAIRS = [('alanine_L','alanine_D'),('serine','phosphoserine'),
         ('alanine_L','aminobutyrate'),('alanine_L','alaninamide'),
         ('tryptophan_fused12_L','tryptophan_fused12_D')]


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda:handle.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def write_json(path,value):
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--mode',choices=['canary-coverage','features'],required=True)
    parser.add_argument('--asset-root',type=Path,required=True)
    parser.add_argument('--tokenizer-dir',type=Path,required=True)
    parser.add_argument('--input-csv',type=Path,required=True)
    parser.add_argument('--expected-input-sha256',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--threads',type=int,choices=[1,2],default=2)
    parser.add_argument('--batch-size',type=int,choices=[1,2,4],default=4)
    parser.add_argument('--max-seconds',type=int,required=True)
    args=parser.parse_args()
    if args.output.exists():raise ValueError('New run directory required')
    if args.max_seconds<=0:raise ValueError('Bounded positive budget required')
    started=time.monotonic();args.output.mkdir(parents=True)
    os.environ['CUDA_VISIBLE_DEVICES']=''
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    os.environ['TOKENIZERS_PARALLELISM']='false'
    os.environ['OMP_NUM_THREADS']=str(args.threads);os.environ['MKL_NUM_THREADS']=str(args.threads)
    loader_path=Path(__file__).with_name('load_peptideclm2025_spefix.py')
    if sha(loader_path)!=LOADER_SHA256:raise ValueError('Reviewed safe loader changed')
    if sha(args.input_csv)!=args.expected_input_sha256:raise ValueError('Frozen pure input changed')
    pure={}
    with args.input_csv.open(encoding='utf-8-sig',newline='') as handle:
        reader=csv.DictReader(handle)
        if not set(reader.fieldnames).issubset({'smiles','smiles_sha256'}):
            raise ValueError('Input must be SMILES only, without labels')
        for row in reader:
            smiles=row['smiles'];key=hashlib.sha256(smiles.encode()).hexdigest()
            if row.get('smiles_sha256') and row['smiles_sha256']!=key:raise ValueError('Raw molecule key differs')
            pure[key]=smiles
    spec=importlib.util.spec_from_file_location('reviewed_peptideclm2025_safe_loader',loader_path)
    loader=importlib.util.module_from_spec(spec);spec.loader.exec_module(loader)
    import numpy as np
    import torch
    import transformers
    torch.set_num_threads(args.threads);torch.set_num_interop_threads(1);torch.manual_seed(0)
    torch.set_default_dtype(torch.float32);torch.set_float32_matmul_precision('highest')
    tokenizer,encoder,identity=loader.load_encoder(args.asset_root,args.tokenizer_dir)
    encoder.to(device='cpu',dtype=torch.float32).eval().requires_grad_(False)
    write_json(args.output/'safe-load.json',{'status':'succeeded','weights_only':True,
        'unsafe_fallback':False,'custom_globals_allowlisted':False,'state_dict_strict_load':True,
        'model_identity':identity,'loader_sha256':LOADER_SHA256,'parameter_count':sum(p.numel() for p in encoder.parameters()),
        'shared_dependencies_installed':False})

    def encode(values):
        # Validate full original string before padded batch construction.
        for value in values:loader.tokenize_full(tokenizer,value)
        batch=tokenizer(values,add_special_tokens=True,truncation=False,padding=True,return_tensors='pt')
        out=loader.pooled_features(encoder,batch['input_ids'],batch['attention_mask']).cpu().numpy().astype(np.float32)
        if out.shape!=(len(values),768) or not np.isfinite(out).all():raise ValueError('Invalid feature output')
        return out

    tokenizations={}
    for name,smiles in CANARIES.items():
        value=loader.tokenize_full(tokenizer,smiles)
        tokenizations[name]={'input_ids':value['input_ids'],'token_count':len(value['input_ids'])}
    values=encode(list(CANARIES.values()));repeat=encode(list(CANARIES.values()))
    repeat_max=float(np.abs(values-repeat).max())
    if repeat_max>1e-7:raise ValueError('Canary not deterministic')
    names=list(CANARIES);pairs=[]
    for a,b in PAIRS:
        delta=float(np.abs(values[names.index(a)]-values[names.index(b)]).max())
        differ=tokenizations[a]['input_ids']!=tokenizations[b]['input_ids']
        if not differ or delta<=1e-7:raise ValueError('Chemical distinction lost: '+a+'/'+b)
        pairs.append({'a':a,'b':b,'token_ids_differ':differ,'max_abs_embedding_difference':delta})
    canary={'schema':'chemical-encoder.canary.v1','status':'succeeded','model_identity':identity,
        'pooling':identity['pooling'],'embedding_dim':768,'max_tokens_including_special':768,
        'all_finite':True,'no_unknown_tokens':True,'no_truncation':True,'pairs':pairs,
        'repeat_max_abs_difference':repeat_max,'tokenizations':tokenizations,
        'scope':'Explicit SPEfix-adapted2025 chemical backbone canary; no affinity accuracy claim',
        'runtime':{'torch':str(torch.__version__),'transformers':transformers.__version__,'device':'cpu','dtype':'float32','threads':args.threads}}
    write_json(args.output/'canary.json',canary)
    np.savez_compressed(args.output/'canary-embeddings.npz',embeddings=values,ids=np.asarray(names,dtype='U32'))
    accepted,rejected=[],[]
    for key,smiles in sorted(pure.items()):
        if time.monotonic()-started>=args.max_seconds:raise TimeoutError('Coverage budget exhausted')
        try:
            item=loader.tokenize_full(tokenizer,smiles)
            accepted.append((key,smiles,len(item['input_ids'])))
        except ValueError as error:
            rejected.append({'smiles_sha256':key,'reason':str(error)})
    coverage={'schema':'peptideclm2025.input-coverage.v1','status':'succeeded','input_sha256':args.expected_input_sha256,
        'unique_inputs':len(pure),'accepted':len(accepted),'rejected':rejected,'max_tokens_including_special':768,
        'silent_truncation':False,'smiles_mutated':False,'binding_labels_read':False}
    write_json(args.output/'coverage.json',coverage)
    if args.mode=='canary-coverage':
        write_json(args.output/'result.json',{'status':'succeeded','scope':'safe_load_canary_and_metadata_coverage',
            'model_identity':identity,'unique_inputs':len(pure),'accepted':len(accepted),'rejected':len(rejected),
            'canary_sha256':sha(args.output/'canary.json'),'coverage_sha256':sha(args.output/'coverage.json'),
            'elapsed_seconds':time.monotonic()-started,'formal_fits':0,'full_input_feature_rows':0})
        print(json.dumps({'status':'succeeded','safe_load':True,'canary_passed':True,'accepted':len(accepted),
            'rejected':len(rejected),'elapsed_seconds':time.monotonic()-started}))
        return 0
    if not accepted:raise ValueError('No molecule can be encoded')
    accepted.sort(key=lambda x:(x[2],x[0]));chunks=args.output/'chunks';chunks.mkdir()
    matrices=[];keys=[]
    for offset in range(0,len(accepted),args.batch_size):
        if time.monotonic()-started>=args.max_seconds:raise TimeoutError('Feature budget exhausted; chunks retained')
        batch=accepted[offset:offset+args.batch_size];array=encode([x[1] for x in batch]);ids=np.asarray([x[0] for x in batch],dtype='U64')
        np.savez_compressed(chunks/f'{offset:07d}.npz',embeddings=array,smiles_sha256=ids)
        matrices.append(array);keys.extend(ids.tolist())
        write_json(args.output/'progress.json',{'rows':len(keys),'total':len(accepted),'elapsed_seconds':time.monotonic()-started})
    embeddings=args.output/'embeddings.npz'
    np.savez_compressed(embeddings,embeddings=np.concatenate(matrices),smiles_sha256=np.asarray(keys,dtype='U64'))
    binding={'schema':'chemical-encoder.cache.v1','status':'succeeded','model_identity':identity,
        'embedding_file':str(embeddings.resolve()),'embedding_sha256':sha(embeddings),
        'embedding_key':'embeddings','ids_key':'smiles_sha256','keys_kind':'sha256_raw_smiles',
        'rows':len(keys),'dimensions':768,'dtype':'float32','allow_pickle':False,'pooling':identity['pooling'],
        'no_truncation':True,'chemical_canary_passed':True,'canary_sha256':sha(args.output/'canary.json'),
        'input_csv_sha256':args.expected_input_sha256,'extractor_sha256':sha(__file__),
        'loader_sha256':LOADER_SHA256,'supervised_binding_labels_used':False,'elapsed_seconds':time.monotonic()-started}
    write_json(args.output/'cache-manifest.json',binding)
    write_json(args.output/'result.json',{'status':'succeeded','scope':'frozen_features','rows':len(keys),
        'rejected':len(rejected),'cache_manifest_sha256':sha(args.output/'cache-manifest.json'),'formal_fits':0})
    print(json.dumps({'status':'succeeded','scope':'frozen_features','rows':len(keys),'rejected':len(rejected),
        'elapsed_seconds':time.monotonic()-started}))
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as error:
        print(json.dumps({'status':'failed','error':type(error).__name__+': '+str(error)}),file=sys.stderr)
        raise
