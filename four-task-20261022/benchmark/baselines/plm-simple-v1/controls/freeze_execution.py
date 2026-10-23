"""Create one bounded non-GPU resource spec and its explicit frozen deployment payload."""
import datetime as dt
import hashlib
import json
import tarfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
REMOTE='/data/qlyu/projects/peptide-four-task-benchmark-20261022'
PYTHON='/data/qlyu/projects/peptide-binding-benchmark-20261020/common-prior-methods-20261021/swing/.venv/bin/python'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def remote(path):return REMOTE+'/'+Path(path).relative_to(ROOT).as_posix()

def main():
    original=ROOT/'baselines/frozen-code/cpu-baselines-v2.py'
    copy=HERE/'source-manual-v2.py';assert not copy.exists();copy.write_bytes(original.read_bytes())
    manifest=HERE/'remote-manifest.json';views=json.loads(manifest.read_text(encoding='utf-8'))['views']
    files=[HERE/name for name in ['run_manual_controls.py','supervise_controls.py','run_controls_campaign.py',
        'smoke_controls.py','verify_manual_controls.py','comparison-protocol.json','coverage-manifest.json','remote-manifest.json','source-manual-v2.py']]
    inputs=[{'path':remote(path),'sha256':sha(path)} for path in files]
    inputs += [{'path':v['path'],'sha256':v['sha256']} for v in views]
    auth=HERE.parent/'user-authorization.copy.json'
    inputs.append({'path':remote(auth),'sha256':sha(auth)})
    spec={'schema':'plm.matched-manual-controls.resource-contract.v1','created_at':dt.datetime.now(dt.timezone.utc).isoformat(),
        'output':REMOTE+'/runs/plm-cohort-manual-controls-v1','cwd':remote(HERE),
        'cpu_affinity':[25,30],'reserved_sibling_cores':[57,62],'cpu_threads':2,
        'max_rss_bytes':3*1024**3,'queue_timeout_seconds':1800,'timeout_seconds':3600,
        'command':[PYTHON,'-B',remote(HERE/'run_controls_campaign.py')],
        'input_hashes':inputs,'user_authorization_sha256':sha(auth),'gpu':False,'nice':15,
        'new_dependencies':False,'shared_environment_modified':False,
        'seeds':list(range(10)),'selected_runs_expected':150,'candidate_fits_expected':300,
        'runtime_canary_fits_separate':30,'selection':'validation MAE only','original_data_or_prior_results_changed':False,
        'coordination':'DTA owner assigned25+30, protected57+62; avoid DTA8-23, SWING0-7, classification24, and busy31/63',
        'admission':{'fresh_frames':3,'reserved_core_and_sibling_min_idle_percent':60,
                     'global_min_idle_percent':40,'min_available_memory_bytes':36*1024**3,'max_uid_rss_with_job_bytes':80*1024**3}}
    path=HERE/'execution-contract.json';assert not path.exists();path.write_text(json.dumps(spec,indent=2),encoding='utf-8')
    files.append(path)
    archive=HERE/'deployment-payload.tar.gz'
    with tarfile.open(archive,'w:gz') as tar:
        for path in files:tar.add(path,arcname=path.relative_to(ROOT).as_posix())
    receipt={'payload_sha256':sha(archive),'payload_bytes':archive.stat().st_size,
        'execution_contract_sha256':sha(HERE/'execution-contract.json'),'source_sha256':sha(original),
        'new_dependencies':False,'raw_inputs_reused_without_copy_or_change':True}
    (HERE/'deployment-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt))
if __name__=='__main__':main()
