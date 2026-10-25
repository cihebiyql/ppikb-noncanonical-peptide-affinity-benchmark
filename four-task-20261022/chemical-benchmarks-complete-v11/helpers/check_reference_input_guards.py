"""Run the restored original model's input guards, without importing its encoder.

All checks below use standard-library-only helpers from the original39-source
tree. Neither Torch nor NumPy nor an upstream model is imported.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

from restore_scientific_inputs import native_root
from scientific_path_bridge import path_bridge


def file_sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def check(project):
    project=native_root(project).resolve()
    def module(name,relative):
        spec=importlib.util.spec_from_file_location(name,project/relative)
        value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
    source=project/'baselines/peptideclm2025-spefix-finetune-expanded-v3/dataset_binding.py'
    if file_sha(source)!='4425a38dd0dd7f62e6971905b3a1bc72c98652148c62706f5ed584848a437e80':raise ValueError('Use original4425 scientific guard, not the superseded public path adapter')
    binding=module('public_recovered_original4425_binding','baselines/peptideclm2025-spefix-finetune-expanded-v3/dataset_binding.py')
    rejected=[]
    with path_bridge(project):
        binding.validate_frozen_files(binding.REMOTE_MANIFEST,binding.REMOTE_SPEC)
        actual=binding.sha(binding.REMOTE_CSV)
        if actual!=binding.CSV_SHA:raise ValueError('c3 raw bytes differ')
        manifest=json.loads(Path(binding.REMOTE_MANIFEST).read_text(encoding='utf-8'))
        view=next(x for x in manifest['views'] if '_target_' in x['id'])
        binding.validate_target_view(view,actual)
        variants=[('old963_manifest',('963c7bc996643d8c63ccd67c9c2d7697eedf2882a4495367b3dd77bdbc42dace',binding.SPEC_SHA,binding.CSV_SHA)),('old9cde_spec',(binding.MANIFEST_SHA,'9cde3fd5d87e5e4d597393f640a5b8eb9ede702f853e9511e88841414e682db7',binding.CSV_SHA)),('old4f_CSV',(binding.MANIFEST_SHA,binding.SPEC_SHA,'4f4694b8937c6e3bd2e5b1091faf948fd66ecc57180b09d0ff5c236cded83c60')),('unknown_CSV',(binding.MANIFEST_SHA,binding.SPEC_SHA,'unknown'))]
        for label,args in variants:
            try:binding.validate_hashes(*args,split_counts=binding.FRAME_SPLITS)
            except ValueError:rejected.append(label)
            else:raise ValueError('Original guard wrongly accepted: '+label)
        ring=module('public_recovered_original_ring_guard','methods/chemical-encoders-20261024-v2-ringfix/ringfix_adapter.py');ring.load_recipe()
        spe=module('public_recovered_original_SPE_guard','methods/chemical-encoders-20261025-v3-peptideclm2025-spefix/load_peptideclm2025_spefix.py')
        if spe.source_identity()!='c1541420d34a09a642d3390011a3e4419b011ad01cb5a77e65e2b6a743a0f914':raise ValueError('Original SPE source identity changed')
    if any(name in sys.modules for name in ('torch','numpy')):raise ValueError('Standard-library-only guard check imported a model/numeric framework')
    return {'schema':'public-original-reference-input-guard-check.v1','status':'passed','source4425_original_SHA_verified':True,'original93_manifest_and8b_spec_accepted':True,'original_c3_CSV_and_target_view_accepted':True,'mismatched_original_inputs_rejected':rejected,'actual_original_ring_recipe_load':'passed','actual_original_SPE_source_identity_c154':'passed','original_bytes_rewritten':False,'execution_only_path_bridge':True,'Torch_imports':0,'NumPy_imports':0,'models_loaded':0,'new_fits':0,'new_predictions':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--project',type=Path,required=True);parser.add_argument('--receipt',type=Path,required=True)
    args=parser.parse_args();result=check(args.project)
    with args.receipt.open('x',encoding='utf-8',newline='\n') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps(result,indent=2))
