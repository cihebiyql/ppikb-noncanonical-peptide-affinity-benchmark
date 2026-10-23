"""Combine hash-verified old means and only new frozen representations; no model calls or labels."""
import hashlib
import json
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
RUN=ROOT/'runs/plm-classification-contact-v1'
OLD=ROOT/'baselines/plm-simple-v1/feature-cache-cpu-v3'
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024**2),b''):h.update(b)
    return h.hexdigest()
def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def write(path,obj):Path(path).write_text(json.dumps(obj,indent=2,allow_nan=False),encoding='utf-8')

def main():
    status=load(RUN/'feature-queue-status.json');assert status['status']=='features_complete'
    c=load(HERE/'feature-contract.json');coverage=load(HERE/'coverage-manifest.json')
    expected=[json.loads(line) for line in (HERE/'inputs/requested-mean-sequences.jsonl').read_text(encoding='utf-8').splitlines()]
    jobs=[json.loads(line) for line in (HERE/'inputs/missing-representations.jsonl').read_text(encoding='utf-8').splitlines()]
    residue_expected={r['sequence_id']:r['sequence'] for r in jobs if r['need_residue']}
    reused=load(HERE/'inputs/old-cache-reuse.json');old_path=OLD/'embeddings.npz'
    assert sha(old_path)==reused['old_cache_sha256']==coverage['old_cache_sha256']
    old=np.load(old_path,allow_pickle=False);old_values,old_ids=old['embeddings'],old['sequence_ids']
    means={};sources=[];residues={}
    for item in reused['vectors']:
        key=item['sequence_id'];index=item['source_row_index'];assert old_ids[index]==key
        value=old_values[index];assert hashlib.sha256(value.tobytes()).hexdigest()==item['source_vector_sha256']
        means[key]=value
        sources.append({'sequence_id':key,'kind':'old_mean_exact_bytes','source_relative':old_path.relative_to(ROOT).as_posix(),
            'source_index':index,'vector_sha256':item['source_vector_sha256']})
    for chunk in range(status['chunk_count']):
        directory=RUN/'feature-chunks'/f'chunk-{chunk:03d}';receipt=load(directory/'receipt.json')
        assert receipt['status']=='succeeded' and not receipt['canary']
        assert receipt['contract_sha256']==sha(HERE/'feature-contract.json') and receipt['model_sha256']==c['model_sha256']
        path=directory/'means.npz';assert sha(path)==receipt['means_sha256']
        archive=np.load(path,allow_pickle=False);values,ids=archive['means'],archive['sequence_ids']
        assert values.shape==(len(ids),320) and values.dtype==np.float32 and np.isfinite(values).all()
        for index,key in enumerate(ids):
            assert key not in means;means[str(key)]=values[index].copy()
            sources.append({'sequence_id':str(key),'kind':'new_chunk_mean','source_relative':path.relative_to(ROOT).as_posix(),
                'source_index':index,'vector_sha256':hashlib.sha256(values[index].tobytes()).hexdigest()})
        for item in receipt['residue_sequences']:
            key=item['sequence_id'];assert key not in residues and key in residue_expected
            path=ROOT/'runs/plm-classification-contact-v1/feature-chunks'/f'chunk-{chunk:03d}'/('residues-'+key+'.npz')
            assert sha(path)==item['sha256'];archive=np.load(path,allow_pickle=False)
            sequence=str(archive['sequence'].item());assert sequence==residue_expected[key]
            assert str(archive['sequence_id'].item())==key
            assert hashlib.sha256(sequence.encode('ascii')).hexdigest()==key
            assert archive['residues'].shape==(len(sequence),320) and archive['residues'].dtype==np.float32
            assert np.isfinite(archive['residues']).all()
            np.testing.assert_array_equal(archive['positions1'],np.arange(1,len(sequence)+1))
            residues[key]={'relative_path':path.relative_to(ROOT).as_posix(),'sha256':sha(path),'length':len(sequence)}
    assert set(means)=={r['sequence_id'] for r in expected}
    assert set(residues)==set(residue_expected)
    destination=HERE/'feature-cache';destination.mkdir(exist_ok=False)
    target=destination/'means.npz';keys=[r['sequence_id'] for r in expected]
    matrix=np.asarray([means[key] for key in keys],dtype=np.float32)
    assert matrix.shape==(25912,320) and np.isfinite(matrix).all()
    np.savez_compressed(target,embeddings=matrix,sequence_ids=np.asarray(keys,dtype=str))
    source_path=destination/'mean-vector-sources.json';write(source_path,sources)
    proof_path=HERE/'inputs/contact-sequence-index-proof.json';proof=load(proof_path)
    for row in proof:
        assert row['target_sequence_id'] in residues and row['peptide_sequence_id'] in means
        assert 1<=row['residue_index1']<=residues[row['target_sequence_id']]['length']
        assert row['target_residue_aa']==row['observed_chain_residue_aa'] and row['sequence_index_AA_equal']
    binding={'schema':'frozen-esm2.classification-contact.cache-binding.v1','mean_relative_path':target.relative_to(ROOT).as_posix(),
        'mean_sha256':sha(target),'mean_count':len(means),'mean_shape':[len(means),320],
        'old_mean_reused_exact_bytes':len(reused['vectors']),'new_mean_count':len(means)-len(reused['vectors']),
        'mean_vector_sources_relative_path':source_path.relative_to(ROOT).as_posix(),'mean_vector_sources_sha256':sha(source_path),
        'residue_sources':residues,'residue_sequence_count':len(residues),'contact_proof_sha256':sha(proof_path),
        'contact_proof_rows':len(proof),'feature_contract_sha256':sha(HERE/'feature-contract.json'),
        'model_sha256':c['model_sha256'],'code_sha256':sha(__file__),'dtype':'float32','device':'cpu',
        'new_model_forward_count':0,'new_fit_count':0,'label_or_coordinate_files_opened':0,
        'chemical_identity_encoded':False,'original_cache_modified':False}
    write(HERE/'feature-cache-binding.json',binding)
    print(json.dumps({k:v for k,v in binding.items() if k!='residue_sources'}))
if __name__=='__main__':main()
