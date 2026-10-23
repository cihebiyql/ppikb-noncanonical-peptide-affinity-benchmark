"""Validate the completed CPU cache before binding it to any trainable head."""
import hashlib
import json
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

contract=HERE/'extraction-contract.cpu-revision3.json';c=json.loads(contract.read_text())
directory=HERE/'feature-cache-cpu-v3';receipt=directory/'receipt.json';r=json.loads(receipt.read_text())
assert r['status']=='succeeded' and not r['canary'] and r['device']=='cpu'
assert r['sequence_count']==5159 and r['contract_sha256']==sha(contract)
assert r['model_sha256']==c['model_sha256'] and r['no_truncation']
sequences=[json.loads(line) for line in Path(c['sequence_manifest']).read_text().splitlines()]
path=directory/'embeddings.npz';assert sha(path)==r['embedding_sha256']
values=np.load(path,allow_pickle=False)
assert values['embeddings'].shape==(5159,320) and values['embeddings'].dtype==np.float32
assert np.isfinite(values['embeddings']).all()
assert list(values['sequence_ids'])==[row['sequence_id'] for row in sequences]
token_checks=json.loads((directory/'token-checks.json').read_text())
assert len(token_checks)==5159 and all(row['tokens']==row['residues']+2 for row in token_checks)
binding={'schema':'frozen-esm2.embedding-cache-binding.v1','directory':directory.name,
    'embedding_sha256':sha(path),'receipt_sha256':sha(receipt),'device':'cpu',
    'extraction_contract_sha256':sha(contract),'shape':[5159,320],'dtype':'float32',
    'source_order_and_token_counts_verified':True,'head_fit_count_at_binding':0,
    'chemical_identity_encoded':False,'no_truncation':True,'gpu_used':False}
target=HERE/'feature-cache-binding.json';assert not target.exists()
target.write_text(json.dumps(binding,indent=2),encoding='utf-8');print(json.dumps(binding))
