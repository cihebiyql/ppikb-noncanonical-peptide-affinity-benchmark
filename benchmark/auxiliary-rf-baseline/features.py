"""Conventional, data-independent Morgan + protein composition features."""
from pathlib import Path
import hashlib
import json
import numpy as np
from rdkit import Chem,DataStructs
from rdkit.Chem import rdFingerprintGenerator

AA='ACDEFGHIKLMNPQRSTVWY'
AA_INDEX={letter:index for index,letter in enumerate(AA)}
DIMENSION=2469
GENERATOR=rdFingerprintGenerator.GetMorganGenerator(radius=2,fpSize=2048,includeChirality=True,
    countSimulation=False,useBondTypes=True,onlyNonzeroInvariants=False,includeRingMembership=True,
    includeRedundantEnvironments=False)

def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda:handle.read(1048576),b''):digest.update(block)
    return digest.hexdigest()

def text_hash(text):return hashlib.sha256(text.encode('utf-8')).hexdigest()

def encode_record(row):
    smiles=row.get('canonical_isomeric_smiles') or row.get('peptide_smiles')
    target=row.get('target_sequence')
    if not isinstance(smiles,str) or not smiles or not isinstance(target,str) or not target:
        raise ValueError(str(row.get('record_id'))+': missing full molecule or reference protein')
    parser=Chem.SmilesParserParams();parser.sanitize=True;parser.removeHs=False
    mol=Chem.MolFromSmiles(smiles,parser)
    if mol is None or mol.GetNumAtoms()==0:raise ValueError(str(row['record_id'])+': invalid molecule; no repair attempted')
    output=np.zeros(DIMENSION,dtype=np.float32)
    bits=np.zeros(2048,dtype=np.uint8)
    DataStructs.ConvertToNumpyArray(GENERATOR.GetFingerprint(mol),bits)
    output[:2048]=bits
    prefix=target[:1000];length=len(prefix)
    for letter in prefix:
        index=AA_INDEX.get(letter)
        if index is not None:output[2048+index]+=1
    output[2048:2068]/=length
    if length>1:
        for first,second in zip(prefix,prefix[1:]):
            a=AA_INDEX.get(first);b=AA_INDEX.get(second)
            if a is not None and b is not None:output[2068+a*20+b]+=1
        output[2068:2468]/=(length-1)
    output[2468]=length
    if not np.isfinite(output).all():raise ValueError('Nonfinite fixed feature')
    audit=dict(record_id=row['record_id'],smiles_sha256=text_hash(smiles),molecule_atoms=mol.GetNumAtoms(),
        molecule_fragments=len(Chem.GetMolFrags(mol)),specified_chiral_atoms=sum(atom.GetChiralTag()!=Chem.ChiralType.CHI_UNSPECIFIED for atom in mol.GetAtoms()),
        full_reference_length=len(target),effective_prefix_length=length,reference_truncated=len(target)>1000,
        full_reference_sha256=text_hash(target),effective_prefix_sha256=text_hash(prefix),
        prefix_unknown_count=sum(letter not in AA_INDEX for letter in prefix),
        prefix_unknown_characters=sorted(set(prefix)-set(AA)),
        feature_sha256=hashlib.sha256(output.tobytes()).hexdigest(),all_fragments_retained=True,
        inferred_stereochemistry=False,learned_preprocessing=False)
    return output,audit

def read_label_free(path):
    forbidden={'pKd','pKd_true','p_value','value','value_raw','value_molar','affinity','gold','label','y'}
    rows=[];ids=set()
    with Path(path).open(encoding='utf-8-sig') as handle:
        for line in handle:
            if not line.strip():continue
            row=json.loads(line)
            if forbidden & set(row):raise ValueError('Feature preparation received actual label-bearing row')
            if row['record_id'] in ids:raise ValueError('Duplicate input record_id')
            ids.add(row['record_id']);rows.append(row)
    return rows
