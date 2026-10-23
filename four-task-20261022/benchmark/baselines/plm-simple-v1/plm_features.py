"""Frozen sequence-only embeddings; chemical annotations remain evaluation metadata."""
import hashlib
import json
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
FEATURE_VERSION = 'frozen-official-esm2-t6-8M-layer6-mean-raw20-v1'
_CACHE = None

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def load_cache():
    global _CACHE
    if _CACHE is None:
        binding = json.loads((HERE/'feature-cache-binding.json').read_text())
        directory = HERE/binding['directory']
        path = directory/'embeddings.npz'
        receipt_path = directory/'receipt.json'
        receipt = json.loads(receipt_path.read_text())
        assert receipt['status']=='succeeded' and not receipt['canary']
        assert sha(path)==receipt['embedding_sha256']
        assert sha(path)==binding['embedding_sha256']
        assert sha(receipt_path)==binding['receipt_sha256']
        obj = np.load(path,allow_pickle=False)
        values,ids = obj['embeddings'],obj['sequence_ids']
        assert values.shape == (len(ids),320) and np.isfinite(values).all()
        assert len(set(ids))==len(ids)
        _CACHE = ({key:values[i] for i,key in enumerate(ids)},sha(path),sha(receipt_path),receipt)
    return _CACHE

def build_features(frame,task):
    cache,cache_sha,receipt_sha,receipt = load_cache()
    def vector(sequence):
        assert sequence and set(sequence)<=set('ACDEFGHIKLMNPQRSTVWY')
        return cache[hashlib.sha256(sequence.encode('ascii')).hexdigest()]
    values=[]
    for _,row in frame.iterrows():
        target = vector(row['embedding_target'])
        if task=='effect':
            wild,mut = vector(row['embedding_peptide_wt']),vector(row['embedding_peptide_mut'])
            values.append(np.concatenate([wild,mut-wild,target]))
        else:
            values.append(np.concatenate([vector(row['embedding_peptide']),target]))
    matrix=np.asarray(values,dtype=np.float32)
    assert np.isfinite(matrix).all()
    return matrix, {'version':FEATURE_VERSION,'shape':list(matrix.shape),
        'embedding_cache_sha256':cache_sha,'embedding_receipt_sha256':receipt_sha,
        'model_sha256':receipt['model_sha256'],'fit_count':0,'chemical_identity_encoded':False,
        'effect_representation':'WT peptide, mutant-WT peptide, identical target' if task=='effect' else None,
        'coordinates_or_labels_used_for_features':False,'normalization_or_truncation':False}
