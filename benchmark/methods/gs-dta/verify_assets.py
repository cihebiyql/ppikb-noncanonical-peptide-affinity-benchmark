import ast,hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent;project=P.parents[1]
source=project/'model-audit/author-source/zhuziguang__GS-DTA/source'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
original=ast.parse((source/'create_data.py').read_text(encoding='utf-8'))
derived=ast.parse((P/'author_features.py').read_text(encoding='utf-8'))
names=['atom_features','one_of_k_encoding','one_of_k_encoding_unk','smile_to_graph','seq_cat']
comparisons={}
for name in names:
 a=next(x for x in original.body if isinstance(x,ast.FunctionDef) and x.name==name)
 b=next(x for x in derived.body if isinstance(x,ast.FunctionDef) and x.name==name)
 comparisons[name]=ast.dump(a,include_attributes=False)==ast.dump(b,include_attributes=False)
assert all(comparisons.values())
assert sha(source/'Models/gatv2_gcn.py')==sha(P/'author_model.py')
assert sha(project/'model-audit/replacement-gs-dta/GS-DTA-published.pdf')=='725e257cf378b2959afc34dd8b65d8c29787af6330c1d9fee3b464fd0a0619e3'
for mode in ['cpu','gpu']:
 d=P/('canary-'+mode+'-v1');c=json.loads((d/'contract.json').read_text());r=json.loads((d/'result.json').read_text());w=json.loads((d/'watchdog-receipt.json').read_text())
 assert r['status']==w['status']=='passed' and w['process_exited']
 assert sha(d/'contract.json')==r['contract_sha256']==w['contract_sha256']
 for name,value in c['source_files_sha256'].items():assert sha(P/name)==value
 for name,v in w['outputs'].items():assert sha(d/name)==v['sha256']
assert sha(P/'cpu-input-audit.jsonl')==sha(P/'gpu-input-audit.jsonl')
files={str(p.relative_to(P)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in P.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='asset-verification.json'}
result={'status':'passed','author_model_exact_copy':True,'five_feature_functions_AST_identical':comparisons,'CPU_GPU_inputs_identical':True,
 'current_canary_code_hashes_match':True,'PDF_original_sha_verified':True,'source_and_receipt_file_manifest':files}
(P/'asset-verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps({'status':'passed','manifest_files':len(files),'AST_function_count':len(comparisons)}))
