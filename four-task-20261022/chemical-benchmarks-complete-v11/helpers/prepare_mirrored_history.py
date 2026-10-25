"""Prepare complete existing full-fine-tuning small artifacts from owner mirrors.

All source bytes are rechecked against the mirror map. Original prediction CSVs
are preserved; private execution paths/hosts in other files receive disclosed
transformations. Raw input datasets and upstream/binary models are not log files.
"""
import argparse
import collections
import csv
import io
import json
from pathlib import Path
import re

from public_artifacts import deterministic_archive, inspect_prediction_csv, prepare_bytes, sanitize_text, sha

CONTROL_SHA='4f4694b8937c6e3bd2e5b1091faf948fd66ecc57180b09d0ff5c236cded83c60'
EXPANDED_SHA='c3d8f4e42600f0c762bb9d2d24595a32c8f13de7a1f5018d59047d241dd8525a'
MODELS=('hybrid','mlm','peptideclm2025')
RUN_ID=re.compile(r'/(hybrid|mlm|peptideclm2025-spefix|2025)-seed(\d{2})(?:-candidate(\d+))?/')


def write_json(path,value):
    with Path(path).open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,indent=2,ensure_ascii=False,allow_nan=False);stream.write('\n')


def prepare(maps,cohort,output,scope,phase='complete'):
    if phase not in ('complete','training_only'):raise ValueError('Unknown preparation phase')
    output=Path(output)
    if output.exists():raise FileExistsError(output)
    csv_sha=CONTROL_SHA if scope=='control' else EXPANDED_SHA
    if sha(Path(cohort).read_bytes())!=csv_sha:raise ValueError('Wrong frozen input cohort')
    with Path(cohort).open(encoding='utf-8-sig',newline='') as stream:cohort_rows=list(csv.DictReader(stream))
    split_rows={split:[r for r in cohort_rows if r['split']==split] for split in ('validation','test')}
    expected_sizes={'validation':495,'test':656} if scope=='control' else {'validation':570,'test':685}
    if {k:len(v) for k,v in split_rows.items()}!=expected_sizes:raise ValueError('Unexpected frozen split sizes')
    archive_files={};mapping=[];exclusions=[];predictions=[];candidates={};selections={};histories={};checkpoint_hashes={};source_maps=[]
    file_types=collections.Counter();redactions=collections.Counter();failure_artifacts=[]
    for input_map in maps:
        input_map=Path(input_map);alias=input_map.parent.name
        mirror=json.loads(input_map.read_text(encoding='utf-8-sig'))
        if mirror.get('all_files_exact_verified') is not True:raise ValueError('Mirror not marked byte verified')
        source_maps.append({'source_ref':sanitize_text(str(input_map))[0],'sha256':sha(input_map.read_bytes()),'source_archive_sha256':mirror['archive_sha256'],'files':len(mirror['files'])})
        for record in mirror['files']:
            path=input_map.parent/record['archive_member'];data=path.read_bytes()
            if len(data)!=record['bytes'] or sha(data)!=record['sha256']:raise ValueError('Mirror original bytes changed')
            source_ref=sanitize_text(record['remote'])[0]
            metadata={'source_ref':source_ref,'source_sha256':record['sha256'],'source_size_bytes':len(data),'source_mirror_map_sha256':source_maps[-1]['sha256']}
            suffix=Path(record['remote']).suffix.lower();name=Path(record['remote']).name
            upstream_markers=('/chemical-encoders-20261024-v1/models/','/peptideclm2025-assets-v1/vendor/','/peptideclm2025-assets-v1/dependency/','/chemical-encoders-20261024-v1/sources/')
            if any(marker in record['remote'] for marker in upstream_markers):
                exclusions.append(dict(metadata,disposition='upstream_dependency_obtain_via_official_lock',reason='Upstream model/tokenizer/vendor bytes are not self-authored experiment logs. Exact official revision, licenses, byte hashes and acquisition are disclosed in UPSTREAM-INPUTS-LOCK.json. No experimental result or training history is excluded by this rule.'))
                continue
            if suffix=='.gz' and name=='smallproof.tar.gz' and '/expanded30-first-IO-evidence--20261025T034858/' in record['remote']:
                exclusions.append(dict(metadata,disposition='nested_raw_archive_represented_by_sanitized_IO_history_asset',reason='All55 original small members are independently byte-verified and published as selected-first-IO-history.tar.gz with source→public mappings. The raw nested archive is not copied because it contains original resource identities; its exact original SHA remains indexed. This is a successful460.112-second TEST attempt, not a timeout.'))
                continue
            run_match=RUN_ID.search(record['remote']) if '/runs/' in record['remote'] else None
            parsed=json.loads(data) if suffix=='.json' else None
            if suffix=='.csv':
                reader=csv.DictReader(io.StringIO(data.decode('utf-8-sig'),newline=''))
                if any(key in (reader.fieldnames or []) for key in ('peptide_sequence','target_sequence','peptide_smiles','smiles')):
                    exclusions.append(dict(metadata,disposition='exact_frozen_dataset_duplicate_available_in_data_component',reason='The complete licensed frozen CSV, including its sequences, full SMILES and labels, is supplied byte-for-byte in the canonical data component under PPIKB CC BY4.0. This identical input snapshot is referenced by its SHA rather than duplicated inside the log asset. No training, epoch, failure or prediction log is excluded by this rule.'))
                    continue
                if name in ('best-validation.csv','test-predictions.csv','validation-predictions.csv'):
                    split='test' if name=='test-predictions.csv' else 'validation'
                    review=inspect_prediction_csv(data,len(split_rows[split]),[r['row_id'] for r in split_rows[split]])
                    rows=list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'),newline='')))
                    for row,expected in zip(rows,split_rows[split]):
                        if float(row['label'])!=float(expected['label']) or row['global_group_id']!=expected['global_group_id'] or row['evaluation_stratum']!=expected['evaluation_stratum']:raise ValueError('Prediction float64 label/group/stratum mismatch')
                else:
                    review=None
            else:review=None
            public,changes=prepare_bytes(data,suffix)
            if suffix=='.csv' and public!=data:
                # This coverage metadata CSV contains execution paths in the
                # reason column, not measurements or predictions.
                metadata_fields={'view_id','row_id','split','evaluation_stratum','reasons'}
                if name!='input-only-exclusions.csv' or set(reader.fieldnames or [])!=metadata_fields:
                    raise ValueError('Scientific CSV must preserve original bytes')
            public_path=scope+'-fullfine/'+alias+'/'+record['archive_member']
            if public_path in archive_files:raise ValueError('Duplicate mirror alias or archive path')
            archive_files[public_path]=public
            mapping.append(dict(metadata,public_archive_path=public_path,public_sha256=sha(public),public_size_bytes=len(public),redactions=changes,transform='none; original bytes preserved' if public==data else 'Private execution-path/host or explicit raw-input sanitation; numeric scientific history retained',prediction_review=review))
            file_types[suffix]+=1;redactions.update(x['rule'] for x in changes)
            if parsed is not None and isinstance(parsed,dict):
                if parsed.get('status') in ('failed','error','oom','partial','timeout') or parsed.get('exit_code') not in (None,0):failure_artifacts.append({'source_ref':source_ref,'source_sha256':record['sha256'],'public_archive_path':public_path,'status':parsed.get('status'),'exit_code':parsed.get('exit_code')})
            if not run_match:continue
            model=run_match.group(1)
            if model in ('2025','peptideclm2025-spefix'):model='peptideclm2025'
            seed=int(run_match.group(2));candidate=int(run_match.group(3)) if run_match.group(3) is not None else None
            if name=='test-predictions.csv':
                if candidate is not None:raise ValueError('Candidate TEST would violate final selection structure')
                predictions.append({'kind':'full_encoder','representation':model,'model':'full_finetune','seed':seed,'split':'test','n':expected_sizes['test'],'public_archive_path':public_path,'source_sha256':record['sha256']})
            if name=='result.json' and isinstance(parsed,dict) and parsed.get('complete_candidate') is True:
                key=(model,seed,candidate)
                if key in candidates:raise ValueError('Duplicate completed candidate snapshot')
                if parsed.get('test_evaluated') is not False:raise ValueError('Candidate used TEST')
                if parsed['contract']['input_csv_sha256']!=csv_sha:raise ValueError('Candidate points to another cohort')
                candidates[key]={'representation':model,'seed':seed,'candidate':candidate,'public_archive_path':public_path,'source_sha256':record['sha256'],'best_model_sha256':parsed['best_model_sha256'],'cursor':parsed['cursor'],'elapsed_seconds':parsed['elapsed_seconds']}
                checkpoint_hashes[parsed['best_model_path']]=parsed['best_model_sha256']
            if name=='selection.json' and isinstance(parsed,dict):
                key=(model,seed)
                if key in selections:raise ValueError('Duplicate selection snapshot')
                if parsed.get('test_used_for_selection') is not False:raise ValueError('TEST selection')
                winner=min(parsed['candidates'],key=lambda x:x['mae'])['candidate']
                if winner!=parsed['selected_candidate']:raise ValueError('Wrong VAL-only selected candidate')
                selections[key]={'representation':model,'seed':seed,'selected_candidate':winner,'public_archive_path':public_path,'source_sha256':record['sha256']}
            if name=='epochs.jsonl':
                key=(model,seed,candidate)
                if key in histories:raise ValueError('Duplicate epoch history')
                history=[json.loads(line) for line in data.decode('utf-8-sig').splitlines() if line.strip()]
                if not history:raise ValueError('Empty actual completed-candidate epoch history')
                histories[key]={'representation':model,'seed':seed,'candidate':candidate,'epochs':len(history),'public_archive_path':public_path,'source_sha256':record['sha256']}
    expected={(model,seed) for model in MODELS for seed in range(10)}
    if phase=='complete':
        if {(x['representation'],x['seed']) for x in predictions}!=expected or len(predictions)!=30:raise ValueError('Missing/extra exact30 selected prediction slots')
        if set(selections)!=expected:raise ValueError('Missing/extra exact30 VAL selection records')
    elif predictions or selections:
        raise ValueError('Training-only component cannot contain selected TEST results or selection records')
    expected_candidates={unit+(candidate,) for unit in expected for candidate in (0,1)}
    if set(candidates)!=expected_candidates or set(histories)!=expected_candidates:raise ValueError('Missing/extra exact60 candidate results or epoch histories')
    for key in expected_candidates:
        candidates[key]['epoch_history']=histories[key]
    output.mkdir(parents=True)
    archive_files[scope+'-fullfine/ALL-60-CANDIDATES.json']=(json.dumps([candidates[key] for key in sorted(candidates)],indent=2)+'\n').encode()
    archive_files[scope+'-fullfine/SELECTED-30-PREDICTION-INDEX.json']=(json.dumps({'schema':'public-selected-prediction-index.v1','entries':sorted(predictions,key=lambda x:(x['representation'],x['seed']))},indent=2)+'\n').encode()
    write_json(output/'SOURCE-TO-PUBLIC-MAPPING.json',{'schema':'public-log-byte-mapping.v1','entries':mapping})
    write_json(output/'EXCLUDED-INPUT-INDEX.json',{'entries':exclusions})
    write_json(output/'ALL-60-CANDIDATES.json',{'entries':[candidates[key] for key in sorted(candidates)]})
    write_json(output/'SELECTED-30-PREDICTION-INDEX.json',{'entries':sorted(predictions,key=lambda x:(x['representation'],x['seed']))})
    write_json(output/'CHECKPOINT-PRODUCER-SHA-INDEX.json',{'fresh_binary_rehash':False,'models_loaded':0,'entries':[{'source_ref':sanitize_text(key)[0],'source_sha256':value,'evidence':'original result.json production SHA binding'} for key,value in sorted(checkpoint_hashes.items())]})
    archive=deterministic_archive(archive_files,output/(scope+'-fullfine-'+('training-only' if phase=='training_only' else 'all-candidates')+'-logs-and-predictions.tar.gz'))
    receipt={'schema':'public-fullfine-history-component.v1','status':'component_prepared_not_published','scope':scope,'phase':phase,'cohort_csv_sha256':csv_sha,'source_mirror_maps':source_maps,'source_files_rechecked':len(mapping)+len(exclusions),'public_files':len(mapping),'explicit_input_exclusions':len(exclusions),'file_types':dict(file_types),'redaction_counts':dict(redactions),'completed_candidate_slots':len(candidates),'actual_epoch_histories':len(histories),'epoch_records':sum(x['epochs'] for x in histories.values()),'selected_prediction_slots':len(predictions),'selected_test_prediction_rows':len(predictions)*expected_sizes['test'],'checkpoint_producer_hashes':len(checkpoint_hashes),'failure_status_artifacts_preserved':failure_artifacts,'all_prediction_csv_bytes_preserved':True,'archive':archive,'new_fits':0,'new_predictions':0,'models_loaded':0,'final_packet_ready':False}
    write_json(output/'COMPONENT-RECEIPT.actual.json',receipt)
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--map',action='append',type=Path,required=True);parser.add_argument('--cohort',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--scope',choices=('control','expanded'),required=True)
    parser.add_argument('--phase',choices=('complete','training_only'),default='complete')
    args=parser.parse_args();print(json.dumps(prepare(args.map,args.cohort,args.output,args.scope,args.phase),indent=2))


if __name__=='__main__':main()
