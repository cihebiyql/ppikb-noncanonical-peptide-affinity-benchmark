"""Freeze a separately bounded CPU fallback phase after metadata and canary gates."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
PYTHON='/data/qlyu/anaconda3/envs/cuda12.1/bin/python'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['canary','formal'],required=True);args=parser.parse_args()
    contract=HERE/'extraction-contract.cpu-revision3.json';c=json.loads(contract.read_text())
    validation=HERE/'generic-contract-validation.cpu-revision3.json';v=json.loads(validation.read_text())
    assert v['valid'] and v['contract_sha256']==sha(contract) and c['device']=='cpu'
    checks=c['input_hashes']+[{'path':str(f),'sha256':sha(f)} for f in [contract,validation,HERE/'supervise_heads.py']]
    if args.phase=='formal':
        canary=Path(c['output_canary'])/'receipt.json';e=json.loads(canary.read_text())
        actual_max=max(json.loads(line)['length'] for line in Path(c['sequence_manifest']).read_text().splitlines())
        assert e['status']=='succeeded' and e['canary'] and e['max_residues']==actual_max
        assert actual_max<=c['max_residues_compute_budget']
        assert e['contract_sha256']==sha(contract) and e['no_truncation'] and e['device']=='cpu'
        token_checks=json.loads((Path(c['output_canary'])/'token-checks.json').read_text())
        assert all(r['tokens']==r['residues']+2 for r in token_checks)
        checks.append({'path':str(canary),'sha256':sha(canary)})
    command=[PYTHON,'-B',str(HERE/'extract_embeddings.py'),'--contract',str(contract)]
    if args.phase=='canary':command+=['--canary']
    out=ROOT/'runs/plm-simple-v1'/f'extraction-cpu-v3-{args.phase}-supervision'
    spec={'schema':'frozen-esm2.cpu-extraction-owned-run.v1','phase':args.phase,
        'created_at':dt.datetime.now(dt.timezone.utc).isoformat(),'command':command,
        'output':str(out),'cwd':str(HERE),'cpu_affinity':[30,31],'cpu_threads':2,
        'max_rss_bytes':3*1024**3,'timeout_seconds':180 if args.phase=='canary' else 5400,
        'input_hashes':checks,'gpu':False,'user_authorization_sha256':c['user_authorization_sha256'],
        'total_campaign_cap_cancelled':True,'whole_owned_group_bounded':True,
        'no_shared_environment_change':True,'new_dependencies':False}
    target=HERE/f'cpu-extraction-spec-{args.phase}.json';assert not target.exists()
    target.write_text(json.dumps(spec,indent=2),encoding='utf-8')
    print(json.dumps({'phase':args.phase,'spec':str(target),'sha256':sha(target)}))
if __name__=='__main__':main()
