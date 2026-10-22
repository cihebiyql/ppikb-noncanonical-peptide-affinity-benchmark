"""Verify feature bytes, frozen GPU spec ancestry, and preprocessing receipts."""
from pathlib import Path
import hashlib
import json

HERE=Path(__file__).resolve().parent
PROJECT=HERE.parent
FOLDERS={'GraphDTA-GIN':'graphdta-deepnc','DeepNC-GEN':'graphdta-deepnc','MGraphDTA':'mgraph-dgdta','DGDTA-CL':'mgraph-dgdta','GS-DTA':'gs-dta'}
def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda:handle.read(1024**2),b''):digest.update(block)
    return digest.hexdigest()
def tree_hash(root):
    entries=[(str(path.relative_to(root)).replace('\\','/'),sha(path)) for path in sorted(root.rglob('*.py')) if '__pycache__' not in path.parts]
    return hashlib.sha256(json.dumps(entries,separators=(',',':')).encode()).hexdigest()
def main():
    index=json.loads((HERE/'cache-index.json').read_text(encoding='utf-8'))
    source=json.loads((PROJECT/'execution/formal-specs-gpu-v3/execution-index.json').read_text(encoding='utf-8'))
    expected_specs={Path(row['spec_path']).name:row['spec_sha256'] for row in source['candidate_fits']}
    files=[];rows=[];errors=[]
    if index['ready_cell_count']!=20:errors.append('Not all 20 cells materialized')
    for cell,entry in index['by_cell'].items():
        receipt=json.loads((HERE/(cell+'.producer-receipt.json')).read_text(encoding='utf-8'))
        contract=json.loads((HERE/'contracts'/(cell+'.json')).read_text(encoding='utf-8'))
        filename=cell+'__seed-0.json'
        if contract['original_gpu_spec_sha256']!=expected_specs[filename]:errors.append(cell+': original spec hash mismatch')
        if tree_hash(PROJECT/'methods'/FOLDERS[entry['method_id']])!=entry['adapter_tree_sha256']:
            errors.append(cell+': current GPU Python source tree differs from producer snapshot')
        if receipt['model_construction_calls'] or receipt['optimizer_steps'] or receipt['test_label_reads'] or receipt['external_label_reads']:
            errors.append(cell+': scope violation')
        for output in entry['outputs']:
            path=Path(output['local_path'])
            if not output['adopted']:
                errors.append(cell+': different existing bytes retained, not adopted');continue
            if path.resolve().parent!=(PROJECT/'encoded-cache-v3').resolve():errors.append(cell+': unsafe path')
            if sha(path)!=output['sha256'] or path.stat().st_size!=output['bytes']:
                errors.append(cell+': materialized output hash mismatch '+path.name)
            files.append(dict(filename=path.name,bytes=output['bytes'],sha256=output['sha256']))
            if path.name.endswith('.input-audit.jsonl'):
                audits=[json.loads(line) for line in path.open(encoding='utf-8') if line.strip()]
                rows.append(dict(cell_id=cell,file=path.name,n=len(audits)))
    process=index.get('processes',[])
    result=dict(status='passed' if not errors else 'needs_attention',errors=errors,cells=len(index['by_cell']),
        ready_cells=index['ready_cell_count'],files_verified=len(files),total_bytes=sum(row['bytes'] for row in files),
        input_audit_row_counts=rows,producer_processes=len(process),
        all_producer_exits_zero=len(process)==20 and all(row['returncode']==0 for row in process),
        preserved_original_failures=[row for row in process if row['returncode']!=0],
        recovered_v2_cells=[cell for cell,entry in index['by_cell'].items() if entry.get('completion_type')=='validation-cache-completion-v2'],
        conservative_sum_all_job_peak_rss_bytes=sum(row['peak_rss_bytes'] for row in process),
        max_job_seconds=max((row['seconds'] for row in process),default=None),
        max_job_rss_bytes=max((row['peak_rss_bytes'] for row in process),default=None),
        model_fits=0,optimizer_steps=0,test_or_external_label_reads_by_workers=0,
        consumer_pickle_abi_and_signature_verification='root GPU runner responsibility, no producer claim',
        producer_versions=sorted({json.dumps(entry['producer_versions'],sort_keys=True) for entry in index['by_cell'].values()}),
        source_gpu_spec_index_sha256=sha(PROJECT/'execution/formal-specs-gpu-v3/execution-index.json'))
    (HERE/'materialization-verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
