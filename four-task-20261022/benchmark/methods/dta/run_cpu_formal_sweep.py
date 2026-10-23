"""Execute remaining preregistered seeds, preserving completed or failed runs."""
import json
from pathlib import Path
from cpu_fallback import ROOT, load, sha, write, execute
from cpu_formal_synthetic import FORMAL

results = []
for job in load(FORMAL/'jobs.json')['jobs']:
    folder = Path(job['log_dir'])
    receipt_path = folder/'execution-receipt.json'
    if receipt_path.exists():
        receipt = load(receipt_path)
        complete_path = ROOT/job['run_root']/'complete.json'
        if receipt['status'] == 'succeeded' and receipt['contract_sha256'] == job['contract_sha256'] and complete_path.exists():
            complete = load(complete_path)
            prediction = complete_path.parent/'test-predictions.jsonl'
            if complete['prediction_sha256'] != sha(prediction):
                raise ValueError('Existing own completed run prediction changed')
            result = {'job_id':job['job_id'],'status':'verified_current_batch_complete_skipped','seed':job['seed']}
        else:
            result = {'job_id':job['job_id'],'status':'preserved_failed_or_incomplete_no_retry','seed':job['seed']}
    else:
        result = execute(job)
    results.append(result)
    print(json.dumps(result,ensure_ascii=False),flush=True)
    write(FORMAL/'sweep-progress.json',{'results':results,'no_old_results_imported':True})
write(FORMAL/'sweep-result.json',{'results':results,'no_old_results_imported':True})
