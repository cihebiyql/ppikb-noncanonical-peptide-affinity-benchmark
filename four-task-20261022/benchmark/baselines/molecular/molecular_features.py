"""Classical chiral molecular fingerprints and protein composition; no learned encoder."""
from __future__ import annotations

import hashlib
import math
from collections import Counter

import numpy as np
from rdkit import Chem, DataStructs, rdBase
from rdkit.Chem import Crippen, Descriptors, Lipinski, rdFingerprintGenerator, rdMolDescriptors


FEATURE_VERSION = "chiral-morgan-r2-2048-rdkit10-proteinAAC23-v1"
AA = "ACDEFGHIKLMNPQRSTVWY"
GENERATOR = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048, includeChirality=True,
                                                      useBondTypes=True, includeRingMembership=True,
                                                      countSimulation=False)
DESCRIPTOR_NAMES = ["MolWt", "MolLogP", "TPSA", "HBD", "HBA", "NumRotatableBonds", "FractionCSP3",
                    "HeavyAtomCount", "RingCount", "NumAliphaticRings"]


def choose(row, *columns):
    for column in columns:
        value = row.get(column)
        if isinstance(value, str) and value:
            return value
    return ""


def protein_features(sequence):
    if not sequence:
        raise ValueError("protein sequence is required")
    counts = Counter(sequence)
    n = len(sequence)
    return np.asarray([counts[aa]/n for aa in AA] +
                      [sum(v for aa,v in counts.items() if aa not in AA)/n, math.log1p(n), 0.], dtype=np.float32)


def chemical_features(smiles):
    if not smiles:
        raise ValueError("full, nonempty SMILES is required; no sequence substitution")
    molecule = Chem.MolFromSmiles(smiles)
    if molecule is None:
        raise ValueError("RDKit could not parse a frozen SMILES; input not repaired or silently dropped")
    fingerprint = np.zeros(2048, dtype=np.float32)
    DataStructs.ConvertToNumpyArray(GENERATOR.GetFingerprint(molecule), fingerprint)
    descriptor = np.asarray([Descriptors.MolWt(molecule), Crippen.MolLogP(molecule), rdMolDescriptors.CalcTPSA(molecule),
                             Lipinski.NumHDonors(molecule), Lipinski.NumHAcceptors(molecule), Lipinski.NumRotatableBonds(molecule),
                             rdMolDescriptors.CalcFractionCSP3(molecule), molecule.GetNumHeavyAtoms(),
                             rdMolDescriptors.CalcNumRings(molecule), rdMolDescriptors.CalcNumAliphaticRings(molecule)], dtype=np.float32)
    result = np.concatenate([fingerprint, descriptor])
    if not np.isfinite(result).all():
        raise ValueError("nonfinite classical molecular descriptor")
    return result


def chiral_canary():
    left = chemical_features("N[C@@H](C)C(=O)O")
    right = chemical_features("N[C@H](C)C(=O)O")
    return {"passed": not np.array_equal(left[:2048],right[:2048]),
            "different_chiral_morgan_bits": int(np.count_nonzero(left[:2048] != right[:2048])),
            "same_achiral_basic_descriptors": bool(np.array_equal(left[2048:],right[2048:]))}


def build_features(frame, task):
    effect = any(name in task.lower() for name in ("effect", "delta", "ddg"))
    if any(name in task.lower() for name in ("contact", "site", "classification")):
        raise ValueError("this classical molecular feature contract covers affinity and effect only")
    molecules, proteins = {}, {}
    def molecular(value):
        if value not in molecules:
            molecules[value] = chemical_features(value)
        return molecules[value]
    def protein(value):
        if value not in proteins:
            proteins[value] = protein_features(value)
        return proteins[value]
    vectors, zero_changes = [], 0
    smiles_hashes = set()
    for row in frame.to_dict("records"):
        target = choose(row,"target_sequence","target_wt_sequence")
        if effect:
            reference_smiles = choose(row,"smiles_wt","reference_smiles","peptide_smiles_wt")
            variant_smiles = choose(row,"smiles_mut","variant_smiles","peptide_smiles_mut")
            target_mut = choose(row,"target_mut_sequence") or target
            target_wt = choose(row,"target_wt_sequence") or target
            if target_wt != target_mut:
                raise ValueError("same-target effect contract cannot silently encode protein mutations")
            reference, variant = molecular(reference_smiles), molecular(variant_smiles)
            change = variant-reference
            zero_changes += int(np.all(change == 0))
            vectors.append(np.concatenate([reference,change,protein(target_wt)]))
            smiles_hashes.update([hashlib.sha256(reference_smiles.encode()).hexdigest(), hashlib.sha256(variant_smiles.encode()).hexdigest()])
        else:
            smiles = choose(row,"peptide_smiles","smiles")
            vectors.append(np.concatenate([molecular(smiles),protein(target)]))
            smiles_hashes.add(hashlib.sha256(smiles.encode()).hexdigest())
    matrix = np.asarray(vectors,dtype=np.float32)
    canary = chiral_canary()
    if not canary["passed"]:
        raise ValueError("chiral Morgan encoder failed D/L canary")
    audit = {"version":FEATURE_VERSION,"shape":list(matrix.shape),"rdkit_version":rdBase.rdkitVersion,
             "morgan":{"radius":2,"bits":2048,"includeChirality":True,"useBondTypes":True,"includeRingMembership":True,"countSimulation":False},
             "molecular_descriptor_names":DESCRIPTOR_NAMES,"protein_features":"20AA composition, original non-AA20 fraction, log length, empty indicator",
             "effect_features":"WT molecular fingerprint+descriptors, MUT-minus-WT fingerprint+descriptor difference, same-target protein AAC",
             "unique_raw_smiles":len(molecules),"raw_smiles_sha256_count":len(smiles_hashes),"unique_target_sequences":len(proteins),
             "source":"complete frozen SMILES including explicit stereochemistry and unmodified full target sequence",
             "chiral_canary":canary,"effect_zero_molecular_change_rows":zero_changes if effect else None,
             "nc_ptm_chemical_identity_encoded":"to extent present in source SMILES; source annotation/graph conflicts remain flagged",
             "coordinates_or_labels_used_for_features":False,"feature_matrix_sha256":hashlib.sha256(matrix.tobytes()).hexdigest()}
    return matrix,audit
