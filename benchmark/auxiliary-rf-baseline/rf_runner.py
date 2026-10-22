"""Extra conventional RF baseline, separate from the five-paper NN benchmark."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import random
import time
import numpy as np
import common
NN_APPROVED_INDEX_SHA='c7b3bde68c9a741c0ac3f255a825e4a55dd7234e2b4e6d48f212fee8d5609ab1'
NN_APPROVED_INDEX_RELATIVE='administration/io-recovery01/execution-index-v5-recovery.json'

def source_hashes():
    return {name:common.sha(common.HERE/name) for name in ('features.py','common.py','rf_runner.py','rf_score.py','feature-spec-v1.json','protocol-v1.json','installed-assets-v1.json','installed-binaries-v1.json')}

def installed_assets(asset_path):
    assets=common.read(asset_path)
    import sklearn
    if sklearn.__version__!=assets['versions']['sklearn']:raise ValueError('sklearn runtime changed')
    for entry in assets['source_files'].values():common.require(entry['installed_path'],entry['sha256'])
    binaries=common.read(common.HERE/'installed-binaries-v1.json')
    if binaries['installed_assets_sha256']!=common.sha(asset_path):raise ValueError('Installed asset lineage changed')
    for entry in binaries['binaries'].values():common.require(entry['path'],entry['sha256'])
    return assets

def estimator(assets,candidate_index,seed):
    from sklearn.ensemble import RandomForestRegressor
    profiles=assets['candidate_profiles']
    match=[profile for profile in profiles if profile['candidate_index']==candidate_index]
    if len(match)!=1:raise ValueError('Unknown fixed profile')
    parameters=dict(match[0]['effective_parameters_seed0'],random_state=seed)
    model=RandomForestRegressor(**parameters)
    if model.get_params(deep=False)!=parameters:raise ValueError('Effective RF parameters differ')
    return model,parameters

def fit_array_candidates(X_train,y_train,X_val,y_val,assets,seed,candidate_indices=(0,1)):
    """Array-level mechanics helper; public CLI separately enforces real-fit authorization."""
    result=[]
    for candidate_index in candidate_indices:
        model,parameters=estimator(assets,candidate_index,seed)
        started=time.time();model.fit(X_train,y_train);prediction=model.predict(X_val)
        if not np.isfinite(prediction).all():raise FloatingPointError('Nonfinite RF validation prediction')
        result.append(dict(candidate_index=candidate_index,model=model,parameters=parameters,prediction=prediction,
            validation_MAE=float(np.mean(np.abs(np.asarray(y_val,dtype=np.float64)-prediction))),seconds=time.time()-started))
    return result

def authorize_fit(auth_path,spec_path):
    authorization=common.read(auth_path)
    if authorization.get('root_real_RF_fit_authorized') is not True:
        raise PermissionError('Real RF fitting is not authorized')
    if common.sha(spec_path) not in authorization.get('allowed_spec_sha256',[]):raise PermissionError('Unsigned RF unit')
    if authorization.get('source_sha256')!=source_hashes():raise ValueError('RF implementation changed after authorization')
    if time.time()>=authorization['deadline_unix']:raise TimeoutError('Original root deadline reached')
    if os.environ.get('CUDA_VISIBLE_DEVICES')!='':raise ValueError('CPU-only RF requires no visible GPU')
    return authorization

def fit_unit(spec_path,authorization_path):
    authorization=authorize_fit(authorization_path,spec_path)
    spec=common.read(spec_path)
    if spec['method_id']!=common.METHOD or spec['panel'] not in common.PANELS or spec['regime'] not in common.REGIMES or spec['seed'] not in range(10):
        raise ValueError('Invalid preregistered RF coordinates')
    allowed=common.PROJECT/'execution/prepared-panels-wsl-v3'/spec['panel']
    if common.path(spec['train_rows']).resolve()!=(allowed/'train.jsonl').resolve() or common.path(spec['validation_rows']).resolve()!=(allowed/'validation.jsonl').resolve():
        raise ValueError('RF labels must come only from whitelisted prepared train/validation, never full labels.jsonl')
    for key in ('train_rows','validation_rows','train_ids','validation_ids','feature_manifest','installed_assets'):
        common.require(spec[key],spec[key+'_sha256'])
    desired=spec['regime']=='NC_only'
    train=[row for row in common.jsonl(spec['train_rows']) if row['NC_core'] is desired]
    validation=[row for row in common.jsonl(spec['validation_rows']) if row['NC_core'] is desired]
    if [row['record_id'] for row in train]!=common.read(spec['train_ids']) or [row['record_id'] for row in validation]!=common.read(spec['validation_ids']):
        raise ValueError('Train/validation rows differ from frozen own-regime IDs')
    if not train or not validation or {r['record_id'] for r in train}&{r['record_id'] for r in validation}:raise ValueError('Empty/leaking train/validation')
    manifest=common.read(spec['feature_manifest']);X,lookup,entry=common.load_feature_dataset(manifest,'PPIKB9619')
    audits={row['record_id']:row for row in common.jsonl(entry['audit_path'])}
    for row in train+validation:
        smiles=row.get('canonical_isomeric_smiles') or row.get('peptide_smiles')
        if hashlib.sha256(smiles.encode()).hexdigest()!=audits[row['record_id']]['smiles_sha256'] or hashlib.sha256(row['target_sequence'].encode()).hexdigest()!=audits[row['record_id']]['full_reference_sha256']:
            raise ValueError('Prepared row molecule/reference differs from fixed label-free X')
    y_train=np.asarray([row['pKd'] for row in train],dtype=np.float64);y_val=np.asarray([row['pKd'] for row in validation],dtype=np.float64)
    if not np.isfinite(y_train).all() or not np.isfinite(y_val).all():raise ValueError('Nonfinite prepared training/validation labels')
    X_train=X[[lookup[row['record_id']] for row in train]];X_val=X[[lookup[row['record_id']] for row in validation]]
    assets=installed_assets(spec['installed_assets']);random.seed(spec['seed']);np.random.seed(spec['seed'])
    output=common.path(spec['output_root']);output.mkdir(parents=True,exist_ok=False)
    common.write(output/'started.json',dict(stage='root_authorized_RF_train_validation_only',spec_sha256=common.sha(spec_path),
        authorization_sha256=common.sha(authorization_path),pid=os.getpid(),started_unix=time.time(),source_sha256=source_hashes()))
    import joblib
    candidates=[]
    for candidate_index in (0,1):
        # Persist candidate0 before candidate1 begins, retaining completed work
        # even if a later candidate hits a root-issued resource/time bound.
        try:result=fit_array_candidates(X_train,y_train,X_val,y_val,assets,spec['seed'],(candidate_index,))[0]
        except BaseException as error:
            common.write(output/'failed.json',dict(status='failed',candidate_index=candidate_index,error=repr(error),
                completed_candidate_indices=[row['candidate_index'] for row in candidates],holdout_reads=0))
            raise
        folder=output/('candidate-'+str(result['candidate_index']));folder.mkdir()
        joblib.dump(result['model'],folder/'model.joblib')
        records=[dict(row_id=row['record_id'],record_id=row['record_id'],pKd_true=float(y),pKd_pred=float(pred),
                      evaluation_stratum=row['evaluation_stratum'],NC_core=row['NC_core'],study_id=row.get('study_id'),target_id=row.get('target_id'))
                 for row,y,pred in zip(validation,y_val,result['prediction'])]
        common.write_jsonl(folder/'validation-predictions.jsonl',records)
        receipt=dict(status='complete',candidate_index=result['candidate_index'],effective_parameters=result['parameters'],
            validation_MAE=result['validation_MAE'],train_n=len(train),validation_n=len(validation),seconds=result['seconds'],
            model_path=str(folder/'model.joblib'),model_sha256=common.sha(folder/'model.joblib'),
            validation_predictions_sha256=common.sha(folder/'validation-predictions.jsonl'),
            spec_sha256=common.sha(spec_path),feature_manifest_sha256=spec['feature_manifest_sha256'],
            installed_assets_sha256=spec['installed_assets_sha256'],source_sha256=source_hashes(),holdout_reads=0)
        common.write(folder/'complete.json',receipt);candidates.append(receipt)
    best=min(candidates,key=lambda row:(row['validation_MAE'],row['candidate_index']))
    selection=dict(status='frozen',method_id=common.METHOD,panel=spec['panel'],regime=spec['regime'],seed=spec['seed'],
        candidate_index=best['candidate_index'],model_path=best['model_path'],model_sha256=best['model_sha256'],
        validation_MAE=best['validation_MAE'],candidates=candidates,selection_metric='same-regime validation MAE',
        tie_break='lower candidate_index',spec_sha256=common.sha(spec_path),source_sha256=source_hashes(),
        feature_manifest_sha256=spec['feature_manifest_sha256'],installed_assets_sha256=spec['installed_assets_sha256'],
        validation_only=True,true_holdout_predictions=0,gold_reads=0,global_clock_not_reset=True)
    common.write(output/'selection.json',selection)
    common.write(output/'complete.json',dict(status='complete',stage='additional_RF_train_validation_only',
        method_id=common.METHOD,panel=spec['panel'],regime=spec['regime'],seed=spec['seed'],
        candidate_fits_completed=2,selection_path=str(output/'selection.json'),selection_sha256=common.sha(output/'selection.json'),
        spec_sha256=common.sha(spec_path),source_sha256=source_hashes(),real_holdout_predictions=0,gold_reads=0,
        installed_assets_sha256=spec['installed_assets_sha256'],feature_manifest_sha256=spec['feature_manifest_sha256']))
    return selection

def rf_barrier(index_path,output_path):
    index=common.read(index_path)
    if index['unit_count']!=40 or index['candidate_fit_count']!=80:raise ValueError('Wrong RF plan')
    if common.path(output_path).exists():raise FileExistsError('Preserve frozen RF barrier')
    entries=[];identities=set()
    for unit in index['units']:
        common.require(unit['spec_path'],unit['spec_sha256'])
        selected=common.read(unit['selection_path'])
        identity=tuple(selected[key] for key in ('panel','regime','seed'))
        if identity in identities or selected['status']!='frozen' or not selected['validation_only'] or selected['gold_reads']:
            raise ValueError('Invalid RF selection')
        identities.add(identity)
        if selected['source_sha256']!=source_hashes() or selected['spec_sha256']!=unit['spec_sha256']:raise ValueError('Selected code/spec changed')
        frozen=common.read(unit['spec_path'])
        if identity!=tuple(frozen[key] for key in ('panel','regime','seed')):raise ValueError('RF selection coordinate mismatch')
        common.require(selected['model_path'],selected['model_sha256'])
        if len(selected['candidates'])!=2 or any(c['status']!='complete' for c in selected['candidates']):raise ValueError('Missing candidate')
        best=min(selected['candidates'],key=lambda row:(row['validation_MAE'],row['candidate_index']))
        if selected['candidate_index']!=best['candidate_index']:raise ValueError('Non-validation winner')
        entries.append(dict(selection_path=unit['selection_path'],selection_sha256=common.sha(unit['selection_path']),
                            panel=identity[0],regime=identity[1],seed=identity[2],model_sha256=selected['model_sha256']))
    if identities!={(panel,regime,seed) for panel in common.PANELS for regime in common.REGIMES for seed in range(10)}:
        raise ValueError('Incomplete RF40 grid')
    result=dict(status='all_40_RF_selections_frozen',selection_count=40,candidate_fit_count=80,selections=entries,
        task_index_sha256=common.sha(index_path),validation_only=True,holdout_predictions=0,global_clock_not_reset=True)
    common.write(output_path,result);return result

def validate_joint(nn_path,rf_path):
    nn=common.read(nn_path);rf=common.read(rf_path)
    if nn.get('status')!='all_selections_frozen' or nn.get('selection_count')!=200 or nn.get('candidate_fit_count')!=400 or len(nn.get('selections',[]))!=200:
        raise ValueError('Original full NN200 barrier required unchanged')
    if rf.get('status')!='all_40_RF_selections_frozen' or rf.get('selection_count')!=40 or rf.get('candidate_fit_count')!=80 or len(rf.get('selections',[]))!=40:
        raise ValueError('Full RF40 barrier required')
    nn_index_path=common.PROJECT/NN_APPROVED_INDEX_RELATIVE
    common.require(nn_index_path,NN_APPROVED_INDEX_SHA)
    nn_index=common.read(nn_index_path)
    if nn.get('execution_index_sha256')!=NN_APPROVED_INDEX_SHA:
        raise ValueError('NN barrier does not bind the root-approved IO-recovery01 execution index')
    if {entry['path'] for entry in nn['selections']}!={entry['selection_path'] for entry in nn_index['per_seed_selections']}:
        raise ValueError('NN200 selection paths differ from approved recovery-aware index')
    nn_ids=set()
    for entry in nn['selections']:
        common.require(entry['path'],entry['sha256']);selected=common.read(entry['path'])
        if selected['status']!='frozen' or selected['holdout_metrics_consulted']:raise ValueError('Unfrozen NN selection')
        identity=tuple(selected[key] for key in ('method_id','split_id','regime','seed'))
        if identity in nn_ids:raise ValueError('Repeated NN selection')
        nn_ids.add(identity)
    nn_methods={'GraphDTA-GIN','MGraphDTA','DGDTA-CL','DeepNC-GEN','GS-DTA'}
    if nn_ids!={(m,p,r,s) for m in nn_methods for p in common.PANELS for r in common.REGIMES for s in range(10)}:
        raise ValueError('Original full NN200 grid missing')
    rf_ids=set()
    for entry in rf['selections']:
        common.require(entry['selection_path'],entry['selection_sha256']);selected=common.read(entry['selection_path'])
        if not selected['validation_only'] or selected['gold_reads'] or selected['status']!='frozen':raise ValueError('Invalid RF selection')
        identity=tuple(selected[key] for key in ('panel','regime','seed'))
        if identity in rf_ids:raise ValueError('Repeated RF selection')
        rf_ids.add(identity)
    if rf_ids!={(p,r,s) for p in common.PANELS for r in common.REGIMES for s in range(10)}:raise ValueError('RF40 grid missing')
    return dict(status='all_200_NN_plus_40_RF_frozen',NN_barrier_path=str(nn_path),RF_barrier_path=str(rf_path),
                NN_barrier_sha256=common.sha(nn_path),RF_barrier_sha256=common.sha(rf_path),
                NN_selections=200,RF_selections=40,NN_candidate_fits=400,RF_candidate_fits=80,original_NN_barrier_unchanged=True,
                NN_execution_index_path=str(nn_index_path),NN_execution_index_sha256=NN_APPROVED_INDEX_SHA,
                RF_selection_entries=rf['selections'],validation_only=True,gold_reads=0,true_holdout_predictions=0)

def main():
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='command',required=True)
    fit=sub.add_parser('fit');fit.add_argument('--spec',required=True);fit.add_argument('--authorization',required=True)
    barrier=sub.add_parser('rf-barrier');barrier.add_argument('--index',required=True);barrier.add_argument('--output',required=True)
    joint=sub.add_parser('joint-barrier');joint.add_argument('--NN-barrier',required=True);joint.add_argument('--RF-barrier',required=True);joint.add_argument('--output',required=True)
    args=parser.parse_args()
    if args.command=='fit':result=fit_unit(args.spec,args.authorization)
    elif args.command=='rf-barrier':result=rf_barrier(args.index,args.output)
    else:
        result=validate_joint(args.NN_barrier,args.RF_barrier)
        if common.path(args.output).exists():raise FileExistsError('Preserve joint barrier')
        common.write(args.output,result)
    print(json.dumps(result,allow_nan=False))
if __name__=='__main__':main()
