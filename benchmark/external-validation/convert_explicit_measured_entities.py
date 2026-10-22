"""Format only explicitly annotated existing Kliche/SH2 measured entities.

No generation of candidate ligands, optimization, or inference of unknown labels.
This constructs a machine-readable chemical graph of an already reported entity.
Unknown/end-ambiguous chemistry fails closed. Phosphate protonation is a declared
neutral representation convention, not a claim about solution speciation.
"""
from pathlib import Path
from collections import Counter
import hashlib, json, os, resource, time
import rdkit
from rdkit import Chem
from rdkit.Chem import rdMolDescriptors

HERE=Path(__file__).resolve().parent

def elements(mol):
    return Counter(a.GetSymbol() for a in Chem.AddHs(mol).GetAtoms())

def pdbindex(mol, position, name):
    ids=[a.GetIdx() for a in mol.GetAtoms() if a.GetPDBResidueInfo() is not None and a.GetPDBResidueInfo().GetResidueNumber()==position and a.GetPDBResidueInfo().GetName().strip()==name]
    assert len(ids)==1, (position,name,len(ids))
    return ids[0]

def convert(row):
    seq=row['peptide_sequence']; mods=row['residue_modifications']; flags=row.get('source_flags')or{}
    assert row['resource_id'] in ('Kliche2023_phosphomimetic','SH2_ProBound')
    if row['resource_id']=='Kliche2023_phosphomimetic':assert flags.get('terminal_identity_ambiguous') is False
    assert row['n_terminal'] in ('H3COC','Ac') and row['c_terminal'] in ('NH2','COO-')
    assert len(mods)==1
    base=Chem.MolFromSequence(seq, sanitize=True, flavor=0)
    assert base is not None
    initial_elements=elements(base)
    base_chiral={a.GetIdx():str(a.GetChiralTag()) for a in base.GetAtoms() if a.GetChiralTag()!=Chem.ChiralType.CHI_UNSPECIFIED}
    expected=initial_elements.copy(); edits=[];rw=Chem.RWMol(base)
    for mod in mods:
        pos=mod['position_1based'];typ=mod['type']
        aa,atom={'phosphoserine':('S','OG'),'phosphothreonine':('T','OG1'),'phosphotyrosine':('Y','OH')}[typ]
        assert seq[pos-1]==aa
        side_o=pdbindex(base,pos,atom)
        phosphate=rw.AddAtom(Chem.Atom('P'));rw.AddBond(side_o,phosphate,Chem.BondType.SINGLE)
        for order in (Chem.BondType.DOUBLE,Chem.BondType.SINGLE,Chem.BondType.SINGLE):
            ox=rw.AddAtom(Chem.Atom('O'));rw.AddBond(phosphate,ox,order)
        expected.update({'P':1,'O':3,'H':1})
        edits.append({'annotation':typ,'position_1based':pos,'residue_atom':atom,'graph_operation':'reported_sidechain_O_phosphate','phosphate_charge_convention':'neutral_OP(=O)(O)O'})
    # Explicit measured N-acetyl identity (H3COC), not an arbitrary terminal tag.
    nidx=pdbindex(base,1,'N');ac=rw.AddAtom(Chem.Atom('C'));ox=rw.AddAtom(Chem.Atom('O'));methyl=rw.AddAtom(Chem.Atom('C'))
    rw.AddBond(nidx,ac,Chem.BondType.SINGLE);rw.AddBond(ac,ox,Chem.BondType.DOUBLE);rw.AddBond(ac,methyl,Chem.BondType.SINGLE)
    expected.update({'C':2,'O':1,'H':2});edits.append({'annotation':'H3COC','graph_operation':'N_acetyl'})
    last_o=pdbindex(base,len(seq),'OXT');last_c=pdbindex(base,len(seq),'C')
    if row['c_terminal']=='NH2':
        # Replace terminal hydroxyl oxygen in-place to preserve all residue indices.
        replacement=Chem.Atom('N');replacement.SetPDBResidueInfo(rw.GetAtomWithIdx(last_o).GetPDBResidueInfo())
        rw.ReplaceAtom(last_o,replacement)
        expected.update({'N':1,'H':1});expected['O']-=1
        edits.append({'annotation':'NH2','graph_operation':'C_terminal_carboxamide'})
    else:
        oxygen=rw.GetAtomWithIdx(last_o);oxygen.SetFormalCharge(-1);oxygen.SetNoImplicit(True);oxygen.SetNumExplicitHs(0)
        expected['H']-=1;edits.append({'annotation':'COO-','graph_operation':'explicit_C_terminal_carboxylate'})
    mol=rw.GetMol();Chem.SanitizeMol(mol);Chem.AssignStereochemistry(mol,cleanIt=True,force=True)
    assert elements(mol)==+expected, (elements(mol),expected)
    assert all(str(mol.GetAtomWithIdx(idx).GetChiralTag())==tag for idx,tag in base_chiral.items())
    assert sum(a.GetSymbol()=='P' for a in mol.GetAtoms())==len(mods)
    assert Chem.GetFormalCharge(mol)==(-1 if row['c_terminal']=='COO-' else 0)
    smiles=Chem.MolToSmiles(mol,isomericSmiles=True,canonical=True)
    restored=Chem.MolFromSmiles(smiles);assert restored is not None
    assert Chem.MolToSmiles(restored,isomericSmiles=True,canonical=True)==smiles
    assert len(Chem.GetMolFrags(restored))==1
    return {
        'external_id':row['external_id'],'peptide_smiles':smiles,
        'representation_origin':'deterministic_format_conversion_of_exact_existing_author_annotated_measured_entity',
        'is_new_experimental_identity_evidence':False,'is_ligand_design':False,
        'atom_count_formula_and_stereotag_checks':True,'formula':rdMolDescriptors.CalcMolFormula(mol),
        'phosphate_protonation_convention':'neutral_phosphate; unknown solution protonation not inferred',
        'source_terminal_annotation':{'n_terminal':row['n_terminal'],'c_terminal':row['c_terminal']},
        'source_modifications':mods,'edits':edits,'source_flags':flags,
        'source_warning_preserved':True,
    }

def main():
    os.environ['CUDA_VISIBLE_DEVICES']=''
    resource.setrlimit(resource.RLIMIT_CPU,(60,60));resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
    try:os.sched_setaffinity(0,{min(os.sched_getaffinity(0))});os.nice(19)
    except (AttributeError,OSError):pass
    p=HERE/'blind-inputs.jsonl';before=hashlib.sha256(p.read_bytes()).hexdigest();started=time.time()
    rows=[json.loads(l) for l in p.open(encoding='utf-8')]
    out=[];failed=[]
    for row in rows:
        if row['resource_id'] not in ('Kliche2023_phosphomimetic','SH2_ProBound'):continue
        try:out.append(convert(row))
        except Exception as ex:failed.append({'external_id':row['external_id'],'reason':type(ex).__name__+': '+str(ex)})
    with (HERE/'Kliche-exact-annotation-format-converted.jsonl').open('w',encoding='utf-8') as f:
        for r in out:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    summary={'input_sha256':before,'input_unchanged':before==hashlib.sha256(p.read_bytes()).hexdigest(),'rdkit':rdkit.__version__,'format_converted_rows':len(out),'failed_rows':failed,'runtime_seconds':time.time()-started,'training_executed':False,'optimization_executed':False,'process_id':os.getpid(),'thread_budget':1,'GPU_used':False}
    (HERE/'conversion-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':main()
