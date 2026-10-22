"""Freeze author model files and extract side-effect-free author feature functions.

This writes only inside this adapter directory; frozen author-source is read-only.
"""
import ast
import difflib
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
SOURCES = PROJECT / "model-audit" / "author-source"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    vendor = HERE / "vendor"
    vendor.mkdir(exist_ok=True)
    specs = [
        ("GraphDTA-GIN", "thinng__GraphDTA/source", "models/ginconv.py", "create_data.py", "graphdta_gin.py"),
        ("DeepNC-GEN", "thntran__DeepNC/source", "models/gen.py", "prepare_data.py", "deepnc_gen.py"),
    ]
    manifest = []
    for method, root, model_rel, prep_rel, name in specs:
        model = SOURCES / root / model_rel
        prep = SOURCES / root / prep_rel
        original = model.read_text(encoding="utf-8")
        adapted = original
        reasons = []
        if method == "DeepNC-GEN":
            assert original.count("super(GEN_Conv, self).__init__()") == 1
            adapted = original.replace("super(GEN_Conv, self).__init__()", "super(GEN, self).__init__()")
            reasons.append("Fix author NameError: constructor references undefined GEN_Conv although class is named GEN. No architecture change.")
        dest = vendor / name
        dest.write_text(adapted, encoding="utf-8", newline="\n")
        diff = "".join(difflib.unified_diff(original.splitlines(True), adapted.splitlines(True), fromfile=str(model), tofile="vendor/" + name))
        (HERE / (name + ".patch")).write_text(diff or "# No author model code changes.\n", encoding="utf-8", newline="\n")
        tree = ast.parse(prep.read_text(encoding="utf-8"))
        wanted = {"atom_features", "one_of_k_encoding", "one_of_k_encoding_unk", "smile_to_graph", "seq_cat"}
        selected = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in wanted]
        assert {n.name for n in selected} == wanted
        feature = "import numpy as np\nfrom rdkit import Chem\nimport networkx as nx\n\n"
        feature += "\n\n".join(ast.unparse(n) for n in selected)
        feature += '\n\nseq_voc = "ABCDEFGHIKLMNOPQRSTUVWXYZ"\nseq_dict = {v: i + 1 for i, v in enumerate(seq_voc)}\nmax_seq_len = 1000\n'
        feature_dest = vendor / name.replace(".py", "_features.py")
        feature_dest.write_text(feature, encoding="utf-8", newline="\n")
        manifest.append({"method": method, "source_model": str(model), "source_model_sha256": sha(model), "source_preprocessing": str(prep), "source_preprocessing_sha256": sha(prep), "adapted_model": str(dest.relative_to(HERE)), "adapted_model_sha256": sha(dest), "feature_file": str(feature_dest.relative_to(HERE)), "feature_sha256": sha(feature_dest), "preprocessing_extraction": "AST function extraction; original function semantics preserved; removes module-level author dataset I/O", "changes": reasons})
    (HERE / "vendor-manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
