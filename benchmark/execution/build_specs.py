"""Generate 200 immutable per-seed fit specs / 400 candidates; never launch them."""
import argparse
from pathlib import Path
import runner

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--panels',required=True,help='JSON list of {split_id,directory} from prepared panels')
    parser.add_argument('--output',required=True)
    parser.add_argument('--run-root',required=True)
    parser.add_argument('--cache-root',required=True)
    parser.add_argument('--methods-root',required=True)
    parser.add_argument('--batch-size',type=int,choices=[32,64],required=True)
    parser.add_argument('--cpu-threads',type=int,choices=[1,2],required=True)
    parser.add_argument('--max-epochs',type=int,default=20)
    parser.add_argument('--patience',type=int,default=5)
    parser.add_argument('--device',choices=['cpu','cuda:0'],default='cpu')
    parser.add_argument('--gpu-explicitly-authorized',action='store_true')
    parser.add_argument('--gpu-allocator-budget-bytes',type=int,default=3*1024**3)
    args=parser.parse_args()
    if args.device!='cpu' and not args.gpu_explicitly_authorized:
        parser.error('cuda:0 requires --gpu-explicitly-authorized')
    panels=runner.read_json(args.panels)
    if len(panels)!=2:raise ValueError('Exactly two frozen cold panels required')
    output=Path(args.output).resolve()
    output.mkdir(parents=True,exist_ok=False)
    jobs=[]
    selections=[]
    for panel in panels:
        directory=Path(panel['directory']).resolve()
        manifest=runner.read_json(directory/'panel-manifest.json')
        if manifest['split_id']!=panel['split_id']:raise ValueError('Panel identity mismatch')
        for name,expected in manifest['files'].items():runner.require_hash(directory/name,expected)
        label_path=directory/'sealed-test-labels.jsonl' if 'sealed-test-labels.jsonl' in manifest['files'] else Path(manifest['sealed_label_source']).resolve()
        label_hash=manifest['files'].get('sealed-test-labels.jsonl') or manifest['sealed_label_source_sha256']
        scoring=dict(split_id=panel['split_id'],holdout_id='internal-test',
                     input_rows=str(directory/'test-inputs.jsonl'),
                     label_rows=str(label_path),
                     input_rows_sha256=manifest['files']['test-inputs.jsonl'],
                     label_rows_sha256=label_hash,
                     output_root=str(Path(args.run_root)/'scores'/panel['split_id']),
                     selection_barrier_path=str(Path(args.run_root)/'all-selections-frozen.json'),
                     methods_root=args.methods_root,cpu_threads=args.cpu_threads,batch_size=args.batch_size,
                     device=args.device,gpu_explicitly_authorized=args.gpu_explicitly_authorized,
                     gpu_allocator_budget_bytes=args.gpu_allocator_budget_bytes if args.device!='cpu' else None,
                     scientific_external_status='internal heldout partition, not an independent external source')
        runner.write_json(output/(panel['split_id']+'-score.json'),scoring)
        for method in runner.FORMAL_METHOD_IDS:
            for regime in ('NC_only','standard_only'):
                for seed in range(10):
                    key=f"{panel['split_id']}__{method}__{regime}__seed-{seed}"
                    spec=dict(method_id=method,split_id=panel['split_id'],regime=regime,seed=seed,
                              validation_scope='same_as_regime',max_epochs=args.max_epochs,patience=args.patience,
                              batch_size=1 if method=='MRBDTA' else args.batch_size,
                              gradient_accumulation=8 if method=='MRBDTA' else 1,
                              cpu_threads=args.cpu_threads,device=args.device,y_standardize=False,
                              gpu_explicitly_authorized=args.gpu_explicitly_authorized,
                              gpu_allocator_budget_bytes=args.gpu_allocator_budget_bytes if args.device!='cpu' else None,
                              train_rows=str(directory/'train.jsonl'),validation_rows=str(directory/'validation.jsonl'),
                              train_rows_sha256=manifest['files']['train.jsonl'],
                              validation_rows_sha256=manifest['files']['validation.jsonl'],
                              methods_root=args.methods_root,run_root=str(Path(args.run_root)/'fits'/key),
                              cache_root=args.cache_root,candidates=runner.HYPERPARAMETERS)
                    runner.validate_fit_spec(spec)
                    spec_path=output/(key+'.json')
                    runner.write_json(spec_path,spec)
                    for index in (0,1):jobs.append(dict(job_id=key+'__candidate-'+str(index),
                        argv=['runner.py','fit','--spec',str(spec_path),'--candidate-index',str(index)],
                        spec_path=str(spec_path),spec_sha256=runner.sha_file(spec_path),candidate_index=index))
                    selections.append(dict(spec_path=str(spec_path),selection_path=str(Path(spec['run_root'])/'selection.json')))
    index=dict(candidate_fits=jobs,per_seed_selections=selections,total_fits=len(jobs),total_selections=len(selections),
               max_epochs=args.max_epochs,patience=args.patience,validation_scope='same_as_regime',
               formal_method_ids=runner.FORMAL_METHOD_IDS,device=args.device,cpu_threads=args.cpu_threads,
               regime_interpretation='standard-only transfer is selected without NC validation labels',
               launched=False)
    runner.write_json(output/'execution-index.json',index)
    print(f'Generated {len(jobs)} candidate fits and {len(selections)} per-seed selections; no processes launched.')

if __name__=='__main__':main()
