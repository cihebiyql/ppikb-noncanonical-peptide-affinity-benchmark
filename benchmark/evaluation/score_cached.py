"""Authorized blind-first scoring from immutable label-free fixed-author X."""
from pathlib import Path
import argparse
import hashlib
import json
import time
import common
import feature_cache
import metrics_stable

HERE=Path(__file__).resolve().parent

def code_hashes():return {name:common.sha(HERE/name) for name in ('common.py','feature_cache.py','score_cached.py','metrics_stable.py')}

def authorize(path,phase):
    authorization=common.read_json(path)
    if authorization.get('root_scoring_authorized') is not True or phase not in authorization.get('allowed_phases',[]):
        raise PermissionError('Explicit root post-barrier scoring authorization required')
    if authorization.get('evaluation_code_sha256')!=code_hashes():raise ValueError('Evaluation code changed after authorization')
    return authorization

def verify_barrier(authorization_path,barrier_path,execution_index_path,output_path):
    authorization=authorize(authorization_path,'barrier_audit')
    if common.sha(barrier_path)!=authorization['barrier_sha256'] or common.sha(execution_index_path)!=authorization['execution_index_sha256']:
        raise ValueError('Authorized global barrier/index SHA mismatch')
    barrier=common.read_json(barrier_path)
    if barrier['status']!='all_selections_frozen' or barrier['selection_count']!=200 or barrier['candidate_fit_count']!=400 or len(barrier['selections'])!=200:
        raise ValueError('Complete 200-selection barrier required before accessing selected files')
    index=common.read_json(execution_index_path)
    if barrier['execution_index_sha256']!=common.sha(execution_index_path) or index['total_fits']!=400 or index['total_selections']!=200:
        raise ValueError('Wrong frozen execution plan')
    expected_specs={entry['selection_path']:entry['spec_path'] for entry in index['per_seed_selections']}
    if set(expected_specs)!={entry['path'] for entry in barrier['selections']}:raise ValueError('Barrier selection paths differ from full plan')
    identities=set();verified=[]
    for entry in barrier['selections']:
        path=entry['path']
        if common.sha(path)!=entry['sha256']:raise ValueError('Selection mutated '+path)
        selection=common.read_json(path)
        identity=tuple(selection[key] for key in ('method_id','split_id','regime','seed'))
        if identity in identities:raise ValueError('Duplicate selected experimental cell')
        identities.add(identity)
        if selection['status']!='frozen' or selection['holdout_metrics_consulted']:
            raise ValueError('Selection is not validation-only frozen')
        if len(selection['candidates'])!=2 or any(c['status']!='complete' for c in selection['candidates']):
            raise ValueError('Both preregistered hyperparameter candidates must complete')
        if {candidate['candidate_index'] for candidate in selection['candidates']}!={0,1}:
            raise ValueError('Missing one of the two preregistered configurations')
        winner=min(selection['candidates'],key=lambda candidate:(candidate['best_validation_MAE'],candidate['candidate_index']))
        if selection['candidate_index']!=winner['candidate_index'] or selection['checkpoint_sha256']!=winner['checkpoint_sha256']:
            raise ValueError('Selected candidate is not the validation-MAE winner')
        if selection['fit_spec_sha256']!=common.sha(expected_specs[path]):raise ValueError('Selected fit spec changed')
        fit_spec=common.read_json(expected_specs[path])
        if tuple(fit_spec[key] for key in ('method_id','split_id','regime','seed'))!=identity:
            raise ValueError('Selected coordinates differ from frozen fit specification')
        if common.sha(selection['checkpoint'])!=selection['checkpoint_sha256']:raise ValueError('Selected checkpoint changed')
        verified.append(dict(path=path,sha256=entry['sha256'],method_id=identity[0],split_id=identity[1],
            regime=identity[2],seed=identity[3],checkpoint_sha256=selection['checkpoint_sha256'],fit_spec_sha256=selection['fit_spec_sha256']))
    panels={identity[1] for identity in identities}
    expected={(method,panel,regime,seed) for method in common.METHODS for panel in panels
              for regime in ('NC_only','standard_only') for seed in range(10)}
    if len(panels)!=2 or identities!=expected:raise ValueError('Incomplete five-method/two-panel/two-regime/ten-seed grid')
    if Path(output_path).exists():raise FileExistsError('Preserve existing barrier audit')
    receipt=dict(status='all_200_selections_and_checkpoints_verified',selections=verified,
        barrier_sha256=common.sha(barrier_path),execution_index_sha256=common.sha(execution_index_path),
        evaluation_code_sha256=code_hashes(),authorization_sha256=common.sha(authorization_path),
        gold_reads=0,model_forwards=0,created_unix=time.time(),
        boundary='Immutable file receipts and current-selection recheck; procedural, not an OS security guarantee')
    common.write_json(output_path,receipt)
    return receipt

