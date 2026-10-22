"""CPU bounded chemical and short-peptide dependency construction; never reads labels."""
import os,resource,signal,json,time,hashlib,socket
from pathlib import Path
resource.setrlimit(resource.RLIMIT_CPU,(300,300));resource.setrlimit(resource.RLIMIT_AS,(3*1024**3,3*1024**3))
os.sched_setaffinity(0,{min(os.sched_getaffinity(0))});os.nice(19)
signal.alarm(330)
from rdkit import Chem,DataStructs,rdBase
from rdkit.Chem import rdFingerprintGenerator
P=Path(__file__).resolve().parent
rows=list(map(json.loads,(P/'label-free-grouping-input.jsonl').open()))
start=time.time();fg=rdFingerprintGenerator.GetMorganGenerator(radius=2,fpSize=2048,includeChirality=False)
graphs={};mapping=[]
for r in rows:
 sm=r['peptide_smiles']
 if sm not in graphs:
  m=Chem.MolFromSmiles(sm);assert m is not None
  iso=Chem.MolToSmiles(m,canonical=True,isomericSmiles=True)
  ach=Chem.MolToSmiles(m,canonical=True,isomericSmiles=False)
  graphs[sm]=(iso,ach,fg.GetFingerprint(m))
 iso,ach,_=graphs[sm]
 mapping.append({'record_id':r['record_id'],'chemical_entity_id':hashlib.sha256(iso.encode()).hexdigest(),'achiral_entity_id':hashlib.sha256(ach.encode()).hexdigest(),'canonical_isomeric_smiles':iso})
byiso={}
for iso,ach,fp in graphs.values():byiso[iso]=(ach,fp)
isos=sorted(byiso);fps=[byiso[k][1] for k in isos]
edges=0
with (P/'chemical-neighbor-edges.jsonl').open('w') as f:
 for i in range(len(isos)):
  similarities=DataStructs.BulkTanimotoSimilarity(fps[i],fps[:i])
  for j,s in enumerate(similarities):
   if s>=.8:
    f.write(json.dumps({'a':hashlib.sha256(isos[i].encode()).hexdigest(),'b':hashlib.sha256(isos[j].encode()).hexdigest(),'tanimoto':s})+'\n');edges+=1
with (P/'chemical-entity-mapping.jsonl').open('w') as f:
 for r in mapping:f.write(json.dumps(r)+'\n')
(P/'chemical-runtime-receipt.json').write_text(json.dumps({'host':socket.gethostname(),'rdkit_version':rdBase.rdkitVersion,'rows':len(rows),'unique_canonical_isomeric_graphs':len(isos),'chemical_neighbor_edges':edges,'threshold':.8,'fingerprint':'Morgan radius2 2048bits achiral','labels_read':False,'gpu_used':False,'seconds':time.time()-start,'input_sha256':hashlib.sha256((P/'label-free-grouping-input.jsonl').read_bytes()).hexdigest(),'niceness':os.nice(0),'cpu_affinity':list(os.sched_getaffinity(0))},indent=2))
print((P/'chemical-runtime-receipt.json').read_text())
