"""Machine-readable format of fourteen existing measured author entities only.

Each input is a fixed author-observed ligand with explicit SI chemistry. No new
ligands are selected, generated as candidates, scored, optimized or designed.
Graph edits encode the source notation. Missing/ambiguous chemistry fails closed.
"""
from pathlib import Path
from collections import Counter
import hashlib,json,os,re,resource,time
import rdkit
from rdkit import Chem
from rdkit.Chem import rdMolDescriptors
HERE=Path(__file__).resolve().parent
AA=set('ACDEFGHIKLMNPQRSTVWY')
TEMPLATES={'Abu':'A','D-Asp':'D','1-Nal':'F','2-Nal':'F','alloThr':'T','D-Arg':'R','2-Pya':'F'}
def atom(m,pos,name):
 ids=[a.GetIdx() for a in m.GetAtoms() if a.GetPDBResidueInfo() is not None and a.GetPDBResidueInfo().GetResidueNumber()==pos and a.GetPDBResidueInfo().GetName().strip()==name]
 assert len(ids)==1,(pos,name,ids)
 return ids[0]
def formula_counter(txt):return Counter({m[0]:int(m[1] or 1) for m in re.findall(r'([A-Z][a-z]?)(\d*)',txt)})
def replace_ring(rw,pos,notation):
 beta=atom(rw,pos,'CB');start=atom(rw,pos,'CG');stack=[start];drop=set()
 while stack:
  i=stack.pop()
  if i in drop or i==beta:continue
  drop.add(i);stack.extend(n.GetIdx() for n in rw.GetAtomWithIdx(i).GetNeighbors() if n.GetIdx()!=beta)
 assert len(drop)==6
 for i in sorted(drop,reverse=True):rw.RemoveAtom(i)
 beta=atom(rw,pos,'CB');frag=Chem.MolFromSmiles(notation);mapping={}
 for a in frag.GetAtoms():mapping[a.GetIdx()]=rw.AddAtom(Chem.Atom(a))
 for b in frag.GetBonds():rw.AddBond(mapping[b.GetBeginAtomIdx()],mapping[b.GetEndAtomIdx()],b.GetBondType())
 rw.AddBond(beta,mapping[0],Chem.BondType.SINGLE)