def validate_gate(authorization_path,barrier_path,audit_path,selection_path,score_spec_path):
    authorization=authorize(authorization_path,'score')
    if common.sha(score_spec_path) not in authorization.get('allowed_score_spec_sha256',[]):
        raise PermissionError('Root did not authorize this exact scoring contract')
    if common.sha(barrier_path)!=authorization['barrier_sha256'] or common.sha(audit_path)!=authorization['barrier_audit_sha256']:
        raise ValueError('Global freeze or independent full-grid audit changed')
    barrier=common.read_json(barrier_path);audit=common.read_json(audit_path)
    if barrier.get('status')!='all_selections_frozen' or barrier.get('selection_count')!=200 or len(barrier.get('selections',[]))!=200:
        raise ValueError('Complete 200-selection barrier absent')
    if audit['status']!='all_200_selections_and_checkpoints_verified' or len(audit['selections'])!=200:
        raise ValueError('Full-grid checkpoint audit absent')
    if audit['barrier_sha256']!=authorization['barrier_sha256'] or audit['execution_index_sha256']!=authorization['execution_index_sha256']:
        raise ValueError('Audited barrier lineage mismatch')
    if audit['evaluation_code_sha256']!=code_hashes():raise ValueError('Scorer changed since full-grid audit')
    selection_hash=common.sha(selection_path)
    matches=[entry for entry in audit['selections'] if entry['path']==str(selection_path) and entry['sha256']==selection_hash]
    if len(matches)!=1:raise ValueError('Current selection not in verified global barrier')
    selection=common.read_json(selection_path)
    if selection['status']!='frozen' or selection['holdout_metrics_consulted']:raise ValueError('Invalid selected model')
    if common.sha(selection['checkpoint'])!=selection['checkpoint_sha256'] or selection['checkpoint_sha256']!=matches[0]['checkpoint_sha256']:
        raise ValueError('Current selected weights changed')
    return authorization,selection

def state_fingerprint(model):
    digest=hashlib.sha256()
    for name,tensor in sorted(model.state_dict().items()):
        digest.update(name.encode());digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()

def _join_gold_after_blind(spec,output,rows,blind,blind_hash):
    """Internal post-gate helper; first gold access requires persisted blind proof."""
    output=Path(output)
    proof=common.read_json(output/'blind-complete.json')
    if proof['blind_predictions_sha256']!=blind_hash or common.sha(output/'blind-predictions.jsonl')!=blind_hash:
        raise ValueError('Blind prediction proof absent or changed before gold access')
    if common.sha(spec['gold_rows'])!=spec['gold_rows_sha256']:raise ValueError('Authorized gold source changed')
    desired={row['record_id'] for row in rows};labels={}
    with Path(spec['gold_rows']).open(encoding='utf-8-sig') as handle:
        for line in handle:
            if not line.strip():continue
            row=json.loads(line)
            if row['record_id'] in desired:
                if row['record_id'] in labels:raise ValueError('Duplicate requested gold ID')
                labels[row['record_id']]=float(row['pKd'])
    if set(labels)!=desired:raise ValueError('Gold/cache input coverage mismatch')
    if common.sha(output/'blind-predictions.jsonl')!=blind_hash:raise ValueError('Blind predictions changed before joining gold')
    joined=[dict(row,pKd_true=labels[row['record_id']],residual=row['pKd_pred']-labels[row['record_id']]) for row in blind]
    return labels,joined

