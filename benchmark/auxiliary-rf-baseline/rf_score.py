"""Future authorized RF scoring: joint NN200+RF40 gate, blind then gold."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import time
import numpy as np
import common
import rf_runner

def authorize(authorization_path,joint_path,selection_path,spec_path):
    auth=common.read(authorization_path)
    if auth.get('root_RF_holdout_score_authorized') is not True:raise PermissionError('Real RF holdout scoring not authorized')
    if common.sha(spec_path) not in auth.get('allowed_score_spec_sha256',[]):raise PermissionError('Unsigned RF score spec')
    if auth['source_sha256']!=rf_runner.source_hashes():raise ValueError('RF scoring implementation changed')
    common.require(joint_path,auth['joint_barrier_sha256'])
    joint=common.read(joint_path)
    if joint.get('status')!='all_200_NN_plus_40_RF_frozen' or joint.get('NN_selections')!=200 or joint.get('RF_selections')!=40:
        raise ValueError('Complete original NN200 AND independent RF40 joint barrier required')
    entries=joint.get('RF_selection_entries',[])
    if len(entries)!=40 or {(entry['panel'],entry['regime'],entry['seed']) for entry in entries}!={(p,r,s) for p in common.PANELS for r in common.REGIMES for s in range(10)}:
        raise ValueError('Joint barrier RF40 entries are incomplete')
    common.require(joint['NN_barrier_path'],joint['NN_barrier_sha256']);common.require(joint['RF_barrier_path'],joint['RF_barrier_sha256'])
    if joint.get('NN_execution_index_sha256')!=rf_runner.NN_APPROVED_INDEX_SHA:
        raise ValueError('Joint gate is not bound to the approved recovery-aware NN index')
    common.require(common.PROJECT/rf_runner.NN_APPROVED_INDEX_RELATIVE,rf_runner.NN_APPROVED_INDEX_SHA)
    nn=common.read(joint['NN_barrier_path']);rf=common.read(joint['RF_barrier_path'])
    if nn.get('status')!='all_selections_frozen' or nn.get('selection_count')!=200 or len(nn.get('selections',[]))!=200:
        raise ValueError('Linked original NN200 barrier missing')
    if nn.get('execution_index_sha256')!=rf_runner.NN_APPROVED_INDEX_SHA:raise ValueError('Linked NN barrier uses an unapproved old execution index')
    if rf.get('status')!='all_40_RF_selections_frozen' or len(rf.get('selections',[]))!=40:
        raise ValueError('Linked RF40 barrier missing')
    matches=[entry for entry in joint['RF_selection_entries'] if entry['selection_path']==str(selection_path)]
    if len(matches)!=1:raise ValueError('RF selection absent from joint barrier')
    common.require(selection_path,matches[0]['selection_sha256'])
    selected=common.read(selection_path)
    if selected['status']!='frozen' or not selected['validation_only'] or selected['gold_reads'] or selected['source_sha256']!=rf_runner.source_hashes():
        raise ValueError('Invalid frozen RF selected model')
    if selected['model_sha256']!=matches[0]['model_sha256']:raise ValueError('RF selected weights differ')
    common.require(selected['model_path'],selected['model_sha256'])
    if time.time()>=auth['deadline_unix']:raise TimeoutError('Original root deadline reached')
    if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise ValueError('RF scoring must be CPU only')
    return auth,selected

def score(authorization_path,joint_path,selection_path,spec_path):
    auth,selected=authorize(authorization_path,joint_path,selection_path,spec_path)
    spec=common.read(spec_path)
    if spec.get('panel') not in (None,selected['panel']):raise ValueError('Internal test panel mismatch')
    common.require(spec['input_rows'],spec['input_rows_sha256'])
    common.require(spec['feature_manifest'],spec['feature_manifest_sha256'])
    from features import read_label_free
    rows=read_label_free(common.path(spec['input_rows']))
    manifest=common.read(spec['feature_manifest'])
    X,lookup,entry=common.load_feature_dataset(manifest,spec['feature_dataset_id'])
    if len(rows)!=len({row['record_id'] for row in rows}) or any(row['record_id'] not in lookup for row in rows):raise ValueError('Score X ID coverage mismatch')
    # Check molecule/reference identity in addition to IDs, without inspecting gold.
    audits={row['record_id']:row for row in common.jsonl(entry['audit_path'])}
    for row in rows:
        molecule=row.get('canonical_isomeric_smiles') or row.get('peptide_smiles')
        if hashlib.sha256(molecule.encode()).hexdigest()!=audits[row['record_id']]['smiles_sha256'] or hashlib.sha256(row['target_sequence'].encode()).hexdigest()!=audits[row['record_id']]['full_reference_sha256']:
            raise ValueError('Score X molecule/reference identity differs')
    assets=rf_runner.installed_assets(spec['installed_assets'])
    common.require(spec['installed_assets'],selected['installed_assets_sha256'])
    import joblib
    from sklearn.ensemble import RandomForestRegressor
    model=joblib.load(common.path(selected['model_path']))
    expected,parameters=rf_runner.estimator(assets,selected['candidate_index'],selected['seed'])
    if not isinstance(model,RandomForestRegressor) or model.get_params(deep=False)!=parameters or model.n_features_in_!=2469 or len(model.estimators_)!=200:
        raise ValueError('Selected RF parameters/features differ')
    values=model.predict(X[[lookup[row['record_id']] for row in rows]])
    if not np.isfinite(values).all():raise FloatingPointError('Nonfinite RF blind prediction')
    root=common.path(spec['output_root'])/spec['dataset_id']/selected['panel']/selected['regime']/('seed-'+str(selected['seed']))
    root.mkdir(parents=True,exist_ok=False)
    excluded={'peptide_smiles','canonical_isomeric_smiles','target_sequence','peptide_sequence','peptide_sequence_raw'}
    blind=[dict({key:val for key,val in row.items() if key not in excluded},pKd_pred=float(pred)) for row,pred in zip(rows,values)]
    common.write_jsonl(root/'blind-predictions.jsonl',blind)
    blind_sha=common.sha(root/'blind-predictions.jsonl')
    common.write(root/'blind-complete.json',dict(status='RF_blind_saved_before_gold_access',n=len(rows),blind_sha256=blind_sha,gold_reads=0))
    # No actual gold byte, including hash computation, is accessed before this point.
    common.require(spec['gold_rows'],spec['gold_rows_sha256'])
    desired={row['record_id'] for row in rows};gold={}
    for row in common.jsonl(spec['gold_rows']):
        if row['record_id'] in desired:
            if row['record_id'] in gold:raise ValueError('Duplicate requested RF gold ID')
            gold[row['record_id']]=float(row['pKd'])
    if set(gold)!=desired:raise ValueError('Gold row coverage differs')
    common.require(root/'blind-predictions.jsonl',blind_sha)
    joined=[dict(row,pKd_true=gold[row['record_id']],residual=row['pKd_pred']-gold[row['record_id']]) for row in blind]
    common.write_jsonl(root/'predictions.jsonl',joined)
    metric_file=common.PROJECT/'evaluation/metrics_stable.py'
    common.require(metric_file,auth['frozen_stable_metrics_sha256'])
    loader=importlib.util.spec_from_file_location('RF_frozen_posthoc_metrics',metric_file);metrics=importlib.util.module_from_spec(loader);loader.loader.exec_module(metrics)
    results=metrics.grouped_metrics([dict(row,pKd=gold[row['record_id']]) for row in rows],values)
    common.write(root/'metrics.json',results)
    receipt=dict(status='complete',stage='additional_classical_RF_post_joint_barrier_score',method_id=common.METHOD,
        panel=selected['panel'],regime=selected['regime'],seed=selected['seed'],holdout_id=spec['dataset_id'],
        dataset_id=spec['dataset_id'],n=len(rows),metrics=results,blind_predictions_sha256=blind_sha,
        predictions_sha256=common.sha(root/'predictions.jsonl'),joint_barrier_sha256=common.sha(joint_path),
        selected_model_sha256=selected['model_sha256'],selection_sha256=common.sha(selection_path),
        source_sha256=rf_runner.source_hashes(),feature_manifest_sha256=spec['feature_manifest_sha256'],
        score_spec_sha256=common.sha(spec_path),gold_source_sha256=spec['gold_rows_sha256'],
        parameter_updates=0,blind_before_gold=True,paper_count_contribution=0,
        external_subgroup_recompute='independent review handles67/8/2 and NC8/std5; all input metadata retained')
    common.write(root/'complete.json',receipt)
    return receipt

def main():
    parser=argparse.ArgumentParser()
    for name in ('authorization','joint-barrier','selection','spec'):parser.add_argument('--'+name,required=True)
    args=parser.parse_args();print(json.dumps(score(args.authorization,args.joint_barrier,args.selection,args.spec),allow_nan=False))
if __name__=='__main__':main()
