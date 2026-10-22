"""Stage only root-approved label-free X sets; no gold, selections or weights."""
from pathlib import Path
import copy
import json
import shutil
import common
HERE=Path(__file__).resolve().parent
PROJECT=HERE.parent
NODE='/data/qlyu/projects/peptide-binding-nc-benchmark-20261021'
def main():
    original=common.read_json(HERE/'proposed-manifest-v1.json')
    assert common.sha(HERE/'proposed-manifest-v1.json')=='e73afbc3707ed52fc2e576ca8b3e57fec93d17b9bb7b879157ccd4e5f6d1be36'
    relative='external-validation/scoring-supplement13-v1/inputs/input13.jsonl'
    path=PROJECT/relative
    assert common.sha(path)=='6c7839966e786cc62fb3c1e49eee64898b539a9f2454941e5ec09f0593da44ad'
    rows=common.read_inputs(path);assert len(rows)==13
    manifest=copy.deepcopy(original)
    manifest.update(status='ROOT_AUTHORIZED_LABEL_FREE_X_ONLY',parent_manifest_sha256=common.sha(HERE/'proposed-manifest-v1.json'),job_count=20,
                    supplementary_dataset_separate=True)
    manifest['datasets']['supplement13']=dict(input_relative=relative,input_sha256=common.sha(path),input_bytes=path.stat().st_size,n=13,
        node_staged_path=NODE+'/evaluation/stage/inputs/supplement13.jsonl',
        wsl_path='/mnt/d/work/科研工作台/research-tasks/peptide-binding-nc-benchmark-20261021/'+relative,
        non_target_cold=True,old_external75_unchanged=True)
    for method in common.METHODS:
        adapter=common.tree_hash(PROJECT/'methods'/common.FOLDERS[method])
        signature=common.signature(method,common.sha(path),adapter)
        manifest['jobs'].append(dict(dataset_id='supplement13',method_id=method,input_sha256=common.sha(path),n=13,
            adapter_tree_sha256=adapter,signature=signature,cache_filename='supplement13__'+method+'__X_'+signature[:16]+'.pkl',
            cache_generation_requires_models=False,placeholder_pKd=0.0))
    assert manifest['jobs'][:15]==original['jobs']
    common.write_json(HERE/'authorized-manifest-v2.json',manifest)
    common.write_json(HERE/'cache-authorization-v2.json',dict(root_cache_generation_authorized=True,
        manifest_sha256=common.sha(HERE/'authorized-manifest-v2.json'),
        basis='Direct root approval of original15 SHA and accepted independent supplement13 five caches; X-only, no predictions/gold/weights',
        root_scoring_authorized=False))
    stage=HERE/'stage/inputs';stage.mkdir(parents=True,exist_ok=False)
    for name,dataset in manifest['datasets'].items():
        source=PROJECT/dataset['input_relative'];assert common.sha(source)==dataset['input_sha256']
        shutil.copy2(source,stage/(name+'.jsonl'))
    print('Staged 20 authorized X-only jobs; original15 signatures unchanged; no processes launched.')
if __name__=='__main__':main()
