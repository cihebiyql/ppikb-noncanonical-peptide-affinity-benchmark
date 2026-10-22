"""Freeze train/validation-only feature-preparation inputs; no model execution."""
from pathlib import Path
import hashlib
import json
import shutil

HERE=Path(__file__).resolve().parent
PROJECT=HERE.parent
WSL='/mnt/d/work/科研工作台/research-tasks/peptide-binding-nc-benchmark-20261021'
NODE='/data/qlyu/projects/peptide-binding-nc-benchmark-20261021'
REMOTE=NODE+'/feature-cache-preparation'
FOLDERS={'GraphDTA-GIN':'graphdta-deepnc','DeepNC-GEN':'graphdta-deepnc','MGraphDTA':'mgraph-dgdta','DGDTA-CL':'mgraph-dgdta','GS-DTA':'gs-dta'}
PYTHON='/data/qlyu/projects/peptide-binding-benchmark-20261020/common-prior-methods-20261021/.venv/bin/python'

def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda:handle.read(1024**2),b''):digest.update(block)
    return digest.hexdigest()
def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf-8')
def tree_hash(root):
    entries=[(str(path.relative_to(root)).replace('\\','/'),sha(path)) for path in sorted(root.rglob('*.py')) if '__pycache__' not in path.parts]
    return hashlib.sha256(json.dumps(entries,separators=(',',':')).encode()).hexdigest()
def main():
    stage=HERE/'stage'
    stage.mkdir(exist_ok=False)
    write(HERE/'resource-contract.json',dict(stage='fixed_author_feature_preparation_only',host='node23',python=PYTHON,
        max_parallel=16,cpu_per_job=1,nice=15,rss_bytes_per_job=4*1024**3,pool_rss_bytes=64*1024**3,
        timeout_per_job_seconds=1800,gpu_count=0,CUDA_VISIBLE_DEVICES='',
        no_model_construction=True,no_optimizer=True,no_test_or_external_label_files_staged=True,
        stopping='owned PGID terminated on timeout/RSS excess; failed receipts preserved',
        destination='D:/work/科研工作台/research-tasks/peptide-binding-nc-benchmark-20261021/encoded-cache-v3'))
    shutil.copy2(PROJECT/'execution/runner.py',stage/'runner.py')
    snapshots={}
    for folder in sorted(set(FOLDERS.values())):
        src=PROJECT/'methods'/folder
        dest=stage/'methods'/folder
        for path in src.rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix in ('.py','.json'):
                relative=path.relative_to(src)
                (dest/relative).parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(path,dest/relative)
        assert tree_hash(src)==tree_hash(dest)
        snapshots[folder]=dict(adapter_tree_sha256=tree_hash(src),snapshot_relative=str(dest.relative_to(HERE)))
    specs=PROJECT/'execution/formal-specs-gpu-v3'
    index=json.loads((specs/'execution-index.json').read_text(encoding='utf-8'))
    jobs=[]
    copied=set()
    for entry in index['per_seed_selections']:
        source=specs/Path(entry['spec_path']).name
        original=json.loads(source.read_text(encoding='utf-8'))
        if original['seed']!=0:continue
        cell='__'.join([original['split_id'],original['method_id'],original['regime']])
        derived=dict(original)
        for key in ('train_rows','validation_rows'):
            source_data=PROJECT/Path(original[key][len(WSL)+1:])
            if sha(source_data)!=original[key+'_sha256']:raise ValueError('Frozen data changed '+str(source_data))
            relative=Path('inputs')/original['split_id']/source_data.name
            if str(relative) not in copied:
                (stage/relative).parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(source_data,stage/relative)
                copied.add(str(relative))
            derived[key]=REMOTE+'/stage/'+relative.as_posix()
        derived.update(device='cpu',gpu_explicitly_authorized=False,gpu_allocator_budget_bytes=None,cpu_threads=1,
            methods_root=REMOTE+'/stage/methods',cache_root=NODE+'/encoded-cache-v3',
            run_root=REMOTE+'/no-fit-output/'+cell)
        write(stage/'specs'/(cell+'.json'),derived)
        contract=dict(cell_id=cell,method_id=original['method_id'],split_id=original['split_id'],regime=original['regime'],
            original_gpu_spec_sha256=sha(source),derived_spec_sha256=sha(stage/'specs'/(cell+'.json')),
            spec_path=REMOTE+'/stage/specs/'+cell+'.json',python=PYTHON,cpu_threads=1,nice=15,
            rss_bytes=4*1024**3,timeout_seconds=1800,cache_root=NODE+'/encoded-cache-v3',
            input_sha256={key:original[key+'_sha256'] for key in ('train_rows','validation_rows')},
            adapter_tree_sha256=snapshots[FOLDERS[original['method_id']]]['adapter_tree_sha256'],
            CUDA_VISIBLE_DEVICES='',stage='feature_cache_only_no_fit',record_scope='train and validation labels only')
        write(HERE/'contracts'/(cell+'.json'),contract)
        jobs.append(dict(cell_id=cell,contract_path=REMOTE+'/contracts/'+cell+'.json',contract_relative='contracts/'+cell+'.json'))
    assert len(jobs)==20 and len({job['cell_id'] for job in jobs})==20
    write(HERE/'stage-manifest.json',dict(jobs=jobs,count=20,source_gpu_index_sha256=sha(specs/'execution-index.json'),
        runner_sha256=sha(stage/'runner.py'),snapshots=snapshots,inputs={rel:sha(stage/rel) for rel in copied},
        resource_contract_sha256=sha(HERE/'resource-contract.json'),no_test_or_external_files_copied=True))
    print('Staged 20 cache-only specifications, 4 train/validation files, frozen Python snapshots; no jobs launched.')
if __name__=='__main__':main()
