"""Incrementally copy completed CPU caches without overwriting different bytes."""
from pathlib import Path
import hashlib
import json
import os
import shlex
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
PROJECT=HERE.parent
DEST=(PROJECT/'encoded-cache-v3').resolve()
REMOTE='/data/qlyu/projects/peptide-binding-nc-benchmark-20261021/feature-cache-preparation'
PYTHON='/data/qlyu/projects/peptide-binding-benchmark-20261020/common-prior-methods-20261021/.venv/bin/python'
REMOTE_QUERY="""from pathlib import Path
import json
p=Path(%r)
receipts=[]
for f in (p/'receipts').glob('*.json'):
 try:
  d=json.loads(f.read_text())
  if d.get('stage')=='feature_preprocessing_only':receipts.append(d)
 except (OSError,json.JSONDecodeError):pass
processes=[]
for f in (p/'receipts').glob('*.process.json'):
 try:processes.append(json.loads(f.read_text()))
 except (OSError,json.JSONDecodeError):pass
print(json.dumps(dict(receipts=receipts,processes=processes,pool_complete=(p/'pool-complete.json').exists())))
"""%REMOTE

def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda:handle.read(1024**2),b''):digest.update(block)
    return digest.hexdigest()
def write(path,obj):
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf-8')
    temporary.replace(path)
def persist(index):
    index['updated_unix']=time.time()
    index['ready_cells']=[key for key,row in index['by_cell'].items() if row['status']=='materialized_producer_verified']
    index['ready_cell_count']=len(index['ready_cells'])
    write(HERE/'cache-index.json',index)
    write(DEST/'cache-index.json',index)
def main():
    if os.name!='nt':raise RuntimeError('Windows no-overwrite rename semantics required')
    if DEST.is_symlink() or DEST!=PROJECT.resolve()/'encoded-cache-v3':raise ValueError('Unexpected destination')
    DEST.mkdir(exist_ok=True)
    downloads=HERE/'downloads';downloads.mkdir(exist_ok=True)
    manifest=json.loads((HERE/'stage-manifest.json').read_text(encoding='utf-8'))
    index=dict(schema='feature-cache-index-v1',scope='fixed author CPU feature encoding, no models fit',
        source_gpu_spec_index_sha256=manifest['source_gpu_index_sha256'],expected_cells=20,
        consumer_torch_abi_verified=False,consumer_note='GPU runner must independently unpickle and verify signature/adapter hash; never relabel producer runtime',
        by_cell={},processes=[],producer='node23 Torch2.6/PyG2.6.1/RDKit2024.03.2')
    if (HERE/'cache-index.json').exists():
        previous=json.loads((HERE/'cache-index.json').read_text(encoding='utf-8'))
        if previous['source_gpu_spec_index_sha256']!=manifest['source_gpu_index_sha256']:
            raise ValueError('Existing synchronization index belongs to different frozen GPU specs')
        index=previous
    started=time.time()
    persist(index)
    while time.time()-started<2100:
        result=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=20','node23',
            PYTHON+' -c '+shlex.quote(REMOTE_QUERY)],capture_output=True,text=True,encoding='utf-8',timeout=40)
        if result.returncode:
            print('Metadata transport retry: '+result.stderr[:300],flush=True)
            time.sleep(10);continue
        state=json.loads(result.stdout)
        for receipt in state['receipts']:
            cell=receipt['cell_id']
            if cell in index['by_cell']:continue
            entry=dict(status='materialized_producer_verified',method_id=receipt['method_id'],split_id=receipt['split_id'],
                regime=receipt['regime'],producer_versions=receipt['producer_versions'],adapter_tree_sha256=receipt['adapter_tree_sha256'],
                input_sha256=receipt['input_sha256'],outputs=[],consumer_abi_verified=False,model_fits=0)
            if receipt.get('completion_type'):
                entry['completion_type']=receipt['completion_type']
                entry['linked_original_failure']=receipt['original_failure']
                entry['train_cache_sha256_unchanged']=receipt['train_cache_sha256_unchanged']
            for output in receipt['outputs']:
                name=output['filename']
                if Path(name).name!=name or not name.endswith(('.pkl','.input-audit.jsonl')):
                    raise ValueError('Unexpected cache filename '+name)
                destination=DEST/name
                if destination.resolve().parent!=DEST:raise ValueError('Destination escaped cache directory')
                if destination.exists():
                    existing=sha(destination)
                    if existing!=output['sha256']:
                        entry['status']='existing_different_sha_preserved'
                        entry['outputs'].append(dict(**output,local_path=str(destination),existing_sha256=existing,adopted=False))
                        continue
                else:
                    temporary=downloads/(name+'.part')
                    copy=subprocess.run(['scp','node23:'+output['path'],str(temporary)],capture_output=True,text=True,timeout=300)
                    if copy.returncode or sha(temporary)!=output['sha256'] or temporary.stat().st_size!=output['bytes']:
                        raise RuntimeError('Transfer or checksum failed for '+name+': '+copy.stderr[:500])
                    # Windows rename fails if destination appeared; never overwrite a racing GPU cache.
                    try:temporary.rename(destination)
                    except FileExistsError:
                        existing=sha(destination)
                        if existing!=output['sha256']:
                            entry['status']='existing_different_sha_preserved'
                            entry['outputs'].append(dict(**output,local_path=str(destination),existing_sha256=existing,adopted=False))
                            continue
                entry['outputs'].append(dict(**output,local_path=str(destination),
                    wsl_path='/mnt/d/work/科研工作台/research-tasks/peptide-binding-nc-benchmark-20261021/encoded-cache-v3/'+name,adopted=True))
            index['by_cell'][cell]=entry
            write(HERE/(cell+'.producer-receipt.json'),receipt)
            persist(index)
            print('SYNC '+cell+' '+entry['status'],flush=True)
        index['processes']=state['processes']
        persist(index)
        if state['pool_complete']:
            index['pool_complete']=True
            index['completed_producer_cells']=len(state['receipts'])
            index['failed_cells']=[row for row in state['processes'] if row['status']!='completed']
            persist(index)
            print('Producer pool complete: '+str(index['ready_cell_count'])+'/20 cells materialized',flush=True)
            return
        time.sleep(10)
    index['sync_timeout']=True;persist(index)
    raise TimeoutError('Bounded synchronization window expired; preserved all partial evidence')
if __name__=='__main__':main()
