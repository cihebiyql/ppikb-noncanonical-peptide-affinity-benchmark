"""Freeze head-run resources only after the immutable feature extraction succeeded."""
import datetime as dt
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
PYTHON='/data/qlyu/projects/peptide-binding-benchmark-20261020/common-prior-methods-20261021/swing/.venv/bin/python'

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    manifest=HERE/'inputs/remote-manifest.json'
    views=json.loads(manifest.read_text())['views']
    binding_path=HERE/'feature-cache-binding.json';binding=json.loads(binding_path.read_text())
    cache=HERE/binding['directory']/'embeddings.npz';receipt=HERE/binding['directory']/'receipt.json'
    evidence=json.loads(receipt.read_text())
    assert evidence['status']=='succeeded' and not evidence['canary'] and evidence['sequence_count']==5159
    assert sha(cache)==evidence['embedding_sha256']
    canary=json.loads((ROOT/'runs/plm-simple-v1/feature-canary-cpu-v3/receipt.json').read_text())
    actual_max=max(json.loads(line)['length'] for line in (HERE/'inputs/unique-sequences.jsonl').read_text().splitlines())
    assert canary['status']=='succeeded' and canary['max_residues']==actual_max and canary['no_truncation']
    files=[HERE/n for n in ['run_heads.py','plm_features.py','supervise_heads.py','smoke_heads.py',
        'verify_results.py','summarize_strata.py','user-authorization.copy.json','cpu-runtime-lock.json']]
    files += [manifest,cache,receipt,binding_path]+[Path(view['path']) for view in views]
    out=ROOT/'runs/plm-simple-v1/heads'
    spec={'schema':'frozen-esm2.cpu-head-owned-run.v1','created_at':dt.datetime.now(dt.timezone.utc).isoformat(),
        'output':str(out),'cwd':str(HERE),'cpu_affinity':[30,31],'cpu_threads':2,
        'max_rss_bytes':3*1024**3,'timeout_seconds':5500,'gpu':False,'new_dependencies':False,
        'input_hashes':[{'path':str(f),'sha256':sha(f)} for f in files],
        'command':[PYTHON,'-B',str(HERE/'run_head_campaign.py')],
        'selected_runs_expected':150,'candidate_fits_expected':300,
        'runtime_canary_expected':30,'validation_only_selection':True,'test_split_fixed_for_all_seeds':True,
        'no_model_pretraining_or_finetuning':True,'chemical_identity_encoded':False,
        'user_authorization_sha256':sha(HERE/'user-authorization.copy.json'),
        'total_campaign_cap_cancelled':True,'resource_coordination':'dta_build released30/31 and reserves siblings62/63; no interaction slots used',
        'memory_budget_basis':'Existing same-family Morgan150runs peak0.65GiB at2081/4139D; this640/960D route capped3GiB to share grammar-cache allowance.',
        'host_admission':{'min_idle_percent':40,'min_available_memory_bytes':36*1024**3,
                          'max_uid_rss_with_job_bytes':80*1024**3,'during_job_min_available_memory_bytes':24*1024**3}}
    spec['input_hashes'].append({'path':str(HERE/'run_head_campaign.py'),'sha256':sha(HERE/'run_head_campaign.py')})
    path=HERE/'head-run-spec.json';assert not path.exists();path.write_text(json.dumps(spec,indent=2),encoding='utf-8')
    print(json.dumps({'path':str(path),'sha256':sha(path),'cache_sha256':sha(cache)}))

if __name__=='__main__':main()
