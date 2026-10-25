"""Assemble only a fully audited expanded230 packet, without publishing it.

An explicit SHA-pinned intake is required. This refuses incomplete actual30 and
keeps release assets separate from the exact Git whitelist. No models run here.
"""
import argparse
import json
import os
from pathlib import Path

from public_artifacts import safe_relative,sha
from replay_public_predictions import readbytes

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SLUG='four-task-20261022/chemical-benchmarks-complete-v11'
REPO='cihebiyql/ppikb-noncanonical-peptide-affinity-benchmark'
TAG='chemical-benchmarks-v11-20261025'
HELPERS=('public_artifacts.py','collect_artifacts.py','restore_project_tree.py','restore_scientific_inputs.py','scientific_path_bridge.py','check_reference_input_guards.py','fetch_locked_inputs.py','evaluate_saved_predictions.py','replay_public_predictions.py','normalize_owner_mirrors.py','prepare_mirrored_history.py','test_public_artifacts.py','test_recovery.py','test_scientific_restore.py','test_official_fetch_plan.py','test_history_replay.py','build_final_packet.py','test_final_packet.py')


def project_ref(path):
    raw=os.path.abspath(path)
    if raw.startswith('\\\\?\\'):raw=raw[4:]
    return 'record-ref:project/'+Path(raw).relative_to(ROOT).as_posix()


def read_bound(entry):
    relative=entry['project_relative_path'];safe_relative(relative)
    data=readbytes(ROOT/relative)
    if sha(data)!=entry['sha256']:raise ValueError('Final accepted source changed: '+relative)
    return data


