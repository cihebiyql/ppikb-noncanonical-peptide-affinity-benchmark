import numpy as np
from rdkit import Chem
import networkx as nx
def get_atom_features(atom):
    return np.array(
        encode_one_hot_unknown(atom.GetSymbol(), ['C', 'N', 'O', 'S', 'F', 'Si', 'P', 'Cl', 'Br', 'Mg', 'Na', 'Ca', 'Fe', 
                                                  'As', 'Al', 'I', 'B', 'V', 'K', 'Tl', 'Yb', 'Sb', 'Sn', 'Ag', 'Pd', 
                                                  'Co', 'Se', 'Ti', 'Zn', 'H', 'Li', 'Ge', 'Cu', 'Au', 'Ni', 'Cd', 
                                                  'In', 'Mn', 'Zr', 'Cr', 'Pt', 'Hg', 'Pb', 'Unknown']) +
        encode_one_hot(atom.GetDegree(), list(range(11))) +
        encode_one_hot_unknown(atom.GetTotalNumHs(), list(range(11))) +
        encode_one_hot_unknown(atom.GetImplicitValence(), list(range(11))) +
        [atom.GetIsAromatic()]
    )

def encode_one_hot(value, allowable_set):
    if value not in allowable_set:
        raise ValueError(f"Input {value} not in allowable set {allowable_set}")
    return [value == s for s in allowable_set]

def encode_one_hot_unknown(value, allowable_set):
    if value not in allowable_set:
        value = allowable_set[-1]
    return [value == s for s in allowable_set]

def convert_smile_to_graph(smile):
    mol = Chem.MolFromSmiles(smile)
    atom_count = mol.GetNumAtoms()
    features = [get_atom_features(atom) / sum(get_atom_features(atom)) for atom in mol.GetAtoms()]

    edges = [[bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()] for bond in mol.GetBonds()]
    graph = nx.Graph(edges).to_directed()
    edge_index = [[e1, e2] for e1, e2 in graph.edges]

    return atom_count, features, edge_index

def encode_sequence(protein):
    encoded_seq = np.zeros(max_sequence_length)
    for i, char in enumerate(protein[:max_sequence_length]):
        encoded_seq[i] = sequence_dict[char]
    return encoded_seq
sequence_vocabulary = "ABCDEFGHIKLMNOPQRSTUVWXYZ"
sequence_dict = {char: (i + 1) for i, char in enumerate(sequence_vocabulary)}
max_sequence_length = 1000
