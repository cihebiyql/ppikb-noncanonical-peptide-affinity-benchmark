"""Stdlib-only RF post-joint gates; no model/selection files opened at import."""
import ast
import importlib.util
import os
from pathlib import Path
import re
import sys
import time

HERE=Path(__file__).resolve().parent
PROJECT=HERE.parents[1]
TRAIN_COMMON=PROJECT/'control/rf-launch-v1/rf_common.py'
loader=importlib.util.spec_from_file_location('_frozen_RF_train_resource_primitives',TRAIN_COMMON)
_train=importlib.util.module_from_spec(loader);loader.loader.exec_module(_train)
read,sha,path,checked,utc,deadline,epoch,process_table,stop_owned_group,write,ProgressWriter,cpu_probe,full_timeout_fits,runtime_gate,reference,same=(getattr(_train,n) for n in ('read','sha','path','checked','utc','deadline','epoch','process_table','stop_owned_group','write','ProgressWriter','cpu_probe','full_timeout_fits','runtime_gate','reference','same'))
GIB,CPU_IDS,HOST,PANELS,METHOD,SOURCE_NAMES,LAUNCH=(_train.GIB,_train.CPU_IDS,_train.HOST,_train.PANELS,_train.METHOD,_train.SOURCE_NAMES,_train.LAUNCH)


def private_pool_gate(binding_path):
    if os.getpid()!=os.getpgrp() or os.getsid(0)!=os.getpid():raise RuntimeError('RF score unit requires private PGID/session')
    parent=os.getppid();row=process_table().get(parent)
    if os.environ.get('RF_SCORE_POOL_OWNER_PID')!=str(parent) or not row or row['uid']!=os.getuid() or str(row['start_ticks'])!=os.environ.get('RF_SCORE_POOL_OWNER_START_TICKS'):raise RuntimeError('Wrong RF score parent pool/start time')
    if not same(os.environ.get('RF_SCORE_POOL_BINDING_PATH',''),binding_path) or os.environ.get('RF_SCORE_POOL_BINDING_SHA256')!=sha(binding_path):raise RuntimeError('Pool did not issue exact RF scoring binding')
    if not re.fullmatch('[0-9a-f]{64}',os.environ.get('RF_SCORE_POOL_INDEX_SHA256','')):raise RuntimeError('Issued RF score pool index SHA absent')
    if str(HERE/'rf_score_pool.py').encode() not in (Path('/proc')/str(parent)/'cmdline').read_bytes().split(b'\0'):raise RuntimeError('Wrong RF score parent command')


def approved_NN_index():
    """Read literal frozen-source constants without importing NumPy/RF worker."""
    tree=ast.parse((PROJECT/'auxiliary-rf-baseline/rf_runner.py').read_text(encoding='utf-8'))
    found={}
    for node in tree.body:
        if isinstance(node,ast.Assign):
            for target in node.targets:
                if isinstance(target,ast.Name) and target.id in ('NN_APPROVED_INDEX_SHA','NN_APPROVED_INDEX_RELATIVE'):
                    found[target.id]=ast.literal_eval(node.value)
    if len(found)!=2:raise ValueError('Frozen approved NN index literals missing')
    return found


