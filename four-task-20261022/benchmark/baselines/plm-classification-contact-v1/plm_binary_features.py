"""Sequence-only frozen means or target-residue+partner-mean; labels/geometry never enter X."""
import hashlib
import json
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
FEATURE_VERSION='frozen-esm2-t6-layer6-raw20-pairmean-or-targetresidue-partnermean-v1'
_CACHE=None
_RESIDUES={}
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def seqid(sequence):return hashlib.sha256(sequence.encode('ascii')).hexdigest()
def load_cache():
    global _CACHE
    if _CACHE is None:
        binding_path=HERE/'feature-cache-binding.json';binding=json.loads(binding_path.read_text(encoding='utf-8'))
        path=ROOT/binding['mean_relative_path'];assert sha(path)==binding['mean_sha256']
        data=np.load(path,allow_pickle=False);values,ids=data['embeddings'],data['sequence_ids']
        assert values.shape==(len(ids),320) and values.dtype==np.float32 and np.isfinite(values).all()
        proof_path=HERE/'inputs/contact-sequence-index-proof.json';assert sha(proof_path)==binding['contact_proof_sha256']
        proof={r['row_id']:r for r in json.loads(proof_path.read_text(encoding='utf-8'))}
        _CACHE=(binding,{key:values[index] for index,key in enumerate(ids)},proof,sha(binding_path))
    return _CACHE
def residue_cache(key,sequence,binding):
    if key not in _RESIDUES:
        source=binding['residue_sources'][key];path=ROOT/source['relative_path'];assert sha(path)==source['sha256']
        obj=np.load(path,allow_pickle=False);values=obj['residues']
        assert str(obj['sequence'].item())==sequence and str(obj['sequence_id'].item())==key
        assert values.shape==(len(sequence),320) and values.dtype==np.float32
        np.testing.assert_array_equal(obj['positions1'],np.arange(1,len(sequence)+1))
        assert np.isfinite(values).all();_RESIDUES[key]=values
    return _RESIDUES[key]
def build_features(frame,task):
    binding,means,proof,binding_sha=load_cache();vectors=[];contact='contact' in task or 'site' in task
    for row in frame.to_dict('records'):
        peptide,target=row['embedding_peptide'],row['embedding_target']
        assert peptide and target and set(peptide+target)<=set('ACDEFGHIKLMNPQRSTVWY')
        peptide_key,target_key=seqid(peptide),seqid(target)
        if contact:
            index=int(row['residue_index']);mapping=proof[row['row_id']]
            assert str(row['sequence_index_mapping_verified']).lower()=='true'
            assert mapping['target_sequence_id']==target_key and mapping['peptide_sequence_id']==peptide_key
            assert index==mapping['residue_index1'] and 1<=index<=len(target)
            assert target[index-1]==row['target_residue_aa']==mapping['target_residue_aa']
            residue=residue_cache(target_key,target,binding)[index-1]
            vectors.append(np.concatenate([residue,means[peptide_key]]))
        else:vectors.append(np.concatenate([means[peptide_key],means[target_key]]))
    x=np.asarray(vectors,dtype=np.float32);assert x.shape==(len(frame),640) and np.isfinite(x).all()
    return x,{'version':FEATURE_VERSION,'shape':list(x.shape),'model_sha256':binding['model_sha256'],
        'cache_binding_sha256':binding_sha,'contact_index_proofs_checked':len(frame) if contact else 0,
        'target_residue_and_peptide_mean_only':contact,'label_or_geometry_used':False,
        'coordinates_or_labels_used_for_features':False,'observed_region_mask_used':False,'chemical_identity_encoded':False}
