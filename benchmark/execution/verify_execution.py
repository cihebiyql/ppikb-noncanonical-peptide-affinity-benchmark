"""Read-only verification of generated execution grid and retained canary evidence."""
from pathlib import Path
import statistics
import runner

HERE=Path(__file__).resolve().parent
def main():
    index=runner.read_json(HERE/'formal-specs-v2/execution-index.json')
    assert index['total_fits']==400 and index['total_selections']==200
    assert len({job['job_id'] for job in index['candidate_fits']})==400
    data_hashes={}
    identities=set()
    counts={}
    for entry in index['per_seed_selections']:
        spec=runner.read_json(entry['spec_path'])
        runner.validate_fit_spec(spec)
        assert spec['cpu_threads']==1 and spec['validation_scope']=='same_as_regime'
        identity=tuple(spec[key] for key in ('method_id','split_id','regime','seed'))
        assert identity not in identities
        identities.add(identity)
        for key in ('train_rows','validation_rows'):
            if spec[key] not in data_hashes:
                data_hashes[spec[key]]=runner.sha_file(spec[key])
            assert data_hashes[spec[key]]==spec[key+'_sha256']
        key=(spec['split_id'],spec['regime'])
        if key not in counts:
            counts[key]=dict(train=len(runner.filter_scope(runner.read_jsonl(spec['train_rows']),spec['regime'])),
                             validation=len(runner.filter_scope(runner.read_jsonl(spec['validation_rows']),spec['regime'])))
    assert len(identities)==200
    canaries=[]
    total_seconds=0.
    for method in runner.METHOD_FOLDERS:
        receipt=runner.read_json(HERE/'canary-contracts-v1'/(method+'-receipt.json'))
        assert receipt['status']=='passed' and receipt['optimizer_steps']==4 and receipt['test_label_reads']==0
        step=statistics.mean(receipt['step_seconds'][1:])
        effective_batch=8 if method=='MRBDTA' else 32
        steps=sum((count['train']+effective_batch-1)//effective_batch for count in counts.values())
        estimate=step*steps*20*30 # two hyperparameters x ten seeds for each panel/regime
        total_seconds+=estimate
        canaries.append(dict(method_id=method,mean_last_three_step_seconds=step,
            max_rss_MiB=receipt['max_rss_kib']/1024,full_30_epoch_training_update_core_hours=estimate/3600))
    result=dict(status='passed',formal_fits_launched=False,candidate_fits=400,selections=200,
                execution_index_sha256=runner.sha_file(HERE/'formal-specs-v2/execution-index.json'),
                grid_unique=True,all_train_validation_file_hashes_verified=True,
                counts=[dict(split_id=key[0],regime=key[1],**value) for key,value in counts.items()],
                canaries=canaries,total_training_update_core_hours_full_budget=total_seconds/3600,
                lower_bound_16_parallel_wall_hours=total_seconds/3600/16,
                timing_scope='rough training-update extrapolation only; excludes validation/IO/encoding, heterogeneous input lengths, contention and early stopping',
                pending=['root freeze launch resource contract','stage canonical production methods folders','root authorize cache prewarm and formal launcher'])
    runner.write_json(HERE/'implementation-verification.json',result)
    print(result)

if __name__=='__main__':main()
