"""Compare label-free externally certified molecular format conversions only."""
import json,os,hashlib,time,socket,signal,resource
from pathlib import Path
from rdkit import Chem,DataStructs,rdBase
from rdkit.Chem import rdFingerprintGenerator
P=Path(__file__).resolve().parent;os.nice(19);os.sched_setaffinity(0,{min(os.sched_getaffinity(0))});signal.alarm(180);resource.setrlimit(resource.RLIMIT_CPU,(170,170))
start=time.time();fg=rdFingerprintGenerator.GetMorganGenerator(radius=2,fpSize=2048,includeChirality=False)
main=list(map(json.loads,(P/'chemical-entity-mapping.jsonl').open()));external=list(map(json.loads,(P/'external-blind-chemical-inputs.jsonl').open()))
byid={r['chemical_entity_id']:r for r in main};ids=sorted(byid);fps=[]
for k in ids:fps.append(fg.GetFingerprint(Chem.MolFromSmiles(byid[k]['canonical_isomeric_smiles'])))
result=[];tested=0
for r in external:
 if not r.get('peptide_smiles'):continue
 tested+=1;m=Chem.MolFromSmiles(r['peptide_smiles']);assert m is not None
 iso=Chem.MolToSmiles(m,canonical=True,isomericSmiles=True);ach=Chem.MolToSmiles(m,canonical=True,isomericSmiles=False)
 entity=hashlib.sha256(iso.encode()).hexdigest();achid=hashlib.sha256(ach.encode()).hexdigest();sims=DataStructs.BulkTanimotoSimilarity(fg.GetFingerprint(m),fps)
 edges=[]
 for j,s in enumerate(sims):
  if s>=.8:edges.append({'main_chemical_entity_id':ids[j],'tanimoto':s,'exact_isomeric_graph':entity==ids[j],'exact_achiral_graph':achid==byid[ids[j]]['achiral_entity_id']})
 result.append({'external_id':r['external_id'],'external_chemical_entity_id':entity,'external_achiral_entity_id':achid,'maximum_tanimoto':max(sims),'neighbor_edges':edges})
with (P/'external-chemical-overlap.jsonl').open('w') as f:
 for r in result:f.write(json.dumps(r)+'\n')
receipt={'host':socket.gethostname(),'rdkit_version':rdBase.rdkitVersion,'external_all_rows':len(external),'external_molecule_inputs_tested':tested,'external_missing_SMILES_rows':len(external)-tested,'main_unique_graphs':len(ids),'threshold':.8,'fingerprint':'Morgan radius2 2048bits achiral','labels_read':False,'gpu_used':False,'seconds':time.time()-start,'external_graph_overlap_rows':sum(any(e['exact_isomeric_graph'] for e in r['neighbor_edges']) for r in result),'external_achiral_overlap_rows':sum(any(e['exact_achiral_graph'] for e in r['neighbor_edges']) for r in result),'external_chemical_neighbor_rows':sum(bool(r['neighbor_edges']) for r in result)}
(P/'external-chemical-runtime-receipt.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt,indent=2))
