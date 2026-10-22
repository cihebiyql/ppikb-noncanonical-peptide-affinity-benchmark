"""MRBDTA author architecture adapter. No sequence/chemical identity replacement."""
import hashlib
import importlib.util
import json
from pathlib import Path
import torch
from torch.nn.utils.rnn import pad_sequence

HERE = Path(__file__).resolve().parent
METHOD_IDS = ['MRBDTA']
VOCAB = json.loads((HERE/'vocabularies.json').read_text(encoding='utf-8'))
PROTEIN_LIMIT = 1000  # Author main KIBA configuration; not a construct assertion.
SMILES_LIMIT = 5000  # Native positional encoding capacity; never truncate ligand.

def _hash(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def _tokens(text, vocab, name, record_id):
    unknown = [{'offset':i,'token':c} for i,c in enumerate(text) if c not in vocab]
    if unknown:
        raise ValueError(json.dumps({'record_id':record_id,'error':'unknown_token','input':name,'unknown':unknown}))
    return torch.tensor([vocab[c] for c in text], dtype=torch.long)

def encode_record(row, method_id=None):
    if method_id not in (None, 'MRBDTA'):
        raise ValueError(method_id)
    rid = row['record_id']
    # Preserve isomeric stereochemistry, aromatic case, all fragments, and full molecule.
    smiles = row.get('canonical_isomeric_smiles') or row.get('peptide_smiles')
    protein = row.get('target_sequence')
    if not isinstance(smiles, str) or not smiles or not isinstance(protein, str) or not protein:
        raise ValueError(json.dumps({'record_id':rid,'error':'missing_input'}))
    if len(smiles) > SMILES_LIMIT:
        raise ValueError(json.dumps({'record_id':rid,'error':'smiles_exceeds_native_position_capacity','length':len(smiles),'capacity':SMILES_LIMIT}))
    effective = protein[:PROTEIN_LIMIT]
    drug = _tokens(smiles, VOCAB['drug'], 'smiles', rid)
    target = _tokens(effective, VOCAB['target'], 'protein', rid)
    # Validate discarded protein prefix suffix too, so unknown tokens are never silent.
    unknown_full = [{'offset':i,'token':c} for i,c in enumerate(protein) if c not in VOCAB['target']]
    if unknown_full:
        raise ValueError(json.dumps({'record_id':rid,'error':'unknown_full_protein_token','unknown':unknown_full}))
    meta = {'record_id':rid,'smiles_length':len(smiles),'effective_smiles_length':len(smiles),
            'protein_length':len(protein),'effective_protein_length':len(effective),
            'protein_truncated':len(protein)>PROTEIN_LIMIT,'smiles_truncated':False,
            'unknown_smiles_tokens':[],'unknown_protein_tokens':[],
            'smiles_sha256':_hash(smiles),'full_protein_sha256':_hash(protein),
            'effective_protein_sha256':_hash(effective),
            'effective_input_sha256':_hash(smiles+'\0'+effective)}
    return {'drug':drug,'target':target,'y':float(row['pKd']),'metadata':meta}

def collate(items):
    if not items:
        raise ValueError('Empty batch')
    return {'drug':pad_sequence([x['drug'] for x in items],batch_first=True),
            'target':pad_sequence([x['target'] for x in items],batch_first=True),
            'drug_lengths':[len(x['drug']) for x in items],
            'target_lengths':[len(x['target']) for x in items],
            'y':torch.tensor([x['y'] for x in items],dtype=torch.float32),
            'metadata':[x['metadata'] for x in items]}

def build_model(method_id, config):
    if method_id != 'MRBDTA':
        raise ValueError(method_id)
    for key in ('d_model','d_ff','d_k','d_v','n_layers','n_heads'):
        if key in config:
            raise ValueError('Native architecture is frozen; do not tune '+key)
    spec = importlib.util.spec_from_file_location('mrbdta_author_isolated', HERE/'author_model.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.Transformer()

def predict(model, batch, device):
    # Native pooling sums padding queries too. Independent true-length forwards
    # ensure identical input has identical evaluation prediction across batch sizes.
    out = []
    for i,(ld,lt) in enumerate(zip(batch['drug_lengths'],batch['target_lengths'])):
        d = batch['drug'][i:i+1,:ld].to(device)
        t = batch['target'][i:i+1,:lt].to(device)
        pred = model(d,t)[0]
        out.append(pred.reshape(1))
    return torch.cat(out).reshape(-1)

def batch_targets(batch):
    return batch['y'].reshape(-1)
