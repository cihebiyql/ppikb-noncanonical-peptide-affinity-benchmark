"""Generic fixed-representation preflight; resource admission remains the GPU router's job."""
import argparse
import hashlib
import json
from pathlib import Path

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--contract',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    c=json.loads(args.contract.read_text());errors=[];checks=[]
    required={'schema':'frozen-esm2.sequence-representation.contract.v1',
        'model_name':'esm2_t6_8M_UR50D','representation_layer':6,'embedding_dim':320,
        'precision':'float32','batch_size':1,'max_residues_compute_budget':2048,
        'api_hard_maximum_claimed':False,'eval':True,'requires_grad':False,
        'fitting_count':0,'truncation':False,'chemical_identity_encoded':False,
        'legacy_do_not_execute_wrapper_used':False,'independent_new_benign_benchmark':True}
    for key,value in required.items():
        if c.get(key)!=value:errors.append({'field':key,'expected':value,'actual':c.get(key)})
    hashes={x['path']:x['sha256'] for x in c.get('input_hashes',[])}
    for path,expected in hashes.items():
        try:actual=sha(path)
        except OSError as exc:actual=None;errors.append({'path':path,'error':str(exc)})
        checks.append({'path':path,'actual_sha256':actual,'expected_sha256':expected})
        if actual!=expected:errors.append({'path':path,'problem':'hash_mismatch'})
    for field in ['entrypoint','sequence_manifest','model_path','regression_path','user_authorization_path']:
        if c.get(field) not in hashes:errors.append({'field':field,'problem':'not_bound_to_input_hash'})
    if hashes.get(c['model_path'])!=c['model_sha256']:errors.append({'field':'model_sha256','problem':'identity_mismatch'})
    try:
        auth=json.loads(Path(c['user_authorization_path']).read_text())
        if auth.get('authority')!='direct_user_message' or auth.get('campaign_total_wall_clock_cap_cancelled') is not True:
            errors.append({'field':'user_authorization_path','problem':'explicit_campaign_authorization_missing'})
        if hashes[c['user_authorization_path']]!=c['user_authorization_sha256']:errors.append({'field':'user_authorization_sha256','problem':'mismatch'})
        sequences=[json.loads(line) for line in Path(c['sequence_manifest']).read_text().splitlines()]
        if len(sequences)!=c['sequence_count']:errors.append({'field':'sequence_count','problem':'mismatch'})
        for row in sequences:
            seq=row['sequence']
            if not seq or set(seq)-set('ACDEFGHIKLMNPQRSTVWY') or len(seq)>2048 or hashlib.sha256(seq.encode()).hexdigest()!=row['sequence_id']:
                errors.append({'sequence_id':row.get('sequence_id'),'problem':'raw_sequence_gate'})
    except (OSError,ValueError,KeyError) as exc:errors.append({'problem':'input_parse','error':str(exc)})
    budget=c.get('resource_request',{})
    expected_gpu_count=0 if c.get('device')=='cpu' else 1
    for field,value in {'gpu_count':expected_gpu_count,'cpu_threads':2,'single_owned_process_group':True}.items():
        if budget.get(field)!=value:errors.append({'resource_field':field,'problem':'budget_mismatch'})
    if expected_gpu_count==0 and budget.get('max_gpu_allocated_bytes')!=0:
        errors.append({'resource_field':'max_gpu_allocated_bytes','problem':'CPU_route_requires_zero_GPU_budget'})
    for field in ['max_rss_bytes','canary_timeout_seconds','formal_timeout_seconds']+(['max_gpu_allocated_bytes'] if expected_gpu_count else []):
        if not isinstance(budget.get(field),int) or budget[field]<=0:errors.append({'resource_field':field,'problem':'missing_positive_limit'})
    report={'schema':'frozen-esm2.generic-contract-validation.v1','valid':not errors,
        'valid_for_execution_contract_only':not errors,'resource_admission_still_required':True,
        'paper_identity_required':False,'full_paper_claim':False,'errors':errors,'files_checked':checks,
        'contract_sha256':sha(args.contract),'validator_sha256':sha(__file__)}
    args.output.write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='files_checked'}));return 0 if not errors else 2
if __name__=='__main__':raise SystemExit(main())
