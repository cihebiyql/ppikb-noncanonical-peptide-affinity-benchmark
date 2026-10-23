"""Stage an isolated payload and explicit POSIX references; never edit frozen source views."""
import hashlib
import json
import shutil
import tarfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
REMOTE='/data/qlyu/projects/peptide-four-task-benchmark-20261022'
PYTHON='/data/qlyu/anaconda3/envs/cuda12.1/bin/python'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def posix(path):
    return REMOTE+'/'+Path(path).relative_to(ROOT).as_posix()

def main():
    auth=ROOT/'protocol/continuation-20261023/user-authorization.json'
    shutil.copyfile(auth,HERE/'user-authorization.copy.json')
    coverage=json.loads((HERE/'coverage-manifest.json').read_text(encoding='utf-8'))
    staged_manifest={**coverage,'views':[]}
    for original in coverage['views']:
        view=dict(original)
        view['original_local_path']=view['path']
        view['path']=posix(view['path'])
        view['coverage_path']=posix(view['coverage_path'])
        staged_manifest['views'].append(view)
    path=HERE/'inputs/remote-manifest.json'
    path.write_text(json.dumps(staged_manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    sequence=HERE/'inputs/unique-sequences.jsonl'
    assets=HERE/'model-assets'
    checked=[HERE/'extract_embeddings.py',sequence,assets/'esm2_t6_8M_UR50D.pt',
             assets/'esm2_t6_8M_UR50D-contact-regression.pt',HERE/'user-authorization.copy.json']
    contract={'schema':'frozen-esm2.sequence-representation.contract.v1','model_name':'esm2_t6_8M_UR50D',
        'model_path':posix(assets/'esm2_t6_8M_UR50D.pt'),'model_source':'https://dl.fbaipublicfiles.com/fair-esm/models/esm2_t6_8M_UR50D.pt',
        'model_sha256':sha(assets/'esm2_t6_8M_UR50D.pt'),'upstream_code_revision':'2b369911bb5b4b0dda914521b9475cad1656b2ac',
        'device':'cuda:0','representation_layer':6,'embedding_dim':320,'precision':'float32',
        'batch_size':1,'max_residues_compute_budget':2048,'api_hard_maximum_claimed':False,
        'pooling':'mean exact residues excluding BOS/EOS/pad','eval':True,'requires_grad':False,
        'fitting_count':0,'normalization':None,'truncation':False,'chemical_identity_encoded':False,
        'sequence_manifest':posix(sequence),'sequence_count':coverage['unique_sequence_count'],
        'output':REMOTE+'/baselines/plm-simple-v1/feature-cache',
        'output_canary':REMOTE+'/runs/plm-simple-v1/feature-canary-v1',
        'entrypoint':posix(HERE/'extract_embeddings.py'),'python':PYTHON,
        'user_authorization_path':posix(HERE/'user-authorization.copy.json'),
        'user_authorization_sha256':sha(auth),'total_campaign_cap_cancelled':True,
        'input_hashes':[{'path':posix(f),'sha256':sha(f)} for f in checked],
        'resource_request':{'gpu_count':1,'max_gpu_allocated_bytes':6*1024**3,'cpu_threads':2,
                            'max_rss_bytes':5*1024**3,'canary_timeout_seconds':180,'formal_timeout_seconds':1800,
                            'single_owned_process_group':True,'route_owner':'gpu_route'},
        'independent_new_benign_benchmark':True,'legacy_do_not_execute_wrapper_used':False,
        'claim_level':'generic frozen representation baseline, not full-paper reproduction'}
    (HERE/'extraction-contract.json').write_text(json.dumps(contract,ensure_ascii=False,indent=2),encoding='utf-8')
    files=[f for f in HERE.rglob('*') if f.is_file() and '__pycache__' not in str(f)
           and f.name not in {'deployment-payload.tar.gz','deployment-receipt.json'}]
    archive=HERE/'deployment-payload.tar.gz'
    with tarfile.open(archive,'w:gz') as stream:
        for f in files:
            stream.add(f,arcname=f.relative_to(ROOT).as_posix())
    (HERE/'deployment-receipt.json').write_text(json.dumps({'archive_sha256':sha(archive),
        'bytes':archive.stat().st_size,'files':len(files),'remote_root':REMOTE,'new_dependencies':False,
        'extraction_contract_sha256':sha(HERE/'extraction-contract.json')},indent=2),encoding='utf-8')
    print(json.dumps({'payload_bytes':archive.stat().st_size,'files':len(files),'contract_sha256':sha(HERE/'extraction-contract.json')}))

if __name__=='__main__':
    main()
