import hashlib,importlib.util,math
from pathlib import Path
import numpy as np
import torch
from rdkit import Chem
from torch_geometric.data import Batch,Data
P=Path(__file__).resolve().parent
METHOD_IDS=['GS-DTA']
def _load(name,filename):
 spec=importlib.util.spec_from_file_location(name,P/filename);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
_author=_load('gs_dta_author','author_model.py')
_features=_load('gs_dta_features','author_features.py')
def _sha(s):return hashlib.sha256(s.encode()).hexdigest()
def encode_record(row,method_id=None):
 if method_id not in (None,'GS-DTA'):raise ValueError(method_id)
 s=row.get('canonical_isomeric_smiles') or row.get('peptide_smiles');t=row.get('target_sequence');rid=row['record_id']
 if not isinstance(s,str) or not s or not isinstance(t,str) or not t:raise ValueError(rid+': missing input')
 y=float(row['pKd'])
 if not math.isfinite(y):raise ValueError(rid+': nonfinite target')
 unknown=sorted(set(t)-set(_features.seq_voc))
 if unknown:raise ValueError(rid+': unknown protein tokens '+repr(unknown))
 mol=Chem.MolFromSmiles(s)
 if mol is None or not mol.GetNumAtoms():raise ValueError(rid+': invalid molecular graph')
 n,x,e=_features.smile_to_graph(s);x=np.asarray(x,dtype=np.float32);e=np.asarray(e,dtype=np.int64).reshape(-1,2).T.copy();target=_features.seq_cat(t).astype(np.int64)
 assert x.shape==(n,78) and n==mol.GetNumAtoms() and target.shape==(1000,) and np.isfinite(x).all()
 graphhash=hashlib.sha256(x.tobytes()+e.tobytes()).hexdigest();fullhash=_sha(t);effhash=_sha(t[:1000]);inputhash=hashlib.sha256(x.tobytes()+e.tobytes()+target.tobytes()).hexdigest()
 audit={'record_id':rid,'target_original_length':len(t),'target_effective_length':min(len(t),1000),'target_truncated':len(t)>1000,
  'target_full_sha256':fullhash,'target_effective_sha256':effhash,'target_encoded_sha256':hashlib.sha256(target.tobytes()).hexdigest(),
  'smiles_sha256':_sha(s),'molecule_atoms_original':n,'molecule_atoms_effective':n,'molecule_truncated':False,'directed_edges':e.shape[1],
  'graph_feature_sha256':graphhash,'effective_input_sha256':inputhash,'atom_chirality_encoded':False,'bond_order_encoded':False,'bond_stereo_encoded':False}
 return {'record_id':rid,'x':x,'edge_index':e,'target':target,'y':np.float32(y),'audit':audit}
def collate(items):
 if not items:raise ValueError('empty batch')
 return Batch.from_data_list([Data(x=torch.as_tensor(i['x']),edge_index=torch.as_tensor(i['edge_index']),target=torch.as_tensor(i['target']).reshape(1,1000),y=torch.as_tensor([i['y']]),record_id=i['record_id']) for i in items])
def build_model(method_id,config=None):
 if method_id!='GS-DTA':raise ValueError(method_id)
 if config and any(k in config for k in ['n_output','num_features_xd','num_features_xt','n_filters','embed_dim','output_dim','nhead','transformer_layers']):raise ValueError('author architecture dimensions frozen')
 model=_author.GATv2_GCN_CNN_BiLSTM_Transformer();model.method_id=method_id;return model
def predict(model,batch,device):return model(batch.to(device)).reshape(-1)
def batch_targets(batch):return batch.y.reshape(-1)
