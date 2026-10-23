"""Independent local cache/sequence/token identity and canary equality check; no forward."""
import hashlib
import json
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
binding=json.loads((HERE/'feature-cache-binding.json').read_text())
directory=HERE/binding['directory'];path=directory/'embeddings.npz'
receipt=json.loads((directory/'receipt.json').read_text())
assert sha(path)==receipt['embedding_sha256']==binding['embedding_sha256']
assert sha(directory/'receipt.json')==binding['receipt_sha256']
sequences=[json.loads(line) for line in (HERE/'inputs/unique-sequences.jsonl').read_text().splitlines()]
tokens=json.loads((directory/'token-checks.json').read_text())
assert len(tokens)==len(sequences)==5159
cache=np.load(path,allow_pickle=False)
assert cache['embeddings'].shape==(5159,320) and cache['embeddings'].dtype==np.float32
assert np.isfinite(cache['embeddings']).all()
assert list(cache['sequence_ids'])==[r['sequence_id'] for r in sequences]
for sequence,token in zip(sequences,tokens):
    assert sequence['sequence_id']==token['sequence_id']
    assert len(sequence['sequence'])==sequence['length']==token['residues']
    assert token['tokens']==sequence['length']+2
    assert hashlib.sha256(sequence['sequence'].encode('ascii')).hexdigest()==sequence['sequence_id']
canary_path=ROOT/'runs/plm-simple-v1/feature-canary-cpu-v3/embeddings.npz'
canary=np.load(canary_path,allow_pickle=False)
lookup={key:i for i,key in enumerate(cache['sequence_ids'])}
maximum=0.
for i,key in enumerate(canary['sequence_ids']):
    error=float(np.max(np.abs(cache['embeddings'][lookup[key]]-canary['embeddings'][i])))
    assert error==0.;maximum=max(maximum,error)
report={'passed':True,'sequence_token_identity_checks':len(tokens),'shape':[5159,320],
        'exact_repeated_canary_vectors':len(canary['sequence_ids']),'max_canary_abs_difference':maximum,
        'embedding_sha256':sha(path),'canary_sha256':sha(canary_path),'device':'cpu','new_fit_count':0,
        'new_forward_count':0,'test_labels_opened':0,'code_sha256':sha(__file__)}
(HERE/'independent-local-cache-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(report))