def build(intake,output):
    intake_raw=Path(intake).read_bytes();spec=json.loads(intake_raw)
    if spec.get('schema')!='public-v11.final-accepted-inputs.v1':raise ValueError('Wrong final intake')
    comparison=json.loads(read_bound(spec['comparison']))
    raw30=json.loads(read_bound(spec['raw30_audit']))
    if comparison.get('status')!='passed' or comparison.get('model_seed_units')!=230 or comparison.get('fullfine30_models_fresh_raw_audited')!=30 or comparison.get('groups')!=155:raise ValueError('Final expanded230 actual comparison not accepted')
    if raw30.get('status')!='passed' or raw30.get('raw_selected_models_recomputed')!=30 or raw30.get('test_n')!=685 or raw30.get('validation_n')!=570:raise ValueError('Actual complete30 raw audit required')
    if comparison.get('csv_sha256')!='c3d8f4e42600f0c762bb9d2d24595a32c8f13de7a1f5018d59047d241dd8525a':raise ValueError('Wrong expanded cohort')
    fullfine=HERE/spec['fullfine_component'];receipt=json.loads((fullfine/'COMPONENT-RECEIPT.actual.json').read_text())
    if receipt.get('phase')!='complete' or receipt.get('completed_candidate_slots')!=60 or receipt.get('selected_prediction_slots')!=30 or receipt.get('selected_test_prediction_rows')!=20550:raise ValueError('Complete60/30 public history component required')
    output=Path(output)
    if output.exists():raise FileExistsError(output)
    absolute=os.path.abspath(output)
    if os.name=='nt' and not absolute.startswith('\\\\?\\'):output=Path('\\\\?\\'+absolute)
    files={};source_map=[];assets=[]
    def add(source,destination):
        safe_relative(destination)
        if destination in files:raise ValueError('Duplicate public destination: '+destination)
        data=readbytes(source);files[destination]=data
        try:ref=project_ref(source)
        except ValueError:raise ValueError('Public source outside approved project')
        source_map.append({'source_ref':ref,'source_sha256':sha(data),'public_path':destination,'public_sha256':sha(data),'bytes':len(data),'transform':'original prepared public bytes; source→public transformations are recorded inside the associated component'})
    def tree(source,dest):
        source=Path(source)
        absolute=os.path.abspath(source)
        if os.name=='nt' and not absolute.startswith('\\\\?\\'):source=Path('\\\\?\\'+absolute)
        if source.is_symlink():raise ValueError('Component symlink rejected')
        for path in sorted(source.rglob('*')):
            if path.is_symlink():raise ValueError('Component symlink rejected')
            if not path.is_file():continue
            relative=path.relative_to(source).as_posix()
            if path.suffix=='.gz':
                raw=readbytes(path);assets.append({'name':path.name,'source_component':source.name,'sha256':sha(raw),'bytes':len(raw),'download_url':'https://github.com/'+REPO+'/releases/download/'+TAG+'/'+path.name,'local_source_ref':project_ref(path)})
            else:add(path,SLUG+'/'+dest+'/'+relative)
    for component,dest in [
      ('data-component-v1','data'),('code-component-v2-original-scientific','source/execution'),
      (spec['verification_component'],'source/evaluation'),('evidence-component-v1','evidence/accepted-control-and-heads'),
      (spec['final_evidence_component'],'evidence/expanded-final'),
      ('head-component-v1','logs/expanded-heads'),('control-head-component-v1','logs/control-heads'),
      ('control-fullfine-component-v3','logs/control-fullfine'),(spec['fullfine_component'],'logs/expanded-fullfine'),
      ('expanded-resource-history-component-v1','logs/expanded-resource-history'),
      ('selected-first-IO-history-component-v1','logs/selected-first-IO-history'),
    ]:tree(HERE/component,dest)
    runtime=HERE/'collection/scientific-runtime-inputs-original-v2.tar.gz';data=readbytes(runtime)
    assets.append({'name':runtime.name,'source_component':'original-scientific-runtime-inputs','sha256':sha(data),'bytes':len(data),'download_url':'https://github.com/'+REPO+'/releases/download/'+TAG+'/'+runtime.name,'local_source_ref':'record-ref:project/'+runtime.relative_to(ROOT).as_posix()})
    if len({a['name'] for a in assets})!=len(assets):raise ValueError('Duplicate release asset filenames')
    for name in HELPERS:add(HERE/name,SLUG+'/helpers/'+name)
    add(HERE/'UPSTREAM-INPUTS-LOCK.json',SLUG+'/UPSTREAM-INPUTS-LOCK.json')
    for entry in spec['additional_public_files']:
        data=read_bound(entry);destination=SLUG+'/'+entry['public_path'];safe_relative(destination)
        if destination in files:raise ValueError('Duplicate additional public file')
        files[destination]=data
        source_map.append({'source_ref':'record-ref:project/'+entry['project_relative_path'],'source_sha256':sha(data),'public_path':destination,'public_sha256':sha(data),'bytes':len(data),'transform':'original bytes of explicitly approved additional public metadata or self-authored descriptor script'})
    readme=readbytes(HERE/spec['README_draft']);files[SLUG+'/README.zh-CN.md']=readme
    files['AGENTS.md']=readbytes(HERE/spec['AGENTS_draft'])
    checkout=ROOT/'publication/github-checkout';old=readbytes(checkout/'README.md');title,sep,body=old.partition(b'\n')
    if not sep:raise ValueError('Existing public README title required')
    prefix=readbytes(HERE/'drafts/README-PREFIX.zh-CN.md')
    files['README.md']=title+sep+b'\n'+prefix+b'\n'+body
    old_latest=readbytes(checkout/'four-task-20261022/LATEST.md')
    entry='|[非标准肽化学基准完整结果 v11](chemical-benchmarks-complete-v11/README.zh-CN.md)|两个冻结cohort分别230模型、全部0–9种子；扩展531/570/685与对照497/495/656分开；全部400头候选＋60全微调候选/每cohort及逐样本预测、日志、原字节数据与评价代码；同一数据并集1786，非3434独立测量。独立gold外测0。|\n'
    files['four-task-20261022/LATEST.md']=old_latest+(b'' if old_latest.endswith(b'\n') else b'\n')+entry.encode()
    assets_public=[{k:v for k,v in a.items() if k!='local_source_ref'} for a in assets]
    files[SLUG+'/RELEASE-ASSETS.json']=(json.dumps({'schema':'public-v11.release-assets.v1','tag':TAG,'assets':assets_public,'all_assets_required_for_complete_logs_and_runtime_inputs':True},indent=2)+'\n').encode()
    files[SLUG+'/SOURCE-TO-PACKET-MAPPING.json']=(json.dumps({'entries':source_map},indent=2)+'\n').encode()
    manifest={'schema':'public-v11.git-file-manifest.v1','files':[{'path':name,'sha256':sha(data),'bytes':len(data)} for name,data in sorted(files.items())],'manifest_self_excluded':True,'release_assets':assets_public,'actual_selected_models_control':230,'actual_selected_models_expanded':230,'expanded_selected_TEST_rows':157550,'control_selected_TEST_rows':150880,'dataset_unique_union':1786,'new_fits_or_predictions_during_packaging':0}
    files[SLUG+'/FILE-MANIFEST.json']=(json.dumps(manifest,indent=2)+'\n').encode()
    output.mkdir(parents=True)
    for relative,data in sorted(files.items()):
        target=output/'payload'/relative;target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('xb') as stream:stream.write(data)
    metadata={'schema':'public-v11.concrete-prepared-whitelist.v1','status':'PREPARED_WAIT_ROOT_FINAL_REVIEW_NOT_PUSHED','intake_sha256':sha(intake_raw),'comparison_source_sha256':spec['comparison']['sha256'],'raw30_source_sha256':spec['raw30_audit']['sha256'],'whitelist':[{'path':name,'sha256':sha(data),'bytes':len(data)} for name,data in sorted(files.items())],'release_assets':assets,'root_readme_before_sha256':sha(old),'root_latest_before_sha256':sha(old_latest),'root_AGENTS_before_sha256':sha(readbytes(checkout/'AGENTS.md')) if (checkout/'AGENTS.md').exists() else None,'old_published_snapshots_untouched':True,'new_fits':0,'new_predictions':0,'weights_loaded':0}
    with (output/'CONCRETE-WHITELIST.actual.json').open('x',encoding='utf-8',newline='\n') as stream:json.dump(metadata,stream,indent=2);stream.write('\n')
    return {'files':len(files),'release_assets':len(assets),'whitelist_sha256':sha((output/'CONCRETE-WHITELIST.actual.json').read_bytes()),'pushed':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--intake',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(build(args.intake,args.output),indent=2))
