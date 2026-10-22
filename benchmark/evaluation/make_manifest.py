"""Inspect only three label-free X files and source code; never open gold/runs."""
from pathlib import Path
import common

HERE=Path(__file__).resolve().parent
PROJECT=HERE.parent
WSL='/mnt/d/work/科研工作台/research-tasks/peptide-binding-nc-benchmark-20261021'
NODE='/data/qlyu/projects/peptide-binding-nc-benchmark-20261021'
DATASETS={
 'source_test':'execution/prepared-panels-wsl-v3/source_peptide_dependency_cold/test-inputs.jsonl',
 'target_test':'execution/prepared-panels-wsl-v3/target_reference_homology_cold/test-inputs.jsonl',
 'external75':'external-validation/scoring-views-v1/inputs75.jsonl',
}
def main():
    output=HERE/'proposed-manifest-v1.json'
    if output.exists():raise FileExistsError('Preserve existing proposal')
    runner_sha=common.sha(PROJECT/'execution/runner.py')
    adapters={method:common.tree_hash(PROJECT/'methods'/common.FOLDERS[method]) for method in common.METHODS}
    datasets={};jobs=[]
    for dataset,relative in DATASETS.items():
        source=PROJECT/relative
        rows=common.read_inputs(source)
        checksum=common.sha(source)
        datasets[dataset]=dict(input_relative=relative,input_sha256=checksum,input_bytes=source.stat().st_size,n=len(rows),
            windows_path=str(source),wsl_path=WSL+'/'+relative,node_staged_path=NODE+'/evaluation/stage/inputs/'+dataset+'.jsonl',
            gold_keys_detected=False,record_ids_unique=True)
        for method in common.METHODS:
            identity=common.signature(method,checksum,adapters[method])
            jobs.append(dict(dataset_id=dataset,method_id=method,input_sha256=checksum,n=len(rows),
                adapter_tree_sha256=adapters[method],signature=identity,
                cache_filename=dataset+'__'+method+'__X_'+identity[:16]+'.pkl',
                cache_generation_requires_models=False,placeholder_pKd=0.0))
    manifest=dict(schema=common.SCHEMA,status='PROPOSED_AWAITING_ROOT_CACHE_AUTHORIZATION',
        datasets=datasets,jobs=jobs,job_count=15,runner_sha256=runner_sha,
        no_gold_selection_or_weights_accessed=True,
        resource_proposal=dict(host='node23',max_parallel=8,cpu_per_job=1,nice=15,rss_watch_bytes=4*1024**3,
            timeout_seconds_per_job=1800,gpu_count=0,CUDA_VISIBLE_DEVICES='',global_deadline='same root 01:45Z; no reset'),
        node_runner=NODE+'/feature-cache-preparation/stage/runner.py',
        node_methods_root=NODE+'/feature-cache-preparation/stage/methods',
        consumer_runner=WSL+'/execution/runner.py',consumer_methods_root=WSL+'/methods',
        cache_generation_authorization_template=dict(root_cache_generation_authorized=False,manifest_sha256='FILL_AFTER_ROOT_REVIEW'),
        true_scoring_authorized=False,IgG13_included=False,
        provenance='Only fixed author X, raw input-byte identity and source hashes; no fitting and no true holdout predictions')
    common.write_json(output,manifest)
    print('Proposed 15 caches; manifest SHA '+common.sha(output)+'; no cache generation launched.')
if __name__=='__main__':main()