def score(authorization_path,barrier_path,audit_path,selection_path,score_spec_path):
    authorization,selection=validate_gate(authorization_path,barrier_path,audit_path,selection_path,score_spec_path)
    spec=common.read_json(score_spec_path)
    if spec['method_id']!=selection['method_id']:raise ValueError('Selected method differs from cached method')
    if spec.get('selection_split_id') not in (None,selection['split_id']):raise ValueError('Wrong source panel')
    if common.sha(spec['runner'])!=authorization['runner_sha256']:raise ValueError('Frozen runner changed')
    if common.sha(spec['cache_manifest'])!=spec['cache_manifest_sha256']:raise ValueError('X cache manifest changed')
    if common.sha(spec['input_rows'])!=spec['input_rows_sha256']:raise ValueError('Input bytes changed')
    runner=common.load_runner(spec['runner'],authorization['runner_sha256'])
    device_receipt=runner.configure_device(spec)
    runner.seed_everything(selection['seed'],int(spec.get('cpu_threads',2)))
    adapter=runner.load_adapter(selection['method_id'],spec['methods_root'])
    if runner.adapter_tree_hash(adapter)!=spec['adapter_tree_sha256']:raise ValueError('Scoring author code changed')
    y_proof=common.read_json(spec['forward_y_proof'])
    if common.sha(spec['forward_y_proof'])!=spec['forward_y_proof_sha256'] or y_proof['status']!='passed':
        raise ValueError('Independent no-y-forward proof absent')
    proof=[entry for entry in y_proof['methods'] if entry['method_id']==selection['method_id']]
    if len(proof)!=1 or proof[0]['adapter_tree_sha256']!=spec['adapter_tree_sha256'] or not proof[0]['forward_y_independent']:
        raise ValueError('No-y-forward proof belongs to different code')
    rows,items,metadata=feature_cache.load_cache(runner,adapter,spec['cache_manifest'],spec['cache_path'],spec['input_rows'],selection['method_id'])
    internal_panel={'source_test':'source_peptide_dependency_cold','target_test':'target_reference_homology_cold'}
    if metadata['dataset_id'] in internal_panel and selection['split_id']!=internal_panel[metadata['dataset_id']]:
        raise ValueError('Internal X cache belongs to a different frozen test panel')
    import torch
    checkpoint=torch.load(selection['checkpoint'],map_location='cpu',weights_only=True)
    if checkpoint['adapter_tree_sha256']!=spec['adapter_tree_sha256'] or checkpoint['fit_spec_sha256']!=selection['fit_spec_sha256']:
        raise ValueError('Checkpoint source/spec lineage changed')
    if checkpoint['method_id']!=selection['method_id'] or checkpoint['seed']!=selection['seed']:
        raise ValueError('Checkpoint identity mismatch')
    model=runner.native_model(adapter,selection['method_id'])
    model.load_state_dict(checkpoint['model_state'],strict=True)
    before=state_fingerprint(model)
    model.to(device=device_receipt['device'],dtype=torch.float32)
    dataset=spec['dataset_id']
    if not dataset or any(char in dataset for char in '/\\') or dataset in ('.','..'):raise ValueError('Unsafe dataset identifier')
    output=Path(spec['output_root'])/dataset/selection['split_id']/selection['method_id']/selection['regime']/('seed-'+str(selection['seed']))
    output.mkdir(parents=True,exist_ok=False)
    values=runner.predict_rows(adapter,model,items,device_receipt['device'],int(spec.get('batch_size',32)))
    if state_fingerprint(model)!=before:raise RuntimeError('Evaluation modified model state')
    blind=[]
    excluded={'peptide_smiles','canonical_isomeric_smiles','target_sequence','peptide_sequence','peptide_sequence_raw'}
    for row,value in zip(rows,values):
        record={key:val for key,val in row.items() if key not in excluded}
        record.update(pKd_pred=float(value),input_record_sha256=hashlib.sha256(json.dumps(row,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest())
        blind.append(record)
    runner.write_jsonl(output/'blind-predictions.jsonl',blind)
    blind_hash=common.sha(output/'blind-predictions.jsonl')
    common.write_json(output/'blind-complete.json',dict(stage='blind_predictions_persisted_before_gold_open',n=len(blind),
        blind_predictions_sha256=blind_hash,cache_sha256=metadata['cache_sha256'],selection_sha256=common.sha(selection_path),gold_reads=0))
    # First gold-byte access happens only after the full blind predictions are persisted.
    labels,joined=_join_gold_after_blind(spec,output,rows,blind,blind_hash)
    runner.write_jsonl(output/'predictions.jsonl',joined)
    metric_rows=[dict(row,pKd=labels[row['record_id']]) for row in rows]
    metrics=metrics_stable.grouped_metrics(metric_rows,values)
    common.write_json(output/'metrics.json',metrics)
    receipt=dict(status='complete',stage='post-selection-score-only',prediction_protocol='label-free cached X; blind first, gold later',
        method_id=selection['method_id'],split_id=selection['split_id'],regime=selection['regime'],seed=selection['seed'],
        holdout_id=dataset,holdout_kind=spec['holdout_kind'],n=len(rows),metrics=metrics,
        selection_sha256=common.sha(selection_path),checkpoint_sha256=selection['checkpoint_sha256'],
        barrier_sha256=common.sha(barrier_path),barrier_audit_sha256=common.sha(audit_path),
        authorization_sha256=common.sha(authorization_path),score_spec_sha256=common.sha(score_spec_path),
        input_sha256=spec['input_rows_sha256'],X_cache_sha256=metadata['cache_sha256'],cache_producer_versions=metadata['producer_versions'],
        blind_predictions_sha256=blind_hash,predictions_sha256=common.sha(output/'predictions.jsonl'),
        gold_source_sha256=spec['gold_rows_sha256'],device_receipt=device_receipt,no_parameter_updates=True,
        cached_y_constant_zero=True,true_gold_used_only_after_blind_file=True,
        metric_implementation='independent metrics_stable.py; exact all(x==x[0]) constant detection; undefined is null',
        external_67_8_2_or_supplement_subgroups='Independent review recomputes declared external subsets from retained flags; this receipt does not certify external independence')
    common.write_json(output/'complete.json',receipt)
    return receipt

def main():
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='command',required=True)
    audit=sub.add_parser('audit-barrier')
    for name in ('authorization','barrier','execution-index','output'):audit.add_argument('--'+name,required=True)
    scoring=sub.add_parser('score')
    for name in ('authorization','barrier','barrier-audit','selection','spec'):scoring.add_argument('--'+name,required=True)
    args=parser.parse_args()
    result=verify_barrier(args.authorization,args.barrier,args.execution_index,args.output) if args.command=='audit-barrier' else score(args.authorization,args.barrier,args.barrier_audit,args.selection,args.spec)
    print(json.dumps(result,allow_nan=False))
if __name__=='__main__':main()
