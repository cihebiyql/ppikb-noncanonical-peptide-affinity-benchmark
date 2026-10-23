"""Bind a bounded CPU resource contract after successful heads; acceptance checks only."""
import datetime as dt
import json
from mirror_artifacts import HERE, ROOT, RUN, sha, write

pipeline=json.loads((HERE/'binary-pipeline-receipt.json').read_text())
process=json.loads((RUN/'heads/process-receipt.json').read_text())
assert pipeline['status']=='succeeded'
assert process['exit_code']==0 and process['worker_pid_absent'] and not process['surviving_group_pids']
paths=[HERE/name for name in ['run_readonly_audits.py','verify_cache.py','verify_fitted_metadata.py',
    'mirror_artifacts.py','supervise_heads.py','feature-cache-binding.json','coverage-manifest.json','inputs/remote-manifest.json']]
paths += [RUN/'heads/process-receipt.json',RUN/'heads/independent-recalculation.json',
    ROOT/'baselines/plm-simple-v1/user-authorization.copy.json']
spec={'schema':'frozen-esm2.binary-readonly-audit.resource-contract.v1',
    'created_at':dt.datetime.now(dt.timezone.utc).isoformat(),'output':str(RUN/'read-only-audit-supervision'),
    'cwd':str(HERE),'cpu_affinity':[25,26],'reserved_sibling_cores':[57,58],'cpu_threads':2,
    'max_rss_bytes':3*1024**3,'queue_timeout_seconds':600,'timeout_seconds':900,'nice':19,'gpu':False,
    'new_fit_count':0,'new_forward_count':0,'input_hashes':[{'path':str(p),'sha256':sha(p)} for p in paths],
    'command':['/data/qlyu/projects/peptide-binding-benchmark-20261020/common-prior-methods-20261021/swing/.venv/bin/python',
        '-B',str(HERE/'run_readonly_audits.py')],
    'user_authorization_sha256':sha(ROOT/'baselines/plm-simple-v1/user-authorization.copy.json')}
path=HERE/'read-only-audit-execution-contract.json';assert not path.exists();write(path,spec)
print(json.dumps({'contract':str(path),'sha256':sha(path),'new_fit_count':0,'new_forward_count':0}))