def preflight(binding_path,private=True,reserve=True):
    binding_path=path(binding_path);binding=read(binding_path)
    if binding.get('schema')!='rf-score-unit-binding-v1' or binding.get('issued') is not True:raise PermissionError('Root-issued RF score binding required')
    if not re.fullmatch('[A-Za-z0-9_.-]+',binding['unit_id']):raise ValueError('Unsafe RF score unit id')
    runtime_gate(binding,unit=private)
    if private:private_pool_gate(binding_path)
    cutoff=deadline(binding['deadline'])
    if binding['timeout_seconds']!=1800:raise ValueError('RF three-score unit requires fixed1800sec')
    if reserve and not full_timeout_fits(cutoff):raise TimeoutError('Full RF scoring timeout cannot fit original global window')
    checked(HERE/'rf_score_unit.py',binding['entrypoint_sha256']);checked(HERE/'rf_score_pool.py',binding['pool_sha256']);checked(__file__,binding['common_sha256'])
    # Score permission, NOT RF fit permission, is the first scientific gate.
    auth=read(reference(binding['authorization']))
    if auth.get('root_RF_holdout_score_authorized') is not True:raise PermissionError('Explicit post-joint RF scoring authorization required')
    if auth['deadline_unix']!=cutoff or time.time()>=auth['deadline_unix']:raise TimeoutError('RF score authorization must retain original live cutoff')
    if len(binding['score_specs'])!=3 or any(r['sha256'] not in auth.get('allowed_score_spec_sha256',[]) for r in binding['score_specs']):raise PermissionError('Exactly three root-authorized scoring specs required')
    joint_path=reference(binding['joint_barrier']);nn_path=reference(binding['NN_barrier']);rf_path=reference(binding['RF_barrier'])
    if binding['joint_barrier']['sha256']!=auth['joint_barrier_sha256']:raise ValueError('Authorized joint barrier mismatch')
    joint,nn,rf=read(joint_path),read(nn_path),read(rf_path)
    if joint.get('status')!='all_200_NN_plus_40_RF_frozen' or joint.get('NN_selections')!=200 or joint.get('RF_selections')!=40 or joint.get('NN_candidate_fits')!=400 or joint.get('RF_candidate_fits')!=80:raise PermissionError('All NN200 AND RF40 selections /480 fits required')
    for key,ref in [('NN',binding['NN_barrier']),('RF',binding['RF_barrier'])]:
        if not same(joint[key+'_barrier_path'],ref['path']) or joint[key+'_barrier_sha256']!=ref['sha256']:raise ValueError('Joint linked '+key+' barrier mismatch')
    if nn.get('status')!='all_selections_frozen' or nn.get('selection_count')!=200 or nn.get('candidate_fit_count')!=400 or len(nn.get('selections',[]))!=200:raise PermissionError('Original NN200 barrier incomplete')
    if len({r['path'] for r in nn['selections']})!=200:raise ValueError('NN200 repeated selection paths')
    if rf.get('status')!='all_40_RF_selections_frozen' or rf.get('selection_count')!=40 or rf.get('candidate_fit_count')!=80 or len(rf.get('selections',[]))!=40:raise PermissionError('RF40 barrier incomplete')
    expected={(p,r,s) for p in PANELS for r in ('NC_only','standard_only') for s in range(10)}
    entries=joint.get('RF_selection_entries',[])
    if len(entries)!=40 or {(r['panel'],r['regime'],r['seed']) for r in entries}!=expected:raise PermissionError('Joint RF40 experimental grid incomplete')
    if {(r['panel'],r['regime'],r['seed']) for r in rf['selections']}!=expected:raise PermissionError('Linked RF40 grid incomplete')
    if len({r['selection_path'] for r in entries})!=40:raise ValueError('Repeated RF selection paths')
    identity=lambda row:(row['panel'],row['regime'],row['seed'])
    linkage=lambda row:(str(path(row['selection_path']).resolve()),row['selection_sha256'],row['model_sha256'])
    if {identity(row):linkage(row) for row in entries}!={identity(row):linkage(row) for row in rf['selections']}:raise ValueError('Joint RF40 entries differ from linked frozen RF barrier')
    contract=read(reference(binding['central_contract']));validation=read(reference(binding['validation']))
    if contract.get('is_template') is not False or contract.get('contract_status')!='frozen' or contract['run_id']!=binding['unit_id']:raise PermissionError('Actual frozen RF scoring central contract required')
    vsha=validation.get('contract_sha256') or validation.get('launch_binding',{}).get('contract_sha256')
    if validation.get('valid_for_execution') is not True or vsha!=binding['central_contract']['sha256']:raise PermissionError('Positive exact central validation required')
    if 'central_validation_path' in validation:
        if read(checked(validation['central_validation_path'],validation['central_validation_sha256'])).get('valid_for_execution') is not True:raise PermissionError('Central validator rejected RF score')
    timing=contract['timing']
    if cutoff>epoch(timing['effective_deadline_at']) or timing.get('prior_window_expired') is True or timing.get('retry_resets_clock') is not False:raise ValueError('Original RF score clock cannot reset/extend')
    argv=[binding['python'],str(HERE/'rf_score_unit.py'),'--binding',str(binding_path)]
    if contract['execution']['command']!=argv or contract['execution']['timeout_seconds']!=1800:raise ValueError('Wrong RF score command or timeout')
    resources=contract['resources']
    if resources['expected_hostname']!=HOST or resources.get('cpu_threads')!=1 or resources.get('memory_limit_bytes')!=2*GIB or resources.get('gpu_devices')!=[]:raise ValueError('Wrong CPU-only RF scoring resources')
    if not same(contract['environment']['environment_path'],sys.prefix):raise ValueError('Wrong RF score virtual environment')
    proof=read(reference(binding['live_cpu_proof']))
    if proof.get('hostname')!=HOST or not (proof.get('at') or proof.get('observed_at')):raise ValueError('Real host/time CPU proof required')
    files=binding['code_files'];seen=set()
    for ref in files:
        p=path(ref['path']).resolve()
        if p.suffix!='.py' and p.name not in SOURCE_NAMES:raise ValueError('Model/gold/cache cannot be code proofs')
        if str(p) in seen:raise ValueError('Repeated RF score source proof')
        reference(ref);seen.add(str(p))
    required=[HERE/n for n in ('rfs_common.py','rf_score_pool.py','rf_score_unit.py')]+[TRAIN_COMMON,LAUNCH/'common.py',PROJECT/'evaluation/metrics_stable.py']+[PROJECT/'auxiliary-rf-baseline'/n for n in SOURCE_NAMES]
    if not {str(p.resolve()) for p in required}<=seen:raise ValueError('RF scoring/primitive/metrics source proofs incomplete')
    source_sha={n:sha(PROJECT/'auxiliary-rf-baseline'/n) for n in SOURCE_NAMES}
    if auth['source_sha256']!=source_sha or auth['frozen_stable_metrics_sha256']!=sha(PROJECT/'evaluation/metrics_stable.py'):raise ValueError('Frozen RF scoring or metric source changed')
    worker=reference(binding['worker'])
    if not same(worker,PROJECT/'auxiliary-rf-baseline/rf_score.py'):raise ValueError('Wrong frozen RF scoring worker')
    approved=approved_NN_index()
    if joint.get('NN_execution_index_sha256')!=approved['NN_APPROVED_INDEX_SHA'] or nn.get('execution_index_sha256')!=approved['NN_APPROVED_INDEX_SHA']:raise ValueError('Wrong approved NN recovery-aware index')
    checked(PROJECT/approved['NN_APPROVED_INDEX_RELATIVE'],approved['NN_APPROVED_INDEX_SHA'])
    specs=[read(reference(r)) for r in binding['score_specs']]
    selection_path=reference(binding['selection']);selected=read(selection_path)
    matches=[r for r in entries if same(r['selection_path'],selection_path) and r['selection_sha256']==binding['selection']['sha256']]
    if len(matches)!=1 or selected.get('status')!='frozen' or selected.get('validation_only') is not True or selected.get('gold_reads')!=0 or selected.get('true_holdout_predictions')!=0 or selected.get('source_sha256')!=source_sha:raise PermissionError('Selection is not one of audited frozen RF40')
    if selected['model_sha256']!=matches[0]['model_sha256']:raise ValueError('Selected model metadata differs from joint barrier')
    coordinate=(selected['panel'],selected['regime'],selected['seed'])
    if coordinate not in expected:raise ValueError('Wrong RF selected experimental coordinate')
    meta=contract['benchmark_metadata']
    if meta['method_id']!='RF-Classic' or coordinate!=(meta['split_id'],meta['regime_id'],meta['seed']):raise ValueError('RF scoring contract identity mismatch')
    internal='source_test' if coordinate[0]=='source_peptide_dependency_cold' else 'target_test'
    if {s['dataset_id'] for s in specs}!={internal,'external75','supplement13'}:raise ValueError('Wrong RF three-dataset set')
    expected_root=PROJECT/'auxiliary-rf-baseline/rf-scores-v1'
    for spec in specs:
        if spec.get('method_id')!=METHOD or spec.get('panel')!=coordinate[0]:raise ValueError('RF score spec method/panel mismatch')
        if spec.get('cpu_threads')!=1 or spec.get('n_jobs')!=1 or spec.get('CUDA_VISIBLE_DEVICES')!='':raise ValueError('RF scoring CPU1/n_jobs1/CUDA-empty required')
        if not same(spec['output_root'],binding['score_root']) or not same(binding['score_root'],expected_root):raise ValueError('Frozen RF output layout changed')
        checked(spec['input_rows'],spec['input_rows_sha256']);checked(spec['feature_manifest'],spec['feature_manifest_sha256'])
        if not same(spec['installed_assets'],PROJECT/'auxiliary-rf-baseline/installed-assets-v1.json'):raise ValueError('Wrong fixed RF installed assets')
    stage=contract['rf_score_execution_stage']
    for key in ('selection','score_specs','authorization','joint_barrier','NN_barrier','RF_barrier','live_cpu_proof','worker','code_files','receipt_root','score_root'):
        if stage[key]!=binding[key]:raise ValueError('Central RF score stage '+key+' binding mismatch')
    if not path(binding['receipt_root']).resolve().is_relative_to(HERE.resolve()):raise ValueError('RF scoring receipt path outside owned launcher')
    return {'binding':binding,'binding_path':binding_path,'selection':selected,'specs':specs,'contract':contract,'coordinate':coordinate,'cutoff':cutoff,'worker':worker}


def score_outputs(context):
    p,r,s=context['coordinate']
    return [path(context['binding']['score_root'])/spec['dataset_id']/p/r/('seed-'+str(s)) for spec in context['specs']]


def validate_complete(folder,binding_sha):
    folder=path(folder);complete=read(checked(folder/'unit-complete.json',(folder/'unit-complete.sha256').read_text().strip()))
    if complete.get('status')!='complete' or complete['binding_sha256']!=binding_sha or len(complete.get('scores',[]))!=3:raise ValueError('RF scoring completion lineage/count mismatch')
    for ref in complete['artifacts']:reference(ref)
    for score in complete['scores']:checked(score['complete_path'],score['complete_sha256'])
    proof=read(checked(folder/'pool-exit-verification.json',(folder/'pool-exit-verification.sha256').read_text().strip()))
    if proof.get('exit_code')!=0 or proof.get('private_session_handles_absent') is not True or proof['binding_sha256']!=binding_sha:raise ValueError('Actual RF score pool exit proof absent')
    for name in ('stdout','stderr'):checked(proof[name+'_path'],proof[name+'_sha256'])
    return complete
