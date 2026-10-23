"""Frozen ESM2 means/residues for an explicitly unlabeled missing-representation shard."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import time
import traceback
import numpy as np
import torch
import esm

AA=frozenset('ACDEFGHIKLMNPQRSTVWY')
def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(1024**2),b''):h.update(block)
    return h.hexdigest()
def write(path,obj):Path(path).write_text(json.dumps(obj,indent=2,allow_nan=False),encoding='utf-8')
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--contract',type=Path,required=True)
    parser.add_argument('--chunk',type=int);parser.add_argument('--canary',action='store_true')
    args=parser.parse_args();c=json.loads(args.contract.read_text())
    assert os.environ.get('CUDA_VISIBLE_DEVICES','')=='' and c['device']=='cpu'
    for item in c['input_hashes']:assert sha(item['path'])==item['sha256'],item['path']
    all_jobs=[json.loads(line) for line in Path(c['sequence_manifest']).read_text().splitlines()]
    if args.canary:
        chosen=sorted(set([0,min(range(len(all_jobs)),key=lambda i:all_jobs[i]['length']),max(range(len(all_jobs)),key=lambda i:all_jobs[i]['length'])]))
        jobs=[all_jobs[i] for i in chosen];output=Path(c['output_root'])/'feature-canary-v1'
    else:
        assert args.chunk is not None and args.chunk>=0
        start=args.chunk*c['chunk_size'];jobs=all_jobs[start:start+c['chunk_size']]
        assert jobs;output=Path(c['output_root'])/'feature-chunks'/f'chunk-{args.chunk:03d}'
    output.mkdir(parents=True,exist_ok=False)
    started=time.time();torch.set_num_threads(c['math_threads']);torch.manual_seed(0)
    torch.use_deterministic_algorithms(True)
    model_data=torch.load(c['model_path'],map_location='cpu',weights_only=False)
    regression_data=torch.load(c['regression_path'],map_location='cpu',weights_only=False)
    model,alphabet=esm.pretrained.load_model_and_alphabet_core(c['model_name'],model_data,regression_data)
    model.eval().requires_grad_(False)
    assert model.num_layers==6 and model.embed_dim==320
    assert not model.training and not any(p.requires_grad for p in model.parameters())
    assert all(p.dtype==torch.float32 for p in model.parameters())
    converter=alphabet.get_batch_converter(truncation_seq_length=None)
    means=[];mean_ids=[];checks=[];residue_files=[]
    try:
        with torch.inference_mode():
            for number,job in enumerate(jobs):
                sequence=job['sequence'];key=job['sequence_id'];length=len(sequence)
                assert sequence and set(sequence)<=AA and length<=2048
                assert hashlib.sha256(sequence.encode('ascii')).hexdigest()==key
                assert job['need_mean'] or job['need_residue']
                _,_,tokens=converter([(key,sequence)])
                assert tokens.shape==(1,length+2)
                assert int(tokens[0,0])==alphabet.cls_idx and int(tokens[0,-1])==alphabet.eos_idx
                assert all(int(t)==alphabet.get_idx(aa) for t,aa in zip(tokens[0,1:-1],sequence))
                result=model(tokens,repr_layers=[6],return_contacts=False)
                representation=result['representations'][6][0,1:length+1]
                assert representation.shape==(length,320) and torch.isfinite(representation).all()
                if job['need_mean']:
                    mean=representation.mean(0).numpy();assert mean.shape==(320,) and np.isfinite(mean).all()
                    means.append(mean);mean_ids.append(key)
                if job['need_residue']:
                    path=output/('residues-'+key+'.npz')
                    np.savez_compressed(path,residues=representation.numpy(),sequence=np.asarray(sequence),
                        sequence_id=np.asarray(key),positions1=np.arange(1,length+1,dtype=np.int32))
                    residue_files.append({'sequence_id':key,'path':str(path),'sha256':sha(path),'length':length})
                checks.append({'sequence_id':key,'length':length,'tokens':length+2,
                    'mean_extracted':bool(job['need_mean']),'residues_extracted':bool(job['need_residue'])})
                if (number+1)%128==0:
                    np.savez_compressed(output/f'partial-means-{number+1:04d}.npz',
                        means=np.asarray(means,dtype=np.float32).reshape(-1,320),sequence_ids=np.asarray(mean_ids,dtype=str))
                    print(json.dumps({'completed':number+1,'chunk_jobs':len(jobs),'elapsed_seconds':time.time()-started}),flush=True)
        path=output/'means.npz'
        np.savez_compressed(path,means=np.asarray(means,dtype=np.float32).reshape(-1,320),sequence_ids=np.asarray(mean_ids,dtype=str))
        write(output/'token-and-representation-checks.json',checks)
        receipt={'status':'succeeded','canary':args.canary,'chunk':args.chunk,'forward_calls':len(jobs),
            'mean_count':len(mean_ids),'residue_sequences':residue_files,'means_sha256':sha(path),
            'contract_sha256':sha(args.contract),'model_sha256':sha(c['model_path']),'code_sha256':sha(__file__),
            'model_name':c['model_name'],'num_layers':6,'dimension':320,'parameter_count':sum(p.numel() for p in model.parameters()),
            'dtype':'float32','all_parameters_frozen':True,'eval':True,'inference_mode':True,'math_threads':c['math_threads'],
            'pooling':'representation[1:L+1].mean(0); excludes BOS/EOS/pad','residue_position':'representation[1:L+1][index1-1]',
            'label_or_coordinate_files_opened':0,'no_normalization_or_truncation':True,'device':'cpu','gpu_used':False,
            'torch':torch.__version__,'esm':getattr(esm,'__version__',None),'python':platform.python_version(),
            'pid':os.getpid(),'pgid':os.getpgid(0),'elapsed_seconds':time.time()-started,
            'max_sequence_length':max(len(r['sequence']) for r in jobs)}
        write(output/'receipt.json',receipt);print(json.dumps(receipt),flush=True)
    except BaseException as exc:
        write(output/'failed-receipt.json',{'status':'failed','error':repr(exc),'traceback':traceback.format_exc(),
            'completed_jobs':checks,'contract_sha256':sha(args.contract),'elapsed_seconds':time.time()-started})
        raise
if __name__=='__main__':main()
