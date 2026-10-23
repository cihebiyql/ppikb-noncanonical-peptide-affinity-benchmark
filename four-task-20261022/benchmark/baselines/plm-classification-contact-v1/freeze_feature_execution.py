"""Freeze model/data/code/auth hashes and the newly coordinated CPU-only finite shard queue."""
import datetime as dt
import hashlib
import json
import tarfile
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OLD=ROOT/'baselines/plm-simple-v1'
REMOTE='/data/qlyu/projects/peptide-four-task-benchmark-20261022'
PYTHON='/data/qlyu/anaconda3/envs/cuda12.1/bin/python'
SUPERVISOR_PYTHON='/data/qlyu/projects/peptide-binding-benchmark-20261020/common-prior-methods-20261021/swing/.venv/bin/python'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def remote(path):return REMOTE+'/'+Path(path).relative_to(ROOT).as_posix()
def write(path,obj):Path(path).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')

def main():
    coverage=json.loads((HERE/'coverage-manifest.json').read_text(encoding='utf-8'))
    manifest={**coverage,'views':[]}
    for original in coverage['views']:
        view=dict(original);view['original_local_path']=view['path'];view['path']=remote(view['path']);manifest['views'].append(view)
    write(HERE/'inputs/remote-manifest.json',manifest)
    required=[HERE/'extract_chunk.py',HERE/'inputs/missing-representations.jsonl',
        OLD/'model-assets/esm2_t6_8M_UR50D.pt',OLD/'model-assets/esm2_t6_8M_UR50D-contact-regression.pt',OLD/'user-authorization.copy.json']
    hashes=[{'path':remote(path),'sha256':sha(path)} for path in required]
    old_canary=json.loads((ROOT/'runs/plm-simple-v1/feature-canary-cpu-v3/receipt.json').read_text())
    hashes += [{'path':path,'sha256':digest} for path,digest in old_canary['esm_source_hashes'].items()]
    contract={'schema':'frozen-esm2.classification-contact.feature-contract.v1','created_at':dt.datetime.now(dt.timezone.utc).isoformat(),
        'model_name':'esm2_t6_8M_UR50D','model_path':remote(OLD/'model-assets/esm2_t6_8M_UR50D.pt'),
        'regression_path':remote(OLD/'model-assets/esm2_t6_8M_UR50D-contact-regression.pt'),
        'model_sha256':sha(OLD/'model-assets/esm2_t6_8M_UR50D.pt'),'sequence_manifest':remote(HERE/'inputs/missing-representations.jsonl'),
        'sequence_count':coverage['missing_representation_forward_jobs'],'chunk_size':512,'representation_layer':6,
        'device':'cpu','math_threads':2,'dtype':'float32','eval':True,'requires_grad':False,'inference_mode':True,
        'max_residues_compute_budget':2048,'model_API_hard_limit_claimed':False,'normalization':False,'truncation':False,
        'pooling':'mean actual residues excludingBOS/EOS/pad','contact_residue_index':'cache[original_index1-1] from layer6[1:L+1]',
        'output_root':REMOTE+'/runs/plm-classification-contact-v1','input_hashes':hashes,
        'old_mean_cache_sha256':coverage['old_cache_sha256'],'old_mean_reused_unique':coverage['reused_mean_unique'],
        'requested_missing_means':coverage['missing_mean_unique'],'requested_missing_residue_sequences':coverage['required_residue_unique'],
        'label_or_coordinate_files_in_model_inputs':False,'new_dependencies':False,
        'user_authorization_sha256':sha(OLD/'user-authorization.copy.json'),'generic_baseline_not_paper_reproduction':True}
    contract_path=HERE/'feature-contract.json';assert not contract_path.exists();write(contract_path,contract)
    plan={'schema':'frozen-esm2.classification-contact.resource-plan.v1','prepared_at':dt.datetime.now(dt.timezone.utc).isoformat(),
        'feature_contract':remote(contract_path),'feature_contract_sha256':sha(contract_path),
        'feature_python':PYTHON,'supervisor_python':SUPERVISOR_PYTHON,'extractor':remote(HERE/'extract_chunk.py'),
        'supervisor':remote(HERE/'supervise_features.py'),'cwd':remote(HERE),'output_root':contract['output_root'],
        'cpu_affinity':[25,26],'reserved_siblings':[57,58],'nice':19,'rss_limit_bytes':3*1024**3,
        'queue_timeout_seconds':1200,'canary_timeout_seconds':180,'chunk_timeout_seconds':1800,'controller_timeout_seconds':21600,
        'gpu_used':False,'no_preemption':True,'shared_environment_modified':False,
        'coordination_reference':'methods/dta/additional-CPU-slot-20261023T050621Z.json; fresh three-frame gate repeats per actual scientific job',
        'input_hashes':hashes+[{'path':remote(path),'sha256':sha(path)} for path in [contract_path,HERE/'supervise_features.py',HERE/'run_feature_queue.py']]}
    write(HERE/'resource-plan.json',plan)
    files=[path for path in HERE.rglob('*') if path.is_file() and 'preparation-history' not in path.parts
           and '__pycache__' not in path.parts and path.name not in {'deployment-payload.tar.gz','deployment-receipt.json'}]
    archive=HERE/'deployment-payload.tar.gz'
    with tarfile.open(archive,'w:gz') as tar:
        for path in files:tar.add(path,arcname=path.relative_to(ROOT).as_posix())
    receipt={'payload_sha256':sha(archive),'payload_bytes':archive.stat().st_size,'files':len(files),
        'feature_contract_sha256':sha(contract_path),'resource_plan_sha256':sha(HERE/'resource-plan.json'),
        'source_views_unchanged':True,'old_cache_unchanged':True,'model_weights_reused_without_download':True}
    write(HERE/'deployment-receipt.json',receipt);print(json.dumps(receipt))
if __name__=='__main__':main()
