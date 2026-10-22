"""Make isolated, auditable compatibility copy; frozen upstream stays unchanged."""
import ast
import difflib
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[1] / 'model-audit/author-source/LiZhang30__MRBDTA/source'
original = (SOURCE / 'MRBDTA.py').read_text(encoding='utf-8')
# Never import the upstream training script or its dataset/metrics helpers.
adapted = original.split("if __name__ == '__main__':")[0]
adapted = adapted.replace('import DataHelper as DH', 'from types import SimpleNamespace\nDH = SimpleNamespace(drugSeq_vocabSize=65, targetSeq_vocabSize=26)')
adapted = adapted.replace('import emetrics as EM\n', '')
adapted = adapted.replace('nn.LayerNorm(d_model).cuda()(output+residual)', 'torch.nn.functional.layer_norm(output+residual, (d_model,))')
adapted = adapted.replace('enc_Drugs_2D0.squeeze()', 'enc_Drugs_2D0')
adapted = adapted.replace('enc_Tars_2D0.squeeze()', 'enc_Tars_2D0')
adapted = adapted.replace('affi = fc2.squeeze()', 'affi = fc2.reshape(-1)')
(HERE / 'author_model.py').write_text(adapted, encoding='utf-8')
helper = (SOURCE / 'DataHelper.py').read_text(encoding='utf-8')
# The commented alternative vocabulary is explicitly supplied by the authors.
start = helper.index('CharIsoSmiSet = ')
end = helper.index('\nCharIsoSmiLen', start)
drug = ast.literal_eval(helper[start:end].split('=', 1)[1].strip())
tree = ast.parse(helper)
target = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'targetSeq_vocab' for t in n.targets))
(HERE / 'vocabularies.json').write_text(json.dumps({'drug': drug, 'target': target}, indent=2), encoding='utf-8')
(HERE / 'author-compatibility.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True), adapted.splitlines(True), fromfile='frozen/MRBDTA.py', tofile='mrbdta/author_model.py')), encoding='utf-8')
manifest = {
 'upstream_commit': 'e338dd2f3aa55a09ba8b82c1ee5e79dc3aaab95c',
 'upstream_sha256': hashlib.sha256((SOURCE/'MRBDTA.py').read_bytes()).hexdigest(),
 'adapted_sha256': hashlib.sha256((HERE/'author_model.py').read_bytes()).hexdigest(),
 'changes': [
  'Enable author commented CharIsoSmiSet IDs1..64, embedding65 including PAD0; target IDs1..25 embedding26.',
  'Forward-created CUDA LayerNorm replaced by parameter-free functional LayerNorm, preserving original fresh gamma1/beta0 behavior; no trainable new norm.',
  'Preserve B dimension after sum and flatten final scalar output only.',
  'Remove upstream executable training main and unused emetrics import; frozen upstream unchanged.',
 ],
 'architecture': {'d_model':128,'d_ff':512,'d_k':32,'d_v':32,'n_layers':1,'n_heads':4,'streams_per_modality':3},
 'protein_prefix_limit':1000, 'smiles_limit':5000,
 'pooling_policy':'Per-record unpadded forwards preserve author all-position sum and avoid batch-composition-dependent padding contributions.',
 'claim':'Author architecture with disclosed vocabulary and execution compatibility adaptation, not original paper metric replication.'
}
(HERE/'source-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps(manifest,indent=2))
