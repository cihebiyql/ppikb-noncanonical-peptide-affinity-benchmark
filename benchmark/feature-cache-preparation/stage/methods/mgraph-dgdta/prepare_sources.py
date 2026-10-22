"""Freeze isolated author components and minimal compatibility patches, never edit originals."""
from pathlib import Path
import ast
import difflib
import hashlib
import json

HERE = Path(__file__).resolve().parent
AUDIT = HERE.parents[1] / 'model-audit'
OUT = HERE / 'patched-author'
OUT.mkdir(exist_ok=True)
PATCHES = [
 ('guaguabujianle__MGraphDTA', 'regression/model.py', 'mgraph_model.py', [
   ('    def forward(self, data):\n        target = data.target',
    '    def forward(self, data):\n        data = data.clone()  # isolate author in-place intermediate updates\n        target = data.target')]),
 ('guaguabujianle__MGraphDTA', 'regression/preprocessing.py', 'mgraph_preprocessing.py', []),
 ('luojunwei__DGDTA', 'model/gatv2GCN.py', 'dgdta_model.py', [
   ('GCNConv(output_dim * 10, output_dim * 10, dropout=dropout_rate)',
    'GCNConv(output_dim * 10, output_dim * 10)'),
   ('nn.LSTM(embed_dim, 64, 1, dropout=0.2, bidirectional=True)',
    'nn.LSTM(embed_dim, 64, 1, dropout=0.2, bidirectional=True, batch_first=True)'),
   ('CombinedDenseBlock(256, output_size, dropout_rate)',
    'CombinedDenseBlock(xd_features * 10 * 2 + dense_output_dim, output_size, dropout_rate)')]),
]

def sha(data):
    return hashlib.sha256(data).hexdigest()

entries = []
for repo, relative, output, replacements in PATCHES:
    source = AUDIT / 'author-source' / repo / 'source' / relative
    raw = source.read_bytes()
    original = raw.decode('utf-8-sig')
    patched = original
    for old, new in replacements:
        assert patched.count(old) == 1, (output, old)
        patched = patched.replace(old, new)
    target = OUT / output
    target.write_text(patched, encoding='utf-8', newline='\n')
    diff = ''.join(difflib.unified_diff(original.splitlines(True), patched.splitlines(True),
                                      fromfile=repo + '/' + relative, tofile='patched-author/' + output))
    (OUT / (output + '.diff')).write_text(diff, encoding='utf-8', newline='\n')
    entries.append(dict(repo=repo, source_relative=relative, source_sha256=sha(raw),
                        patched_file=output, patched_sha256=sha(target.read_bytes()),
                        patch_replacements=len(replacements)))

# The author create_data module executes dataset I/O on import. Isolate its unchanged
# function AST nodes rather than import its top-level preprocessing pipeline.
source = AUDIT / 'author-source/luojunwei__DGDTA/source/create_data.py'
raw = source.read_bytes()
original = raw.decode('utf-8-sig')
tree = ast.parse(original)
names = {'get_atom_features', 'encode_one_hot', 'encode_one_hot_unknown', 'convert_smile_to_graph', 'encode_sequence'}
nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
selected = '\n\n'.join(ast.get_source_segment(original, node) for node in nodes)
prefix = 'import numpy as np\nfrom rdkit import Chem\nimport networkx as nx\n'
suffix = '\nsequence_vocabulary = "ABCDEFGHIKLMNOPQRSTUVWXYZ"\nsequence_dict = {char: (i + 1) for i, char in enumerate(sequence_vocabulary)}\nmax_sequence_length = 1000\n'
target = OUT / 'dgdta_preprocessing.py'
target.write_text(prefix + selected + suffix, encoding='utf-8', newline='\n')
entries.append(dict(repo='luojunwei__DGDTA', source_relative='create_data.py',
                    source_sha256=sha(raw), patched_file=target.name,
                    patched_sha256=sha(target.read_bytes()), extraction='unchanged function source segments; no top-level dataset IO'))
(HERE / 'source-freeze-manifest.json').write_text(json.dumps(entries, indent=2), encoding='utf-8')
print(json.dumps({'frozen_components': len(entries), 'output': str(OUT)}))
