"""Independent frozen fair-esm extraction; no labels, fitting, contact prediction or truncation."""
import argparse
import hashlib
import json
import os
import platform
import time
from pathlib import Path

import numpy as np
import torch
import esm

AA = frozenset('ACDEFGHIKLMNPQRSTVWY')

def sha(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda:stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()

def write(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False),encoding='utf-8')

def mean_residue_pool(representation, length):
    # Exactly the original residues; BOS/EOS/padding are not averaged.
    return representation[1:length+1].mean(0)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--contract',required=True,type=Path)
    parser.add_argument('--canary',action='store_true')
    args = parser.parse_args()
    contract = json.loads(args.contract.read_text())
    for item in contract['input_hashes']:
        assert sha(item['path']) == item['sha256'], item['path']
    assert contract['model_name'] == 'esm2_t6_8M_UR50D'
    assert contract['representation_layer'] == 6
    device = contract['device']
    if device.startswith('cuda'):
        assert torch.cuda.is_available()
    torch.set_num_threads(2)
    torch.manual_seed(0)
    if device.startswith('cuda'):
        torch.cuda.manual_seed_all(0)
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
    torch.use_deterministic_algorithms(True)
    records = [json.loads(line) for line in Path(contract['sequence_manifest']).read_text().splitlines()]
    for item in records:
        seq = item['sequence']
        assert seq and set(seq)<=AA and len(seq)<=contract['max_residues_compute_budget']
        assert hashlib.sha256(seq.encode('ascii')).hexdigest() == item['sequence_id']
    if args.canary:
        indexes = sorted(set([0,min(range(len(records)),key=lambda i:records[i]['length']),
                              max(range(len(records)),key=lambda i:records[i]['length'])]))
        records = [records[i] for i in indexes]
    output = Path(contract['output_canary'] if args.canary else contract['output'])
    output.mkdir(parents=True,exist_ok=False)
    started = time.time()
    # Official hash-verified pickles only. Explicit false handles Torch2.6's changed
    # default without a global environment override or mutation of fair-esm.
    model_data = torch.load(contract['model_path'],map_location='cpu',weights_only=False)
    regression_data = torch.load(contract['regression_path'],map_location='cpu',weights_only=False)
    model, alphabet = esm.pretrained.load_model_and_alphabet_core(
        contract['model_name'],model_data,regression_data)
    assert model.num_layers == 6 and model.embed_dim == 320
    model.eval().requires_grad_(False).to(device)
    assert not model.training and not any(p.requires_grad for p in model.parameters())
    converter = alphabet.get_batch_converter(truncation_seq_length=None)
    vectors = []
    token_checks = []
    with torch.inference_mode():
        for index,item in enumerate(records):
            seq = item['sequence']
            _,_,tokens = converter([(item['sequence_id'], seq)])
            assert tokens.shape == (1,len(seq)+2)
            assert int(tokens[0,0]) == alphabet.cls_idx
            assert int(tokens[0,-1]) == alphabet.eos_idx
            assert all(int(t)==alphabet.get_idx(aa) for t,aa in zip(tokens[0,1:-1],seq))
            result = model(tokens.to(device), repr_layers=[6], return_contacts=False)
            value = mean_residue_pool(result['representations'][6][0],len(seq)).cpu().numpy()
            assert value.shape==(320,) and np.isfinite(value).all()
            vectors.append(value)
            token_checks.append({'sequence_id':item['sequence_id'],'residues':len(seq),'tokens':tokens.shape[1]})
            if (index+1)%128==0:
                np.savez_compressed(output/f'partial-{index+1:05d}.npz',
                    embeddings=np.asarray(vectors,dtype=np.float32),
                    sequence_ids=np.asarray([r['sequence_id'] for r in records[:index+1]],dtype=str))
                print(json.dumps({'completed':index+1,'total':len(records),'elapsed_seconds':time.time()-started}),flush=True)
    target = output/'embeddings.npz'
    np.savez_compressed(target,embeddings=np.asarray(vectors,dtype=np.float32),
                        sequence_ids=np.asarray([r['sequence_id'] for r in records],dtype=str))
    write(output/'token-checks.json',token_checks)
    files = {}
    for module in (esm,esm.pretrained):
        files[str(module.__file__)] = sha(module.__file__)
    import esm.model.esm2 as architecture
    files[str(architecture.__file__)] = sha(architecture.__file__)
    receipt = {'status':'succeeded','canary':args.canary,'fit_count':0,'label_files_opened':0,
        'sequence_count':len(records),'shape':[len(vectors),320],'frozen_parameter_count':sum(p.numel() for p in model.parameters()),
        'torch':torch.__version__,'esm_version':getattr(esm,'__version__',None),'esm_source_hashes':files,
        'python':platform.python_version(),'pid':os.getpid(),'pgid':os.getpgid(0),
        'device':device,'model_sha256':sha(contract['model_path']),'contract_sha256':sha(args.contract),
        'embedding_sha256':sha(target),'elapsed_seconds':time.time()-started,
        'max_residues':max(r['length'] for r in records),'no_truncation':True,'chemical_identity_encoded':False,
        'layer':6,'pooling':'mean exact residue positions1..L; excludes BOS/EOS/pad',
        'max_gpu_allocated_bytes':torch.cuda.max_memory_allocated() if device.startswith('cuda') else 0}
    write(output/'receipt.json',receipt)
    print(json.dumps(receipt),flush=True)

if __name__=='__main__':
    main()
