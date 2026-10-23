"""Independent source/vector/index/terminal audit of completed frozen feature chunks, no forward."""
import hashlib
import json
from pathlib import Path
import numpy as np

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];RUN=ROOT/'runs/plm-classification-contact-v1'
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1024**2),b''):h.update(b)
    return h.hexdigest()
def load(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def main():
    binding=load(HERE/'feature-cache-binding.json');contract=load(HERE/'feature-contract.json')
    path=ROOT/binding['mean_relative_path'];assert sha(path)==binding['mean_sha256']
    archive=np.load(path,allow_pickle=False);values,ids=archive['embeddings'],archive['sequence_ids']
    assert values.shape==(25912,320) and values.dtype==np.float32 and np.isfinite(values).all()
    lookup={str(key):i for i,key in enumerate(ids)};assert len(lookup)==len(ids)
    jobs=[json.loads(line) for line in (HERE/'inputs/missing-representations.jsonl').read_text(encoding='utf-8').splitlines()]
    reused=load(HERE/'inputs/old-cache-reuse.json');oldpath=ROOT/'baselines/plm-simple-v1/feature-cache-cpu-v3/embeddings.npz'
    assert sha(oldpath)==reused['old_cache_sha256'];old=np.load(oldpath,allow_pickle=False);oldvalues=old['embeddings'];oldids=old['sequence_ids']
    for item in reused['vectors']:
        key=item['sequence_id'];index=item['source_row_index'];assert str(oldids[index])==key
        assert hashlib.sha256(oldvalues[index].tobytes()).hexdigest()==item['source_vector_sha256']
        np.testing.assert_array_equal(values[lookup[key]],oldvalues[index])
    checked_means=0;checked_tokens=0;terminal=[];residue_arrays={}
    chunks=(len(jobs)+contract['chunk_size']-1)//contract['chunk_size']
    for chunk in range(chunks):
        expected=jobs[chunk*contract['chunk_size']:(chunk+1)*contract['chunk_size']]
        directory=RUN/'feature-chunks'/f'chunk-{chunk:03d}';receipt=load(directory/'receipt.json')
        assert receipt['contract_sha256']==sha(HERE/'feature-contract.json') and receipt['model_sha256']==binding['model_sha256']
        checks=load(directory/'token-and-representation-checks.json')
        assert [r['sequence_id'] for r in checks]==[r['sequence_id'] for r in expected]
        for item,check in zip(expected,checks):
            assert hashlib.sha256(item['sequence'].encode('ascii')).hexdigest()==item['sequence_id']
            assert len(item['sequence'])==check['length'] and check['tokens']==check['length']+2
            assert check['mean_extracted']==item['need_mean'] and check['residues_extracted']==item['need_residue'];checked_tokens+=1
        source_path=directory/'means.npz';assert sha(source_path)==receipt['means_sha256']
        source=np.load(source_path,allow_pickle=False);source_values,source_ids=source['means'],source['sequence_ids']
        assert list(source_ids)==[r['sequence_id'] for r in expected if r['need_mean']]
        for index,key in enumerate(source_ids):
            np.testing.assert_array_equal(values[lookup[str(key)]],source_values[index]);checked_means+=1
        process_candidates=[load(p) for p in (RUN/'resource-supervision').glob(f'chunk-{chunk:03d}*/process-receipt.json')]
        matches=[p for p in process_candidates if p['pid']==receipt['pid']]
        assert len(matches)==1
        process=matches[0]
        assert process['exit_code']==0 and process['worker_pid_absent'] and not process['surviving_group_pids']
        assert process['peak_rss_bytes']<=3*1024**3
        terminal.append({'chunk':chunk,'pid':process['pid'],'peak_rss_bytes':process['peak_rss_bytes'],'exit_code':process['exit_code']})
    for key,info in binding['residue_sources'].items():
        path=ROOT/info['relative_path'];assert sha(path)==info['sha256'];obj=np.load(path,allow_pickle=False)
        sequence=str(obj['sequence'].item());array=obj['residues'];assert hashlib.sha256(sequence.encode('ascii')).hexdigest()==key
        assert array.shape==(len(sequence),320) and array.dtype==np.float32 and np.isfinite(array).all()
        np.testing.assert_array_equal(obj['positions1'],np.arange(1,len(sequence)+1))
        residue_arrays[key]=(sequence,array)
    proof=load(HERE/'inputs/contact-sequence-index-proof.json')
    for row in proof:
        sequence,_=residue_arrays[row['target_sequence_id']];index=row['residue_index1']
        assert sequence[index-1]==row['target_residue_aa']==row['observed_chain_residue_aa']
        assert row['peptide_sequence_id'] in lookup and row['substring_occurrences']==1
    canary=load(RUN/'feature-canary-v1/receipt.json');canary_means=np.load(RUN/'feature-canary-v1/means.npz',allow_pickle=False)
    for index,key in enumerate(canary_means['sequence_ids']):np.testing.assert_array_equal(values[lookup[str(key)]],canary_means['means'][index])
    for item in canary['residue_sequences']:
        obj=np.load(RUN/'feature-canary-v1'/('residues-'+item['sequence_id']+'.npz'),allow_pickle=False)
        np.testing.assert_array_equal(residue_arrays[item['sequence_id']][1],obj['residues'])
    report={'passed':checked_tokens==25336 and checked_means==25290 and len(proof)==8625,
        'old_mean_exact_bytes_checked':len(reused['vectors']),'new_mean_exact_bytes_checked':checked_means,
        'token_checks':checked_tokens,'per_residue_sequence_checks':len(residue_arrays),'row_index_AA_proofs_checked':len(proof),
        'canary_mean_vectors_exact':len(canary_means['sequence_ids']),'canary_residue_matrices_exact':len(canary['residue_sequences']),
        'terminal_chunks':terminal,'new_fit_count':0,'new_forward_count':0,'label_or_coordinate_files_opened':0,'code_sha256':sha(__file__)}
    (HERE/'independent-cache-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k!='terminal_chunks'}))
    assert report['passed']
if __name__=='__main__':main()
