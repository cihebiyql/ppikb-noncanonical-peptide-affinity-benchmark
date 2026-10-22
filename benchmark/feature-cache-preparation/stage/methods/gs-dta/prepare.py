import ast,hashlib,json,shutil
from pathlib import Path
P=Path(__file__).resolve().parent;project=P.parents[1]
src=project/'model-audit/author-source/zhuziguang__GS-DTA/source'
model=src/'Models/gatv2_gcn.py';helper=src/'create_data.py'
shutil.copyfile(model,P/'author_model.py')
tree=ast.parse(helper.read_text(encoding='utf-8'))
functions={'atom_features','one_of_k_encoding','one_of_k_encoding_unk','smile_to_graph','seq_cat'}
nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in functions]
out='import numpy as np\nfrom rdkit import Chem\nimport networkx as nx\n\n'+'\n\n'.join(ast.unparse(n) for n in nodes)+'\n\nseq_voc="ABCDEFGHIKLMNOPQRSTUVWXYZ"\nseq_dict={v:i+1 for i,v in enumerate(seq_voc)}\nmax_seq_len=1000\n'
(P/'author_features.py').write_text(out,encoding='utf-8')
assert len(nodes)==5
sample=project/'execution/canary-staging-v1/train-only-32.jsonl'
assert hashlib.sha256(sample.read_bytes()).hexdigest()=='1562172160338140f24cf3de9e2e46c6c14d5e305627caec9e37ceaacb8a8333'
shutil.copyfile(sample,P/'train-only-32.jsonl')
(P/'author-compatibility.patch').write_text('',encoding='utf-8')
manifest={'paper_doi':'10.1186/s12864-025-11234-4','commit':'a36750c0c2567b5b4c3f9b3aed64eac5c40a3d3c',
 'model_source_path':str(model),'model_source_sha256':hashlib.sha256(model.read_bytes()).hexdigest(),
 'adapted_model_sha256':hashlib.sha256((P/'author_model.py').read_bytes()).hexdigest(),
 'model_patch':'none: author model copied byte-for-byte; empty unifieddiff intentional',
 'preprocessor_source_sha256':hashlib.sha256(helper.read_bytes()).hexdigest(),
 'preprocessor_extraction':'AST copy five author functions plus exact author alphabet/limit; excludes top-level dataset IO',
 'preprocessor_functions':sorted(functions),'architecture':'unchanged author defaults; CNN1000 channels, BiLSTM2, Transformer2x4heads',
 'paper_pdf_sha256':'725e257cf378b2959afc34dd8b65d8c29787af6330c1d9fee3b464fd0a0619e3',
 'train_sample_sha256':hashlib.sha256(sample.read_bytes()).hexdigest()}
(P/'source-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps(manifest))
