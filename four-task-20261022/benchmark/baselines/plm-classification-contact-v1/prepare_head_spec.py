"""Freeze actual feature/input/code hashes immediately before the first binary head fit."""
import datetime as dt
import hashlib
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
PYTHON='/data/qlyu/projects/peptide-binding-benchmark-20261020/common-prior-methods-20261021/swing/.venv/bin/python'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
    binding=HERE/'feature-cache-binding.json';b=json.loads(binding.read_text())
    assert b['mean_count']==25912 and b['residue_sequence_count']==46 and b['contact_proof_rows']==8625
    manifest=HERE/'inputs/remote-manifest.json';views=json.loads(manifest.read_text())['views']
    files=[HERE/n for n in ['run_heads.py','plm_binary_features.py','supervise_heads.py','smoke_heads.py',
        'verify_heads.py','summarize_binary_results.py','run_head_campaign.py']]
    files += [binding,manifest,ROOT/b['mean_relative_path'],HERE/'inputs/contact-sequence-index-proof.json',
        ROOT/'baselines/plm-simple-v1/user-authorization.copy.json']
    files += [Path(view['path']) for view in views]
    files += [ROOT/item['relative_path'] for item in b['residue_sources'].values()]
    checks=[{'path':str(path),'sha256':sha(path)} for path in files]
    spec={'schema':'frozen-esm2.classification-contact.head-resource-contract.v1','created_at':dt.datetime.now(dt.timezone.utc).isoformat(),
        'output':str(ROOT/'runs/plm-classification-contact-v1/heads'),'cwd':str(HERE),
        'cpu_affinity':[25,26],'reserved_sibling_cores':[57,58],'cpu_threads':2,'max_rss_bytes':3*1024**3,
        'queue_timeout_seconds':1200,'timeout_seconds':7200,'nice':19,'gpu':False,'new_dependencies':False,
        'input_hashes':checks,'command':[PYTHON,'-B',str(HERE/'run_head_campaign.py')],
        'selected_runs_expected':100,'candidate_fits_expected':200,'training_seeds':list(range(10)),
        'validation_selection':'AUPRC; threshold from frozen validation MCC grid0.1..0.9 only',
        'separate_head_per_task':True,'normalization_or_truncation':False,'labels_or_geometry_as_features':False,
        'cache_binding_sha256':sha(binding),'user_authorization_sha256':sha(ROOT/'baselines/plm-simple-v1/user-authorization.copy.json'),
        'coordination':'DTA lease25/26+sibling57/58; fresh threeframe gate repeated at head admission; nice19',
        'no_new_paper_full_reproduction':True}
    target=HERE/'head-execution-contract.json';assert not target.exists();target.write_text(json.dumps(spec,indent=2),encoding='utf-8')
    print(json.dumps({'spec':str(target),'sha256':sha(target)}))
if __name__=='__main__':main()