def convert(row):
 ann=row['actual_chemical_annotation'];tokens=ann['actual_residue_tokens'];assert len(tokens)==15
 assert set(tokens)<=AA|set(TEMPLATES)
 seq=''.join(TEMPLATES.get(t,t) for t in tokens);base=Chem.MolFromSequence(seq,flavor=0);assert base is not None
 rw=Chem.RWMol(base);edits=[]
 for pos,tok in enumerate(tokens,1):
  if tok=='Abu':
   beta=atom(rw,pos,'CB');extra=rw.AddAtom(Chem.Atom('C'));rw.AddBond(beta,extra,Chem.BondType.SINGLE)
  elif tok in ('D-Asp','D-Arg'):rw.GetAtomWithIdx(atom(rw,pos,'CA')).InvertChirality()
  elif tok=='alloThr':rw.GetAtomWithIdx(atom(rw,pos,'CB')).InvertChirality()
  elif tok in ('1-Nal','2-Nal'):replace_ring(rw,pos,'c1cccc2ccccc12' if tok=='1-Nal' else 'c1ccc2ccccc2c1')
  elif tok=='2-Pya':
   idx=atom(rw,pos,'CD1');replacement=Chem.Atom('N');replacement.SetIsAromatic(True);replacement.SetPDBResidueInfo(rw.GetAtomWithIdx(idx).GetPDBResidueInfo());rw.ReplaceAtom(idx,replacement)
  if tok in TEMPLATES:edits.append({'source_residue_token':tok,'actual_position_1based':pos,'operation':'encode_author_reported_residue_chemical_identity'})
 assert ann['n_terminal']=='Ac'
 n=atom(rw,1,'N');ac=rw.AddAtom(Chem.Atom('C'));ox=rw.AddAtom(Chem.Atom('O'));methyl=rw.AddAtom(Chem.Atom('C'))
 rw.AddBond(n,ac,Chem.BondType.SINGLE);rw.AddBond(ac,ox,Chem.BondType.DOUBLE);rw.AddBond(ac,methyl,Chem.BondType.SINGLE)
 if ann['c_terminal']=='NH2':
  idx=atom(rw,len(tokens),'OXT');replacement=Chem.Atom('N');replacement.SetPDBResidueInfo(rw.GetAtomWithIdx(idx).GetPDBResidueInfo());rw.ReplaceAtom(idx,replacement)
 else:assert ann['c_terminal']=='OH'
 cys=ann['disulfide_residue_positions_1based'];assert len(cys)==2
 rw.AddBond(atom(rw,cys[0],'SG'),atom(rw,cys[1],'SG'),Chem.BondType.SINGLE)
 mol=rw.GetMol();Chem.SanitizeMol(mol);Chem.AssignStereochemistry(mol,cleanIt=True,force=True)
 expected=formula_counter(ann['author_protonated_molecular_formula']);expected['H']-=1
 actual=Counter(a.GetSymbol() for a in Chem.AddHs(mol).GetAtoms());assert actual==+expected,('author_formula_identity_conflict_no_repair',row['record_id'],dict(actual),dict(expected))
 ca_checks=[]
 for pos,tok in enumerate(tokens,1):
  if tok=='G':continue
  a=mol.GetAtomWithIdx(atom(mol,pos,'CA'));assert a.HasProp('_CIPCode')
  expected_ca='R' if tok in ('C','D-Asp','D-Arg') else 'S'
  assert a.GetProp('_CIPCode')==expected_ca,(row['record_id'],pos,tok,a.GetProp('_CIPCode'),expected_ca)
  ca_checks.append({'position':pos,'CIP':a.GetProp('_CIPCode')})
  if tok=='alloThr':assert mol.GetAtomWithIdx(atom(mol,pos,'CB')).GetProp('_CIPCode')=='S'
 smiles=Chem.MolToSmiles(mol,canonical=True,isomericSmiles=True);back=Chem.MolFromSmiles(smiles)
 assert back is not None and Chem.MolToSmiles(back,isomericSmiles=True,canonical=True)==smiles
 assert len(Chem.GetMolFrags(back))==1
 return {'record_id':row['record_id'],'peptide_smiles':smiles,'canonical_isomeric_smiles':smiles,'chemical_entity_id':hashlib.sha256(smiles.encode()).hexdigest(),'achiral_entity_id':hashlib.sha256(Chem.MolToSmiles(mol,canonical=True,isomericSmiles=False).encode()).hexdigest(),'representation_origin':'strict_format_conversion_of_fixed_author_SI_measured_entity_not_ligand_design','full_measured_chemical_annotation':ann,'residue_chemical_edits':edits,'alpha_stereochemistry_checks':ca_checks,'formula':rdMolDescriptors.CalcMolFormula(mol),'author_MH_formula_matched':True,'formal_charge_representation':Chem.GetFormalCharge(mol),'new_identity_experiment':False,'model_prediction':False}
def main():
 resource.setrlimit(resource.RLIMIT_CPU,(60,60));resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3));os.sched_setaffinity(0,{min(os.sched_getaffinity(0))});os.nice(19)
 start=time.time();inp=HERE/'explicit-label-free-inputs.jsonl';rows=[json.loads(l) for l in inp.open(encoding='utf-8')];out=[];failed=[]
 for row in rows:
  try:out.append(convert(row))
  except Exception as ex:failed.append({'record_id':row['record_id'],'failure':type(ex).__name__+': '+str(ex),'no_source_repair_adopted':True})
 with (HERE/'author-entity-formats.jsonl').open('w',encoding='utf-8') as f:
  for r in out:f.write(json.dumps(r,ensure_ascii=False)+'\n')
 summary={'attempted_existing_entities':len(rows),'format_checked_success':len(out),'failed':failed,'rdkit':rdkit.__version__,'runtime_seconds':time.time()-start,'input_sha256':hashlib.sha256(inp.read_bytes()).hexdigest(),'GPU_used':False,'threads':1,'PID':os.getpid(),'training_or_inference_or_design':False}
 (HERE/'author-entity-conversion-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
