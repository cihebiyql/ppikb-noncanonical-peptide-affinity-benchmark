"""Freeze original candidate bytes, prepared features and 100 already-selected weights; no load/fit."""
import datetime as dt
from pathlib import Path
from common import HERE,ROOT,DATA,RUN,sha,load,write,read

def main():
    assert not (HERE/'execution-contract.json').exists()
    path=DATA/'conditional-sequence-external-candidates.csv'
    assert sha(path)=='35573d98d14b4ae65575ba9557a1508ea145c30a47a2855f7ef0bfdd625bdef4'
    rows=read(path);assert len(rows)==27 and len({r['row_id'] for r in rows})==27
    assert {r['split'] for r in rows}=={'external'} and {r['endpoint'] for r in rows}=={'pKd'}
    assert all(r['certified_independent_external']=='False' for r in rows)
    interface=load(DATA/'fixed-model-interface-and-inputcoverage.json')
    assert interface['existing_fixed_weight_files_SHA_checked']==100
    models=[];extra=[]
    for item in interface['weight_checks']:
        weight=Path(item['weight_path']);assert sha(weight)==item['sha256']
        result_path=weight.parent/'result.json';result=load(result_path)
        candidates_path=weight.parent/'candidates.json';candidates=load(candidates_path)
        selected=next(c for c in candidates if c['candidate']==result['selected_candidate'])
        assert selected['model_sha256']==item['sha256']
        assert weight.name==f"candidate-{result['selected_candidate']}.joblib"
        models.append({**item,'training_result_path':str(result_path),'training_result_sha256':sha(result_path),
            'training_candidates_path':str(candidates_path),'training_candidates_sha256':sha(candidates_path),
            'selected_candidate':result['selected_candidate']})
        extra.extend([result_path,candidates_path,weight])
    assert len(models)==100 and len({(m['training_view'],m['model'],m['seed']) for m in models})==100
    authority=ROOT/'protocol/continuation-20261023/user-authorization.json'
    delegation={'origin':'trusted_parent_delegation_under_existing_user_continuation',
        'recorded_at':dt.datetime.now(dt.timezone.utc).isoformat(),
        'scope':'27候选条件外测;100既有selected手工模型;0fit/0tune;all27;source/protein/binding-group macro;independently recalc;keep original prepare-only manifest and all old results unchanged',
        'human_continuation_authorization_path':str(authority),'human_continuation_authorization_sha256':sha(authority),
        'not_a_new_human_message':True,'certified_independent_external_rows':0}
    write(HERE/'delegated-task-authority.json',delegation)
    files=[path,DATA/'manual-feature-preparation.npy',DATA/'fixed-model-interface-and-inputcoverage.json',
        DATA/'conditional-view-manifest.json',DATA/'VALIDATION.json',DATA/'REPORT.zh-CN.md',
        DATA/'source-pins.json',HERE/'delegated-task-authority.json',authority,
        Path(interface['same_source_frozen_feature_code'])]
    files += [Path(p) for p in interface['training_contracts']]
    files += [HERE/name for name in ['common.py','run_fixed.py','supervise_fixed.py','verify_fixed.py']]
    files+=extra;files=list(dict.fromkeys(files))
    contract={'schema':'pepbi.27conditional.fixed-model-execution.v1','created_at':dt.datetime.now(dt.timezone.utc).isoformat(),
        'title':'27条候选条件外测','status':'authorized_fixed_prediction_under_new_delegation',
        'original_prepare_only_manifest_unchanged':True,'candidate_csv':str(path),'candidate_sha256':sha(path),
        'candidate_rows':27,'feature_array':str(DATA/'manual-feature-preparation.npy'),
        'feature_sha256':sha(DATA/'manual-feature-preparation.npy'),'feature_shape':[27,174],
        'feature_code_path':interface['same_source_frozen_feature_code'],'feature_code_sha256':interface['feature_code_sha256'],
        'models':models,'training_seeds':list(range(10)),'fixed_model_applications':100,
        'new_fit_count':0,'tuning_count':0,'gpu':False,'certified_independent_external_rows':0,
        'blind_external':False,'new_target_family_external':False,'NC_core_external':False,
        'all_candidates_reported':True,'metric_groups':['target_id','study_id','binding_group'],
        'seed_SD_is_not_biological_CI':True,'runtime':'Windows same sklearn1.9.0 as original weights',
        'cpu_threads':2,'max_rss_bytes':1024**3,'os_reserve_bytes':2*1024**3,'queue_timeout_seconds':300,
        'timeout_seconds':600,'priority':'Windows IDLE_PRIORITY_CLASS; POSIX numeric nice19 unsupported',
        'cpu_admission':'3frames globalidle>=40,each selected coreidle>=60; available>=maxRSS+OSreserve',
        'input_hashes':[{'path':str(p),'sha256':sha(p)} for p in files]}
    write(HERE/'execution-contract.json',contract)
    print({'contract_sha256':sha(HERE/'execution-contract.json'),'fixed_models':100,'rows':27,'new_fits':0})
if __name__=='__main__':main()
